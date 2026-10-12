"""Carga de refrigeración con modelo dinámico del local (red de nodos).

Planteamiento (el mismo que los métodos de balance térmico de UNE-EN ISO 52016-1
y EnergyPlus, simplificado):

* Cada elemento opaco se discretiza por capas en nodos con capacidad térmica
  (diferencias finitas implícitas). Las ventanas no tienen masa.
* Cara interior de cada elemento:
    - convección con el aire del local, coeficiente h_ci;
    - radiación de onda larga con el resto de superficies a través de un nodo de
      temperatura radiante media (red en estrella), coeficiente h_ri.
* Cara exterior:
    - exteriores: aire exterior (h_ce + h_re), radiación solar absorbida α·I y
      pérdida de onda larga hacia el cielo F_sky·h_re·Δθ_er;
    - hacia espacios no climatizados: aire a la temperatura adyacente (1/Rsi);
    - interiores (masas adiabáticas): flujo nulo.
* Radiación solar transmitida por los huecos: la directa incide sobre el suelo y
  la difusa se reparte por área entre todas las superficies interiores.
* Ganancias internas: parte convectiva directa al aire y parte radiante repartida
  por área entre las superficies interiores.
* El aire se mantiene a la consigna; la carga sensible es el calor que hay que
  extraer del aire en cada instante.

Como el sistema es lineal, la carga total es la suma de las respuestas a cada
excitación por separado; así se obtiene el desglose exacto por componente.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import solar
from .cerramientos import Capa
from .modelo import Cerramiento, MasaInterior, Proyecto
from .psicrometria import (coeficientes_aire, humedad_especifica_desde_bulbo_humedo,
                           humedad_especifica_desde_hr, presion_atmosferica)
from .verano import HoraVerano, ResultadoVerano, fraccion_oscilacion

# Coeficientes superficiales (UNE-EN ISO 6946, anexo C / UNE-EN ISO 52016-1)
H_CI = {"vertical": 2.5, "suelo": 2.5, "techo": 2.5}
H_RI = 5.13          # radiación interior (ε = 0,9)
def h_ce(viento: float) -> float:
    """Convección exterior según UNE-EN ISO 6946, anexo C: h_c = 4 + 4·v [W/(m²·K)]."""
    return 4.0 + 4.0 * viento
H_RE = 4.14          # radiación exterior (ε = 0,9)
DELTA_CIELO = 11.0   # diferencia aire exterior - cielo [K]

PASO_S = 600.0       # paso de cálculo [s]
DIAS = 12            # días de diseño repetidos hasta régimen periódico


@dataclass
class Superficie:
    nombre: str
    area: float
    capas: list[Capa]                 # interior → exterior
    contorno: str                     # exterior | adyacente | adiabatica
    posicion: str                     # vertical | suelo | techo
    elemento: Cerramiento | None = None
    nodos: list[int] = field(default_factory=list)


def _capas_equivalentes(c: Cerramiento, rsi: float, rse: float) -> list[Capa]:
    if c.capas:
        return c.capas
    r = max(1.0 / c.U - rsi - rse, 0.01)
    return [Capa("equivalente", 0.0, 1.0, densidad=0.0, resistencia=r)]


def _discretizar(capas: list[Capa], max_dx: float = 0.02):
    """Devuelve listas (capacidad J/m²K por nodo, conductancia W/m²K entre nodos)."""
    cap, res = [], []
    for c in capas:
        if c.densidad <= 0 or c.espesor <= 0:
            res.append(c.R)
            cap.append(0.0)
            continue
        n = max(2, math.ceil(c.espesor / max_dx))
        dx = c.espesor / n
        for _ in range(n):
            res.append(dx / c.conductividad)
            cap.append(c.densidad * c.calor_especifico * dx)
    return cap, res


# Forjado tipo para la masa interior por defecto (interior → otro lado)
FORJADO_TIPO = [Capa("solado", 0.02, 1.3, 2300, 840), Capa("mortero", 0.04, 1.3, 1900, 1000),
                Capa("forjado", 0.25, 1.65, 2150, 1000)]


def masas_por_defecto(p: Proyecto) -> list[MasaInterior]:
    """Suelo y techo interiores si el local no los tiene como cerramientos ni masas."""
    pos = {c.posicion for c in p.cerramientos if c.tipo != "ventana"}
    pos |= {m.posicion for m in p.masas_interiores}
    extra = []
    if "suelo" not in pos:
        extra.append(MasaInterior("Suelo interior (supuesto)", p.local.superficie, FORJADO_TIPO, "suelo"))
    if "techo" not in pos:
        extra.append(MasaInterior("Techo interior (supuesto)", p.local.superficie,
                                  list(reversed(FORJADO_TIPO)), "techo"))
    return extra


class ModeloLocal:
    def __init__(self, p: Proyecto):
        self.p = p
        lo = p.local
        self.h_ext = h_ce(p.clima.viento_verano) + H_RE
        self.superficies: list[Superficie] = []
        for c in p.cerramientos:
            if c.tipo == "ventana":
                continue
            pos = c.posicion
            contorno = "exterior" if c.exterior else "adyacente"
            rsi = 1 / (H_CI[pos] + H_RI)
            self.superficies.append(Superficie(
                c.nombre, c.area, _capas_equivalentes(c, rsi, 1 / (self.h_ext)),
                contorno, pos, c))
        self.supuestas = masas_por_defecto(p)
        for m in p.masas_interiores + self.supuestas:
            self.superficies.append(Superficie(m.nombre, m.area, m.capas, "adiabatica",
                                               m.posicion))
        self.ventanas = [c for c in p.cerramientos if c.tipo == "ventana"]
        self._montar()

    # ------------------------------------------------------------------ red
    def _montar(self):
        cap_total: list[float] = []
        enlaces: list[tuple[int, int, float]] = []   # (i, j, G) ; j = -1 → aire/ext
        self.enlace_aire: list[tuple[int, float]] = []
        self.enlace_ext: list[tuple[int, float, Superficie]] = []
        idx = 0
        for s in self.superficies:
            cap, res = _discretizar(s.capas)
            # nodos: uno en cada interfaz (n_capas_discretas + 1)
            n = len(res) + 1
            s.nodos = list(range(idx, idx + n))
            caps = [0.0] * n
            for k, (c, r) in enumerate(zip(cap, res)):
                caps[k] += c / 2
                caps[k + 1] += c / 2
                enlaces.append((idx + k, idx + k + 1, s.area / r))
            cap_total += [x * s.area for x in caps]
            hci = H_CI[s.posicion]
            self.enlace_aire.append((s.nodos[0], hci * s.area))
            if s.contorno == "exterior":
                self.enlace_ext.append((s.nodos[-1], self.h_ext * s.area, s))
            elif s.contorno == "adyacente":
                self.enlace_ext.append((s.nodos[-1], s.area / (1 / (H_CI[s.posicion] + H_RI)), s))
            idx += n
        self.n_sup = idx
        self.i_mrt = idx                     # nodo radiante (sin capacidad)
        n_tot = idx + 1
        C = np.array(cap_total + [0.0]) / PASO_S
        G = np.zeros((n_tot, n_tot))
        for i, j, g in enlaces:
            G[i, i] += g
            G[j, j] += g
            G[i, j] -= g
            G[j, i] -= g
        for s in self.superficies:          # estrella radiante
            g = H_RI * s.area
            i = s.nodos[0]
            G[i, i] += g
            G[self.i_mrt, self.i_mrt] += g
            G[i, self.i_mrt] -= g
            G[self.i_mrt, i] -= g
        for i, g in self.enlace_aire:
            G[i, i] += g
        for i, g, _ in self.enlace_ext:
            G[i, i] += g
        self.C = C
        self.A_inv = np.linalg.inv(np.diag(C) + G)
        area_int = sum(s.area for s in self.superficies)
        self.reparto_area = {s.nodos[0]: s.area / area_int for s in self.superficies}
        suelos = [s for s in self.superficies if s.posicion == "suelo"]
        if suelos:
            a = sum(s.area for s in suelos)
            self.reparto_directa = {s.nodos[0]: s.area / a for s in suelos}
        else:
            self.reparto_directa = self.reparto_area

    # ----------------------------------------------------------- excitaciones
    def _excitaciones(self):
        """Lista de (nombre, función(t_h) -> (vector de fuentes en nodos, carga directa al aire))."""
        p, cl, it, lo, ve = self.p, self.p.clima, self.p.interior, self.p.local, self.p.ventilacion
        ti = it.t_verano
        cambio = cl.diferencia_horaria - cl.huso
        pa = presion_atmosferica(cl.altitud)
        w_ext = humedad_especifica_desde_bulbo_humedo(cl.t_verano, cl.th_verano, pa)
        RHO_CP_AIRE, _ = coeficientes_aire(cl.t_verano, w_ext, pa)

        def te(h):
            return cl.t_verano - cl.oscilacion_diaria * fraccion_oscilacion(h - cambio)

        n = self.i_mrt + 1
        exc = []
        perf = {}
        for s in self.superficies:
            if s.contorno == "exterior":
                c = s.elemento
                perf[s.nombre] = solar.perfil(cl.latitud, cl.longitud, cl.altitud, cl.mes_verano,
                                              cl.diferencia_horaria, c.orientacion, c.inclinacion,
                                              cl.modelo_cielo, cl.claridad, cl.albedo)
        for w in self.ventanas:
            perf[w.nombre] = solar.perfil(cl.latitud, cl.longitud, cl.altitud, cl.mes_verano,
                                          cl.diferencia_horaria, w.orientacion, w.inclinacion,
                                          cl.modelo_cielo, cl.claridad, cl.albedo)

        # Cerramientos opacos: temperatura exterior (o adyacente) + sol + cielo
        for i, g, s in self.enlace_ext:
            if s.contorno == "exterior":
                c = s.elemento
                ps = perf[s.nombre]
                f_cielo = (1 + math.cos(math.radians(c.inclinacion))) / 2

                def f(h, i=i, g=g, s=s, c=c, ps=ps, f_cielo=f_cielo):
                    b = np.zeros(n)
                    sol = c.absortividad * solar.interpolar(ps.horas, ps.total, h)
                    b[i] = g * (te(h) - ti) + s.area * (sol - f_cielo * H_RE * DELTA_CIELO)
                    return b, 0.0
            else:
                salto = s.elemento.temperatura_adyacente_verano - ti
                if salto < 0 and not p.descontar_perdidas_verano:
                    # Espacio adyacente más frío: no se descuenta (lado de la seguridad);
                    # el elemento sigue aportando su masa térmica.
                    salto = 0.0

                def f(h, i=i, g=g, salto=salto):
                    b = np.zeros(n)
                    b[i] = g * salto
                    return b, 0.0
            exc.append((s.nombre, f))

        # Ventanas: conducción (al aire) y solar transmitida (radiante)
        for w in self.ventanas:
            ps = perf[w.nombre]
            iam = solar.iam_vidrio(ps.aoi, w.hojas)
            k = w.area * (1 - w.fraccion_marco) * w.g * w.factor_sombra
            directa = k * ps.directa * iam
            difusa = k * ps.difusa * solar.iam_difusa(w.hojas)

            def fc(h, w=w):
                return np.zeros(n), w.U * w.area * (te(h) - ti)

            def fs(h, d=directa, dd=difusa, hh=ps.horas):
                b = np.zeros(n)
                qd = float(np.interp(h % 24, hh, d, period=24))
                qf = float(np.interp(h % 24, hh, dd, period=24))
                for i, r in self.reparto_directa.items():
                    b[i] += qd * r
                for i, r in self.reparto_area.items():
                    b[i] += qf * r
                return b, 0.0
            exc.append((f"{w.nombre} (conducción)", fc))
            exc.append((f"{w.nombre} (solar)", fs))

        # Puentes térmicos: conducción sin masa, directa al aire
        for pt in p.puentes_termicos:
            def fpt(h, H=pt.H):
                return np.zeros(n), H * (te(h) - ti)
            exc.append((f"PT {pt.tipo}: {pt.nombre}", fpt))

        # Ganancias internas
        h_ini, h_fin = lo.horario

        def ocupado(h):
            hh = (h - 1e-9) % 24
            return h_ini <= hh < h_fin if h_ini < h_fin else (hh >= h_ini or hh < h_fin)

        for nombre, potencia, frad in (
                ("Ocupantes", lo.personas * lo.sensible_persona, lo.fraccion_radiante_personas),
                ("Iluminación", lo.iluminacion_wm2 * lo.superficie, lo.fraccion_radiante_iluminacion),
                ("Equipos", lo.equipos_wm2 * lo.superficie, lo.fraccion_radiante_equipos)):
            if potencia <= 0:
                continue

            def fg(h, potencia=potencia, frad=frad):
                b = np.zeros(n)
                if not ocupado(h):
                    return b, 0.0
                for i, r in self.reparto_area.items():
                    b[i] += potencia * frad * r
                return b, potencia * (1 - frad)
            exc.append((nombre, fg))

        # Aire exterior (convectivo)
        inf = ve.infiltracion_h * lo.volumen

        def finf(h):
            return np.zeros(n), RHO_CP_AIRE * inf * (te(h) - ti)
        exc.append(("Infiltración", finf))

        def fvent(h):
            if not ocupado(h):
                return np.zeros(n), 0.0
            return np.zeros(n), RHO_CP_AIRE * ve.caudal_m3h * (1 - ve.eficiencia_recuperador) * (te(h) - ti)
        exc.append(("Ventilación", fvent))
        return exc

    # ------------------------------------------------------------ simulación
    def _respuesta(self, fuente) -> np.ndarray:
        """Carga sensible horaria (24 valores, horas 1..24) para una excitación."""
        pasos_dia = int(86400 / PASO_S)
        T = np.zeros(self.i_mrt + 1)          # temperaturas relativas a la consigna
        nodos_aire = np.array([i for i, _ in self.enlace_aire])
        g_aire = np.array([g for _, g in self.enlace_aire])
        cargas = np.zeros(pasos_dia)
        for dia in range(DIAS):
            for k in range(pasos_dia):
                h = (k + 1) * PASO_S / 3600.0
                b, directa = fuente(h)
                T = self.A_inv @ (self.C * T + b)
                if dia == DIAS - 1:
                    cargas[k] = float(np.dot(g_aire, T[nodos_aire])) + directa
        # valor horario: media del paso que termina en cada hora → muestreo en la hora
        idx = np.arange(1, 25) * int(3600 / PASO_S) - 1
        return cargas[idx]

    def calcular(self) -> dict[str, np.ndarray]:
        return {nombre: self._respuesta(f) for nombre, f in self._excitaciones()}


def calcular_verano_dinamico(p: Proyecto) -> ResultadoVerano:
    cl, it, lo, ve = p.clima, p.interior, p.local, p.ventilacion
    modelo = ModeloLocal(p)
    for m in modelo.supuestas:
        aviso = (f"Método dinámico: se ha supuesto '{m.nombre}' ({m.area:.1f} m², forjado de "
                 "hormigón). Descríbelo en 'masas_interiores' si es distinto.")
        if aviso not in p.avisos:
            p.avisos.append(aviso)
    comp = modelo.calcular()
    pa = presion_atmosferica(cl.altitud)
    w_ext = humedad_especifica_desde_bulbo_humedo(cl.t_verano, cl.th_verano, pa)
    w_int = humedad_especifica_desde_hr(it.t_verano, it.hr_verano, pa)
    dw = max(w_ext - w_int, 0.0)
    _, RHO_HFG_AIRE = coeficientes_aire(cl.t_verano, w_ext, pa)
    cambio = cl.diferencia_horaria - cl.huso
    h_ini, h_fin = lo.horario
    horas = []
    for k, h in enumerate(range(1, 25)):
        te = cl.t_verano - cl.oscilacion_diaria * fraccion_oscilacion(h - cambio)
        hv = HoraVerano(hora=h, t_ext=te)
        for nombre, serie in comp.items():
            hv.componentes[nombre] = float(serie[k])
        hh = (h - 1e-9) % 24
        ocupado = h_ini <= hh < h_fin if h_ini < h_fin else (hh >= h_ini or hh < h_fin)
        if ocupado:
            hv.latente["Ocupantes"] = lo.personas * lo.latente_persona
            hv.latente["Ventilación"] = RHO_HFG_AIRE * ve.caudal_m3h * dw
        hv.latente["Infiltración"] = RHO_HFG_AIRE * ve.infiltracion_h * lo.volumen * dw
        horas.append(hv)
    punta = max(horas, key=lambda x: x.total)
    return ResultadoVerano(horas=horas, punta=punta, w_ext=w_ext, w_int=w_int,
                           mayoracion=p.mayoracion)

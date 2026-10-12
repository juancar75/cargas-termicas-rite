"""Carga de refrigeración (verano) — cálculo horario del día de diseño.

Se calculan las 24 horas (hora oficial) del día 21 del mes de cálculo y se toma
la hora de máxima carga total.

Componentes:
  * Temperatura exterior horaria: θe(h) = θs − OMD · X(h), perfil X de ASHRAE.
  * Muros y cubiertas exteriores: temperatura sol-aire y método de admitancias
        Q(h) = U·A·[(θsa,m − θi) + f·(θsa(h−φ) − θsa,m)]
    con f = factor de amortiguamiento y φ = desfase [h].
  * Huecos: conducción U·A·(θe − θi) + radiación A·(1−FM)·g·Fs·I(h)
    (ganancia solar instantánea, sin factor de almacenamiento: lado de la seguridad).
  * Particiones a espacios no climatizados: U·A·(θady − θi), sólo si es positiva.
  * Ocupantes, iluminación y equipos en horario de ocupación.
  * Ventilación (en horario) e infiltración (24 h): sensible y latente.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import solar
from .modelo import Proyecto
from .psicrometria import (RHO_CP_AIRE, RHO_HFG_AIRE, humedad_especifica_desde_bulbo_humedo,
                           humedad_especifica_desde_hr, presion_atmosferica)

# Fracción de la oscilación diaria por hora solar 1..24 (ASHRAE Fundamentals).
PERFIL_X = [0.87, 0.92, 0.96, 0.99, 1.00, 0.98, 0.93, 0.84, 0.71, 0.56, 0.39, 0.23,
            0.11, 0.03, 0.00, 0.03, 0.10, 0.21, 0.34, 0.47, 0.58, 0.68, 0.76, 0.82]

H_EXT = 17.0          # coeficiente superficial exterior verano [W/(m²·K)]
DELTA_R_HORIZ = 3.9   # corrección por radiación de onda larga en horizontal [K]


def fraccion_oscilacion(hora_solar: float) -> float:
    """Interpola PERFIL_X para una hora solar cualquiera (periódica 24 h)."""
    h = hora_solar % 24
    if h == 0:
        h = 24
    i = int(h)
    frac = h - i
    a = PERFIL_X[(i - 1) % 24]
    b = PERFIL_X[i % 24]
    return a + (b - a) * frac


@dataclass
class HoraVerano:
    hora: int                     # hora oficial (1..24)
    t_ext: float
    componentes: dict[str, float] = field(default_factory=dict)   # sensibles [W]
    latente: dict[str, float] = field(default_factory=dict)       # latentes [W]

    @property
    def sensible(self) -> float:
        return sum(self.componentes.values())

    @property
    def total_latente(self) -> float:
        return sum(self.latente.values())

    @property
    def total(self) -> float:
        return self.sensible + self.total_latente


@dataclass
class ResultadoVerano:
    horas: list[HoraVerano]
    punta: HoraVerano
    w_ext: float
    w_int: float
    mayoracion: float

    @property
    def sensible(self) -> float:
        return self.punta.sensible * (1 + self.mayoracion)

    @property
    def latente(self) -> float:
        return self.punta.total_latente * (1 + self.mayoracion)

    @property
    def total(self) -> float:
        return self.sensible + self.latente


def _hora_solar(p: Proyecto, hora_oficial: float) -> float:
    return hora_oficial - p.clima.diferencia_horaria + p.clima.longitud / 15.0


def calcular_verano(p: Proyecto) -> ResultadoVerano:
    cl, it, lo, ve = p.clima, p.interior, p.local, p.ventilacion
    ti = it.t_verano
    pa = presion_atmosferica(cl.altitud)
    w_ext = humedad_especifica_desde_bulbo_humedo(cl.t_verano, cl.th_verano, pa)
    w_int = humedad_especifica_desde_hr(ti, it.hr_verano, pa)
    dw = max(w_ext - w_int, 0.0)

    def t_ext(hs: float) -> float:
        return cl.t_verano - cl.oscilacion_diaria * fraccion_oscilacion(hs)

    def irr(c, hs: float) -> float:
        return solar.irradiancia(cl.latitud, cl.mes_verano, hs, c.orientacion,
                                 c.inclinacion, claridad=cl.claridad)

    def t_sol_aire(c, hs: float) -> float:
        corr = DELTA_R_HORIZ if c.inclinacion == 0 else 0.0
        return t_ext(hs) + c.absortividad * irr(c, hs) / H_EXT - corr

    # temperatura sol-aire media diaria de cada opaco exterior
    opacos = [c for c in p.cerramientos if c.exterior and c.tipo in ("muro", "cubierta")]
    tsa_media = {c.nombre: sum(t_sol_aire(c, _hora_solar(p, h)) for h in range(1, 25)) / 24
                 for c in opacos}

    h_ini, h_fin = lo.horario
    horas: list[HoraVerano] = []
    for h in range(1, 25):
        hs = _hora_solar(p, h)
        te = t_ext(hs)
        hv = HoraVerano(hora=h, t_ext=te)
        ocupado = h_ini <= h < h_fin if h_ini < h_fin else (h >= h_ini or h < h_fin)
        for c in p.cerramientos:
            if not c.exterior:
                q = c.U * c.area * (c.temperatura_adyacente_verano - ti)
                hv.componentes[c.nombre] = max(q, 0.0)
            elif c.tipo == "ventana":
                cond = c.U * c.area * (te - ti)
                rad = c.area * (1 - c.fraccion_marco) * c.g * c.factor_sombra * irr(c, hs)
                hv.componentes[f"{c.nombre} (conducción)"] = cond
                hv.componentes[f"{c.nombre} (solar)"] = rad
            else:
                m = tsa_media[c.nombre]
                desfasada = t_sol_aire(c, hs - c.desfase_h)
                q = c.U * c.area * ((m - ti) + c.factor_amortiguamiento * (desfasada - m))
                hv.componentes[c.nombre] = q
        if ocupado:
            hv.componentes["Ocupantes"] = lo.personas * lo.sensible_persona
            hv.latente["Ocupantes"] = lo.personas * lo.latente_persona
            hv.componentes["Iluminación"] = lo.iluminacion_wm2 * lo.superficie
            hv.componentes["Equipos"] = lo.equipos_wm2 * lo.superficie
            caudal = ve.caudal_m3h
            hv.componentes["Ventilación"] = (RHO_CP_AIRE * caudal
                                            * (1 - ve.eficiencia_recuperador) * (te - ti))
            hv.latente["Ventilación"] = RHO_HFG_AIRE * caudal * dw
        inf = ve.infiltracion_h * lo.volumen
        hv.componentes["Infiltración"] = RHO_CP_AIRE * inf * (te - ti)
        hv.latente["Infiltración"] = RHO_HFG_AIRE * inf * dw
        horas.append(hv)

    punta = max(horas, key=lambda x: x.total)
    return ResultadoVerano(horas=horas, punta=punta, w_ext=w_ext, w_int=w_int,
                           mayoracion=p.mayoracion)

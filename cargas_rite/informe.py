"""Generación del informe de justificación de cargas (Markdown y CSV)."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from . import __version__
from .invierno import ResultadoInvierno
from .modelo import Proyecto
from .verano import ResultadoVerano


def _w(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def _kw(x: float) -> str:
    return f"{x / 1000:.2f}".replace(".", ",")


def _n(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def markdown(p: Proyecto, inv: ResultadoInvierno, ver: ResultadoVerano) -> str:
    cl, it, lo, ve = p.clima, p.interior, p.local, p.ventilacion
    L: list[str] = []
    a = L.append
    a(f"# {p.titulo}")
    a("")
    a(f"Justificación de cargas térmicas de invierno y verano — `cargas-termicas-rite` v{__version__}  ")
    a(f"Fecha: {date.today():%d/%m/%Y}" + (f" · Autor: {p.autor}" if p.autor else ""))
    a("")
    a("## 1. Resumen")
    a("")
    a("| | Sensible | Latente | Total |")
    a("|---|---:|---:|---:|")
    a(f"| **Refrigeración** (punta a las {ver.punta.hora}:00 h oficiales) | {_kw(ver.sensible)} kW "
      f"| {_kw(ver.latente)} kW | **{_kw(ver.total)} kW** |")
    a(f"| **Calefacción** | {_kw(inv.total)} kW | — | **{_kw(inv.total)} kW** |")
    a("")
    a(f"Ratios: refrigeración {_w(ver.total / lo.superficie)} W/m², "
      f"calefacción {_w(inv.total / lo.superficie)} W/m² "
      f"(superficie {_n(lo.superficie)} m²).")
    if p.mayoracion:
        a(f"Incluye una mayoración del {_n(p.mayoracion * 100, 0)} %.")
    a("")
    if p.avisos:
        a("> **Avisos**")
        for av in p.avisos:
            a(f"> - {av}")
        a("")

    a("## 2. Datos de partida")
    a("")
    a("### 2.1 Condiciones exteriores de proyecto")
    a("")
    a(f"- Latitud {_n(cl.latitud, 2)}°, longitud {_n(cl.longitud, 2)}°, altitud {_w(cl.altitud)} m")
    a(f"- Invierno: temperatura seca {_n(cl.t_invierno)} °C")
    a(f"- Verano: temperatura seca {_n(cl.t_verano)} °C, húmeda coincidente {_n(cl.th_verano)} °C, "
      f"oscilación media diaria {_n(cl.oscilacion_diaria)} K; día 21 del mes {cl.mes_verano}")
    a(f"- Humedad específica exterior {_n(ver.w_ext, 2)} g/kg; interior {_n(ver.w_int, 2)} g/kg")
    if cl.fuente:
        a(f"- Fuente: {cl.fuente}")
    a("")
    a("### 2.2 Condiciones interiores (RITE IT 1.1.4.1.2)")
    a("")
    a(f"- Invierno: {_n(it.t_invierno)} °C, HR {_n(it.hr_invierno * 100, 0)} %")
    a(f"- Verano: {_n(it.t_verano)} °C, HR {_n(it.hr_verano * 100, 0)} %")
    a("")
    a("### 2.3 Local")
    a("")
    a(f"- {lo.nombre}: {_n(lo.superficie)} m², altura {_n(lo.altura, 2)} m, volumen {_n(lo.volumen)} m³")
    a(f"- Ocupación: {_n(lo.personas)} personas ({_w(lo.sensible_persona)} W sensible + "
      f"{_w(lo.latente_persona)} W latente por persona)")
    a(f"- Iluminación {_n(lo.iluminacion_wm2)} W/m² · equipos {_n(lo.equipos_wm2)} W/m² · "
      f"horario {lo.horario[0]}–{lo.horario[1]} h")
    ida = f" ({ve.categoria_ida}, RITE IT 1.1.4.2.3)" if ve.categoria_ida else ""
    a(f"- Ventilación: {_w(ve.caudal_m3h)} m³/h{ida}; recuperador "
      f"{_n(ve.eficiencia_recuperador * 100, 0)} %; infiltración {_n(ve.infiltracion_h, 2)} ren/h")
    a("")
    a("### 2.4 Cerramientos")
    a("")
    a("| Elemento | Tipo | Orient. | Área m² | U W/m²K | Otros |")
    a("|---|---|---|---:|---:|---|")
    for c in p.cerramientos:
        if c.exterior:
            ori = "H" if c.tipo == "cubierta" else f"{c.orientacion:.0f}°"
        else:
            ori = f"adyacente {c.temperatura_adyacente_invierno:g}/{c.temperatura_adyacente_verano:g} °C"
        if c.tipo == "ventana":
            otros = (f"g={_n(c.g, 2)}, marco {c.fraccion_marco * 100:.0f} %, "
                     f"Fs={_n(c.factor_sombra, 2)}, {c.hojas} hojas")
        elif c.exterior:
            otros = (f"α={_n(c.absortividad, 2)}, f={_n(c.factor_amortiguamiento, 2)}, "
                     f"φ={_n(c.desfase_h, 1)} h")
        else:
            otros = ""
        extra = []
        if c.origen:
            extra.append(c.origen)
        elif c.capas:
            extra.append(f"{len(c.capas)} capas (ISO 6946/13786)")
        if c.terreno:
            extra.append(f"terreno ISO 13370: B'={_n(c.terreno['B'], 1)} m, "
                         f"d_t={_n(c.terreno['d_t'], 2)} m")
        if c.espacio_no_acondicionado:
            extra.append(f"no acondicionado, b={_n(c.espacio_no_acondicionado['b'], 2)} (ISO 13789)")
        if extra:
            otros = "; ".join([otros] + extra if otros else extra)
        a(f"| {c.nombre} | {c.tipo} | {ori} | {_n(c.area, 2)} | {_n(c.U, 2)} | {otros} |")
    a("")
    if p.puentes_termicos:
        a("### 2.5 Puentes térmicos")
        a("")
        a("| Puente térmico | Tipo (ISO 14683) | L m | ψ W/mK | ψ·L W/K |")
        a("|---|---|---:|---:|---:|")
        for pt in p.puentes_termicos:
            a(f"| {pt.nombre} | {pt.tipo} | {_n(pt.longitud, 2)} | {_n(pt.psi, 3)} | {_n(pt.H, 2)} |")
        a("")

    a("## 3. Carga de refrigeración")
    a("")
    a(f"Hora punta: **{ver.punta.hora}:00 h** (hora oficial), temperatura exterior "
      f"{_n(ver.punta.t_ext)} °C.")
    a("")
    a("| Componente | Sensible W | Latente W |")
    a("|---|---:|---:|")
    claves = list(ver.punta.componentes) + [k for k in ver.punta.latente
                                            if k not in ver.punta.componentes]
    for k in claves:
        s = ver.punta.componentes.get(k, 0.0)
        lat = ver.punta.latente.get(k, 0.0)
        a(f"| {k} | {_w(s)} | {_w(lat) if lat else ''} |")
    a(f"| **Subtotal** | **{_w(ver.punta.sensible)}** | **{_w(ver.punta.total_latente)}** |")
    if p.mayoracion:
        a(f"| Mayoración {_n(p.mayoracion * 100, 0)} % | {_w(ver.sensible - ver.punta.sensible)} "
          f"| {_w(ver.latente - ver.punta.total_latente)} |")
    a(f"| **Total** | **{_w(ver.sensible)}** | **{_w(ver.latente)}** |")
    a("")
    a(f"Factor de calor sensible: {_n(ver.sensible / ver.total, 2)}")
    a("")
    a("### 3.1 Evolución horaria")
    a("")
    a("| Hora | θe °C | Sensible W | Latente W | Total W |")
    a("|---:|---:|---:|---:|---:|")
    for h in ver.horas:
        marca = " ◀" if h is ver.punta else ""
        a(f"| {h.hora} | {_n(h.t_ext)} | {_w(h.sensible)} | {_w(h.total_latente)} | {_w(h.total)}{marca} |")
    a("")

    a("## 4. Carga de calefacción")
    a("")
    a(f"Salto térmico de diseño: {_n(inv.delta_t)} K. Sin descontar ganancias internas ni solares. "
      f"Puentes térmicos: ΔU = {_n(p.dU_puentes_termicos, 2)} W/m²K en opacos exteriores.")
    a("")
    a("| Componente | W |")
    a("|---|---:|")
    for k, v in inv.transmision.items():
        a(f"| {k} | {_w(v)} |")
    a(f"| Ventilación | {_w(inv.ventilacion)} |")
    a(f"| Infiltración | {_w(inv.infiltracion)} |")
    if inv.mayoracion:
        a(f"| Mayoración {_n(p.mayoracion * 100, 0)} % | {_w(inv.mayoracion)} |")
    a(f"| **Total** | **{_w(inv.total)}** |")
    a("")

    a("## 5. Método y referencias")
    a("")
    a("- Calefacción: régimen estacionario según el planteamiento de UNE-EN 12831-1 (simplificado).")
    if p.metodo_verano == "simplificado":
        a("- Refrigeración (método simplificado): cálculo horario del día de diseño; opacos con "
          "temperatura sol-aire y propiedades dinámicas UNE-EN ISO 13786; ganancia solar por huecos "
          "instantánea (sin almacenamiento), del lado de la seguridad.")
    else:
        a("- Refrigeración (método dinámico): balance térmico horario del local con red de nodos "
          "por capas, intercambio radiante interior y almacenamiento de la radiación solar y de "
          "las ganancias internas en la masa del local (planteamiento de UNE-EN ISO 52016-1). "
          "Validado contra EnergyPlus (ver `validacion/resultados.md`).")
    if not p.descontar_perdidas_verano:
        a("- En verano no se descuenta el calor que sale hacia locales o terreno más fríos "
          "(lado de la seguridad); esos elementos sí cuentan como masa térmica.")
    a("- Radiación solar: posición solar NREL-SPA y cielo despejado (pvlib); vidrios con "
      "modificador por ángulo de incidencia. Psicrometría: CoolProp (ASHRAE RP-1485).")
    a("- Condiciones interiores y ventilación: RITE, IT 1.1.4.1.2 e IT 1.1.4.2.")
    a("- Documentación: RITE art. 15 (memoria técnica para 5 kW ≤ P ≤ 70 kW).")
    a("")
    a("*La herramienta no sustituye el criterio técnico de quien firma la documentación. "
      "Verifique los datos de entrada y los resultados.*")
    return "\n".join(L) + "\n"


def csv_horario(ver: ResultadoVerano, ruta: str | Path) -> None:
    claves = list(ver.horas[0].componentes)
    for h in ver.horas:
        for k in h.componentes:
            if k not in claves:
                claves.append(k)
    lat = sorted({k for h in ver.horas for k in h.latente})
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["hora", "t_ext"] + [f"S {k}" for k in claves] + [f"L {k}" for k in lat]
                   + ["sensible", "latente", "total"])
        for h in ver.horas:
            w.writerow([h.hora, round(h.t_ext, 2)]
                       + [round(h.componentes.get(k, 0.0), 1) for k in claves]
                       + [round(h.latente.get(k, 0.0), 1) for k in lat]
                       + [round(h.sensible, 1), round(h.total_latente, 1), round(h.total, 1)])

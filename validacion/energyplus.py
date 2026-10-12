"""Validación de cargas-termicas-rite contra EnergyPlus.

Para cada caso de referencia (una caja rectangular) se genera:
  1. la entrada de cargas_rite (áreas, capas, cargas), y
  2. un IDF equivalente de EnergyPlus con la misma geometría, capas, huecos,
     cargas internas e infiltración,
se ejecuta EnergyPlus con sus días de diseño (cálculo de dimensionado de zona con
equipo ideal) y se comparan las cargas punta sensibles de refrigeración y calefacción.

Uso:
    python validacion/energyplus.py [--energyplus /ruta/energyplus] [--salida validacion/resultados]
"""
from __future__ import annotations

import argparse
import copy
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from cargas_rite import calcular_invierno, calcular_verano, desde_dict  # noqa: E402
from cargas_rite.dinamico import calcular_verano_dinamico  # noqa: E402
from cargas_rite.psicrometria import presion_atmosferica  # noqa: E402

# --------------------------------------------------------------------------- casos
YESO = dict(conductividad=0.57, densidad=1150, calor_especifico=1000)
LADRILLO = dict(conductividad=0.49, densidad=1200, calor_especifico=1000)
LANA = dict(conductividad=0.037, densidad=40, calor_especifico=1000)
HORMIGON = dict(conductividad=1.65, densidad=2150, calor_especifico=1000)
EPS = dict(conductividad=0.035, densidad=25, calor_especifico=1450)

FACHADA_LIGERA = [dict(nombre="yeso", espesor=0.015, **YESO),
                  dict(nombre="LH7", espesor=0.07, **LADRILLO),
                  dict(nombre="lana", espesor=0.05, **LANA),
                  dict(nombre="medio pie", espesor=0.115, **LADRILLO)]
MURO_PESADO = [dict(nombre="yeso", espesor=0.015, **YESO),
               dict(nombre="hormigon", espesor=0.25, **HORMIGON)]
CUBIERTA = [dict(nombre="yeso", espesor=0.015, **YESO),
            dict(nombre="forjado", espesor=0.25, **HORMIGON),
            dict(nombre="EPS", espesor=0.08, **EPS),
            dict(nombre="capa compresion", espesor=0.05, **HORMIGON)]
TABIQUE = [dict(nombre="placa", espesor=0.015, conductividad=0.25, densidad=900, calor_especifico=1000),
           dict(nombre="lana", espesor=0.05, **LANA),
           dict(nombre="placa", espesor=0.015, conductividad=0.25, densidad=900, calor_especifico=1000)]
FORJADO = [dict(nombre="solado", espesor=0.02, conductividad=1.3, densidad=2300, calor_especifico=840),
           dict(nombre="mortero", espesor=0.04, conductividad=1.3, densidad=1900, calor_especifico=1000),
           dict(nombre="forjado", espesor=0.25, **HORMIGON)]

CLIMA_MADRID = {
    "latitud": 40.41, "longitud": -3.70, "altitud": 667, "diferencia_horaria": 2, "huso": 1,
    "mes_verano": 7, "modelo_cielo": "ashrae",
    "invierno": {"temperatura_seca": -3.0},
    "verano": {"temperatura_seca": 36.0, "temperatura_humeda_coincidente": 21.5,
               "oscilacion_media_diaria": 15.0},
}


@dataclass
class Caso:
    nombre: str
    descripcion: str
    caras: dict           # cara -> dict(tipo: exterior|adiabatica|adyacente, ...)
    ancho: float = 6.0    # x (este)
    fondo: float = 5.0    # y (norte)
    alto: float = 3.0
    personas: float = 0.0
    sensible_persona: float = 75.0
    latente_persona: float = 55.0
    iluminacion: float = 0.0
    equipos: float = 0.0
    horario: tuple = (10, 21)     # hora oficial
    infiltracion: float = 0.0
    absortividad: float = 0.6


def _caras_base():
    return {c: {"tipo": "adiabatica"} for c in ("S", "E", "N", "O", "techo", "suelo")}


def casos() -> list[Caso]:
    lista = []
    for ori in ("S", "O", "E"):
        caras = _caras_base()
        caras[ori] = {"tipo": "exterior", "capas": FACHADA_LIGERA,
                      "ventana": {"ancho": 2.4, "alto": 1.5, "U": 2.7, "g": 0.6}}
        lista.append(Caso(f"fachada_{ori}", f"Fachada {ori} ligera con ventana 3,6 m²", caras))
    caras = _caras_base()
    caras["S"] = {"tipo": "exterior", "capas": MURO_PESADO}
    lista.append(Caso("muro_pesado_S", "Muro S de hormigón 25 cm sin huecos", caras))
    caras = _caras_base()
    caras["techo"] = {"tipo": "exterior", "capas": CUBIERTA}
    lista.append(Caso("cubierta", "Cubierta plana de hormigón con EPS 8 cm", caras))
    caras = _caras_base()
    lista.append(Caso("cargas_internas", "Sólo ocupantes, iluminación y equipos", caras,
                      personas=6, iluminacion=12, equipos=10))
    caras = _caras_base()
    caras["N"] = {"tipo": "adyacente", "capas": TABIQUE, "invierno": 10.0, "verano": 32.0}
    lista.append(Caso("particion", "Tabique a local no climatizado (10 / 32 °C)", caras))
    caras = _caras_base()
    lista.append(Caso("infiltracion", "Sólo infiltración 0,5 ren/h", caras, infiltracion=0.5))
    caras = _caras_base()
    caras["S"] = {"tipo": "exterior", "capas": FACHADA_LIGERA,
                  "ventana": {"ancho": 4.0, "alto": 2.2, "U": 2.7, "g": 0.6}}
    caras["O"] = {"tipo": "adyacente", "capas": TABIQUE, "invierno": 12.0, "verano": 30.0}
    caras["techo"] = {"tipo": "exterior", "capas": CUBIERTA}
    lista.append(Caso("local_completo", "Escaparate S, cubierta, medianera y cargas internas",
                      caras, personas=6, iluminacion=12, equipos=5, infiltracion=0.3))
    return lista


# --------------------------------------------------------------------- geometría
def _rect(origen, u, v, ancho, alto):
    """Vértices en sentido antihorario visto desde fuera, empezando arriba-izquierda."""
    o, u, v = np.array(origen, float), np.array(u, float), np.array(v, float)
    return [o + v * alto, o, o + u * ancho, o + u * ancho + v * alto]


def _geometria(caso: Caso):
    W, D, H = caso.ancho, caso.fondo, caso.alto
    z = (0, 0, 1)
    paredes = {
        "S": ((0, 0, 0), (1, 0, 0), W, 180),
        "E": ((W, 0, 0), (0, 1, 0), D, 90),
        "N": ((W, D, 0), (-1, 0, 0), W, 0),
        "O": ((0, D, 0), (0, -1, 0), D, 270),
    }
    g = {}
    for cara, (o, u, ancho, azim) in paredes.items():
        g[cara] = dict(vertices=_rect(o, u, z, ancho, H), area=ancho * H, azimut=azim,
                       origen=o, u=u, ancho=ancho)
    g["techo"] = dict(vertices=_rect((0, 0, H), (1, 0, 0), (0, 1, 0), W, D), area=W * D)
    g["suelo"] = dict(vertices=_rect((W, 0, 0), (-1, 0, 0), (0, 1, 0), W, D), area=W * D)
    return g


def _ventana(cara_geo, ancho, alto, antepecho=None):
    if antepecho is None:
        antepecho = min(0.9, (3.0 - alto) / 2)
    o, u = np.array(cara_geo["origen"], float), np.array(cara_geo["u"], float)
    desplaz = (cara_geo["ancho"] - ancho) / 2
    return _rect(o + u * desplaz + np.array([0, 0, antepecho]), u, (0, 0, 1), ancho, alto)


# --------------------------------------------------------------- entrada cargas_rite
TIPO_CARA = {"techo": "cubierta", "suelo": "suelo"}


def entrada_cargas(caso: Caso) -> dict:
    geo = _geometria(caso)
    cerr, masas = [], []
    for cara, d in caso.caras.items():
        if d["tipo"] == "adiabatica":
            masas.append({"nombre": f"interior {cara}", "area": geo[cara]["area"],
                          "capas": FORJADO if cara in ("techo", "suelo") else TABIQUE,
                          "posicion": {"techo": "techo", "suelo": "suelo"}.get(cara, "vertical")})
            continue
        tipo = TIPO_CARA.get(cara, "muro")
        area = geo[cara]["area"]
        if "ventana" in d:
            v = d["ventana"]
            av = v["ancho"] * v["alto"]
            area -= av
            cerr.append({"nombre": f"Ventana {cara}", "tipo": "ventana", "orientacion": cara,
                         "area": av, "U": v["U"], "g": v["g"], "fraccion_marco": 0.0})
        e = {"nombre": f"{tipo} {cara}", "tipo": tipo if d["tipo"] == "exterior" else "particion",
             "area": area, "capas": d["capas"], "absortividad": caso.absortividad}
        if d["tipo"] == "exterior" and tipo == "muro":
            e["orientacion"] = cara
        if d["tipo"] == "adyacente":
            e["temperatura_adyacente"] = {"invierno": d["invierno"], "verano": d["verano"]}
        cerr.append(e)
    return {
        "proyecto": {"titulo": caso.descripcion},
        "clima": copy.deepcopy(CLIMA_MADRID),
        "interior": {"invierno": {"temperatura": 21, "humedad_relativa": 0.4},
                     "verano": {"temperatura": 25, "humedad_relativa": 0.5}},
        "local": {"nombre": caso.nombre, "superficie": caso.ancho * caso.fondo, "altura": caso.alto,
                  "ocupacion": {"actividad": "comercio", "personas": caso.personas,
                                "sensible_persona": caso.sensible_persona,
                                "latente_persona": caso.latente_persona},
                  "iluminacion": caso.iluminacion, "equipos": caso.equipos,
                  "horario": list(caso.horario),
                  # mismas fracciones radiantes que el IDF (personas 0,3; luz 0,37+0,18; equipos 0,3)
                  "fracciones_radiantes": {"personas": 0.3, "iluminacion": 0.55, "equipos": 0.3}},
        "masas_interiores": masas,
        "ventilacion": {"caudal_m3h": 0.0, "infiltracion_renovaciones_h": caso.infiltracion},
        "cerramientos": cerr or [{"nombre": "nulo", "tipo": "particion", "area": 1e-6, "U": 1e-6,
                                  "temperatura_adyacente": {"invierno": 21, "verano": 25}}],
        "coeficientes": {"puentes_termicos_dU": 0.0, "mayoracion": 0.0},
    }


# ----------------------------------------------------------------------------- IDF
def _obj(tipo, *campos):
    lineas = [f"{tipo},"]
    for i, c in enumerate(campos):
        fin = ";" if i == len(campos) - 1 else ","
        lineas.append(f"    {c}{fin}")
    return "\n".join(lineas) + "\n\n"


def _pts(vs):
    return [f"{v[0]:.4f},{v[1]:.4f},{v[2]:.4f}" for v in vs]


def _construccion(nombre, capas_int_ext, alfa, idf, materiales):
    """EnergyPlus ordena las capas de EXTERIOR a INTERIOR."""
    nombres = []
    for i, c in enumerate(reversed(capas_int_ext)):
        mn = f"{nombre}_{i}_{c['nombre']}".replace(" ", "_")
        a_sol = alfa if i == 0 else 0.7
        if c.get("densidad", 0) <= 0:
            idf.append(_obj("Material:NoMass", mn, "MediumRough",
                            f"{c['espesor'] / c['conductividad']:.5f}", 0.9, a_sol, a_sol))
        else:
            idf.append(_obj("Material", mn, "MediumRough", c["espesor"], c["conductividad"],
                            c["densidad"], c["calor_especifico"], 0.9, a_sol, a_sol))
        nombres.append(mn)
    idf.append(_obj("Construction", nombre, *nombres))


def idf(caso: Caso) -> str:
    cl = CLIMA_MADRID
    cambio = cl["diferencia_horaria"] - cl["huso"]
    h_ini, h_fin = caso.horario[0] - cambio, caso.horario[1] - cambio   # hora estándar
    p_atm = presion_atmosferica(cl["altitud"]) * 1000
    out = []
    o = out.append
    o(_obj("Version", "26.1"))
    o(_obj("SimulationControl", "Yes", "No", "No", "No", "No", "No", 1))
    o(_obj("Building", caso.nombre, 0, "Suburbs", 0.04, 0.004, "FullInteriorAndExterior", 25, 6))
    o(_obj("Timestep", 6))
    o(_obj("GlobalGeometryRules", "UpperLeftCorner", "Counterclockwise", "World"))
    o(_obj("Site:Location", "Madrid", cl["latitud"], cl["longitud"], cl["huso"], cl["altitud"]))
    o(_obj("SizingPeriod:DesignDay", "Verano", cl["mes_verano"], 21, "SummerDesignDay",
           cl["verano"]["temperatura_seca"], cl["verano"]["oscilacion_media_diaria"], "", "",
           "Wetbulb", cl["verano"]["temperatura_humeda_coincidente"], "", "", "", "",
           f"{p_atm:.0f}", 2.0, 230, "No", "No", "No", "ASHRAEClearSky", "", "", "", "", 1.0))
    o(_obj("SizingPeriod:DesignDay", "Invierno", 1, 21, "WinterDesignDay",
           cl["invierno"]["temperatura_seca"], 0.0, "", "", "Wetbulb",
           cl["invierno"]["temperatura_seca"], "", "", "", "", f"{p_atm:.0f}", 4.0, 0,
           "No", "No", "No", "ASHRAEClearSky", "", "", "", "", 0.0))
    o(_obj("ScheduleTypeLimits", "Fraccion", 0, 1, "Continuous"))
    o(_obj("ScheduleTypeLimits", "Cualquiera", "", "", "Continuous"))
    o(_obj("Schedule:Constant", "Siempre", "Cualquiera", 1))
    o(_obj("Schedule:Constant", "TipoControl", "Cualquiera", 4))
    o(_obj("Schedule:Constant", "Consigna Calor", "Cualquiera", 21))
    o(_obj("Schedule:Constant", "Consigna Frio", "Cualquiera", 25))
    o(_obj("Schedule:Constant", "Actividad", "Cualquiera", caso.sensible_persona + caso.latente_persona))
    o(_obj("Schedule:Compact", "Ocupacion", "Fraccion", "Through: 12/31",
           "For: SummerDesignDay", f"Until: {h_ini:02d}:00", 0, f"Until: {h_fin:02d}:00", 1,
           "Until: 24:00", 0, "For: AllOtherDays", "Until: 24:00", 0))
    o(_obj("Zone", "Local", 0, 0, 0, 0, 1, 1, "autocalculate", "autocalculate"))

    geo = _geometria(caso)
    for cara, d in caso.caras.items():
        tipo_sup = {"techo": "Roof", "suelo": "Floor"}.get(cara, "Wall")
        if d["tipo"] == "adiabatica":
            capas = FORJADO if cara in ("techo", "suelo") else TABIQUE
            cons = f"C_adiab_{cara}"
            _construccion(cons, capas, 0.6, out, None)
            cond, obj_cond, sol, viento = "Adiabatic", "", "NoSun", "NoWind"
        elif d["tipo"] == "exterior":
            cons = f"C_ext_{cara}"
            _construccion(cons, d["capas"], caso.absortividad, out, None)
            cond, obj_cond, sol, viento = "Outdoors", "", "SunExposed", "WindExposed"
        else:
            cons = f"C_ady_{cara}"
            _construccion(cons, d["capas"], 0.6, out, None)
            o(_obj("Schedule:Compact", f"T_ady_{cara}", "Cualquiera", "Through: 12/31",
                   "For: SummerDesignDay", "Until: 24:00", d["verano"],
                   "For: AllOtherDays", "Until: 24:00", d["invierno"]))
            o(_obj("SurfaceProperty:OtherSideCoefficients", f"OSC_{cara}", f"{1 / 0.13:.4f}", 0,
                   1, 0, 0, 0, 0, f"T_ady_{cara}", "No", 24, 0))
            cond, obj_cond, sol, viento = "OtherSideCoefficients", f"OSC_{cara}", "NoSun", "NoWind"
        o(_obj("BuildingSurface:Detailed", f"Sup_{cara}", tipo_sup, cons, "Local", "",
               cond, obj_cond, sol, viento, "autocalculate", 4, *_pts(geo[cara]["vertices"])))
        if "ventana" in d:
            v = d["ventana"]
            o(_obj("WindowMaterial:SimpleGlazingSystem", f"Vidrio_{cara}", v["U"], v["g"], 0.7))
            o(_obj("Construction", f"C_vent_{cara}", f"Vidrio_{cara}"))
            o(_obj("FenestrationSurface:Detailed", f"Ventana_{cara}", "Window", f"C_vent_{cara}",
                   f"Sup_{cara}", "", "autocalculate", "", 1, 4,
                   *_pts(_ventana(geo[cara], v["ancho"], v["alto"]))))

    if caso.personas:
        o(_obj("People", "Personas", "Local", "Ocupacion", "People", caso.personas, "", "", 0.3,
               f"{caso.sensible_persona / (caso.sensible_persona + caso.latente_persona):.4f}",
               "Actividad"))
    if caso.iluminacion:
        o(_obj("Lights", "Iluminacion", "Local", "Ocupacion", "Watts/Area", "", caso.iluminacion,
               "", 0, 0.37, 0.18, 1, "General"))
    if caso.equipos:
        o(_obj("ElectricEquipment", "Equipos", "Local", "Ocupacion", "Watts/Area", "",
               caso.equipos, "", 0, 0.3, 0))
    if caso.infiltracion:
        o(_obj("ZoneInfiltration:DesignFlowRate", "Infiltracion", "Local", "Siempre",
               "AirChanges/Hour", "", "", "", caso.infiltracion, 1, 0, 0, 0))

    o(_obj("ThermostatSetpoint:DualSetpoint", "Consignas", "Consigna Calor", "Consigna Frio"))
    o(_obj("ZoneControl:Thermostat", "Termostato", "Local", "TipoControl",
           "ThermostatSetpoint:DualSetpoint", "Consignas"))
    o(_obj("DesignSpecification:OutdoorAir", "SinAireExterior", "Flow/Zone", 0, 0, 0))
    o(_obj("Sizing:Parameters", 1.0, 1.0, 1))
    o(_obj("Sizing:Zone", "Local", "SupplyAirTemperature", 13, "", "SupplyAirTemperature", 40,
           "", 0.008, 0.008, "SinAireExterior", 1.0, 1.0, "DesignDay", 0, "", "", "",
           "DesignDay", 0, "", "", "", "", "No", "NeutralSupplyAir", "autosize", "autosize"))
    o(_obj("NodeList", "Entradas", "Nodo_Impulsion"))
    o(_obj("ZoneHVAC:EquipmentConnections", "Local", "Equipos Local", "Entradas", "",
           "Nodo_Aire_Local", "Nodo_Retorno"))
    o(_obj("ZoneHVAC:EquipmentList", "Equipos Local", "SequentialLoad",
           "ZoneHVAC:IdealLoadsAirSystem", "Ideal", 1, 1, "", ""))
    o(_obj("ZoneHVAC:IdealLoadsAirSystem", "Ideal", "", "Nodo_Impulsion", "", "", 50, 13,
           0.015, 0.008, "NoLimit", "", "", "NoLimit", "", "", "", "", "None", "", "None"))
    o(_obj("Output:SQLite", "SimpleAndTabular"))
    o(_obj("Output:Table:SummaryReports", "HVACSizingSummary"))
    return "".join(out)


# ----------------------------------------------------------------------- ejecución
def ejecutar_energyplus(texto_idf: str, ejecutable: str, directorio: Path) -> dict:
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / "in.idf"
    ruta.write_text(texto_idf, encoding="utf-8")
    r = subprocess.run([ejecutable, "-d", str(directorio), "-D", str(ruta)],
                       capture_output=True, text=True)
    err = directorio / "eplusout.err"
    if r.returncode != 0 or not (directorio / "eplusout.sql").exists():
        raise RuntimeError(f"EnergyPlus falló en {directorio}:\n"
                           + (err.read_text(errors="ignore")[-3000:] if err.exists() else r.stderr))
    con = sqlite3.connect(directorio / "eplusout.sql")
    filas = con.execute("SELECT LoadType, CalcDesLoad, PeakHrMin FROM ZoneSizes").fetchall()
    con.close()
    res = {}
    for tipo, carga, hora in filas:
        res[tipo.lower()] = (carga, hora)
    return res


def localizar_energyplus(ruta: str | None = None) -> str | None:
    for cand in (ruta, os.environ.get("ENERGYPLUS"), shutil.which("energyplus"),
                 "/opt/energyplus/current/energyplus",
                 r"C:\EnergyPlusV26-1-0\energyplus.exe", r"C:\EnergyPlusV25-1-0\energyplus.exe"):
        if cand and Path(cand).exists():
            return str(cand)
    return None


def comparar(ejecutable: str, directorio_trabajo: Path | None = None) -> list[dict]:
    base = directorio_trabajo or Path(tempfile.mkdtemp(prefix="cargas_ep_"))
    filas = []
    for caso in casos():
        p = desde_dict(entrada_cargas(caso))
        inv = calcular_invierno(p)
        ver = calcular_verano(p)
        din = calcular_verano_dinamico(p)
        ep = ejecutar_energyplus(idf(caso), ejecutable, base / caso.nombre)
        ref_frio, hora_frio = ep.get("cooling", (0.0, ""))
        ref_calor, _ = ep.get("heating", (0.0, ""))
        filas.append(dict(
            caso=caso.nombre, descripcion=caso.descripcion,
            frio=ver.punta.sensible, frio_din=din.punta.sensible, hora_din=din.punta.hora,
            frio_ep=ref_frio, hora=ver.punta.hora,
            hora_ep=hora_frio, calor=inv.total, calor_ep=ref_calor))
    return filas


def _desv(a, b):
    if b < 1:
        return "—" if a < 1 else "n/a"
    return f"{(a - b) / b * 100:+.0f} %"


def _hora_ep(texto: str) -> str:
    """'7/21 14:40:00' (hora estándar) → '15:40' (hora oficial de verano)."""
    try:
        hm = texto.split()[1]
        h, m = int(hm[:2]), int(hm[3:5])
        return f"{(h + 1) % 24}:{m:02d}"
    except (IndexError, ValueError):
        return texto


def tabla_markdown(filas: list[dict]) -> str:
    L = ["| Caso | E+ W | Dinámico W | Desv. | Simplificado W | Desv. | Hora punta oficial (E+ / din.) "
         "| Calef. E+ W | Calef. propio W | Desv. |",
         "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|"]
    for f in filas:
        L.append(f"| {f['descripcion']} | {f['frio_ep']:.0f} | {f['frio_din']:.0f} | "
                 f"{_desv(f['frio_din'], f['frio_ep'])} | {f['frio']:.0f} | "
                 f"{_desv(f['frio'], f['frio_ep'])} | {_hora_ep(f['hora_ep'])} / {f['hora_din']}:00 | "
                 f"{f['calor_ep']:.0f} | {f['calor']:.0f} | {_desv(f['calor'], f['calor_ep'])} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--energyplus")
    ap.add_argument("--salida", default=str(RAIZ / "validacion" / "resultados.md"))
    ap.add_argument("--trabajo", help="Directorio donde dejar los IDF y resultados")
    a = ap.parse_args(argv)
    exe = localizar_energyplus(a.energyplus)
    if not exe:
        print("No se encuentra EnergyPlus. Indícalo con --energyplus o la variable ENERGYPLUS.")
        return 2
    filas = comparar(exe, Path(a.trabajo) if a.trabajo else None)
    version = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    texto = (f"# Validación contra EnergyPlus\n\n{version}. Clima: Madrid (valores ilustrativos), "
             "día de diseño con modelo de cielo ASHRAE.\n\n" + tabla_markdown(filas))
    Path(a.salida).write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

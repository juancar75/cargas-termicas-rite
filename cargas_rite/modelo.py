"""Modelo de datos de entrada: un local climatizado descrito en YAML."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

ORIENTACIONES = {
    "N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180,
    "SO": 225, "SW": 225, "O": 270, "W": 270, "NO": 315, "NW": 315,
}

# Inercia del cerramiento → (factor de amortiguamiento f, desfase φ [h]).
# Valores orientativos del método de admitancias (CIBSE Guide A) para
# cerramientos ligeros, medios y pesados. Se pueden dar valores propios.
INERCIA = {
    "ligera": (0.8, 3.0),
    "media": (0.4, 7.0),
    "pesada": (0.2, 10.0),
}

TIPOS = {"muro", "cubierta", "ventana", "particion", "suelo"}


class ErrorDatos(ValueError):
    """Error en los datos de entrada."""


@dataclass
class Cerramiento:
    nombre: str
    tipo: str
    area: float
    U: float
    orientacion: Optional[float] = None          # grados desde el N
    absortividad: float = 0.7
    factor_amortiguamiento: float = 0.4
    desfase_h: float = 7.0
    g: float = 0.0                               # factor solar del vidrio
    fraccion_marco: float = 0.25
    factor_sombra: float = 1.0
    temperatura_adyacente_invierno: Optional[float] = None
    temperatura_adyacente_verano: Optional[float] = None

    @property
    def exterior(self) -> bool:
        return self.temperatura_adyacente_invierno is None

    @property
    def inclinacion(self) -> float:
        return 0.0 if self.tipo == "cubierta" else 90.0


@dataclass
class Clima:
    latitud: float
    longitud: float
    altitud: float
    diferencia_horaria: float          # hora oficial - UTC en el mes de cálculo
    mes_verano: int
    t_invierno: float                  # temperatura seca exterior de invierno
    t_verano: float                    # temperatura seca exterior de verano
    th_verano: float                   # bulbo húmedo coincidente
    oscilacion_diaria: float
    fuente: str = ""
    claridad: float = 1.0


@dataclass
class Interior:
    t_invierno: float = 21.0
    hr_invierno: float = 0.40
    t_verano: float = 25.0
    hr_verano: float = 0.50


@dataclass
class Local:
    nombre: str
    superficie: float
    altura: float
    personas: float
    sensible_persona: float
    latente_persona: float
    iluminacion_wm2: float
    equipos_wm2: float
    horario: tuple[int, int]

    @property
    def volumen(self) -> float:
        return self.superficie * self.altura


@dataclass
class Ventilacion:
    caudal_m3h: float
    categoria_ida: Optional[str]
    eficiencia_recuperador: float = 0.0
    infiltracion_h: float = 0.3


@dataclass
class Proyecto:
    titulo: str
    autor: str
    clima: Clima
    interior: Interior
    local: Local
    ventilacion: Ventilacion
    cerramientos: list[Cerramiento]
    dU_puentes_termicos: float = 0.10
    mayoracion: float = 0.0
    avisos: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
_DATOS = Path(__file__).parent / "datos"


def _tabla(nombre: str) -> dict:
    with open(_DATOS / nombre, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _orientacion(valor) -> float:
    if isinstance(valor, (int, float)):
        return float(valor) % 360
    clave = str(valor).strip().upper()
    if clave not in ORIENTACIONES:
        raise ErrorDatos(f"Orientación desconocida: {valor!r}")
    return float(ORIENTACIONES[clave])


def _req(d: dict, clave: str, ctx: str):
    if clave not in d or d[clave] is None:
        raise ErrorDatos(f"Falta '{clave}' en {ctx}")
    return d[clave]


def _cerramiento(d: dict) -> Cerramiento:
    nombre = _req(d, "nombre", "cerramiento")
    tipo = str(_req(d, "tipo", nombre)).lower()
    if tipo not in TIPOS:
        raise ErrorDatos(f"{nombre}: tipo '{tipo}' no válido ({', '.join(sorted(TIPOS))})")
    c = Cerramiento(nombre=nombre, tipo=tipo,
                    area=float(_req(d, "area", nombre)), U=float(_req(d, "U", nombre)))
    ady = d.get("temperatura_adyacente")
    if ady is not None:
        c.temperatura_adyacente_invierno = float(_req(ady, "invierno", nombre))
        c.temperatura_adyacente_verano = float(_req(ady, "verano", nombre))
    elif tipo in ("particion", "suelo"):
        raise ErrorDatos(f"{nombre}: un '{tipo}' necesita 'temperatura_adyacente'")
    if c.exterior:
        if tipo == "cubierta":
            c.orientacion = 0.0
        else:
            c.orientacion = _orientacion(_req(d, "orientacion", nombre))
    c.absortividad = float(d.get("absortividad", 0.7))
    inercia = d.get("inercia", "media")
    f, phi = INERCIA.get(str(inercia).lower(), INERCIA["media"])
    c.factor_amortiguamiento = float(d.get("factor_amortiguamiento", f))
    c.desfase_h = float(d.get("desfase_h", phi))
    if tipo == "ventana":
        c.g = float(_req(d, "g", nombre))
        c.fraccion_marco = float(d.get("fraccion_marco", 0.25))
        c.factor_sombra = float(d.get("factor_sombra", 1.0))
    if c.area <= 0 or c.U <= 0:
        raise ErrorDatos(f"{nombre}: área y U deben ser positivas")
    return c


def cargar(ruta: str | Path) -> Proyecto:
    with open(ruta, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return desde_dict(d)


def desde_dict(d: dict) -> Proyecto:
    avisos: list[str] = []
    p = d.get("proyecto", {})
    cl = _req(d, "clima", "raíz")
    inv = _req(cl, "invierno", "clima")
    ver = _req(cl, "verano", "clima")
    clima = Clima(
        latitud=float(_req(cl, "latitud", "clima")),
        longitud=float(cl.get("longitud", -3.7)),
        altitud=float(cl.get("altitud", 0.0)),
        diferencia_horaria=float(cl.get("diferencia_horaria", 2.0)),
        mes_verano=int(cl.get("mes_verano", 7)),
        t_invierno=float(_req(inv, "temperatura_seca", "clima.invierno")),
        t_verano=float(_req(ver, "temperatura_seca", "clima.verano")),
        th_verano=float(_req(ver, "temperatura_humeda_coincidente", "clima.verano")),
        oscilacion_diaria=float(_req(ver, "oscilacion_media_diaria", "clima.verano")),
        fuente=str(cl.get("fuente", "")),
        claridad=float(cl.get("claridad", 1.0)),
    )

    it = d.get("interior", {})
    interior = Interior(
        t_invierno=float(it.get("invierno", {}).get("temperatura", 21.0)),
        hr_invierno=float(it.get("invierno", {}).get("humedad_relativa", 0.40)),
        t_verano=float(it.get("verano", {}).get("temperatura", 25.0)),
        hr_verano=float(it.get("verano", {}).get("humedad_relativa", 0.50)),
    )
    if not 21 <= interior.t_invierno <= 23:
        avisos.append("Temperatura interior de invierno fuera de 21–23 °C (RITE IT 1.1.4.1.2).")
    if not 23 <= interior.t_verano <= 25:
        avisos.append("Temperatura interior de verano fuera de 23–25 °C (RITE IT 1.1.4.1.2).")

    lo = _req(d, "local", "raíz")
    actividades = _tabla("actividades.yaml")
    oc = lo.get("ocupacion", {})
    act = str(oc.get("actividad", "oficina")).lower()
    if act not in actividades:
        raise ErrorDatos(f"Actividad '{act}' no está en datos/actividades.yaml")
    sup = float(_req(lo, "superficie", "local"))
    if "personas" in oc:
        personas = float(oc["personas"])
    elif "m2_por_persona" in oc:
        personas = sup / float(oc["m2_por_persona"])
    else:
        raise ErrorDatos("local.ocupacion necesita 'personas' o 'm2_por_persona'")
    horario = lo.get("horario", [9, 21])
    local = Local(
        nombre=str(lo.get("nombre", "Local")),
        superficie=sup,
        altura=float(_req(lo, "altura", "local")),
        personas=personas,
        sensible_persona=float(oc.get("sensible_persona", actividades[act]["sensible"])),
        latente_persona=float(oc.get("latente_persona", actividades[act]["latente"])),
        iluminacion_wm2=float(lo.get("iluminacion", 0.0)),
        equipos_wm2=float(lo.get("equipos", 0.0)),
        horario=(int(horario[0]), int(horario[1])),
    )

    ve = d.get("ventilacion", {})
    ida = ve.get("categoria_ida")
    caudal = ve.get("caudal_m3h")
    if caudal is None:
        if ida is None:
            raise ErrorDatos("ventilacion: indica 'categoria_ida' o 'caudal_m3h'")
        tabla_ida = _tabla("ventilacion_ida.yaml")
        if ida not in tabla_ida:
            raise ErrorDatos(f"Categoría {ida} no válida (IDA1..IDA4)")
        caudal = tabla_ida[ida]["dm3_s_persona"] * 3.6 * personas
    ventilacion = Ventilacion(
        caudal_m3h=float(caudal),
        categoria_ida=ida,
        eficiencia_recuperador=float(ve.get("eficiencia_recuperador", 0.0)),
        infiltracion_h=float(ve.get("infiltracion_renovaciones_h", 0.3)),
    )
    if ventilacion.caudal_m3h > 1800 and ventilacion.eficiencia_recuperador == 0:
        avisos.append("Caudal de aire exterior > 0,5 m³/s: el RITE (IT 1.2.4.5.2) exige "
                      "recuperación de calor del aire de extracción.")

    cerr = [_cerramiento(c) for c in _req(d, "cerramientos", "raíz")]
    co = d.get("coeficientes", {})
    return Proyecto(
        titulo=str(p.get("titulo", "Cálculo de cargas")),
        autor=str(p.get("autor", "")),
        clima=clima, interior=interior, local=local, ventilacion=ventilacion,
        cerramientos=cerr,
        dU_puentes_termicos=float(co.get("puentes_termicos_dU", 0.10)),
        mayoracion=float(co.get("mayoracion", 0.0)),
        avisos=avisos,
    )

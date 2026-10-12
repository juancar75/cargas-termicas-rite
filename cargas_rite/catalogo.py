"""Catálogo de materiales, soluciones, vidrios y marcos del CTE.

Datos: Base de Datos de Materiales y Productos del CTE (la de HULC), convertida con
`herramientas/importar_catalogo_cte.py`. Los nombres son los oficiales del catálogo,
p. ej. "Enlucido de yeso 1000 < d < 1300" o "MW Lana mineral [0.031 W/[mK]]".
"""
from __future__ import annotations

import difflib
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

from .cerramientos import Capa

_RUTA = Path(__file__).parent / "datos" / "catalogo_cte.json"


class ErrorCatalogo(KeyError):
    def __str__(self):
        return self.args[0]


@lru_cache(maxsize=1)
def datos() -> dict:
    return json.loads(_RUTA.read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def _buscar(seccion: str, nombre: str) -> tuple[str, dict]:
    tabla = datos()[seccion]
    if nombre in tabla:
        return nombre, tabla[nombre]
    normal = {_norm(k): k for k in tabla}
    if _norm(nombre) in normal:
        k = normal[_norm(nombre)]
        return k, tabla[k]
    parecidos = difflib.get_close_matches(nombre, list(tabla), n=5, cutoff=0.45)
    contienen = [k for k in tabla if _norm(nombre) in _norm(k)][:5]
    sugerencias = list(dict.fromkeys(contienen + parecidos))[:6]
    texto = f"'{nombre}' no está en el catálogo CTE ({seccion})."
    if sugerencias:
        texto += " ¿Quizá: " + " | ".join(sugerencias) + "?"
    raise ErrorCatalogo(texto)


def material(nombre: str) -> tuple[str, dict]:
    return _buscar("materiales", nombre)


def solucion(nombre: str) -> tuple[str, dict]:
    return _buscar("soluciones", nombre)


def vidrio(nombre: str) -> tuple[str, dict]:
    return _buscar("vidrios", nombre)


def marco(nombre: str) -> tuple[str, dict]:
    return _buscar("marcos", nombre)


def capa(nombre_material: str, espesor: float | None) -> Capa:
    clave, m = material(nombre_material)
    if "resistencia" in m:
        return Capa(clave, espesor or 0.0, 1.0, densidad=0.0, resistencia=m["resistencia"])
    if espesor is None or espesor <= 0:
        raise ErrorCatalogo(f"La capa '{clave}' necesita 'espesor' (m)")
    return Capa(clave, espesor, m["conductividad"], m["densidad"], m["calor_especifico"])


def capas_solucion(nombre: str) -> tuple[str, list[Capa]]:
    clave, s = solucion(nombre)
    return clave, [capa(c["material"], c["espesor"]) for c in s["capas"]]


def buscar(texto: str, seccion: str = "materiales", limite: int = 20) -> list[str]:
    """Nombres del catálogo que contienen todas las palabras de 'texto'."""
    palabras = _norm(texto).split()
    tabla = datos()[seccion]

    def texto_de(k):
        v = tabla[k]
        return _norm(" ".join([k, v.get("grupo", ""), v.get("descripcion", "")]))
    return [k for k in tabla if all(p in texto_de(k) for p in palabras)][:limite]


def ventana(nombre_vidrio: str, nombre_marco: str, fraccion_marco: float) -> dict:
    """U y g de un hueco a partir de vidrio y marco del catálogo.

    U_H = (1 − FM)·U_v + FM·U_m  (DA DB-HE/1, transmitancia del hueco)
    g   = g⊥ del vidrio (la parte del marco se trata aparte con fraccion_marco)
    """
    kv, v = vidrio(nombre_vidrio)
    km, m = marco(nombre_marco)
    if not 0 <= fraccion_marco < 1:
        raise ErrorCatalogo("fraccion_marco debe estar entre 0 y 1")
    U = (1 - fraccion_marco) * v["U"] + fraccion_marco * m["U"]
    return {"vidrio": kv, "marco": km, "U": U, "g": v["g"], "U_vidrio": v["U"], "U_marco": m["U"]}

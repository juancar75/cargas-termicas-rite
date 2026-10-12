"""Convierte la base de datos de materiales del CTE (BDCatalogo.bdc de HULC) a JSON.

Origen del archivo: Base de Datos de Materiales y Productos del Código Técnico de la
Edificación, distribuida por el Ministerio con la Herramienta Unificada LIDER-CALENER
(HULC). Se toma la copia en UTF-8 del repositorio libre
https://github.com/pachi/cteenergymodel (MIT, Rafael Villar Burke, IETcc-CSIC):
    hulc/src/ctehexml/BDCatalogo.bdc.utf8.gz

Uso:
    python herramientas/importar_catalogo_cte.py BDCatalogo.bdc.utf8.gz \
        cargas_rite/datos/catalogo_cte.json

Convenios de conversión:
  * Materiales tipo PROPERTIES: conductividad λ [W/mK], densidad ρ [kg/m³],
    calor específico c [J/kgK], factor de resistencia al vapor μ.
  * Materiales tipo RESISTANCE (cámaras de aire): resistencia R [m²K/W].
  * Vidrios (GLASS-TYPE): U = GLASS-CONDUCTANCE [W/m²K];
    g⊥ = 0,85 · SHADING-COEF (convenio de HULC: SC = g / 0,85).
  * Marcos (NAME-FRAME): U [W/m²K] y absortividad.
  * Soluciones (LAYERS): capas de EXTERIOR a INTERIOR en el archivo original; aquí
    se guardan de INTERIOR a EXTERIOR, que es el orden de cargas_rite.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

CABECERA = re.compile(r'^\s*"(?P<nombre>[^"]+)"\s*=\s*(?P<tipo>[A-Z-]+)\s*$')
CAMPO = re.compile(r'^\s*(?P<clave>[A-Z_-]+)\s*=\s*(?P<valor>.*?)\s*$')


def _num(v: str) -> float:
    return float(v.replace(",", "."))


def _lista(v: str) -> list[str]:
    v = v.strip()
    if v.startswith("("):
        v = v[1:v.rindex(")")]
    partes = re.findall(r'"([^"]*)"|([^,\s][^,]*)', v)
    return [(a if a else b).strip() for a, b in partes]


def _texto(v: str) -> str:
    return v.strip().strip('"').strip()


def bloques(lineas):
    actual = None
    for linea in lineas:
        if linea.lstrip().startswith("$"):
            continue
        m = CABECERA.match(linea)
        if m:
            actual = {"nombre": m["nombre"].strip(), "tipo_objeto": m["tipo"], "campos": {}}
            continue
        if actual is None:
            continue
        if linea.strip() == "..":
            yield actual
            actual = None
            continue
        c = CAMPO.match(linea)
        if c:
            actual["campos"][c["clave"]] = c["valor"]


def convertir(texto: str) -> dict:
    materiales, vidrios, marcos, soluciones = {}, {}, {}, {}
    for b in bloques(texto.splitlines()):
        f, n, t = b["campos"], b["nombre"], b["tipo_objeto"]
        if t == "MATERIAL":
            grupo = _texto(f.get("GROUP", ""))
            tipo = f.get("TYPE", "").strip()
            if tipo == "RESISTANCE":
                materiales[n] = {"grupo": grupo, "resistencia": _num(f["RESISTANCE"])}
            elif tipo == "PROPERTIES":
                m = {"grupo": grupo, "conductividad": _num(f["CONDUCTIVITY"]),
                     "densidad": _num(f["DENSITY"])}
                if "SPECIFIC-HEAT" in f:
                    m["calor_especifico"] = _num(f["SPECIFIC-HEAT"])
                else:
                    # Materiales "rehab2011" sin c: se supone 1000 J/kgK (valor típico de
                    # fábricas y pétreos) y se marca para que el usuario lo sepa.
                    m["calor_especifico"] = 1000.0
                    m["calor_especifico_supuesto"] = True
                if "VAPOUR-DIFFUSIVITY-FACTOR" in f:
                    m["mu"] = _num(f["VAPOUR-DIFFUSIVITY-FACTOR"])
                desc = _texto(f.get("NAME", n))
                if desc and desc != n:
                    m["descripcion"] = desc
                materiales[n] = m
        elif t == "GLASS-TYPE":
            vidrios[n] = {"grupo": _texto(f.get("GROUP", "")),
                          "U": _num(f["GLASS-CONDUCTANCE"]),
                          "g": round(0.85 * _num(f["SHADING-COEF"]), 4)}
        elif t == "NAME-FRAME":
            marcos[n] = {"grupo": _texto(f.get("GROUP", "")), "U": _num(f["FRAME-CONDUCT"]),
                         "absortividad": _num(f.get("FRAME-ABS", "0.7"))}
        elif t == "LAYERS":
            mats = _lista(f.get("MATERIAL", "()"))
            esps = [_num(x) for x in _lista(f.get("THICKNESS", "()"))]
            if len(mats) != len(esps) or not mats:
                continue
            capas = [{"material": m, "espesor": e} for m, e in zip(mats, esps)]
            soluciones[n] = {"grupo": _texto(f.get("GROUP", "")), "capas": list(reversed(capas))}
    # descartar soluciones con materiales desconocidos
    soluciones = {k: v for k, v in soluciones.items()
                  if all(c["material"] in materiales for c in v["capas"])}
    return {
        "fuente": "Base de Datos de Materiales y Productos del CTE (BDCatalogo.bdc, HULC). "
                  "Copia UTF-8 de github.com/pachi/cteenergymodel (MIT).",
        "materiales": dict(sorted(materiales.items())),
        "vidrios": dict(sorted(vidrios.items())),
        "marcos": dict(sorted(marcos.items())),
        "soluciones": dict(sorted(soluciones.items())),
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    origen, destino = Path(argv[0]), Path(argv[1])
    abrir = gzip.open if origen.suffix == ".gz" else open
    with abrir(origen, "rt", encoding="utf-8", errors="replace") as fh:
        datos = convertir(fh.read())
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: len(v) for k, v in datos.items() if isinstance(v, dict)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

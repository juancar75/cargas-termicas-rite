"""Buscar en el catálogo CTE.

    python -m cargas_rite.buscar lana mineral
    python -m cargas_rite.buscar --soluciones fachada ladrillo
    python -m cargas_rite.buscar --vidrios doble bajo emisivo vertical
    python -m cargas_rite.buscar --marcos pvc
"""
from __future__ import annotations

import argparse

from . import catalogo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cargas-rite-buscar", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    for s in ("soluciones", "vidrios", "marcos"):
        g.add_argument(f"--{s}", action="store_const", const=s, dest="seccion")
    ap.add_argument("texto", nargs="+")
    a = ap.parse_args(argv)
    seccion = a.seccion or "materiales"
    tabla = catalogo.datos()[seccion]
    nombres = catalogo.buscar(" ".join(a.texto), seccion, limite=50)
    if not nombres:
        print("Sin resultados.")
        return 1
    for n in nombres:
        d = tabla[n]
        if seccion == "materiales":
            if "resistencia" in d:
                info = f"R={d['resistencia']} m²K/W"
            else:
                info = (f"λ={d['conductividad']} ρ={d['densidad']:g} c={d['calor_especifico']:g}"
                        + (" (c supuesto)" if d.get("calor_especifico_supuesto") else ""))
        elif seccion == "soluciones":
            info = f"{d['grupo']}, {len(d['capas'])} capas"
        else:
            info = f"U={d['U']}" + (f" g={d['g']}" if "g" in d else "")
        print(f"{n}\n    {info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

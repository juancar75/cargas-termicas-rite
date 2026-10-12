"""Línea de comandos: cargas-rite proyecto.yaml [-o informe.md] [--csv horario.csv]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import calcular_invierno, calcular_refrigeracion, cargar
from .informe import csv_horario, markdown
from .modelo import ErrorDatos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="cargas-rite",
        description="Justificación de cargas térmicas de invierno y verano de un local climatizado (RITE).")
    ap.add_argument("proyecto", help="Archivo YAML con los datos del local")
    ap.add_argument("-o", "--salida", help="Informe Markdown (por defecto, junto al YAML)")
    ap.add_argument("--csv", help="Exportar la evolución horaria de verano a CSV")
    ap.add_argument("--metodo", choices=["dinamico", "simplificado"],
                    help="Método de refrigeración (por defecto, el del YAML o 'dinamico')")
    args = ap.parse_args(argv)

    try:
        p = cargar(args.proyecto)
        if args.metodo:
            p.metodo_verano = args.metodo
    except (ErrorDatos, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    inv = calcular_invierno(p)
    ver = calcular_refrigeracion(p)

    salida = Path(args.salida) if args.salida else Path(args.proyecto).with_suffix(".md")
    salida.write_text(markdown(p, inv, ver), encoding="utf-8")
    if args.csv:
        csv_horario(ver, args.csv)

    print(f"Refrigeración: {ver.total / 1000:.2f} kW (sensible {ver.sensible / 1000:.2f}, "
          f"latente {ver.latente / 1000:.2f}) a las {ver.punta.hora}:00 h")
    print(f"Calefacción:   {inv.total / 1000:.2f} kW")
    for av in p.avisos:
        print(f"Aviso: {av}")
    print(f"Informe: {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

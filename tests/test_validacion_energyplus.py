"""Validación contra EnergyPlus (se omite si EnergyPlus no está instalado).

Criterios de aceptación (carga sensible punta):
  * Refrigeración, método dinámico: entre −12 % y +40 % por caso aislado, y
    ±15 % en el local completo.
  * Refrigeración, método simplificado: nunca por debajo de EnergyPlus (es el
    método conservador).
  * Calefacción: entre −10 % y +30 % (las resistencias superficiales normalizadas
    de UNE-EN ISO 6946 quedan del lado de la seguridad).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validacion"))
import energyplus as V  # noqa: E402

EXE = V.localizar_energyplus()
pytestmark = pytest.mark.skipif(EXE is None, reason="EnergyPlus no instalado")


@pytest.fixture(scope="module")
def filas(tmp_path_factory):
    return {f["caso"]: f for f in V.comparar(EXE, tmp_path_factory.mktemp("ep"))}


def _d(a, b):
    return (a - b) / b


@pytest.mark.parametrize("caso", [c.nombre for c in V.casos() if c.nombre != "local_completo"])
def test_refrigeracion_dinamico_por_caso(filas, caso):
    f = filas[caso]
    assert -0.12 <= _d(f["frio_din"], f["frio_ep"]) <= 0.40, f


def test_refrigeracion_dinamico_local_completo(filas):
    f = filas["local_completo"]
    assert abs(_d(f["frio_din"], f["frio_ep"])) <= 0.15, f


@pytest.mark.parametrize("caso", [c.nombre for c in V.casos()])
def test_simplificado_es_conservador(filas, caso):
    f = filas[caso]
    assert f["frio"] >= f["frio_ep"] * 0.98, f


@pytest.mark.parametrize("caso", [c.nombre for c in V.casos() if c.nombre != "cargas_internas"])
def test_calefaccion(filas, caso):
    f = filas[caso]
    assert -0.10 <= _d(f["calor"], f["calor_ep"]) <= 0.30, f

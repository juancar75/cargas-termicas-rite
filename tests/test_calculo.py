import math
from pathlib import Path

import pytest

from cargas_rite import calcular_invierno, calcular_verano, cargar, desde_dict
from cargas_rite.informe import markdown
from cargas_rite.modelo import ErrorDatos
from cargas_rite.verano import fraccion_oscilacion

EJEMPLO = Path(__file__).parents[1] / "ejemplos" / "local_comercial.yaml"


def caja(**cambios):
    """Local mínimo: un muro sur y una ventana sur."""
    d = {
        "clima": {"latitud": 40.0, "longitud": 0.0, "altitud": 0, "diferencia_horaria": 0, "huso": 0,
                  "invierno": {"temperatura_seca": 0.0},
                  "verano": {"temperatura_seca": 35.0, "temperatura_humeda_coincidente": 22.0,
                             "oscilacion_media_diaria": 10.0}},
        "local": {"superficie": 20.0, "altura": 3.0,
                  "ocupacion": {"actividad": "oficina", "personas": 2}, "horario": [8, 20]},
        "ventilacion": {"caudal_m3h": 100, "infiltracion_renovaciones_h": 0.0},
        "cerramientos": [
            {"nombre": "Muro", "tipo": "muro", "orientacion": "S", "area": 10.0, "U": 0.5},
            {"nombre": "Ventana", "tipo": "ventana", "orientacion": "S", "area": 2.0, "U": 3.0,
             "g": 0.5},
        ],
        "coeficientes": {"puentes_termicos_dU": 0.0},
    }
    d.update(cambios)
    return desde_dict(d)


# --- perfil de temperatura -----------------------------------------------------
def test_perfil_oscilacion():
    assert fraccion_oscilacion(15) == 0.0
    assert fraccion_oscilacion(5) == 1.0


# --- invierno -----------------------------------------------------------------
def test_invierno_a_mano():
    p = caja()
    r = calcular_invierno(p)
    # transmisión: 0,5·10·21 + 3·2·21 = 105 + 126
    assert r.transmision["Muro"] == pytest.approx(105)
    assert r.transmision["Ventana"] == pytest.approx(126)
    # aire a 0 °C y nivel del mar: ρ = 1,292 kg/m³ → ρc = 1,292·1006/3600 = 0,361 W·h/(m³·K)
    assert r.coef_aire == pytest.approx(0.361, abs=0.002)
    assert r.ventilacion == pytest.approx(r.coef_aire * 100 * 21)
    assert r.total == pytest.approx(231 + r.ventilacion)


def test_recuperador_reduce_ventilacion():
    p = caja(ventilacion={"caudal_m3h": 100, "eficiencia_recuperador": 0.7,
                          "infiltracion_renovaciones_h": 0})
    r = calcular_invierno(p)
    assert r.ventilacion == pytest.approx(r.coef_aire * 100 * 0.3 * 21)


# --- verano -------------------------------------------------------------------
def test_verano_punta_en_horario_y_positiva():
    r = calcular_verano(caja())
    assert 8 <= r.punta.hora < 20
    assert r.total > 0
    assert r.punta.componentes["Ocupantes"] == pytest.approx(2 * 70)


def test_mayoracion():
    base = calcular_verano(caja()).total
    con = calcular_verano(caja(coeficientes={"mayoracion": 0.1,
                                             "puentes_termicos_dU": 0})).total
    assert con == pytest.approx(base * 1.1)


def test_ida_calcula_caudal():
    p = caja(ventilacion={"categoria_ida": "IDA2"})
    assert p.ventilacion.caudal_m3h == pytest.approx(12.5 * 3.6 * 2)


def test_aviso_recuperador():
    p = caja(ventilacion={"caudal_m3h": 2000})
    assert any("IT 1.2.4.5.2" in a for a in p.avisos)


def test_particion_sin_temperatura_falla():
    with pytest.raises(ErrorDatos):
        caja(cerramientos=[{"nombre": "X", "tipo": "particion", "area": 1, "U": 1}])


# --- ejemplo completo ---------------------------------------------------------
def test_ejemplo_completo():
    p = cargar(EJEMPLO)
    inv, ver = calcular_invierno(p), calcular_verano(p)
    txt = markdown(p, inv, ver)
    assert "Carga de refrigeración" in txt
    assert 5_000 < ver.total < 20_000
    assert 3_000 < inv.total < 15_000
    assert not math.isnan(ver.total)

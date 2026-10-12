import math
from pathlib import Path

import pytest

from cargas_rite import calcular_invierno, calcular_verano, cargar, desde_dict
from cargas_rite.informe import markdown
from cargas_rite.modelo import ErrorDatos
from cargas_rite.psicrometria import (humedad_especifica_desde_bulbo_humedo,
                                      humedad_especifica_desde_hr, presion_atmosferica)
from cargas_rite.solar import irradiancia
from cargas_rite.verano import fraccion_oscilacion

EJEMPLO = Path(__file__).parents[1] / "ejemplos" / "local_comercial.yaml"


def caja(**cambios):
    """Local mínimo: un muro sur y una ventana sur."""
    d = {
        "clima": {"latitud": 40.0, "longitud": 0.0, "altitud": 0, "diferencia_horaria": 0,
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


# --- psicrometría -------------------------------------------------------------
def test_presion_nivel_del_mar():
    assert presion_atmosferica(0) == pytest.approx(101.325)


def test_humedad_25C_50():
    # ASHRAE: w ≈ 9,9 g/kg a 25 °C y 50 % HR al nivel del mar
    assert humedad_especifica_desde_hr(25, 0.5, 101.325) == pytest.approx(9.9, abs=0.15)


def test_bulbo_humedo_saturado():
    p = 101.325
    assert humedad_especifica_desde_bulbo_humedo(20, 20, p) == pytest.approx(
        humedad_especifica_desde_hr(20, 1.0, p), rel=1e-3)


# --- solar ---------------------------------------------------------------------
def test_noche_sin_radiacion():
    assert irradiancia(40, 7, 2, 180) == 0.0


def test_simetria_este_oeste():
    assert irradiancia(40, 7, 9, 90) == pytest.approx(irradiancia(40, 7, 15, 270), rel=1e-6)


def test_horizontal_mediodia_julio():
    assert 850 < irradiancia(40, 7, 12, 0, 0) < 1000


def test_perfil_oscilacion():
    assert fraccion_oscilacion(15) == 0.0
    assert fraccion_oscilacion(5) == 1.0


# --- invierno -----------------------------------------------------------------
def test_invierno_a_mano():
    p = caja()
    r = calcular_invierno(p)
    # transmisión: 0,5·10·21 + 3·2·21 = 105 + 126 ; ventilación 0,34·100·21 = 714
    assert r.transmision["Muro"] == pytest.approx(105)
    assert r.transmision["Ventana"] == pytest.approx(126)
    assert r.ventilacion == pytest.approx(714)
    assert r.total == pytest.approx(945)


def test_recuperador_reduce_ventilacion():
    p = caja(ventilacion={"caudal_m3h": 100, "eficiencia_recuperador": 0.7,
                          "infiltracion_renovaciones_h": 0})
    assert calcular_invierno(p).ventilacion == pytest.approx(0.34 * 100 * 0.3 * 21)


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

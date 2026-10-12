"""Pruebas de psicrometría y radiación solar contra valores de referencia publicados."""
import math

import numpy as np
import pytest

from cargas_rite import solar
from cargas_rite.psicrometria import (coeficientes_aire, entalpia, humedad_especifica_desde_bulbo_humedo,
                                      humedad_especifica_desde_hr, humedad_relativa,
                                      presion_atmosferica)

P0 = 101.325


# --- Psicrometría: ASHRAE Handbook — Fundamentals (2017), cap. 1 ----------------
@pytest.mark.parametrize("z, p", [(0, 101.325), (500, 95.461), (1000, 89.875),
                                  (1500, 84.556), (2000, 79.495)])
def test_presion_tabla1_ashrae(z, p):
    """Tabla 1 de ASHRAE (atmósfera estándar)."""
    assert presion_atmosferica(z) == pytest.approx(p, abs=0.01)


@pytest.mark.parametrize("t, ws", [(0, 3.789), (10, 7.661), (20, 14.758),
                                   (25, 20.170), (30, 27.329), (40, 49.141)])
def test_humedad_saturacion_tabla2_ashrae(t, ws):
    """Humedad específica de saturación, tabla 2 de ASHRAE (g/kg, 101,325 kPa)."""
    assert humedad_especifica_desde_hr(t, 1.0, P0) == pytest.approx(ws, rel=0.005)


def test_ejemplo_ashrae_bulbo_humedo():
    """ASHRAE Fundamentals, cap. 1, ejemplo 2: 40 °C BS, 20 °C BH, 101,325 kPa → W = 6,5 g/kg."""
    assert humedad_especifica_desde_bulbo_humedo(40, 20, P0) == pytest.approx(6.5, abs=0.1)


def test_ida_y_vuelta_hr():
    w = humedad_especifica_desde_hr(25, 0.5, 93.5)
    assert humedad_relativa(25, w, 93.5) == pytest.approx(0.5, abs=1e-4)


def test_entalpia_25C_50():
    # h ≈ 1,006·t + W·(2501 + 1,86·t) ≈ 50,3 kJ/kg
    w = humedad_especifica_desde_hr(25, 0.5, P0)
    assert entalpia(25, w, P0) == pytest.approx(1.006 * 25 + w / 1000 * (2501 + 1.86 * 25), abs=0.3)


def test_bulbo_humedo_mayor_que_seco_falla():
    with pytest.raises(ValueError):
        humedad_especifica_desde_bulbo_humedo(20, 25, P0)


# --- Solar -------------------------------------------------------------------------
MADRID = dict(latitud=40.41, longitud=-3.70, altitud=667, diferencia_horaria=2)


def _perfil(azimut, inclinacion=90, mes=7, modelo="ashrae"):
    return solar.perfil_irradiancia(MADRID["latitud"], MADRID["longitud"], MADRID["altitud"],
                                    mes, MADRID["diferencia_horaria"], azimut, inclinacion,
                                    modelo=modelo)


def test_altura_solar_maxima_julio():
    """Altura solar máxima el 21 de julio: 90 − φ + δ, con δ ≈ 20,4° (+ refracción)."""
    assert solar.altura_solar_max(40.41, -3.70, 7, 2) == pytest.approx(90 - 40.41 + 20.4, abs=0.3)


def test_mediodia_solar_madrid():
    """Mediodía solar en Madrid en julio ≈ 14:20 hora oficial (long. −3,7°, ec. del tiempo −6 min)."""
    h, v = _perfil(0, 0)
    assert h[np.argmax(v)] == pytest.approx(14 + 20 / 60, abs=0.1)


def test_noche_sin_radiacion():
    h, v = _perfil(180)
    assert solar.interpolar(h, v, 3.0) == 0.0


def test_simetria_este_oeste():
    h, v_hor = _perfil(0, 0)
    t0 = h[np.argmax(v_hor)]
    he, ve = _perfil(90)
    ho, vo = _perfil(270)
    for dt in (2, 3, 4):
        assert solar.interpolar(he, ve, t0 - dt) == pytest.approx(
            solar.interpolar(ho, vo, t0 + dt), rel=0.03)


def test_modelo_ashrae_coincide_con_formula():
    """En horizontal al mediodía: I = I_DN·(sen β + C), I_DN = A·exp(−B/sen β)."""
    A, B, C = solar.CONSTANTES_ASHRAE[7]
    beta = math.radians(solar.altura_solar_max(40.41, -3.70, 7, 2))
    esperado = A * math.exp(-B / math.sin(beta)) * (math.sin(beta) + C)
    h, v = _perfil(0, 0)
    assert v.max() == pytest.approx(esperado, rel=0.01)


def test_fachada_sur_menor_en_verano_que_en_invierno():
    _, v_jul = _perfil(180, mes=7)
    _, v_ene = _perfil(180, mes=1)
    assert v_ene.max() > v_jul.max()


@pytest.mark.parametrize("modelo", ["ashrae", "ineichen"])
def test_horizontal_julio_rango_fisico(modelo):
    _, v = _perfil(0, 0, modelo=modelo)
    assert 850 < v.max() < 1050


def test_modelos_parecidos():
    _, a = _perfil(0, 0, modelo="ashrae")
    _, i = _perfil(0, 0, modelo="ineichen")
    assert a.max() == pytest.approx(i.max(), rel=0.10)


def test_coeficientes_aire_nivel_del_mar():
    """A 20 °C y nivel del mar se recuperan los valores clásicos 0,34 y 0,83."""
    s, l = coeficientes_aire(20, 7.3, P0)
    assert s == pytest.approx(0.34, abs=0.005)
    assert l == pytest.approx(0.83, abs=0.01)


def test_coeficientes_aire_altitud():
    """En Madrid (667 m) a 36 °C el aire es ≈ 13 % menos denso que a 20 °C en la costa."""
    s, _ = coeficientes_aire(36, 11, presion_atmosferica(667))
    assert s == pytest.approx(0.295, abs=0.005)

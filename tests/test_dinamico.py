"""Pruebas físicas del modelo dinámico del local."""
import numpy as np
import pytest

from cargas_rite import calcular_verano, desde_dict
from cargas_rite.dinamico import ModeloLocal, calcular_verano_dinamico

HORMIGON = {"nombre": "hormigón", "espesor": 0.2, "conductividad": 1.65,
            "densidad": 2150, "calor_especifico": 1000}
SIN_MASA = {"nombre": "sin masa", "espesor": 0.0, "conductividad": 1.0, "resistencia": 0.05}


def proyecto(cerramientos, masas, **local):
    base_local = {"superficie": 30.0, "altura": 3.0, "horario": [10, 18],
                  "ocupacion": {"actividad": "oficina", "personas": 0}}
    base_local.update(local)
    return desde_dict({
        "clima": {"latitud": 40.4, "longitud": -3.7, "altitud": 0, "diferencia_horaria": 2,
                  "invierno": {"temperatura_seca": 0},
                  "verano": {"temperatura_seca": 35, "temperatura_humeda_coincidente": 22,
                             "oscilacion_media_diaria": 12}},
        "local": base_local,
        "ventilacion": {"caudal_m3h": 0, "infiltracion_renovaciones_h": 0},
        "cerramientos": cerramientos or [{"nombre": "nulo", "tipo": "particion", "area": 1e-6,
                                          "U": 1e-6, "temperatura_adyacente": {"invierno": 21, "verano": 25}}],
        "masas_interiores": masas,
        "coeficientes": {"puentes_termicos_dU": 0},
    })


def caja_adiabatica(capas, **local):
    masas = [{"nombre": "suelo", "area": 30, "capas": capas, "posicion": "suelo"},
             {"nombre": "techo", "area": 30, "capas": capas, "posicion": "techo"},
             {"nombre": "paredes", "area": 66, "capas": capas, "posicion": "vertical"}]
    return proyecto([], masas, **local)


def test_conservacion_energia_ganancias_internas():
    """En régimen periódico y caja adiabática, la carga media diaria = ganancia media diaria."""
    p = caja_adiabatica([HORMIGON], iluminacion=10, equipos=10,
                        ocupacion={"actividad": "oficina", "personas": 3})
    r = calcular_verano_dinamico(p)
    carga_media = np.mean([h.sensible for h in r.horas])
    horas_ocupadas = 8
    ganancia_media = (3 * 70 + 20 * 30) * horas_ocupadas / 24
    assert carga_media == pytest.approx(ganancia_media, rel=0.02)


def test_masa_reduce_y_retrasa_la_punta():
    gan = dict(iluminacion=10, equipos=10, ocupacion={"actividad": "oficina", "personas": 3})
    pesada = calcular_verano_dinamico(caja_adiabatica([HORMIGON], **gan))
    instantanea = 3 * 70 + 20 * 30
    assert pesada.punta.sensible < instantanea
    assert pesada.punta.hora >= 17          # al final del periodo de ocupación


def test_sin_masa_la_carga_es_instantanea():
    gan = dict(iluminacion=10, equipos=10, ocupacion={"actividad": "oficina", "personas": 3})
    r = calcular_verano_dinamico(caja_adiabatica([SIN_MASA], **gan))
    assert r.punta.sensible == pytest.approx(3 * 70 + 20 * 30, rel=0.01)


def test_superposicion():
    """La suma de las respuestas por componente es la respuesta a todo a la vez."""
    p = proyecto([{"nombre": "ventana", "tipo": "ventana", "orientacion": "O", "area": 3,
                   "U": 2.7, "g": 0.6},
                  {"nombre": "muro", "tipo": "muro", "orientacion": "O", "area": 9,
                   "capas": [HORMIGON]}],
                 [{"nombre": "suelo", "area": 30, "capas": [HORMIGON], "posicion": "suelo"}],
                 iluminacion=10)
    m = ModeloLocal(p)
    excit = m._excitaciones()
    por_partes = sum(m._respuesta(f) for _, f in excit)

    def todas(h):
        b_tot, d_tot = 0, 0.0
        for _, f in excit:
            b, d = f(h)
            b_tot = b_tot + b
            d_tot += d
        return b_tot, d_tot
    assert np.allclose(por_partes, m._respuesta(todas), rtol=1e-6, atol=1e-6)


def test_ventana_sin_masa_coincide_con_metodo_simplificado():
    """Sin masa interior, la ganancia solar de la ventana es la instantánea del método simplificado."""
    ventana = {"nombre": "ventana", "tipo": "ventana", "orientacion": "O", "area": 4,
               "U": 2.7, "g": 0.6}
    masas = [{"nombre": n, "area": a, "capas": [SIN_MASA], "posicion": pos}
             for n, a, pos in (("suelo", 30, "suelo"), ("techo", 30, "techo"), ("paredes", 62, "vertical"))]
    p = proyecto([ventana], masas)
    din = calcular_verano_dinamico(p)
    simp = calcular_verano(p)
    k = "ventana (solar)"
    for h in (16, 18, 20):
        assert din.horas[h - 1].componentes[k] == pytest.approx(
            simp.horas[h - 1].componentes[k], rel=0.03, abs=5)


def test_masas_por_defecto_generan_aviso():
    p = proyecto([], [], iluminacion=5)
    calcular_verano_dinamico(p)
    assert any("supuesto" in a for a in p.avisos)


def test_particion_horizontal_no_duplica_techo():
    """Un forjado a otro local declarado como techo no debe generar un techo supuesto."""
    forjado = {"nombre": "forjado a viviendas", "tipo": "particion", "posicion": "techo",
               "area": 30, "capas": [HORMIGON],
               "temperatura_adyacente": {"invierno": 20, "verano": 26}}
    p = proyecto([forjado], [{"nombre": "suelo", "area": 30, "capas": [HORMIGON],
                              "posicion": "suelo"}], iluminacion=5)
    m = ModeloLocal(p)
    assert m.supuestas == []
    assert p.cerramientos[0].posicion == "techo"


def test_no_descuenta_perdidas_hacia_locales_frios():
    solera = {"nombre": "solera", "tipo": "suelo", "area": 30, "capas": [HORMIGON],
              "temperatura_adyacente": {"invierno": 12, "verano": 18}}
    p = proyecto([solera], [], iluminacion=10)
    r = calcular_verano_dinamico(p)
    assert all(h.componentes["solera"] == pytest.approx(0, abs=1e-6) for h in r.horas)
    p.descontar_perdidas_verano = True
    r2 = calcular_verano_dinamico(p)
    assert all(h.componentes["solera"] < 0 for h in r2.horas)

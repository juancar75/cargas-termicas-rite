"""Catálogo CTE, soleras (ISO 13370) y espacios no acondicionados (ISO 13789)."""
import math

import pytest

from cargas_rite import catalogo, desde_dict, terreno  # noqa: F401
from cargas_rite.cerramientos import propiedades
from cargas_rite.modelo import ErrorDatos


# --- catálogo ----------------------------------------------------------------------
def test_catalogo_tamano():
    d = catalogo.datos()
    assert len(d["materiales"]) > 700
    assert len(d["soluciones"]) > 400
    assert len(d["vidrios"]) > 250
    assert len(d["marcos"]) >= 10


def test_material_yeso():
    _, m = catalogo.material("Enlucido de yeso 1000 < d < 1300")
    assert (m["conductividad"], m["densidad"], m["calor_especifico"]) == (0.57, 1150.0, 1000.0)


def test_busqueda_sin_tildes_ni_mayusculas():
    clave, _ = catalogo.material("enlucido de YESO 1000 < d < 1300")
    assert clave == "Enlucido de yeso 1000 < d < 1300"


def test_error_con_sugerencias():
    with pytest.raises(catalogo.ErrorCatalogo) as e:
        catalogo.material("lana mineral")
    assert "MW Lana mineral" in str(e.value)


def test_camara_de_aire_es_resistencia():
    c = catalogo.capa("Cámara de aire sin ventilar vertical 2 cm", None)
    assert c.R == pytest.approx(0.17)


def test_solucion_fachada_por_defecto_D():
    """U calculada a mano con los datos del catálogo (capas de interior a exterior)."""
    _, capas = catalogo.capas_solucion("Fachada por defecto D")
    r = 0.13 + 0.04 + sum(c.R for c in capas)
    assert propiedades(capas).U == pytest.approx(1 / r)
    assert capas[0].nombre.startswith("Enlucido")   # interior primero


def test_ventana_de_catalogo():
    v = catalogo.ventana("VER_DB1_4-6-4", "VER_PVC dos cámaras", 0.25)
    assert v["U"] == pytest.approx(0.75 * 2.7 + 0.25 * 2.2)
    assert v["g"] == pytest.approx(0.70, abs=0.005)


# --- terreno (ISO 13370) --------------------------------------------------------------
def test_solera_formula_11():
    """Solera sin aislar: B' = 10 m, d_t = w + λ(Rsi+Rf+Rse)."""
    r = terreno.u_solera(100, 20, 0.05)
    d_t = 0.30 + 2.0 * (0.17 + 0.05 + 0.04)
    esperado = 2 * 2.0 / (math.pi * 10 + d_t) * math.log(1 + math.pi * 10 / d_t)
    assert r["d_t"] == pytest.approx(d_t)
    assert r["U"] == pytest.approx(esperado)


def test_solera_continuidad_entre_formulas():
    """Las ecuaciones (11) y (12) casi coinciden en d_t = B' (diferencia < 5 %)."""
    B = 4.0
    u11 = 2 * 2.0 / (math.pi * B + B) * math.log(1 + math.pi * B / B)
    u12 = 2.0 / (0.457 * B + B)
    assert u11 == pytest.approx(u12, rel=0.05)


def test_solera_mas_aislamiento_menos_U():
    us = [terreno.u_solera(100, 40, r)["U"] for r in (0.0, 0.5, 1.0, 2.0, 4.0)]
    assert all(a > b for a, b in zip(us, us[1:]))


def test_solera_grande_menos_U_que_pequena():
    assert terreno.u_solera(400, 40, 0.5)["U"] < terreno.u_solera(25, 20, 0.5)["U"]


def test_aislamiento_perimetral_reduce_U():
    sin = terreno.u_solera(100, 40, 0.1)
    con = terreno.u_solera(100, 40, 0.1, aislamiento_perimetral_R=1.5, aislamiento_perimetral_ancho=1.0)
    assert con["psi_ge"] < 0
    assert con["U"] < sin["U"]


# --- espacios no acondicionados (ISO 13789) -----------------------------------------
def test_factor_b():
    assert terreno.factor_b(10, 30) == pytest.approx(0.75)
    assert terreno.temperatura_no_acondicionado(20, 0, 0.75) == pytest.approx(5)


# --- integración en la entrada YAML -------------------------------------------------
def base(cerramientos, **clima_extra):
    clima = {"latitud": 40.4, "longitud": -3.7, "altitud": 667,
             "invierno": {"temperatura_seca": -3},
             "verano": {"temperatura_seca": 36, "temperatura_humeda_coincidente": 21.5,
                        "oscilacion_media_diaria": 15}}
    clima.update(clima_extra)
    return desde_dict({"clima": clima,
                       "local": {"superficie": 50, "altura": 3,
                                 "ocupacion": {"actividad": "oficina", "personas": 5}},
                       "ventilacion": {"caudal_m3h": 0},
                       "cerramientos": cerramientos})


def test_yaml_solucion_y_material():
    p = base([
        {"nombre": "F", "tipo": "muro", "orientacion": "S", "area": 10,
         "solucion": "Fachada por defecto D"},
        {"nombre": "G", "tipo": "muro", "orientacion": "N", "area": 10,
         "capas": [{"material": "Enlucido de yeso 1000 < d < 1300", "espesor": 0.015},
                   {"material": "MW Lana mineral [0.031 W/[mK]]", "espesor": 0.08}]},
    ])
    assert "Fachada por defecto D" in p.cerramientos[0].origen
    assert p.cerramientos[1].U == pytest.approx(1 / (0.17 + 0.015 / 0.57 + 0.08 / 0.031))


def test_yaml_ventana_catalogo():
    p = base([{"nombre": "V", "tipo": "ventana", "orientacion": "S", "area": 2,
               "vidrio": "VER_DB1_4-6-4", "marco": "VER_PVC dos cámaras", "fraccion_marco": 0.2}])
    v = p.cerramientos[0]
    assert v.U == pytest.approx(0.8 * 2.7 + 0.2 * 2.2)
    assert v.g == pytest.approx(0.70, abs=0.005)


def test_yaml_material_inexistente():
    with pytest.raises(ErrorDatos):
        base([{"nombre": "X", "tipo": "muro", "orientacion": "S", "area": 1,
               "capas": [{"material": "material que no existe", "espesor": 0.1}]}])


def test_yaml_solera_terreno():
    p = base([{"nombre": "Solera", "tipo": "suelo", "area": 50,
               "terreno": {"perimetro": 15},
               "capas": [{"material": "Hormigón armado 2300 < d < 2500", "espesor": 0.15}]}],
             temperatura_media_anual=15.0)
    s = p.cerramientos[0]
    assert s.temperatura_adyacente_invierno == 15.0
    esperado = terreno.u_solera(50, 15, 0.15 / 2.3)["U"]
    assert s.U == pytest.approx(esperado, rel=1e-6)
    # la capa equivalente hace que la U por capas coincida con la de ISO 13370
    assert 1 / (0.17 + 0.17 + sum(c.R for c in s.capas)) == pytest.approx(esperado, rel=1e-6)


def test_yaml_solera_sin_temperatura_media_falla():
    with pytest.raises(ErrorDatos):
        base([{"nombre": "Solera", "tipo": "suelo", "area": 50, "terreno": {"perimetro": 15},
               "capas": [{"material": "Hormigón armado 2300 < d < 2500", "espesor": 0.15}]}])


def test_yaml_espacio_no_acondicionado():
    p = base([{"nombre": "A garaje", "tipo": "particion", "area": 20, "U": 1.0,
               "espacio_no_acondicionado": {"UA_exterior": 40, "renovaciones_h": 1, "volumen": 100}}])
    c = p.cerramientos[0]
    hue = 40 + 0.33 * 100
    b = hue / (20 + hue)
    assert c.espacio_no_acondicionado["b"] == pytest.approx(b)
    assert c.temperatura_adyacente_invierno == pytest.approx(21 - b * 24)
    assert c.temperatura_adyacente_verano == pytest.approx(25 + b * 11)
    assert any("b =" in a for a in p.avisos)


# --- puentes térmicos ---------------------------------------------------------------
def test_puentes_termicos():
    from cargas_rite import calcular_invierno, calcular_refrigeracion
    cerr = [{"nombre": "F", "tipo": "muro", "orientacion": "S", "area": 10, "U": 0.5}]
    sin = base(cerr)
    con = desde_dict({**_dict_base(cerr), "puentes_termicos": [
        {"tipo": "IF", "longitud": 10, "psi": 0.6}, {"tipo": "W", "longitud": 8, "psi": 0.1}]})
    assert sin.dU_puentes_termicos == pytest.approx(0.10)
    assert con.dU_puentes_termicos == 0.0
    inv = calcular_invierno(con)
    assert inv.transmision["PT IF: Forjado intermedio-fachada 1"] == pytest.approx(6 * 24)
    ver = calcular_refrigeracion(con)
    assert sum(v for k, v in ver.punta.componentes.items() if k.startswith("PT")) > 0


def test_puente_termico_tipo_invalido():
    with pytest.raises(ErrorDatos):
        desde_dict({**_dict_base([{"nombre": "F", "tipo": "muro", "orientacion": "S",
                                   "area": 10, "U": 0.5}]),
                    "puentes_termicos": [{"tipo": "XX", "longitud": 1, "psi": 1}]})


def _dict_base(cerramientos):
    return {"clima": {"latitud": 40.4, "longitud": -3.7, "altitud": 667,
                      "invierno": {"temperatura_seca": -3},
                      "verano": {"temperatura_seca": 36, "temperatura_humeda_coincidente": 21.5,
                                 "oscilacion_media_diaria": 15}},
            "local": {"superficie": 50, "altura": 3,
                      "ocupacion": {"actividad": "oficina", "personas": 5}},
            "ventilacion": {"caudal_m3h": 0}, "cerramientos": cerramientos}


def test_buscar_por_grupo():
    assert catalogo.buscar("dobles bajo emisivos vertical", "vidrios")
    assert catalogo.buscar("pvc", "marcos")

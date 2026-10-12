"""Pruebas de cerramientos: U (ISO 6946) y propiedades dinámicas (ISO 13786).

Las propiedades dinámicas se contrastan con una simulación numérica independiente
(diferencias finitas implícitas, régimen periódico) del mismo cerramiento.
"""
import math

import numpy as np
import pytest

from cargas_rite.cerramientos import Capa, propiedades, resistencias_superficiales

LADRILLO = dict(conductividad=0.49, densidad=1200, calor_especifico=1000)
HORMIGON = dict(conductividad=1.65, densidad=2150, calor_especifico=1000)
LANA = dict(conductividad=0.037, densidad=40, calor_especifico=1000)
YESO = dict(conductividad=0.57, densidad=1150, calor_especifico=1000)


def muro_tipo():
    """Fachada tipo: enlucido, LH 7, lana 5 cm, ½ pie perforado (interior → exterior)."""
    return [Capa("yeso", 0.015, **YESO), Capa("LH", 0.07, **LADRILLO),
            Capa("lana", 0.05, **LANA), Capa("1/2 pie", 0.115, **LADRILLO)]


def simulacion_fd(capas, rsi=0.13, rse=0.04, nodos_por_capa=40, pasos_hora=120, dias=12):
    """Respuesta a θe = sen(2πt/24h), θi = 0. Devuelve (amplitud q_i / U, desfase h)."""
    xs, k, rc = [], [], []
    for c in capas:
        n = nodos_por_capa
        dx = c.espesor / n
        for _ in range(n):
            k.append(c.conductividad / dx)          # conductancia W/m²K
            rc.append(c.densidad * c.calor_especifico * dx)
    n = len(rc)
    dt = 3600.0 / pasos_hora
    # Resistencias entre nodos (nodo en el centro de cada celda)
    g = np.zeros(n + 1)
    g[0] = 1.0 / (rsi + 0.5 / k[0])
    g[n] = 1.0 / (rse + 0.5 / k[-1])
    for i in range(1, n):
        g[i] = 1.0 / (0.5 / k[i - 1] + 0.5 / k[i])
    C = np.array(rc) / dt
    A = np.zeros((n, n))
    for i in range(n):
        A[i, i] = C[i] + g[i] + g[i + 1]
        if i > 0:
            A[i, i - 1] = -g[i]
        if i < n - 1:
            A[i, i + 1] = -g[i + 1]
    Ainv = np.linalg.inv(A)
    T = np.zeros(n)
    pasos = 24 * pasos_hora
    q = []
    for p in range(dias * pasos):
        t = (p + 1) * dt
        te = math.sin(2 * math.pi * t / 86400)
        b = C * T
        b[-1] += g[n] * te
        T = Ainv @ b
        if p >= (dias - 1) * pasos:
            q.append(g[0] * T[0])           # flujo hacia el interior (θi = 0)
    q = np.array(q)
    tiempos = (np.arange(len(q)) + 1) * dt
    # componente fundamental
    a = 2 / len(q) * np.sum(q * np.sin(2 * math.pi * tiempos / 86400))
    b = 2 / len(q) * np.sum(q * np.cos(2 * math.pi * tiempos / 86400))
    amp = math.hypot(a, b)
    fase = math.atan2(-b, a)                # q = amp·sen(ωt − fase)
    U = 1 / (rsi + rse + sum(c.R for c in capas))
    return amp / U, (fase % (2 * math.pi)) * 24 / (2 * math.pi)


def test_U_iso6946():
    capas = muro_tipo()
    r = 0.13 + 0.04 + 0.015 / 0.57 + 0.07 / 0.49 + 0.05 / 0.037 + 0.115 / 0.49
    assert propiedades(capas).U == pytest.approx(1 / r)


def test_capa_sin_masa():
    p = propiedades([Capa("aislante ideal", 0.05, 0.04, densidad=0)])
    assert p.amortiguamiento == pytest.approx(1.0)
    assert p.desfase_h == pytest.approx(0.0, abs=1e-9)


def test_camara_de_aire_con_resistencia():
    p = propiedades([Capa("cámara", 0.03, 1.0, resistencia=0.18)])
    assert p.U == pytest.approx(1 / (0.13 + 0.04 + 0.18))


@pytest.mark.parametrize("capas", [
    muro_tipo(),
    [Capa("hormigón 20", 0.20, **HORMIGON)],
    [Capa("ladrillo 24", 0.24, **LADRILLO)],
    [Capa("yeso", 0.015, **YESO), Capa("lana", 0.08, **LANA), Capa("hormigón", 0.15, **HORMIGON)],
])
def test_iso13786_contra_diferencias_finitas(capas):
    p = propiedades(capas)
    f_fd, lag_fd = simulacion_fd(capas)
    assert p.amortiguamiento == pytest.approx(f_fd, rel=0.02, abs=0.005)
    assert p.desfase_h == pytest.approx(lag_fd, abs=0.15)


def test_mas_masa_mas_amortiguamiento_y_desfase():
    finos = propiedades([Capa("h10", 0.10, **HORMIGON)])
    gruesos = propiedades([Capa("h30", 0.30, **HORMIGON)])
    assert gruesos.amortiguamiento < finos.amortiguamiento
    assert gruesos.desfase_h > finos.desfase_h


def test_resistencias_superficiales():
    assert resistencias_superficiales("muro", True) == (0.13, 0.04)
    assert resistencias_superficiales("cubierta", True) == (0.10, 0.04)
    assert resistencias_superficiales("suelo", False) == (0.17, 0.17)

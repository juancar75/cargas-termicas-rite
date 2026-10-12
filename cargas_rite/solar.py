"""Geometría solar y radiación en día despejado.

Modelo de cielo despejado de ASHRAE (Handbook — Fundamentals 1985-2005):
    I_DN = A · exp(-B / sen β)
    I_d  = C · I_DN · (1 + cos Σ)/2
    I_r  = ρg · I_DN · (C + sen β) · (1 - cos Σ)/2

Convenios:
    - Horas en HORA SOLAR verdadera (12 = mediodía solar), evaluadas en el instante.
    - Orientación de la superficie (azimut) en grados desde el NORTE en sentido
      horario: N=0, E=90, S=180, O=270.
    - Inclinación Σ: 90 = vertical, 0 = horizontal (cubierta).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Constantes ASHRAE para el día 21 de cada mes (A [W/m²], B [-], C [-])
CONSTANTES_ASHRAE = {
    1: (1230, 0.142, 0.058),
    2: (1215, 0.144, 0.060),
    3: (1186, 0.156, 0.071),
    4: (1136, 0.180, 0.097),
    5: (1104, 0.196, 0.121),
    6: (1088, 0.205, 0.134),
    7: (1085, 0.207, 0.136),
    8: (1107, 0.201, 0.122),
    9: (1151, 0.177, 0.092),
    10: (1192, 0.160, 0.073),
    11: (1221, 0.149, 0.063),
    12: (1233, 0.142, 0.057),
}

DIA_DEL_ANO_21 = {1: 21, 2: 52, 3: 80, 4: 111, 5: 141, 6: 172,
                  7: 202, 8: 233, 9: 264, 10: 294, 11: 325, 12: 355}


@dataclass
class PosicionSolar:
    altura: float   # β [rad]
    azimut: float   # desde el norte, horario [rad]


def declinacion(dia: int) -> float:
    """Declinación solar [rad] (Cooper)."""
    return math.radians(23.45) * math.sin(math.radians(360.0 * (284 + dia) / 365.0))


def posicion_solar(latitud_deg: float, dia: int, hora_solar: float) -> PosicionSolar:
    lat = math.radians(latitud_deg)
    dec = declinacion(dia)
    h = math.radians(15.0 * (hora_solar - 12.0))
    sen_b = math.cos(lat) * math.cos(dec) * math.cos(h) + math.sin(lat) * math.sin(dec)
    beta = math.asin(max(-1.0, min(1.0, sen_b)))
    az = math.atan2(-math.cos(dec) * math.sin(h),
                    math.sin(dec) * math.cos(lat) - math.cos(dec) * math.sin(lat) * math.cos(h))
    return PosicionSolar(beta, az % (2 * math.pi))


def irradiancia(latitud_deg: float, mes: int, hora_solar: float,
                azimut_sup_deg: float, inclinacion_deg: float = 90.0,
                claridad: float = 1.0, albedo: float = 0.2) -> float:
    """Irradiancia total sobre una superficie [W/m²] en día despejado."""
    A, B, C = CONSTANTES_ASHRAE[mes]
    sol = posicion_solar(latitud_deg, DIA_DEL_ANO_21[mes], hora_solar)
    if sol.altura <= 0.0:
        return 0.0
    sen_b = math.sin(sol.altura)
    i_dn = claridad * A * math.exp(-B / sen_b)
    sigma = math.radians(inclinacion_deg)
    gamma = sol.azimut - math.radians(azimut_sup_deg)
    cos_theta = (math.cos(sol.altura) * math.cos(gamma) * math.sin(sigma)
                 + sen_b * math.cos(sigma))
    directa = i_dn * max(cos_theta, 0.0)
    difusa = C * i_dn * (1.0 + math.cos(sigma)) / 2.0
    reflejada = albedo * i_dn * (C + sen_b) * (1.0 - math.cos(sigma)) / 2.0
    return directa + difusa + reflejada

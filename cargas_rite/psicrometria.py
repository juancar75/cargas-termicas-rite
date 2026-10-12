"""Psicrometría básica para cálculo de cargas.

Fórmulas de ASHRAE Handbook — Fundamentals, cap. 1 (Psychrometrics),
con presión de saturación aproximada por Magnus (error < 0,4 % entre -40 y 50 °C).
"""
from __future__ import annotations

import math

RHO_CP_AIRE = 0.34   # W·h/(m³·K)  ≈ 1,2 kg/m³ · 1006 J/(kg·K) / 3600
RHO_HFG_AIRE = 0.83  # W·h/(m³·(g/kg)) ≈ 1,2 kg/m³ · 2501 kJ/kg / 3600 / 1000


def presion_atmosferica(altitud_m: float) -> float:
    """Presión atmosférica estándar [kPa] a una altitud [m]."""
    return 101.325 * (1.0 - 2.25577e-5 * altitud_m) ** 5.2559


def presion_saturacion(t: float) -> float:
    """Presión de vapor de saturación [kPa] a temperatura t [°C] (Magnus)."""
    return 0.61094 * math.exp(17.625 * t / (t + 243.04))


def humedad_especifica_desde_hr(t: float, hr: float, p: float) -> float:
    """Humedad específica [g/kg aire seco] desde temperatura [°C] y HR [0-1]."""
    pw = hr * presion_saturacion(t)
    return 1000.0 * 0.621945 * pw / (p - pw)


def humedad_especifica_desde_bulbo_humedo(tbs: float, tbh: float, p: float) -> float:
    """Humedad específica [g/kg] desde bulbo seco y bulbo húmedo [°C] (ASHRAE eq. 33)."""
    pws = presion_saturacion(tbh)
    ws = 0.621945 * pws / (p - pws)
    w = ((2501.0 - 2.326 * tbh) * ws - 1.006 * (tbs - tbh)) / (
        2501.0 + 1.86 * tbs - 4.186 * tbh
    )
    return 1000.0 * w

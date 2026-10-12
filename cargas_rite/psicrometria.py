"""Psicrometría con CoolProp (HumidAirProp).

CoolProp implementa las propiedades del aire húmedo de ASHRAE RP-1485
(Herrmann, Kretzschmar y Gatley, 2009), la referencia de ASHRAE Fundamentals.
Aquí sólo se envuelven las funciones que necesita el cálculo de cargas, en
unidades prácticas (°C, kPa, g/kg).
"""
from __future__ import annotations

from CoolProp.HumidAirProp import HAPropsSI

# Coeficientes prácticos de transporte de energía por el aire (ρ≈1,2 kg/m³)
RHO_CP_AIRE = 0.34   # W·h/(m³·K)
RHO_HFG_AIRE = 0.83  # W·h/(m³·(g/kg))

_K = 273.15


def presion_atmosferica(altitud_m: float) -> float:
    """Presión atmosférica estándar [kPa] (ASHRAE Fundamentals, cap. 1, ec. 3)."""
    return 101.325 * (1.0 - 2.25577e-5 * altitud_m) ** 5.2559


def humedad_especifica_desde_hr(t: float, hr: float, p: float) -> float:
    """Humedad específica [g/kg as] desde temperatura [°C], HR [0-1] y presión [kPa]."""
    return 1000.0 * HAPropsSI("W", "T", t + _K, "P", p * 1000.0, "R", hr)


def humedad_especifica_desde_bulbo_humedo(tbs: float, tbh: float, p: float) -> float:
    """Humedad específica [g/kg as] desde bulbo seco y bulbo húmedo [°C]."""
    if tbh > tbs:
        raise ValueError("El bulbo húmedo no puede superar al bulbo seco")
    return 1000.0 * HAPropsSI("W", "T", tbs + _K, "P", p * 1000.0, "B", tbh + _K)


def humedad_relativa(t: float, w: float, p: float) -> float:
    """Humedad relativa [0-1] desde temperatura [°C] y humedad específica [g/kg]."""
    return HAPropsSI("R", "T", t + _K, "P", p * 1000.0, "W", w / 1000.0)


def entalpia(t: float, w: float, p: float) -> float:
    """Entalpía específica [kJ/kg as]."""
    return HAPropsSI("H", "T", t + _K, "P", p * 1000.0, "W", w / 1000.0) / 1000.0


def coeficientes_aire(t: float, w: float, p: float) -> tuple[float, float]:
    """Coeficientes de transporte del aire exterior a sus condiciones reales.

    Devuelve (sensible [W·h/(m³·K)], latente [W·h/(m³·(g/kg))]) para un caudal
    volumétrico medido a temperatura t [°C], humedad w [g/kg] y presión p [kPa].
    Sustituyen a los valores fijos 0,34 y 0,83 (válidos a nivel del mar y 20 °C):
    en Madrid (667 m) y 36 °C el aire es un 10 % menos denso.
    """
    v_as = HAPropsSI("Vda", "T", t + _K, "P", p * 1000.0, "W", w / 1000.0)  # m³/kg as
    rho_as = 1.0 / v_as
    sensible = rho_as * (1006.0 + 1860.0 * w / 1000.0) / 3600.0
    latente = rho_as * 2501.0 / 3600.0
    return sensible, latente

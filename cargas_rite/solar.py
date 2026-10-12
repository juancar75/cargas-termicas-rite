"""Radiación solar sobre los cerramientos el día de diseño, con pvlib.

- Posición solar: algoritmo SPA del NREL (pvlib.solarposition).
- Radiación en cielo despejado, dos modelos:
    * "ashrae":   modelo clásico de ASHRAE (constantes A, B, C del día 21 de cada mes),
                  el mismo que EnergyPlus llama ASHRAEClearSky.
    * "ineichen": modelo de Ineichen-Perez con la turbidez de Linke de la localidad
                  (base de datos SoDa incluida en pvlib). Más realista para España.
- Transposición a la superficie: modelo anisótropo de Perez (circunsolar y brillo
  del horizonte) + reflexión del suelo (pvlib.irradiance.get_total_irradiance).
  Es el mismo modelo que usa EnergyPlus; el isotrópico subestima hasta un 12 % la
  radiación en fachadas E/O con el sol bajo.
- Vidrios: modificador por ángulo de incidencia (IAM) con el modelo físico de
  Fresnel + absorción de pvlib (pvlib.iam.physical), aplicado a cada hoja.

Convenios: azimut de la superficie desde el NORTE en sentido horario
(N=0, E=90, S=180, O=270); inclinación 90 = vertical, 0 = horizontal.
Las horas se expresan en HORA OFICIAL.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
import pvlib

# Constantes ASHRAE para el día 21 de cada mes (A [W/m²], B [-], C [-])
CONSTANTES_ASHRAE = {
    1: (1230, 0.142, 0.058), 2: (1215, 0.144, 0.060), 3: (1186, 0.156, 0.071),
    4: (1136, 0.180, 0.097), 5: (1104, 0.196, 0.121), 6: (1088, 0.205, 0.134),
    7: (1085, 0.207, 0.136), 8: (1107, 0.201, 0.122), 9: (1151, 0.177, 0.092),
    10: (1192, 0.160, 0.073), 11: (1221, 0.149, 0.063), 12: (1233, 0.142, 0.057),
}

PASO_MIN = 5  # resolución interna [min]

# Vidrio sodocálcico: índice de refracción, coef. extinción [1/m], espesor [m]
N_VIDRIO, K_VIDRIO, L_VIDRIO = 1.526, 4.0, 0.004


def _zona(diferencia_horaria: float) -> str:
    """Zona horaria fija de pandas para un desfase entero respecto a UTC."""
    d = int(round(diferencia_horaria))
    return f"Etc/GMT{-d:+d}"  # ojo: el signo de Etc/GMT va invertido


@lru_cache(maxsize=64)
def _cielo(latitud: float, longitud: float, altitud: float, mes: int,
           diferencia_horaria: float, modelo: str, claridad: float):
    """Posición solar y componentes en horizontal cada PASO_MIN minutos."""
    tz = _zona(diferencia_horaria)
    tiempos = pd.date_range(f"2021-{mes:02d}-21 00:00", periods=24 * 60 // PASO_MIN,
                            freq=f"{PASO_MIN}min", tz=tz)
    pos = pvlib.solarposition.get_solarposition(tiempos, latitud, longitud, altitude=altitud)
    if modelo == "ashrae":
        A, B, C = CONSTANTES_ASHRAE[mes]
        sen_b = np.sin(np.radians(pos["apparent_elevation"].to_numpy()))
        dni = np.where(sen_b > 0, claridad * A * np.exp(-B / np.clip(sen_b, 1e-6, None)), 0.0)
        dhi = C * dni
        ghi = dni * np.clip(sen_b, 0, None) + dhi
    elif modelo == "ineichen":
        loc = pvlib.location.Location(latitud, longitud, tz=tz, altitude=altitud)
        cs = loc.get_clearsky(tiempos, model="ineichen", solar_position=pos)
        dni, dhi, ghi = (cs[k].to_numpy() * claridad for k in ("dni", "dhi", "ghi"))
    else:
        raise ValueError(f"Modelo de cielo desconocido: {modelo}")
    horas = np.arange(len(tiempos)) * PASO_MIN / 60.0
    return horas, pos, dni, dhi, ghi


@dataclass
class PerfilSolar:
    """Componentes de la irradiancia sobre una superficie a lo largo del día."""
    horas: np.ndarray        # hora oficial 0-24
    directa: np.ndarray      # W/m²
    difusa: np.ndarray       # cielo + suelo, W/m²
    aoi: np.ndarray          # ángulo de incidencia de la directa [°]

    @property
    def total(self) -> np.ndarray:
        return self.directa + self.difusa

    def transmitida_vidrio(self, hojas: int = 2) -> np.ndarray:
        """Irradiancia efectiva para un vidrio: directa·IAM(θ) + difusa·IAM_dif."""
        iam_d = iam_vidrio(self.aoi, hojas)
        return self.directa * iam_d + self.difusa * iam_difusa(hojas)


def iam_vidrio(aoi, hojas: int = 2):
    """Modificador por ángulo de incidencia de un acristalamiento de 'hojas' vidrios."""
    una = pvlib.iam.physical(np.asarray(aoi, float), n=N_VIDRIO, K=K_VIDRIO, L=L_VIDRIO)
    return np.clip(np.nan_to_num(una, nan=0.0), 0.0, 1.0) ** hojas


@lru_cache(maxsize=8)
def iam_difusa(hojas: int = 2) -> float:
    """IAM medio hemisférico para radiación difusa isotrópica (integral de Brandemuehl)."""
    th = np.linspace(0.0, 89.9, 900)
    pesos = np.sin(np.radians(th)) * np.cos(np.radians(th))
    return float(np.trapezoid(iam_vidrio(th, hojas) * pesos, th) / np.trapezoid(pesos, th))


def perfil(latitud: float, longitud: float, altitud: float, mes: int,
           diferencia_horaria: float, azimut: float, inclinacion: float = 90.0,
           modelo: str = "ashrae", claridad: float = 1.0, albedo: float = 0.2) -> PerfilSolar:
    horas, pos, dni, dhi, ghi = _cielo(latitud, longitud, altitud, mes,
                                       diferencia_horaria, modelo, claridad)
    extra = pvlib.irradiance.get_extra_radiation(pos.index)
    masa_aire = pvlib.atmosphere.get_relative_airmass(pos["apparent_zenith"])
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=inclinacion, surface_azimuth=azimut,
        solar_zenith=pos["apparent_zenith"], solar_azimuth=pos["azimuth"],
        dni=dni, ghi=ghi, dhi=dhi, albedo=albedo, model="perez",
        dni_extra=extra, airmass=masa_aire)
    aoi = pvlib.irradiance.aoi(inclinacion, azimut, pos["apparent_zenith"], pos["azimuth"])
    directa = np.clip(np.nan_to_num(poa["poa_direct"].to_numpy()), 0.0, None)
    difusa = np.clip(np.nan_to_num(poa["poa_diffuse"].to_numpy()), 0.0, None)
    return PerfilSolar(horas, directa, difusa, np.clip(aoi.to_numpy(), 0, 90))


def perfil_irradiancia(latitud: float, longitud: float, altitud: float, mes: int,
                       diferencia_horaria: float, azimut: float, inclinacion: float = 90.0,
                       modelo: str = "ashrae", claridad: float = 1.0,
                       albedo: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (horas oficiales 0-24, irradiancia total sobre la superficie [W/m²])."""
    p = perfil(latitud, longitud, altitud, mes, diferencia_horaria, azimut, inclinacion,
               modelo, claridad, albedo)
    return p.horas, p.total


def interpolar(horas: np.ndarray, valores: np.ndarray, h: float) -> float:
    """Valor en la hora h (periódica de 24 h)."""
    return float(np.interp(h % 24.0, horas, valores, period=24.0))


def altura_solar_max(latitud: float, longitud: float, mes: int,
                     diferencia_horaria: float) -> float:
    """Altura solar máxima del día [°] (útil para comprobaciones)."""
    _, pos, *_ = _cielo(latitud, longitud, 0.0, mes, diferencia_horaria, "ashrae", 1.0)
    return float(pos["apparent_elevation"].max())

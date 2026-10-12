"""Propiedades térmicas de cerramientos multicapa.

- Transmitancia U en régimen estacionario: UNE-EN ISO 6946 (resistencias
  superficiales de su tabla 7, las mismas del DA DB-HE/1 del CTE).
- Características térmicas dinámicas: UNE-EN ISO 13786, método de la matriz de
  transferencia para un periodo de 24 h. Se obtiene la transmitancia térmica
  periódica Y12, y de ella:
      f  = |Y12| / U          factor de amortiguamiento (decremento)
      φ  = desfase [h]        retraso de la onda térmica exterior→interior
"""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

PERIODO = 86400.0  # s

# Resistencias superficiales [m²K/W] según dirección del flujo (ISO 6946, tabla 7)
RSI = {"horizontal": 0.13, "ascendente": 0.10, "descendente": 0.17}
RSE = 0.04


@dataclass
class Capa:
    nombre: str
    espesor: float          # m
    conductividad: float    # λ, W/(m·K)
    densidad: float = 0.0   # ρ, kg/m³ (0 = sin masa, p. ej. cámara de aire)
    calor_especifico: float = 1000.0  # c, J/(kg·K)
    resistencia: float | None = None  # m²K/W, para capas sin λ (cámaras)

    @property
    def R(self) -> float:
        if self.resistencia is not None:
            return self.resistencia
        return self.espesor / self.conductividad


def _matriz_capa(c: Capa) -> list[list[complex]]:
    """Matriz de transferencia de una capa (ISO 13786, apdo. 6.2)."""
    if c.resistencia is not None or c.densidad <= 0:
        return [[1 + 0j, -c.R + 0j], [0j, 1 + 0j]]
    lam, d = c.conductividad, c.espesor
    delta = math.sqrt(lam * PERIODO / (math.pi * c.densidad * c.calor_especifico))
    xi = d / delta
    ch, sh, co, si = math.cosh(xi), math.sinh(xi), math.cos(xi), math.sin(xi)
    z11 = complex(ch * co, sh * si)
    z12 = -delta / (2 * lam) * complex(sh * co + ch * si, ch * si - sh * co)
    z21 = -lam / delta * complex(sh * co - ch * si, sh * co + ch * si)
    return [[z11, z12], [z21, z11]]


def _mult(a, b):
    return [[a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]],
            [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]]]


def _matriz_superficie(R: float):
    return [[1 + 0j, -R + 0j], [0j, 1 + 0j]]


@dataclass
class PropiedadesDinamicas:
    U: float
    Y12: complex
    amortiguamiento: float   # f
    desfase_h: float         # φ


def propiedades(capas: list[Capa], rsi: float = RSI["horizontal"],
                rse: float = RSE) -> PropiedadesDinamicas:
    """Capas ordenadas de INTERIOR a EXTERIOR."""
    if not capas:
        raise ValueError("El cerramiento necesita al menos una capa")
    r_total = rsi + rse + sum(c.R for c in capas)
    U = 1.0 / r_total
    # Z = Z_se · Z_n · … · Z_1 · Z_si  (capa 1 = interior)
    z = _matriz_superficie(rsi)
    for c in capas:
        z = _mult(_matriz_capa(c), z)
    z = _mult(_matriz_superficie(rse), z)
    y12 = -1.0 / z[0][1]
    f = abs(y12) / U
    # El argumento de Y12 es el adelanto de la respuesta; el desfase es su opuesto.
    fase = cmath.phase(y12)
    desfase = (-fase if fase <= 0 else 2 * math.pi - fase) * PERIODO / (2 * math.pi) / 3600.0
    return PropiedadesDinamicas(U=U, Y12=y12, amortiguamiento=f, desfase_h=desfase % 24.0)


def resistencias_superficiales(tipo: str, exterior: bool) -> tuple[float, float]:
    """(Rsi, Rse) según el tipo de elemento. Hacia otro local: Rse = Rsi."""
    flujo = {"cubierta": "ascendente", "suelo": "descendente"}.get(tipo, "horizontal")
    rsi = RSI[flujo]
    return rsi, (RSE if exterior else rsi)

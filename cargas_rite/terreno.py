"""Elementos en contacto con el terreno y con espacios no acondicionados.

Métodos del DA DB-HE/1 (Cálculo de parámetros característicos de la envolvente),
que remite a UNE-EN ISO 13370 y UNE-EN ISO 13789 / 6946. Traducción a Python de la
implementación de referencia del IETcc-CSIC en
https://github.com/pachi/cteenergymodel (bemodel/src/energy/transmittance.rs,
licencia MIT, © Rafael Villar Burke).
"""
from __future__ import annotations

import math

LAMBDA_TERRENO = 2.0      # W/mK (arcilla o limo, valor por defecto de ISO 13370)
LAMBDA_AISLANTE = 0.035   # W/mK
RSI_DESCENDENTE = 0.17
RSE = 0.04
ESPESOR_MUROS = 0.30      # m, espesor supuesto de los muros perimetrales


def dimension_caracteristica(area: float, perimetro: float) -> float:
    """B' = A / (0,5·P)  (ISO 13370, 8.1). P es el perímetro EXPUESTO al exterior."""
    if perimetro <= 0:
        raise ValueError("El perímetro expuesto de la solera debe ser > 0")
    return area / (0.5 * perimetro)


def espesor_equivalente(resistencia_solera: float, w: float = ESPESOR_MUROS) -> float:
    """d_t = w + λ·(Rsi + Rf + Rse)  (ISO 13370, 9.3.2, ec. 10). Rf sin resistencias superficiales."""
    return w + LAMBDA_TERRENO * (RSI_DESCENDENTE + resistencia_solera + RSE)


def psi_aislamiento_perimetral(d_t: float, resistencia: float, ancho: float) -> float:
    """ψ_ge por aislamiento perimetral horizontal (ISO 13370, anexo B, B.4 y B.5) [W/mK]."""
    if resistencia <= 0 or ancho <= 0:
        return 0.0
    d1 = resistencia * (LAMBDA_TERRENO - LAMBDA_AISLANTE)
    return -LAMBDA_TERRENO / math.pi * (math.log(1 + ancho / d_t) - math.log(1 + ancho / (d_t + d1)))


def u_solera(area: float, perimetro: float, resistencia_solera: float, profundidad: float = 0.0,
             aislamiento_perimetral_R: float = 0.0, aislamiento_perimetral_ancho: float = 0.0) -> dict:
    """Transmitancia de solera o suelo de sótano (ISO 13370, 9.1 y 9.3.2; DA DB-HE/1).

    resistencia_solera: R de las capas de la solera, SIN resistencias superficiales.
    profundidad: z ≥ 0 del suelo bajo la cota del terreno.
    """
    B = dimension_caracteristica(area, perimetro)
    d_t = espesor_equivalente(resistencia_solera)
    limite = d_t + 0.5 * profundidad
    if limite < B:   # soleras sin aislar o moderadamente aisladas (11)
        U_bf = 2 * LAMBDA_TERRENO / (math.pi * B + limite) * math.log(1 + math.pi * B / limite)
    else:            # soleras bien aisladas (12)
        U_bf = LAMBDA_TERRENO / (0.457 * B + limite)
    psi = psi_aislamiento_perimetral(d_t, aislamiento_perimetral_R, aislamiento_perimetral_ancho)
    U = U_bf + 2 * psi / B
    return {"U": U, "U_bf": U_bf, "B": B, "d_t": d_t, "psi_ge": psi}


def factor_b(H_iu: float, H_ue: float) -> float:
    """Factor de reducción b = H_ue / (H_iu + H_ue)  (UNE-EN ISO 13789)."""
    return H_ue / (H_iu + H_ue)


def H_ue(ua_exterior: float, renovaciones_h: float, volumen: float) -> float:
    """Coeficiente del espacio no acondicionado al exterior: ΣU·A + 0,33·n·V [W/K]."""
    return ua_exterior + 0.33 * renovaciones_h * volumen


def temperatura_no_acondicionado(theta_i: float, theta_e: float, b: float) -> float:
    """θu = θi − b·(θi − θe)  (sin ganancias internas ni solares en el espacio no acondicionado)."""
    return theta_i - b * (theta_i - theta_e)

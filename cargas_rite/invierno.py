"""Carga de calefacción (invierno) — régimen estacionario.

Método basado en UNE-EN 12831-1 simplificado:
    Φ_T = Σ (U + ΔU_pt) · A · (θi − θe)       elementos exteriores opacos
        + Σ U · A · (θi − θe)                 huecos exteriores
        + Σ U · A · (θi − θady)               elementos a espacios no calefactados / terreno
    Φ_V = ρc · V̇_vent · (1 − η_rec) · (θi − θe)
    Φ_inf = ρc · n · Vol · (θi − θe)

ρc se calcula con CoolProp a la presión de la altitud del lugar y la temperatura
exterior de diseño (≈ 0,34 W·h/(m³·K) a nivel del mar).

No se descuentan ganancias internas ni solares (criterio del lado de la seguridad).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .modelo import Proyecto
from .psicrometria import coeficientes_aire, humedad_especifica_desde_hr, presion_atmosferica


@dataclass
class ResultadoInvierno:
    delta_t: float
    transmision: dict[str, float] = field(default_factory=dict)
    ventilacion: float = 0.0
    infiltracion: float = 0.0
    mayoracion: float = 0.0
    coef_aire: float = 0.34

    @property
    def total_transmision(self) -> float:
        return sum(self.transmision.values())

    @property
    def subtotal(self) -> float:
        return self.total_transmision + self.ventilacion + self.infiltracion

    @property
    def total(self) -> float:
        return self.subtotal + self.mayoracion


def calcular_invierno(p: Proyecto) -> ResultadoInvierno:
    ti = p.interior.t_invierno
    te = p.clima.t_invierno
    r = ResultadoInvierno(delta_t=ti - te)
    pa = presion_atmosferica(p.clima.altitud)
    RHO_CP_AIRE, _ = coeficientes_aire(te, humedad_especifica_desde_hr(te, 0.9, pa), pa)
    r.coef_aire = RHO_CP_AIRE
    for c in p.cerramientos:
        if c.exterior:
            u = c.U + (p.dU_puentes_termicos if c.tipo in ("muro", "cubierta") else 0.0)
            phi = u * c.area * (ti - te)
        else:
            phi = c.U * c.area * (ti - c.temperatura_adyacente_invierno)
        r.transmision[c.nombre] = max(phi, 0.0)
    for pt in p.puentes_termicos:
        r.transmision[f"PT {pt.tipo}: {pt.nombre}"] = pt.H * (ti - te)
    v = p.ventilacion
    r.ventilacion = RHO_CP_AIRE * v.caudal_m3h * (1 - v.eficiencia_recuperador) * (ti - te)
    r.infiltracion = RHO_CP_AIRE * v.infiltracion_h * p.local.volumen * (ti - te)
    r.mayoracion = p.mayoracion * r.subtotal
    return r

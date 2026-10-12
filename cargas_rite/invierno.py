"""Carga de calefacción (invierno) — régimen estacionario.

Método basado en UNE-EN 12831-1 simplificado:
    Φ_T = Σ (U + ΔU_pt) · A · (θi − θe)       elementos exteriores opacos
        + Σ U · A · (θi − θe)                 huecos exteriores
        + Σ U · A · (θi − θady)               elementos a espacios no calefactados / terreno
    Φ_V = 0,34 · V̇_vent · (1 − η_rec) · (θi − θe)
    Φ_inf = 0,34 · n · Vol · (θi − θe)

No se descuentan ganancias internas ni solares (criterio del lado de la seguridad).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .modelo import Proyecto
from .psicrometria import RHO_CP_AIRE


@dataclass
class ResultadoInvierno:
    delta_t: float
    transmision: dict[str, float] = field(default_factory=dict)
    ventilacion: float = 0.0
    infiltracion: float = 0.0
    mayoracion: float = 0.0

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
    for c in p.cerramientos:
        if c.exterior:
            u = c.U + (p.dU_puentes_termicos if c.tipo in ("muro", "cubierta") else 0.0)
            phi = u * c.area * (ti - te)
        else:
            phi = c.U * c.area * (ti - c.temperatura_adyacente_invierno)
        r.transmision[c.nombre] = max(phi, 0.0)
    v = p.ventilacion
    r.ventilacion = RHO_CP_AIRE * v.caudal_m3h * (1 - v.eficiencia_recuperador) * (ti - te)
    r.infiltracion = RHO_CP_AIRE * v.infiltracion_h * p.local.volumen * (ti - te)
    r.mayoracion = p.mayoracion * r.subtotal
    return r

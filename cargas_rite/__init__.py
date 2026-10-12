"""cargas-termicas-rite: justificación de cargas de invierno y verano de un local climatizado."""
__version__ = "0.3.0"

from .modelo import cargar, desde_dict  # noqa: E402
from .invierno import calcular_invierno  # noqa: E402
from .verano import calcular_verano  # noqa: E402


def calcular_refrigeracion(p):
    """Carga de refrigeración con el método elegido en el proyecto (dinámico por defecto)."""
    if p.metodo_verano == "simplificado":
        return calcular_verano(p)
    from .dinamico import calcular_verano_dinamico
    return calcular_verano_dinamico(p)


__all__ = ["cargar", "desde_dict", "calcular_invierno", "calcular_verano",
           "calcular_refrigeracion", "__version__"]

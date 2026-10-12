"""cargas-termicas-rite: justificación de cargas de invierno y verano de un local climatizado."""
__version__ = "0.1.0"

from .modelo import cargar, desde_dict  # noqa: E402
from .invierno import calcular_invierno  # noqa: E402
from .verano import calcular_verano  # noqa: E402

__all__ = ["cargar", "desde_dict", "calcular_invierno", "calcular_verano", "__version__"]

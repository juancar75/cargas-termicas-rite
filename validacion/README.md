# Validación contra EnergyPlus

`energyplus.py` define 9 casos de referencia (una caja de 6 × 5 × 3 m con distintos
cerramientos, huecos, cargas e infiltración). Para cada uno genera la entrada de
`cargas_rite` y un IDF equivalente de EnergyPlus con la misma geometría, capas,
vidrios, ganancias y clima, ejecuta el dimensionado de zona con equipo ideal y
compara las cargas punta.

```bash
# EnergyPlus 26.1: https://github.com/NREL/EnergyPlus/releases
python validacion/energyplus.py --energyplus /ruta/a/energyplus   # o variable ENERGYPLUS
pytest tests/test_validacion_energyplus.py                        # con criterios de aceptación
```

Resultados actuales: [`resultados.md`](resultados.md). En GitHub Actions se ejecuta en
cada cambio (trabajo `validacion-energyplus`).

## Diferencias conocidas y su causa

| Diferencia | Causa |
|---|---|
| Calefacción +11 a +16 % | Resistencias superficiales normalizadas de UNE-EN ISO 6946 frente a convección y radiación detalladas de EnergyPlus. Del lado de la seguridad y conforme al CTE. |
| Cubierta en invierno −8 % | EnergyPlus incluye la radiación nocturna al cielo; UNE-EN 12831-1 no. |
| Muro pesado aislado −10 % | Coeficientes superficiales exteriores; en un local real su peso es pequeño. |
| Fachada S +21 % | Reparto de la radiación transmitida entre superficies interiores. |
| Método simplificado +70 a +150 % | Ganancia solar sin almacenamiento: es una cota superior, no un método de dimensionado ajustado. |

Si comparas con otra herramienta (HAP, DesignBuilder, CYPE…), abre una *issue* con la
plantilla «Comparativa de resultados».

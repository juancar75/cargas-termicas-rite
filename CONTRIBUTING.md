# Cómo colaborar

Gracias por querer ayudar. El proyecto está en español y está pensado para
instaladores e ingenieros de climatización.

## Sin programar

- **Prueba casos reales** y compara con otra herramienta (HAP, DesignBuilder, CYPE,
  hoja propia). Abre una *issue* con la plantilla «Comparativa de resultados».
- **Aporta datos**: condiciones climáticas, cerramientos tipo, perfiles de ocupación.
  Indica siempre la fuente.
- **Revisa la metodología** en [`docs/metodologia.md`](docs/metodologia.md).

## Programando

```bash
git clone https://github.com/juancar75/cargas-termicas-rite
cd cargas-termicas-rite
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Normas:

1. Una rama por cambio y *pull request* contra `main`.
2. Todo cálculo nuevo con su **test** y, si es posible, un caso comprobado a mano.
3. Fórmulas comentadas en el código con su referencia normativa.
4. Nombres de variables y comentarios en español; código Python ≥ 3.10.
5. Sin dependencias pesadas en el núcleo (sólo PyYAML). Las integraciones
   (EnergyPlus, CAD) van en `integraciones/` como extras opcionales.

## Datos con derechos de autor

**No subas tablas copiadas de normas UNE/EN ni de bases de datos de programas
comerciales.** Usa fuentes públicas (CTE, RITE, guías IDAE) o valores propios
justificados. Si un dato procede de una norma de pago, se puede citar la referencia,
pero el valor lo tiene que introducir cada usuario.

## Licencia

Al contribuir aceptas que tu aportación se publique bajo GPL-3.0-or-later.

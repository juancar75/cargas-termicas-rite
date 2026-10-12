# cargas-termicas-rite

**Justificación de cargas térmicas de invierno y verano de un local climatizado, según el RITE.**
Software libre pensado para instaladores e ingenieros que tienen que redactar la
memoria técnica de una instalación de climatización.

> Estado: **v0.1 — en desarrollo**. Funciona para un local, con entrada en YAML y salida
> en Markdown/CSV. Buscamos colaboradores: ver [Cómo colaborar](#cómo-colaborar).

## ¿Para qué sirve?

En España, una instalación térmica de 5 a 70 kW necesita una **memoria técnica** (RITE,
art. 15) que justifique la potencia elegida. Este proyecto calcula, de forma
**transparente y comprobable a mano**:

- **Carga de refrigeración**: cálculo horario del día de diseño (24 h), con sensible y
  latente, hora punta y desglose por componentes.
- **Carga de calefacción**: régimen estacionario, desglose por cerramiento, ventilación
  e infiltración.
- **Comprobaciones RITE**: condiciones interiores (IT 1.1.4.1.2), caudal de ventilación por
  categoría IDA (IT 1.1.4.2.3) y aviso de recuperación de calor obligatoria (IT 1.2.4.5.2).

El resultado es un informe listo para pegar en la memoria.

## Uso rápido

```bash
pip install git+https://github.com/juancar75/cargas-termicas-rite
cargas-rite ejemplos/local_comercial.yaml --csv horario.csv
```

```
Refrigeración: 10.19 kW (sensible 8.79, latente 1.40) a las 17:00 h
Calefacción:   7.41 kW
Informe: ejemplos/local_comercial.md
```

Los datos se describen en un archivo YAML legible (ver
[`ejemplos/local_comercial.yaml`](ejemplos/local_comercial.yaml)):

```yaml
local:
  superficie: 85.0
  altura: 3.0
  ocupacion: {actividad: comercio, m2_por_persona: 5}
ventilacion:
  categoria_ida: IDA3
cerramientos:
  - {nombre: Escaparate SO, tipo: ventana, orientacion: SO, area: 10, U: 3.0, g: 0.6}
  - {nombre: Medianera, tipo: particion, area: 45, U: 1.2,
     temperatura_adyacente: {invierno: 18, verano: 27}}
```

## Método de cálculo

Resumen (detalle en [`docs/metodologia.md`](docs/metodologia.md)):

| Carga | Método |
|---|---|
| Calefacción | Estacionario, planteamiento UNE-EN 12831-1 simplificado. Sin descontar ganancias. |
| Refrigeración, opacos | Temperatura sol-aire + método de admitancias (amortiguamiento y desfase) |
| Refrigeración, huecos | Conducción + radiación solar instantánea (cielo despejado ASHRAE) |
| Cargas internas | Ocupantes (sensible/latente), iluminación y equipos en horario de uso |
| Aire exterior | Ventilación con recuperador opcional + infiltración, sensible y latente |

Todas las fórmulas están en el código, comentadas, y cada componente aparece en el informe.

## Hoja de ruta

Ver [`ROADMAP.md`](ROADMAP.md). En resumen:

1. **v0.1** — un local, YAML → informe (✅ hecho)
2. **v0.2** — base de datos climática (Guía IDAE), biblioteca de cerramientos CTE, salida Excel/Word
3. **v0.3** — varios locales y zonas, simultaneidad
4. **v0.4** — interfaz: paleta en GstarCAD/AutoCAD, plugin IngeTrazo
5. **v1.0** — motor avanzado opcional con EnergyPlus (Honeybee/OpenStudio) y validación cruzada

## Cómo colaborar

Toda ayuda es bienvenida, programes o no:

- **Instaladores e ingenieros**: probar con casos reales, comparar con HAP, DesignBuilder,
  CYPE u otros, y abrir una *issue* con las diferencias.
- **Datos**: condiciones climáticas por localidad, cerramientos tipo, perfiles de uso.
- **Programación**: ver [`CONTRIBUTING.md`](CONTRIBUTING.md) y las *issues* marcadas
  `buena primera tarea`.

## Aviso

Esta herramienta **no sustituye el criterio técnico** de quien firma la documentación.
Los datos de entrada y los resultados deben verificarse. Se distribuye sin garantía
(ver licencia).

## Licencia

[GPL-3.0-or-later](LICENSE). Puedes usarlo, estudiarlo, modificarlo y redistribuirlo;
las versiones modificadas que se distribuyan deben mantener la misma licencia.

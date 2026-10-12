# cargas-termicas-rite

**Justificación de cargas térmicas de invierno y verano de un local climatizado, según el RITE.**
Software libre pensado para instaladores e ingenieros que tienen que redactar la
memoria técnica de una instalación de climatización.

> Estado: **v0.2 — en desarrollo**. Funciona para un local, con entrada en YAML y salida
> en Markdown/CSV, y está **validado contra EnergyPlus** en 9 casos de referencia.
> Buscamos colaboradores: ver [Cómo colaborar](#cómo-colaborar).

## ¿Para qué sirve?

En España, una instalación térmica de 5 a 70 kW necesita una **memoria técnica** (RITE,
art. 15) que justifique la potencia elegida. Este proyecto calcula, de forma
**transparente y comprobable a mano**:

- **Carga de refrigeración**: balance térmico horario del local (método dinámico, con el
  almacenamiento de calor en la masa del local) o método simplificado conservador; sensible
  y latente, hora punta y desglose exacto por componentes.
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
Refrigeración: 6.73 kW (sensible 5.36, latente 1.37) a las 17:00 h
Calefacción:   8.69 kW
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

Resumen (detalle en [`docs/metodologia.md`](docs/metodologia.md) y normas aplicadas en
[`docs/normativa.md`](docs/normativa.md)):

| Parte | Método | Base |
|---|---|---|
| Cerramientos | U por capas y propiedades dinámicas (amortiguamiento, desfase) | UNE-EN ISO 6946, UNE-EN ISO 13786 |
| Calefacción | Estacionario, sin descontar ganancias | UNE-EN 12831-1 (simplificado) |
| Refrigeración | Balance térmico horario con red de nodos por capas y masa interior | Planteamiento UNE-EN ISO 52016-1 |
| Radiación solar | Posición SPA, cielo despejado ASHRAE/Ineichen, transposición de Perez, IAM de vidrios | pvlib |
| Aire húmedo | Propiedades reales a la altitud del lugar | CoolProp (ASHRAE RP-1485) |
| Condiciones y ventilación | Interiores, IDA, recuperación | RITE IT 1.1.4 e IT 1.2.4.5.2 |

## Validación

Cada cambio se comprueba con **78 pruebas automáticas**: tablas de ASHRAE (psicrometría),
geometría solar, una simulación numérica independiente (ISO 13786), conservación de la
energía del modelo dinámico y comparación con **EnergyPlus 26.1** (programa del
Departamento de Energía de EE. UU. validado con ANSI/ASHRAE 140):

| Caso | EnergyPlus | Dinámico | Desv. | Simplificado | Desv. | Calefacción desv. |
|---|---:|---:|---:|---:|---:|---:|
| Fachada S con ventana | 380 W | 459 W | +21 % | 885 W | +133 % | +11 % |
| Fachada O con ventana | 753 W | 718 W | −5 % | 1.790 W | +138 % | +11 % |
| Fachada E con ventana | 691 W | 664 W | −4 % | 1.706 W | +147 % | +11 % |
| Muro de hormigón 25 cm | 421 W | 381 W | −10 % | 756 W | +79 % | +15 % |
| Cubierta | 108 W | 145 W | +35 % | 159 W | +47 % | −8 % |
| Ganancias internas | 956 W | 983 W | +3 % | 1.110 W | +16 % | — |
| Local completo | 1.895 W | 2.101 W | **+11 %** | 3.299 W | +74 % | +12 % |

Tabla completa y cómo reproducirla en [`validacion/`](validacion).

## Hoja de ruta

Ver [`ROADMAP.md`](ROADMAP.md). En resumen:

1. **v0.1** — un local, YAML → informe (✅ hecho)
2. **v0.2** — cerramientos por capas, método dinámico, librerías validadas, validación con EnergyPlus (✅ hecho)
3. **v0.3** — datos españoles (Guía IDAE, Catálogo CTE), métodos completos UNE-EN 12831-1 y 52016-1, salida Excel/Word
4. **v0.4** — varios locales y zonas, simultaneidad
5. **v0.5** — interfaz: paleta en GstarCAD/AutoCAD, plugin IngeTrazo
6. **v1.0** — exportación a EnergyPlus/DesignBuilder (gbXML) para casos complejos

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

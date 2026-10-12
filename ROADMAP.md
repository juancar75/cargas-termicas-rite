# Hoja de ruta

Principio: **aprovechar el software existente** y programar sólo lo que falta.
El núcleo de cálculo es una librería Python independiente; las interfaces
(CAD, IngeTrazo, web) son capas encima.

## v0.1 — Núcleo mínimo ✅
- Un local descrito en YAML.
- Calefacción estacionaria y refrigeración horaria (sensible + latente).
- Comprobaciones RITE básicas, informe Markdown y CSV horario.
- Tests y CI.

## v0.2 — Datos españoles
- [ ] Base de datos climática con los valores de la Guía IDAE (localidad → condiciones).
- [ ] Biblioteca de cerramientos y huecos tipo (Catálogo de Elementos Constructivos del CTE).
- [ ] Lectura del XML de registro de CE3X/HULC para importar cerramientos reales.
- [ ] Salida a Excel y Word para la memoria técnica.
- [ ] Sombras de voladizos y retranqueos.

## v0.3 — Varios locales
- [ ] Varios locales y zonas, carga simultánea del edificio.
- [ ] Factores de almacenamiento (radiación, iluminación).
- [ ] Comparativa automática con resultados de HAP / DesignBuilder.

## v0.4 — Interfaces
- [ ] Paleta para GstarCAD / AutoCAD (.NET): detección de recintos desde los textos de
      nombre de local, datos guardados en el DWG, etiquetas de resultados en el plano.
      Ver [`integraciones/`](integraciones).
- [ ] Plugin para [IngeTrazo](https://github.com/ingelibre/ingetrazo).
- [ ] Interfaz sencilla de escritorio o web para quien no use CAD.

## v1.0 — Motor avanzado opcional
- [ ] Exportar el modelo a [Honeybee](https://github.com/ladybug-tools/honeybee-energy)
      y calcular con EnergyPlus (días de diseño, cargas por componentes).
- [ ] Exportar gbXML / OSM para DesignBuilder y OpenStudio.
- [ ] Paquete `honeybee_energy_cte_standards` con usos y cerramientos españoles.
- [ ] Validación cruzada método simplificado ↔ EnergyPlus en casos de referencia.

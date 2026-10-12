# Hoja de ruta

Principio: **aprovechar el software existente** y programar sólo lo que falta.
El núcleo de cálculo es una librería Python independiente; las interfaces
(CAD, IngeTrazo, web) son capas encima.

## v0.1 — Núcleo mínimo ✅
- Un local descrito en YAML.
- Calefacción estacionaria y refrigeración horaria (sensible + latente).
- Comprobaciones RITE básicas, informe Markdown y CSV horario.
- Tests y CI.

## v0.2 — Base técnica validada ✅
- Cerramientos por capas: U (UNE-EN ISO 6946) y amortiguamiento/desfase (UNE-EN ISO 13786).
- Método dinámico de refrigeración (red de nodos, almacenamiento en la masa del local).
- Librerías validadas: CoolProp (psicrometría), pvlib (solar, Perez, IAM de vidrios).
- Propiedades reales del aire según altitud.
- Validación automática contra EnergyPlus 26.1 en 9 casos, también en CI.

## v0.3 — Normativa española completa
- [ ] Ajustar a los textos de UNE-EN 12831-1, UNE-EN ISO 52016-1, 6946, 13786, 13370 y 13789
      (ver [`docs/normativa.md`](docs/normativa.md)).
- [x] Puentes térmicos por ψ·L con los tipos de UNE-EN ISO 14683.
- [ ] Valores ψ por defecto del DA DB-HE/3.
- [x] Soleras (ISO 13370) y espacios no acondicionados (factor b) según el DA DB-HE/1.
- [ ] Muros enterrados (ISO 13370, 9.3.3).
- [ ] Base de datos climática con los valores de la Guía IDAE (localidad → condiciones).
- [x] Biblioteca de materiales, soluciones, vidrios y marcos del catálogo del CTE.
- [ ] Lectura del XML de registro de CE3X/HULC para importar cerramientos reales.
- [ ] Salida a Excel y Word para la memoria técnica.
- [ ] Sombras de voladizos y retranqueos.

## v0.4 — Varios locales
- [ ] Varios locales y zonas, carga simultánea del edificio.
- [ ] Factores de almacenamiento (radiación, iluminación).
- [ ] Comparativa automática con resultados de HAP / DesignBuilder.

## v0.5 — Interfaces
- [ ] Paleta para GstarCAD / AutoCAD (.NET): detección de recintos desde los textos de
      nombre de local, datos guardados en el DWG, etiquetas de resultados en el plano.
      Ver [`integraciones/`](integraciones).
- [ ] Plugin para [IngeTrazo](https://github.com/ingelibre/ingetrazo).
- [ ] Interfaz sencilla de escritorio o web para quien no use CAD.

## v1.0 — Exportación a herramientas avanzadas
- [ ] Exportar el modelo a [Honeybee](https://github.com/ladybug-tools/honeybee-energy) /
      EnergyPlus para casos complejos (el generador de IDF de `validacion/` es la base).
- [ ] Exportar gbXML / OSM para DesignBuilder y OpenStudio.
- [ ] Paquete `honeybee_energy_cte_standards` con usos y cerramientos españoles.
- [ ] Validación cruzada método simplificado ↔ EnergyPlus en casos de referencia.

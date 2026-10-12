# Integraciones

Capas opcionales sobre el núcleo `cargas_rite`. Ninguna es necesaria para el cálculo.

| Carpeta | Objetivo | Estado |
|---|---|---|
| `gstarcad/` | Paleta .NET para GstarCAD/AutoCAD: detectar recintos, editar datos por local, etiquetar resultados en el plano | Diseño |
| `ingetrazo/` | Plugin Python para el modelador [IngeTrazo](https://github.com/ingelibre/ingetrazo) | Pendiente |
| `honeybee/` | Exportar a Honeybee/OpenStudio, calcular con EnergyPlus y generar gbXML para DesignBuilder | Pendiente |

## Diseño previsto para GstarCAD

- Cada local es una polilínea cerrada en la capa `CLIMA-RECINTO`; sus datos (uso,
  altura, ocupación…) se guardan como XData en la propia polilínea.
- Detección automática desde los textos de nombre de local (contorno tipo `BOUNDARY`),
  cerrando los huecos de puerta.
- Convenio de geometría: muros exteriores por la cara exterior, particiones por el eje,
  alturas de suelo a suelo. Se guarda también la superficie útil.
- La paleta genera el YAML de `cargas_rite`, llama al motor y devuelve los resultados
  como etiquetas y tabla en el dibujo.

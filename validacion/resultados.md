# Validación contra EnergyPlus

EnergyPlus, Version 26.1.0-6f2e40d102. Clima: Madrid (valores ilustrativos), día de diseño con modelo de cielo ASHRAE.

| Caso | E+ W | Dinámico W | Desv. | Simplificado W | Desv. | Hora punta oficial (E+ / din.) | Calef. E+ W | Calef. propio W | Desv. |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Fachada S ligera con ventana 3,6 m² | 380 | 459 | +21 % | 885 | +133 % | 15:40 / 16:00 | 373 | 413 | +11 % |
| Fachada O ligera con ventana 3,6 m² | 753 | 718 | -5 % | 1790 | +138 % | 20:10 / 20:00 | 338 | 375 | +11 % |
| Fachada E ligera con ventana 3,6 m² | 691 | 664 | -4 % | 1706 | +147 % | 11:20 / 12:00 | 338 | 375 | +11 % |
| Muro S de hormigón 25 cm sin huecos | 421 | 381 | -10 % | 756 | +79 % | 22:10 / 22:00 | 1084 | 1242 | +15 % |
| Cubierta plana de hormigón con EPS 8 cm | 108 | 145 | +35 % | 159 | +47 % | 1:00 / 2:00 | 298 | 273 | -8 % |
| Sólo ocupantes, iluminación y equipos | 956 | 983 | +3 % | 1110 | +16 % | 21:00 / 21:00 | 0 | 0 | — |
| Tabique a local no climatizado (10 / 32 °C) | 57 | 71 | +24 % | 73 | +28 % | 1:00 / 24:00 | 92 | 114 | +24 % |
| Sólo infiltración 0,5 ren/h | 127 | 146 | +15 % | 146 | +15 % | 16:00 / 16:00 | 358 | 365 | +2 % |
| Escaparate S, cubierta, medianera y cargas internas | 1895 | 2101 | +11 % | 3299 | +74 % | 15:30 / 16:00 | 1116 | 1255 | +12 % |

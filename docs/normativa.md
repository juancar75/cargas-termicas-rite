# Normativa de referencia

Estado de cada referencia en el proyecto. Las normas UNE son de pago: el proyecto
**cita** sus apartados y aplica sus métodos, pero **no reproduce** sus tablas.

## Reglamentos y documentos públicos

| Documento | Uso en el proyecto | Estado |
|---|---|---|
| RITE (RD 1027/2007 y modificaciones) | Condiciones interiores IT 1.1.4.1.2, ventilación IT 1.1.4.2, recuperación IT 1.2.4.5.2, memoria técnica art. 15 | Aplicado |
| CTE DB-HE (2019, mod. 2022) | Parámetros de cerramientos | Parcial |
| DA DB-HE/1 Cálculo de parámetros característicos | Resistencias superficiales, U de huecos, soleras (ISO 13370), espacios no acondicionados (factor b) | Aplicado según la implementación del IETcc ([cteenergymodel](https://github.com/pachi/cteenergymodel)) — pendiente de cotejar con el PDF |
| DA DB-HE/3 Puentes térmicos | ψ por tipo de encuentro | Entrada ψ·L por tipo (ISO 14683) — **faltan los valores por defecto del documento** |
| Catálogo de Elementos Constructivos / BD de materiales del CTE (HULC) | 761 materiales, 425 soluciones, 258 vidrios, 17 marcos | Aplicado (`datos/catalogo_cte.json`) |
| Guía técnica IDAE *Condiciones climáticas exteriores de proyecto* | Base climática por localidad | **Pendiente**: hace falta el PDF ([MITECO](https://www.miteco.gob.es/es/energia/eficiencia/rite/documentos-reconocidos.html)) |

## Normas UNE (métodos)

| Norma | Uso | Estado |
|---|---|---|
| UNE-EN ISO 6946 | U de cerramientos, resistencias superficiales, h_ce = 4 + 4v | Rsi/Rse coinciden con la implementación del DA DB-HE/1 del IETcc; h_ce de memoria — **verificar con el texto** |
| UNE-EN ISO 13786 | Amortiguamiento y desfase | Aplicado y validado numéricamente — verificar con el texto |
| UNE-EN 12831-1 | Carga de calefacción | Simplificado — **falta el método completo** |
| UNE-EN ISO 52016-1 | Método horario de cargas (base del método dinámico) | Planteamiento general — **falta ajustar a la norma** |
| UNE-EN ISO 52010-1 | Radiación solar sobre superficies | Sustituido por pvlib (Perez) |
| UNE-EN ISO 13370 | Transmisión por el terreno | Soleras (9.1, 9.3.2, anexo B) vía DA DB-HE/1; muros enterrados pendientes |
| UNE-EN ISO 13789 | Factor b de espacios no acondicionados | Aplicado vía DA DB-HE/1 |
| UNE-EN ISO 10077-1 | U de ventanas (vidrio + marco + ψ del intercalario) | Simplificado como en el DA DB-HE/1 (sin ψ del intercalario) |
| UNE-EN 16798-1 | Parámetros del ambiente interior | Sólo si se usa en lugar del RITE |
| UNE-EN ISO 14683 | Tipos de puentes térmicos lineales | Aplicado (códigos R, B, C, IF, IW, GF, P, W, G) |

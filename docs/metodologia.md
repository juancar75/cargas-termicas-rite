# Metodología de cálculo

Notación: θ temperatura [°C], U transmitancia [W/(m²·K)], A área [m²],
V̇ caudal [m³/h], w humedad específica [g/kg aire seco].

Librerías de base (todas libres y ampliamente validadas):

| Tarea | Librería | Referencia |
|---|---|---|
| Psicrometría | [CoolProp](http://www.coolprop.org) (HumidAirProp) | ASHRAE RP-1485 |
| Posición solar | [pvlib](https://pvlib-python.readthedocs.io) | Algoritmo SPA del NREL |
| Radiación sobre superficies | pvlib | Cielo despejado ASHRAE o Ineichen; transposición de Perez |
| Ángulo de incidencia en vidrios | pvlib (`iam.physical`) | Fresnel + absorción |
| Referencia de validación | [EnergyPlus](https://energyplus.net) 26.1 | ANSI/ASHRAE 140 (BESTEST) |

## 1. Condiciones de proyecto

**Exteriores.** Las introduce el usuario. Fuente recomendada: Guía técnica IDAE
*Condiciones climáticas exteriores de proyecto*.

**Interiores.** RITE IT 1.1.4.1.2: verano 23–25 °C y 45–60 % HR; invierno 21–23 °C y
40–50 % HR. Se avisa si la temperatura queda fuera de rango.

**Aire exterior.** RITE IT 1.1.4.2.3: IDA1 20 dm³/s, IDA2 12,5, IDA3 8, IDA4 5 dm³/s por
persona. Si el caudal supera 0,5 m³/s sin recuperador, se avisa (IT 1.2.4.5.2).

**Propiedades del aire.** Los coeficientes de transporte ρ·c y ρ·h_fg se calculan con
CoolProp a la presión de la altitud del lugar y a la temperatura exterior de diseño.
A nivel del mar y 20 °C dan los clásicos 0,34 y 0,83; en Madrid (667 m) en verano
el aire es un ~13 % menos denso.

## 2. Cerramientos

**Transmitancia U** — UNE-EN ISO 6946, con las resistencias superficiales de su
tabla 7 (las mismas del DA DB-HE/1 del CTE): Rsi = 0,13 / 0,10 / 0,17 m²K/W para flujo
horizontal / ascendente / descendente; Rse = 0,04 m²K/W; hacia otro local Rse = Rsi.

**Propiedades dinámicas** — UNE-EN ISO 13786, método de la matriz de transferencia
(periodo 24 h). Da el factor de amortiguamiento f = |Y12|/U y el desfase φ. Validado
contra una simulación por diferencias finitas independiente (error < 0,5 % en f y
< 0,15 h en φ).

Cada cerramiento se puede dar por su U (y la inercia ligera/media/pesada), por capas
(de interior a exterior) o como una solución completa del catálogo del CTE. Cada capa
puede ser un material del catálogo (`material:` + `espesor:`) o propia (λ, ρ, c).

**Catálogo del CTE.** Base de datos de materiales y productos del CTE (la de HULC):
761 materiales, 425 soluciones constructivas, 258 vidrios y 17 marcos. Para los
vidrios, g⊥ = 0,85 · SC (convenio de HULC). Buscador:
`python -m cargas_rite.buscar <palabras>`.

**Huecos del catálogo.** U_H = (1 − FM)·U_vidrio + FM·U_marco (DA DB-HE/1).

**Soleras sobre el terreno** (`terreno:`). UNE-EN ISO 13370 vía DA DB-HE/1:
B' = A / (0,5·P), d_t = w + λ_g·(Rsi + Rf + Rse) con w = 0,30 m y λ_g = 2 W/mK;
U_bf por las ecuaciones (11) o (12) según d_t + z/2 frente a B', más el efecto del
aislamiento perimetral horizontal (anexo B). La temperatura del terreno es la media
anual exterior. En el método dinámico, el terreno se representa como una resistencia
adicional bajo la solera, de forma que la U coincide con la de la norma.

**Espacios no acondicionados** (`espacio_no_acondicionado:`). UNE-EN ISO 13789 vía
DA DB-HE/1: H_ue = ΣU·A + 0,33·n·V, b = H_ue / (H_iu + H_ue) y θu = θi − b·(θi − θe),
en invierno y en verano (sin ganancias en el espacio no acondicionado).

**Puentes térmicos** (`puentes_termicos:`). ψ·L por encuentro con los tipos de
UNE-EN ISO 14683. Si se indican, no se aplica el incremento global ΔU. Se consideran
sin inercia en verano.

## 3. Calefacción

Régimen estacionario (planteamiento UNE-EN 12831-1, simplificado), sin descontar
ganancias internas ni solares:

```
Φ_T,ext = Σ (U + ΔU_pt) · A · (θi − θe)        opacos exteriores
        + Σ U · A · (θi − θe)                  huecos
Φ_T,ady = Σ U · A · (θi − θady)                particiones, suelos (se ignora si < 0)
Φ_V     = ρc · V̇ · (1 − η_rec) · (θi − θe)
Φ_inf   = ρc · n · Vol · (θi − θe)
Φ_total = (Φ_T + Φ_V + Φ_inf) · (1 + mayoración)
```

## 4. Refrigeración

Se calcula el día 21 del mes de cálculo, hora a hora (hora oficial).

**Temperatura exterior.** `θe(h) = θs − OMD · X(h_est)`, perfil X de ASHRAE referido a
la hora estándar local (hora oficial − 1 en verano peninsular).

**Radiación solar.** Posición solar SPA; cielo despejado ASHRAE (constantes A, B, C,
como `ASHRAEClearSky` de EnergyPlus) o Ineichen con turbidez de Linke; transposición
anisótropa de Perez. En vidrios, la directa se multiplica por el modificador de
incidencia de Fresnel de cada hoja y la difusa por su media hemisférica (0,90 para
doble vidrio, coherente con el F_w = 0,90 del DA DB-HE/1).

### 4.1 Método dinámico (por defecto)

Balance térmico horario del local con una red de nodos (planteamiento de
UNE-EN ISO 52016-1 y EnergyPlus):

- cada elemento opaco se discretiza por capas en nodos con capacidad térmica
  (diferencias finitas implícitas, paso de 10 min, 12 días hasta régimen periódico);
- cara interior: convección con el aire (h_ci = 2,5 W/m²K) y radiación de onda larga
  con el resto de superficies a través de un nodo radiante (h_ri = 5,13 W/m²K);
- cara exterior: h_ce = 4 + 4·v (UNE-EN ISO 6946, anexo C; v = 2 m/s en verano por
  defecto), h_re = 4,14 W/m²K, radiación solar absorbida α·I y pérdida hacia el cielo
  F_sky·h_re·11 K;
- la radiación solar transmitida incide (directa) sobre el suelo y (difusa) se
  reparte por área; la parte radiante de las ganancias internas se reparte por área;
- el aire se mantiene a la consigna y la carga sensible es el calor que hay que
  extraerle.

El sistema es lineal: la carga se descompone exactamente por componentes
(superposición), lo que permite el desglose del informe.

Las superficies interiores sin pérdidas (tabiques, forjados entre locales
climatizados) se describen en `masas_interiores`. Si no se indican, se supone un
forjado de hormigón como suelo y techo, y se avisa.

### 4.2 Método simplificado (opcional, conservador)

Opacos: temperatura sol-aire y admitancias (ISO 13786):

```
θsa = θe + α · I / 17 − Δ            (Δ = 3,9 K en horizontal)
Q   = U · A · [ (θsa,m − θi) + f · (θsa(h − φ) − θsa,m) ]
```

Huecos: conducción + radiación **instantánea**, sin almacenamiento. Sobredimensiona
la carga solar entre un 70 y un 150 % (ver validación); sirve como cota superior.

### 4.3 Carga latente

Ocupantes en horario, ventilación en horario e infiltración 24 h:
`Q_l = ρ·h_fg · V̇ · (we − wi)`. Es instantánea en ambos métodos.

## 5. Validación

Ver [`validacion/resultados.md`](../validacion/resultados.md). Resumen frente a
EnergyPlus 26.1 en 9 casos de referencia:

- Refrigeración, método dinámico: entre −10 % y +35 % por caso aislado y +11 % en el
  local completo.
- Refrigeración, método simplificado: siempre por encima (+15 % a +147 %).
- Calefacción: entre −8 % y +24 %.

## 6. Limitaciones conocidas

- Un solo local; sin simultaneidad entre zonas.
- Sin sombras de voladizos ni obstáculos (sólo factor de sombra global Fs).
- Muros muy pesados aislados: el método dinámico da hasta un −10 % frente a
  EnergyPlus (diferencias en los coeficientes superficiales exteriores).
- Cubiertas en invierno: no se considera la radiación nocturna al cielo
  (−8 % frente a EnergyPlus), igual que UNE-EN 12831-1.
- Pendiente de revisar contra el texto de las normas UNE (ver
  [`normativa.md`](normativa.md)).

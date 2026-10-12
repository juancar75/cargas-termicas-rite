# Metodología de cálculo

Notación: θ temperatura [°C], U transmitancia [W/(m²·K)], A área [m²],
V̇ caudal [m³/h], w humedad específica [g/kg aire seco].

## 1. Condiciones de proyecto

**Exteriores.** Las introduce el usuario. Fuente recomendada: Guía técnica IDAE
*Condiciones climáticas exteriores de proyecto* (temperatura seca de invierno según
percentil, temperatura seca y húmeda coincidente de verano, oscilación media diaria).

**Interiores.** RITE IT 1.1.4.1.2: verano 23–25 °C y 45–60 % HR; invierno 21–23 °C y
40–50 % HR. Se avisa si la temperatura queda fuera de rango.

**Aire exterior.** RITE IT 1.1.4.2.3, caudal por persona según categoría:
IDA1 20 dm³/s, IDA2 12,5 dm³/s, IDA3 8 dm³/s, IDA4 5 dm³/s. Se puede imponer un
caudal propio. Si el caudal supera 0,5 m³/s sin recuperador, se avisa
(IT 1.2.4.5.2).

## 2. Calefacción

Régimen estacionario, sin descontar ganancias internas ni solares:

```
Φ_T,ext = Σ (U + ΔU_pt) · A · (θi − θe)        opacos exteriores
        + Σ U · A · (θi − θe)                  huecos
Φ_T,ady = Σ U · A · (θi − θady)                particiones, suelos (se ignora si < 0)
Φ_V     = 0,34 · V̇ · (1 − η_rec) · (θi − θe)
Φ_inf   = 0,34 · n · Vol · (θi − θe)
Φ_total = (Φ_T + Φ_V + Φ_inf) · (1 + mayoración)
```

ΔU_pt es un incremento global por puentes térmicos (por defecto 0,10 W/(m²·K)).

## 3. Refrigeración

Se calculan las 24 horas oficiales del día 21 del mes de cálculo y se toma la de
mayor carga total.

**Hora solar.** `hs = hora_oficial − diferencia_horaria + longitud/15` (se desprecia
la ecuación del tiempo).

**Temperatura exterior.** `θe(h) = θs − OMD · X(hs)`, con el perfil horario X de
ASHRAE (0 a las 15 h solares, 1 a las 5 h).

**Radiación solar.** Modelo de cielo despejado de ASHRAE con las constantes A, B, C
del día 21 de cada mes; directa + difusa + reflejada por el suelo (albedo 0,2).

**Opacos exteriores.** Temperatura sol-aire:

```
θsa = θe + α · I / 17 − Δ            (Δ = 3,9 K en horizontal, 0 en vertical)
Q   = U · A · [ (θsa,m − θi) + f · (θsa(h − φ) − θsa,m) ]
```

donde θsa,m es la media diaria, f el factor de amortiguamiento y φ el desfase (h).
Valores por defecto según inercia: ligera f=0,8 φ=3 h; media f=0,4 φ=7 h;
pesada f=0,2 φ=10 h. Se pueden indicar valores propios por cerramiento.

**Huecos.**

```
Q_cond  = U · A · (θe − θi)
Q_solar = A · (1 − FM) · g · Fs · I(h)
```

La ganancia solar se considera instantánea (sin factor de almacenamiento), lo que
queda del lado de la seguridad.

**Particiones.** `Q = U · A · (θady − θi)`, sólo si es positiva.

**Cargas internas** (en horario de ocupación): ocupantes (sensible y latente por
persona según actividad, tabla en `cargas_rite/datos/actividades.yaml`), iluminación
y equipos (W/m²).

**Aire exterior.**

```
Q_s = 0,34 · V̇ · (1 − η_rec) · (θe − θi)      ventilación en horario; infiltración 24 h
Q_l = 0,83 · V̇ · (we − wi)
```

## 4. Limitaciones conocidas (v0.1)

- Un solo local; sin simultaneidad entre zonas.
- Sin sombras de voladizos ni obstáculos (sólo factor de sombra global Fs).
- Sin factores de almacenamiento para radiación ni iluminación.
- Huecos interiores y puertas se introducen como cerramientos más.
- Condiciones climáticas introducidas a mano (base IDAE prevista para v0.2).

Propuestas de mejora: abrir una *issue*.

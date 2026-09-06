# Hallazgos de la puesta en marcha del Carril 1

**Fecha:** 2026-09-05 · **Alcance:** E1 → E2 → E3 → E4, extremo a extremo
**Evidencia asociada:** `E03_carril1_e1_a_e4.json`

La primera corrida completa del Carril 1 terminó con los tres expedientes
procesados, la bitácora escrita y un resumen que parecía correcto. No lo era.
Este documento registra los seis defectos que expuso, ordenados por gravedad y
no por el orden en que aparecieron.

Cuatro de los seis son de la misma familia que los del Carril 0: **el sistema no
fallaba, aprobaba**. Un guardrail que bloquea de más se descubre en la primera
corrida porque alguien se queja; uno que aprueba de más se descubre leyendo el
JSON con el diseño al lado.

| # | Síntoma observado | Causa raíz | Estado |
|---|---|---|---|
| 1 | O1 aprobó una carta **sin una sola cita** | El control se dejaba satisfacer por vacío | Corregido, con caso X8 |
| 2 | O1 verificó un encabezado como norma | La ingesta antepone la jerarquía al `texto_literal` | Corregido, con caso X9 |
| 3 | O1 verificó el título del artículo como norma | El prompt no decía cómo se cita una tabla | Corregido |
| 4 | O3 bloqueó una carta correcta | El universo de comparación era solo el copago | Corregido, con control negativo X10 |
| 5 | E1 devolvió `prestador_id: null` sobre un texto que lo traía | Campo descrito por su rol, no por su forma | Corregido, con brecha residual |
| 6 | Una carta de carril no-auto podía llegar a `E4` | La condición de borrador miraba el tipo y no la ruta | Corregido |

---

## 1 · «Las 0 citas coinciden carácter por carácter»

**Lo que se observó.** El expediente C3 —cesárea programada, afiliada con 220
días de carencia frente a los 300 que exige maternidad— produjo una carta de
`niega_administrativa` correcta en el fondo, con la causal redactada y el
número de días bien citado en prosa. Los seis controles salieron verdes. O1
declaró literalmente:

    O1 ✓ las 0 citas coinciden carácter por carácter

**Por qué es el defecto más grave de los seis.** No se manifiesta como un fallo
sino como un acierto. Un control que solo verifica *las citas que haya* es
trivialmente satisfecho por una carta que no cita nada, y una carta que no cita
nada es exactamente la que R2 prohíbe: *ninguna afirmación sobre la política sin
cita textual de la versión vigente*. Peor todavía, el camino de menor esfuerzo
para un modelo al que se le exige que sus citas sean verificables es **dejar de
citar**. El control, tal como estaba, premiaba esa salida.

Toda carta de esta mesa afirma algo sobre la política —autoriza según una tabla,
niega por una carencia, observa porque un protocolo exige un documento—, así que
ninguna puede salir sin al menos una cita verificada.

**Lo que se hizo.** `o1_citas_literales` recibió `exige_al_menos_una=True`:

```python
verificadas = len(citas) - len(fallidas)
sin_ninguna  = exige_al_menos_una and verificadas == 0
paso = not fallidas and not huerfanas and not sin_ninguna
```

y la regla 2 del prompt de emisión pasó a decirlo sin rodeos: *«Conforme a la
política vigente» no es una cita: es una promesa de que existe una.*

El caso **X8** del banco lo fija: una carta cuya única referencia normativa es
esa frase debe ser bloqueada por O1.

## 2 · Un encabezado no es una norma

**Lo que se observó.** Una carta entrecomilló

    «Carencias y preexistencias > Periodos de carencia > Tabla de carencias por cobertura»

y O1 la aprobó. La cita existía literalmente en el corpus, carácter por carácter.

**Por qué.** La ingesta antepone la línea de jerarquía al `texto_literal` para
que cada fragmento se explique solo fuera de su documento. Es una buena decisión
de recuperación y abrió un agujero de verificación: la ruta de títulos está en la
**primera línea de todos los fragmentos**, es la cadena más fácil de encontrar y
copiar, y no sustenta nada. Un título dice dónde buscar la norma, no qué ordena.

**Lo que se hizo.** `recuperacion.cuerpo_citable()` devuelve el fragmento sin su
línea de jerarquía, y `verificar_cita_literal` busca solo ahí. El caso **X9**
—entrecomillar la ruta de títulos— queda como guarda de regresión.

## 3 · Cómo se cita una tabla

**Lo que se observó.** Cerrado el defecto anterior, C1 volvió a fallar O1 con
`citas_rechazadas: ['Tabla de carencias por cobertura']`. El modelo había bajado
un nivel: ya no citaba la ruta completa, citaba el **nombre del artículo**, que
sigue siendo un sufijo de la jerarquía y sigue sin ser norma.

**Por qué.** La cláusula que resuelve C1 es una tabla Markdown. El prompt decía
*«cita la frase o la fila de la tabla»* sin mostrar qué aspecto tiene una fila
entrecomillada, y ante la duda el modelo nombraba la tabla y parafraseaba su
contenido —que es lo que uno haría al escribir una carta de verdad.

**Lo que se hizo.** El prompt muestra la forma exacta, con las barras
verticales incluidas, y declara el costo de estilo en vez de esconderlo:

> Cuando la cláusula es una tabla, la norma **es la fila**, y se cita la fila
> entera con sus barras verticales, así:
> «| Hospitalización y cirugía | 60 días | Los tres planes |».
> Queda algo áspero en una carta, y es preferible a parafrasearla: el afiliado
> puede contrastar esa línea contra el documento, y una paráfrasis no.

La carta resultante de C1 dice *«el periodo de carencia para hospitalización y
cirugía es de «| Hospitalización y cirugía | 60 días | Los tres planes |»»*.
**Se lee mal, y es correcta.** Queda anotado como deuda de presentación —la capa
de plantilla puede renderizar la fila como texto sin perder la trazabilidad—, no
como deuda de control.

## 4 · Prohibirle a la carta que explique su aritmética

**Lo que se observó.** O3 bloqueó una carta de C1 que era correcta. El motor
calculó S/ 1,210.00 de copago; la carta lo decía bien y además explicaba que
S/ 600.00 de ese total corresponden al deducible anual del plan VIT-INT. O3 vio
un monto que no era el copago y bloqueó la emisión.

**Por qué.** El universo de comparación era un solo número. Pero el motor no
calcula un número: calcula un desglose, y la carta que solo da el resultado sin
el razonamiento es justo la que el afiliado hoy no entiende —es el dolor P5 del
AS-IS, no una virtud de control.

**Lo que se hizo.** El universo de comparación pasó a ser todo el
`copago_desglose`, excluyendo las claves de porcentaje —`coaseguro_pct` es un
porcentaje, no soles—:

```python
calculados = {Decimal(str(copago_motor))} if copago_motor is not None else set()
for k, v in (desglose or {}).items():
    if "pct" in k:
        continue
    ...
ajenos = [m for m in montos if m not in calculados]
```

Un relajamiento de control se paga con un caso que impida que el relajamiento
siga creciendo en silencio. **X10** es ese caso, y es el único del banco que
**debe pasar**: una carta que explica el desglose correctamente. Sin él, «los
seis controles bloquean» no distingue un guardrail que discrimina de uno que
rechaza todo.

## 5 · Un campo descrito por su rol es un campo que hay que interpretar

**Lo que se observó.** E1 devolvió `prestador_id: null` sobre un correo cuya
primera línea decía *«Clínica San Felipe (PRE-0031)»*.

**Por qué.** De los cinco campos obligatorios, era el único descrito en el
prompt por lo que significa —*«el identificador de la clínica tal como
aparece»*— y no por su forma. El modelo no se equivocó al leer: se equivocó al
decidir qué contaba como identificador. Un campo descrito por su rol es un campo
que el modelo tiene que interpretar; uno descrito por su forma es un campo que
solo tiene que encontrar.

Al arreglarlo apareció un segundo defecto detrás: el campo estaba en
`CAMPOS_OBLIGATORIOS` y **no tenía validador**, así que la primera extracción
que lo devolviera con valor reventaba con `KeyError`. Nunca se había ejecutado
esa rama.

**Lo que se hizo.** El prompt describe la forma —`"PRE-" y cuatro dígitos; suele
ir entre paréntesis junto al nombre de la clínica`— y se añadió el validador
correspondiente.

**Brecha residual, declarada.** `prestador_id` es el único campo obligatorio sin
tabla contra la cual contrastarlo: el MVP no tiene registro de prestadores, así
que solo se verifica la **forma**. Un prestador con el código mal escrito entra
al expediente y solo se detecta al facturar. El diseño lo resuelve leyendo el
maestro de prestadores del core (ADR-18), que en el MVP no está montado. Por eso
el código distingue explícitamente los campos con catálogo de los que solo tienen
forma:

```python
CON_CATALOGO = ("procedimiento_codigo", "afiliado_ref", "dx_cie10")
nota = "" if ok else ("no existe en el catálogo vigente" if nombre in CON_CATALOGO
                      else "no tiene la forma esperada")
```

`validado_catalogo` de ese campo **dice menos** que el de los otros cuatro, y la
evidencia tiene que poder leerse sabiéndolo.

## 6 · La ruta manda igual que el tipo

**Lo que se observó.** La condición que decide si una carta es borrador miraba
solo el tipo de carta y si el guardrail la aprobó. Una carta de observación es
correcta y puede aprobar los seis controles; con esa condición, la de C2 —que va
al carril del agente— habría quedado lista para emitirse.

**Por qué importa.** La máquina de estados no tiene `agente -> E4` ni
`hitl -> E4`. Un expediente en el carril del agente o en la cola de la mesa
**todavía no es de nadie**: falta que una persona lo mueva. Emitir desde ahí no
es un atajo de implementación, es saltarse ADR-10.

**Lo que se hizo.**

```python
borrador = tipo.startswith("niega") or ruta != "auto" or not res.aprobado
```

---

## Estado de la corrida final

| Caso | Ruta | Carta | Estado final | e2e |
|---|---|---|---|---|
| C1 · colecistectomía, 427 días de carencia | `auto` | `autoriza` | **emitida** | 17,195 ms |
| C2 · artroscopia, falta informe de terapia | `agente` | `observa` | `agente` | 12,040 ms |
| C3 · cesárea, 220 días frente a 300 | `hitl` | `niega_administrativa` | `hitl` | 10,231 ms |

- **Fundamentos que no resuelven: 0** de los 10 pares del motor.
- **Banco X: 10/10**, incluidos X9 (encabezado) y X10 (control negativo).
- **Idempotencia:** el reenvío del mismo correo devuelve el mismo expediente y
  no reprocesa.
- **14 eventos de estado**, **3 citas verificadas en base**, **1 carta emitida**
  —solo el carril auto emite, y solo un caso fue auto—.
- **Costo:** US$ 0.018065 en tres expedientes ≈ **S/ 0.0226 por solicitud** de
  modelos. La cifra de diseño (S/ 0.86) incluye infraestructura, que aquí no se
  paga.

**J3 —adjudicación p95 < 90 s— se cumple con tres órdenes de magnitud de
margen: 120–125 ms.** No es mérito de optimización: es la consecuencia directa
de R1. La decisión no pasa por un modelo, así que no cuesta ni espera. La fila
`adjudicacion` de `metrica_costo` registra **US$ 0.000000 en 3 llamadas**, y esa
fila en cero es la prueba, no un hueco en los datos.

**J4 —extremo a extremo p95 < 5 min— se cumple**: el peor caso es 17.2 s. El
reparto es guardrail 0.7–2.8 s + E1 2.7–5.8 s + E2 0.12 s + E4 2.1–3.2 s, más
la escritura en base. Igual que en el Carril 0, casi todo el reloj es viaje de
red a nubes fuera del país.

## Lo que estos seis defectos tienen en común

Cinco de los seis viven en la frontera entre lo que el modelo produce y lo que
el sistema acepta, y ninguno se manifestó como una excepción. Los tres primeros
son la misma pregunta hecha tres veces —**¿qué cuenta como cita?**— y cada
respuesta parcial dejó al descubierto la siguiente: primero «que las citas sean
literales», que se satisface no citando; después «que haya al menos una», que se
satisface citando el encabezado; después «que no sea el encabezado», que se
satisface citando el título del artículo.

Ese patrón es el argumento a favor del banco X. Un guardrail no se demuestra con
cartas correctas: una carta correcta prueba que el guardrail no estorba, no que
sirva. Cada defecto de esta lista quedó fijado con un caso que lo reproduce, de
modo que la próxima vez que alguien afloje un control para hacer pasar una carta,
el banco lo diga.

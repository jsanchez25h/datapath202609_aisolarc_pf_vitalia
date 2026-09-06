# Hallazgos que solo aparecieron cuando hubo pantalla

**Fecha:** 2026-09-05 · **Alcance:** `app-mesa`, las cinco pantallas sobre la API ya probada
**Evidencia asociada:** `E11_servicio_y_mesa.json`, `pantallas/P3`, `pantallas/P4a`, `pantallas/P5`

Al empezar esta etapa el Carril 0 y el Carril 1 estaban verdes: `prueba_carril1`
con 0 fallos, `prueba_motor` 3 de 3, `prueba_guardrail` 16 de 16 en detección y 0
de 4 en falsos positivos, `prueba_api` con sus cinco casos. La interfaz no se
construyó para encontrar defectos —se construyó porque la fase 2 pide una
interfaz final— y encontró tres, dos de ellos corregidos aquí.

Vale la pena decir por qué, porque no es casualidad. Una prueba comprueba lo que
alguien pensó en comprobar; una pantalla pone todo el estado junto, al lado, en
la misma hoja, y ahí el ojo compara cosas que ninguna aserción compara. Los dos
defectos corregidos se vieron **leyendo una captura**, no leyendo un log.

| # | Síntoma observado | Causa raíz | Estado |
|---|---|---|---|
| 1 | O1 reprobó una carta correcta | La expresión que recorta las citas no emparejaba las comillas | Corregido, con control negativo X11 |
| 2 | El panel decía «aciertos de caché —» | El Carril 0 gastaba sin escribir en `metrica_costo` | Corregido, con caso F |
| 3 | Un diagnóstico de vesícula sobre una hernia | Nada compara el dx con el procedimiento | Brecha declarada, no corregida |

---

## 1 · Una comilla suelta le fabricó una cita al modelo

**Lo que se observó.** La captura `P4a` de la primera tanda mostraba un
expediente de ruta `hitl` con la carta reprobada por **O1**. El cuerpo era
correcto: la afiliación de Víctor Hugo Paredes Lino estaba suspendida por mora,
la carta lo decía y citaba la cláusula que lo sostiene, `facturacion_y_pagos-
v2026_09-c08`. La cita estaba bien copiada. O1 la reprobaba igual.

El texto, abreviado:

    …su afiliación se encuentra en estado "suspendido". Según nuestra política,
    «vencido el periodo de gracia sin que se regularice el pago…» (Facturación
    y pagos > Mora y rehabilitación).

**La causa.** La expresión regular que recorta las citas del cuerpo era, en dos
archivos distintos, la misma copia:

```python
CITA = re.compile(r"[«\"“]([^»\"”]{15,})[»\"”]")
```

Una clase de caracteres para abrir y otra para cerrar, sin ninguna relación
entre ellas. La comilla recta que **cierra** `"suspendido"` sirve de apertura; la
clase interior excluye `»`, `"` y `”` pero **no excluye `«`**, así que el tramo
capturado se tragó la comilla angular de apertura y siguió corriendo hasta el
`»` de la cita verdadera. Resultado: un texto de sesenta palabras que empieza en
mitad de una frase de la carta y termina en mitad de la cláusula, y que no está
—no puede estar— en ningún fragmento del corpus.

O1 hizo exactamente lo que debía: reportó que ese texto no tiene fragmento de
origen. **El control acertaba y el insumo mentía.** Que la palabra entrecomillada
sea `"suspendido"` es incidental; lo estructural es que basta una comilla recta
en la prosa —una palabra citada, un nombre de estado, un `"programado"`— para
que la siguiente cita legítima de la carta quede inutilizada.

Es la misma familia del defecto 4 de `E01` —O3 bloqueando una carta correcta
porque su universo de comparación estaba mal elegido—, ahora en O1. Y tiene la
gravedad al revés que los seis de aquel documento: aquellos aprobaban de más,
este bloquea de más. Un guardrail que bloquea de más se paga en la mesa, en
minutos de analista sobre cartas que estaban bien, y es la forma más rápida de
que la mesa deje de usarlo.

**Lo que se hizo.** La expresión se mudó a `comun/recuperacion.py`, junto a
`verificar_cita_literal`, que es quien la consume, y pasó a emparejar sus
delimitadores:

```python
_CITAS = re.compile(r"«([^«»]{15,})»|“([^“”«»]{15,})”|\"([^\"«»“”]{15,})\"")

def citas_de(texto: str) -> list[str]:
    """Los tramos entrecomillados de un texto, en orden de aparición."""
    return [a or b or c for a, b, c in _CITAS.findall(texto)]
```

Cada alternativa abre y cierra con el mismo tipo de comilla y excluye del interior
**todas** las demás, así que un tramo no puede saltar de una comilla a otra. Que
estuviera duplicada en `flujo/consulta_n1.py` y `flujo/emision_e4.py` era parte
del problema: arreglarla en uno habría dejado el otro carril roto y la corrida
habría seguido saliendo verde.

El caso **X11** del banco de `prueba_carril1` lo fija, y es un control negativo:
una carta con una palabra entrecomillada corriente *además* de su cita correcta,
que el guardrail tiene que **dejar pasar**.

    OK   X11 · O1 · debe pasar · bloquearon —

---

## 2 · El carril que lleva el 41% del volumen no aparecía en la cuenta

**Lo que se observó.** La captura `P5` mostraba, en la tarjeta del caché,
«aciertos de caché —». No cero: un guion, porque no había ni una sola lectura
sobre la que calcular el porcentaje. La tabla de costo por tramo tenía
`extraccion`, `adjudicacion` y `emision`, y ninguna fila `n1`.

**La causa.** El único sitio que escribe en `metrica_costo` es
`repositorio.registrar_costo`, y `flujo/consulta_n1.py` nunca lo llamaba. El
Carril 0 pagaba embeddings, pagaba generación y ahorraba con el caché sin dejar
constancia de nada.

Los dos efectos son distintos y los dos importan:

- **El costo por solicitud del panel estaba mal por debajo.** Es el número que
  se compara contra el S/ 0.86 del caso de negocio, y le faltaba justo el carril
  que el caso dice que atiende el 41% de las llamadas.
- **El hit-rate del caché era vacío por construcción.** La ventana de
  `consultas.panel()` es `span IN ('n1', 'recuperacion')` y ninguna fila tenía
  esos spans, así que la consulta no devolvía «0%»: devolvía nada. La sesión 02
  del curso es, entera, sobre ese indicador. `prueba_n1` sí lo medía —40.0% de
  ahorro— pero lo escribía en su propio JSON. **Un ahorro que solo está en el
  archivo de una prueba no es un indicador de operación**, porque el supervisor
  no lee ese archivo: lee el panel.

**Lo que se hizo.** `responder()` acepta ahora una conexión opcional y anota los
tres desenlaces. `solicitud_id` va en NULL —la columna es anulable en el esquema
justamente para esto— y esa fila en NULL es la que dice que hubo una consulta
que no llegó a ser un expediente.

Los desenlaces no comparten span. La consulta que el guardrail de entrada
bloqueó se anota como `n1_bloqueada` y no como `n1`, porque nunca llegó a
preguntarle al caché: contarla como lectura rebajaría el indicador con filas que
no podían acertar. Es el mismo argumento que ya excluía a la extracción de esa
ventana.

El caso **F** de `prueba_api` lo fija sobre las dos llamadas del caso E —una
paga y una servida del caché—, y mide el delta contra el estado previo de la
base, no el total, porque la base es acumulativa entre corridas:

    OK   F · el Carril 0 escribe su costo → 2 lecturas, 1 aciertos, hit-rate 0.5

En la captura `P5` corregida la tarjeta dice **50%** y la tabla de tramos tiene
su fila `n1` con 2 llamadas y US$ 0.000231.

---

## 3 · Nada comprueba que el diagnóstico tenga que ver con el procedimiento

**Lo que se observó.** Al poblar la bandeja para las capturas se ingresaron dos
solicitudes cuyo texto emparejaba mal el código y la descripción. El sistema las
abrió sin objetar nada, y la captura `P3` las muestra tal cual:

| Expediente | Procedimiento | Dx |
|---|---|---|
| `SOL-1f42f948834b` | Hernioplastía inguinal con malla · PRC-1180 | K80.2 · cálculo de vesícula |
| `SOL-984f3cec0cd9` | Colecistectomía laparoscópica · PRC-4712 | M23.2 · lesión de menisco |

El error de origen fue del redactor del correo de prueba —de quien esto
escribe—, no del sistema. Pero que el sistema no lo note es un hallazgo, y las
dos filas se dejan en la bandeja en lugar de borrarse: `evento_estado` es
*append-only* por regla de base de datos, y borrar expedientes para que una
captura quede más limpia es justamente lo que el veto **V2** existe para impedir.
La evidencia dice lo que pasó.

**La causa.** E1 valida **campo por campo**: `dx_cie10` contra
`catalogo_cie10`, `procedimiento_codigo` contra `catalogo_procedimiento`. Los dos
existen, los dos pasan. No hay ninguna tabla que relacione un diagnóstico con los
procedimientos que puede sustentar, así que no hay nada contra qué contrastar la
**pareja**. Es la misma forma de brecha que el defecto 5 de `E01` dejó abierta
para `prestador_id`: un campo cuya validación es todo lo que su catálogo permite,
y su catálogo no cubre lo que haría falta.

**Por qué no se corrige en el MVP.** La tabla dx↔procedimiento no es un detalle
de implementación: es criterio clínico, la escribe un médico auditor y su
contenido decide autorizaciones. Inventarla aquí sería exactamente lo que el
invariante **R3** prohíbe —una restricción de necesidad médica sin médico
detrás—, y hacerlo para que una captura se vea mejor sería peor todavía.

Queda declarada como brecha, en la misma línea que `prestador_id`: en producción
la pareja se valida contra el maestro de pertinencia de la EPS, y mientras ese
maestro no exista el sistema **no puede** afirmar que un expediente es
clínicamente coherente. Puede afirmar, y afirma, que cada uno de sus códigos
existe.

---

## Lo que los tres tienen en común

Los tres son fallos de **frontera**, no de lógica. Ninguno está dentro de una
función que hace mal su trabajo:

1. La expresión regular estaba entre el texto de la carta y el control que lo
   verifica; el control funcionaba.
2. La escritura de costo estaba entre un carril que gasta y una tabla que
   contabiliza; ambas funcionaban.
3. La validación cruzada estaría entre dos catálogos que, por separado, validan
   bien.

Es la razón de que las pruebas unitarias los dejaran pasar y una pantalla no: una
prueba se escribe mirando un componente, y una pantalla obliga a mirar la
costura. Es también el argumento de por qué la pantalla 4 —`P4a`, `P4b`— pone lo
determinista y lo interpretativo **uno al lado del otro y no uno debajo del
otro**. Una frontera que no se ve no se audita.

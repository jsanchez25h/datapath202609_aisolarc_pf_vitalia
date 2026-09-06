# Hallazgos de exponer el sistema como herramientas

**Fecha:** 2026-09-05 · **Alcance:** `mcp_vitalia` — cuatro skills, cinco versiones, seis ganchos
**Evidencia asociada:** `E13_mcp_skills_y_ganchos.json`, `E01_E02_router_y_cache.json`, `E11_servicio_y_mesa.json`

La capa MCP no añade capacidades: no hay una sola cosa que un agente pueda hacer
a través de ella que la mesa no pudiera hacer ya por la API. Lo que añade es un
**consumidor que no es nuestro**. La interfaz la usa un analista al que se le
puede explicar cómo funciona; una herramienta la usa un modelo al que no, y que
va a llamarla con argumentos que nadie previó, en un orden que nadie diseñó y
tantas veces como quiera.

Esa diferencia es la que produjo los hallazgos. Siete, en dos grupos: cuatro son
de la capa misma y tres estaban aguas arriba, en código compartido con la
interfaz y con el Carril 0, y llevaban tiempo ahí sin que ninguna prueba los
mirara.

| # | Síntoma observado | Causa raíz | Estado |
|---|---|---|---|
| 1 | N1 no encontraba la tabla de carencias al preguntar por un procedimiento | El corpus indexa **coberturas**; la gente pregunta por **procedimientos** | Corregido, con el catálogo como puente |
| 2 | El fragmento correcto quedaba séptimo | RRF con `k=60` sobre listas de 20 premia la presencia, no la posición | Corregido, `k=10`, medido |
| 3 | `relation "metrica_costo" does not exist` en una skill que sí la había leído | El pooler de Neon reasigna el backend entre transacciones | Corregido en el rol, no en la conexión |
| 4 | La subsanación caía a N5 **acertando** | El control leía la cita textual como si fuera parte de la petición | Corregido: se mide fuera de las citas |
| 5 | G5 no enmascaró un nombre que la skill conocía | Un detector estadístico necesita una frase; la salida de una herramienta no lo es | Corregido: la skill declara, el gancho retira |
| 6 | Una afirmación correcta sobre la política, sin una sola comilla | O1 no puede rechazar las citas que no existen: aprobaba por vacío | Corregido, R2 como control en N1 |
| 7 | El caso A de `prueba_api` fallaba o pasaba según qué expediente hubiera en cola | La expectativa ataba el resultado a un contexto que cambia | Corregido: A exige O1, A2 aísla O6 |

---

## 1 · El corpus indexa coberturas; la gente pregunta por procedimientos

**Lo que se observó.** El caso B —la primera llamada real a `consultar_politica`—
respondía «No tengo la cláusula que responde eso; la mesa de preautorización
puede confirmarlo». La consulta era la más ordinaria del dominio: *cuántos días
de carencia exige una colecistectomía*.

**Por qué.** La recuperación traía el artículo que explica **qué es** una
carencia, el que explica cómo se cuenta y el protocolo de la mesa. No traía
`carencias_y_preexistencias-v2026_09-c02`, que es la tabla donde está la
respuesta, y no la traía por una razón que se ve al leer la tabla: la fila dice
**«Hospitalización y cirugía · 60 días»**. En los 112 fragmentos del corpus no
aparece la palabra *colecistectomía* ni una sola vez, ni tenía por qué: una
póliza no lista procedimientos, lista coberturas. El prestador pregunta por lo
que va a operar; la norma habla de la familia a la que eso pertenece.

**Lo que se hizo.** No una lista de sinónimos escrita a mano —envejece mal y
nadie la mantiene—. El puente ya existía y estaba en producción: es
`motor.COBERTURA_DE`, la misma tabla con la que el motor determinista adjudica.
Se lee del catálogo de procedimientos, se cruza con esa tabla y se obtiene la
frase que la póliza sí usa:

```
colecistectomía → hospitalización y cirugía
artroscopia     → hospitalización y cirugía
cesárea         → maternidad y parto
artroplastía    → prótesis y órtesis
histerectomía   → hospitalización y cirugía
```

La variante con la cobertura se antepone a las demás en la expansión de la
consulta. Es *«el modelo propone, el catálogo dispone»* aplicado a la
recuperación: si el vocabulario del usuario y el de la norma no coinciden, el
que traduce entre los dos es el catálogo, no un diccionario paralelo.

---

## 2 · Un fragmento en seis listas malas le gana a uno bueno en cuatro

**Lo que se observó.** Corregido el puente, la tabla de carencias entraba en los
resultados, pero en séptimo lugar; el contexto se corta en cinco.

**Por qué.** La fusión de las listas densa y BM25 se hacía con Reciprocal Rank
Fusion y la constante canónica `k = 60`. Esa constante viene de las corridas de
TREC, donde cada lista trae **mil documentos**: con mil, `k = 60` aplana con
razón, porque la diferencia entre el puesto 300 y el 700 no significa gran cosa.
Aquí cada lista trae veinte. Con `k = 60`, el aporte del primer puesto es
`1/61 = 0.0164` y el del puesto veinte `1/80 = 0.0125`: **24% de diferencia entre
ser el mejor y ser el último**. Un fragmento mediocre que aparece en seis
variantes de la consulta le gana a uno excelente que aparece en cuatro. RRF
dejaba de medir posición y medía presencia.

**Lo que se hizo.** `k = 10`, con la medición delante y no como preferencia:

| | posición de `carencias_y_preexistencias-c02` |
|---|---|
| `k = 60` | fuera de los cinco |
| `k = 10` | **segunda** |

Se comprobó además que las otras tres consultas del banco no se movían. La que
sí cambió, en el quinto puesto, destapó el hallazgo 6.

---

## 3 · El `SET` sobrevive a la sesión lógica, no al pooler

**Lo que se observó.** Una skill leía la base sin problema, hacía una llamada al
modelo y, al volver a escribir, fallaba con `UndefinedTable: relation
"metrica_costo" does not exist`. La tabla existe. Sobre una conexión recién
abierta, `SHOW search_path` devolvía `vitalia_mvp, public`.

**Por qué.** El endpoint es el **pooler** de Neon. El pooler reasigna el backend
físico entre transacciones, y el `SET search_path` que hacía `conexion_pg()` vive
en el backend, no en la conexión lógica. La API nunca lo notó porque abre y
cierra conexión dentro de la misma petición; un servidor de herramientas sostiene
la conexión a través de una llamada al modelo, que dura segundos, y en ese hueco
cambia el backend debajo.

El primer arreglo —pasar `options=-c search_path=…` en la conexión— lo rechaza el
propio Neon: *«unsupported startup parameter in options: search_path»*.

**Lo que se hizo.** Mover el estado a donde el pooler no puede perderlo:

```sql
ALTER ROLE neondb_owner IN DATABASE neondb SET search_path TO vitalia_mvp, public;
```

El `SET` por conexión se dejó como red de seguridad para cualquier entorno donde
el rol no se haya podido tocar, y el porqué quedó escrito en el docstring de
`conexion_pg`, que es donde lo va a leer quien se tropiece con lo mismo.

---

## 4 · El control leyó la cita como si fuera la petición

**Lo que se observó.** La skill que redacta la subsanación —la única que llama al
modelo para escribir— caía sistemáticamente a la plantilla N5 con este error:

```
RuntimeError: el modelo alteró la lista determinista:
el mensaje pide documentos que ya estaban adjuntos: informe_medico
```

El mensaje del modelo era **correcto**. Pedía exactamente el documento que
faltaba y ninguno más.

**Por qué.** El control compara la lista de documentos que el motor calculó con
los nombres de documento que aparecen en el texto. Y el texto, por mandato,
incluye la cita textual del artículo del protocolo… que enumera **todos** los
documentos exigibles, incluido el que ya estaba adjunto. El control estaba
midiendo la norma citada en lugar de la petición hecha.

Lo peligroso no es el falso positivo: es que **no se veía desde fuera**. La
cadena de respaldo hacía su trabajo, la plantilla N5 producía un mensaje
correcto, el expediente avanzaba. El sistema respondía bien y tiraba a la basura
una llamada pagada al modelo en cada intento. *La cadena de respaldo es la
escalera de degradación N0–N5, y una degradación que nadie ve es un gasto que
nadie audita.*

**Lo que se hizo.** `_fuera_de_cita()`: se miden los nombres de documento sobre
el texto **sin lo entrecomillado**. Lo que el mensaje pide es lo que el redactor
escribe; lo que la norma dice es contexto, no petición.

---

## 5 · El detector de PII necesita una frase; la respuesta de una herramienta no lo es

**Lo que se observó.** El gancho G5 —O5, sin PII fuera de destino— dejaba pasar
íntegro el nombre del afiliado en la salida de `estado_expediente`.

**Por qué.** Medido con el mismo detector y el mismo nombre, en dos textos:

| texto | resultado |
|---|---|
| «La paciente Rosa Milagros Quispe Ayala solicita una cirugía» | `PERSON`, confianza **0.85** |
| «Expediente SOL-… de Rosa Milagros Quispe Ayala (AF-100234), Cesárea programada. Estado: hitl.» | **`[]`** |

El reconocedor de entidades es un modelo de lenguaje pequeño y necesita
estructura gramatical alrededor. La salida de una herramienta no tiene sintaxis:
es una ficha, campos pegados con paréntesis y puntos. Justo el formato en el que
el detector no ve nada.

**Lo que se hizo.** El caso es que **la skill sabe** cuál es el nombre: lo acaba
de leer de la base. No hacía falta que nadie lo adivinara. La skill lo declara en
un campo de servicio `_pii`, el gancho lo retira por igualdad de cadena —una
certeza, no una probabilidad— y el servidor borra el campo antes de responder. El
detector se queda, ejecutándose siempre, para lo que la skill no sabe que es un
dato personal: **un detector estadístico es la red, no la regla.**

---

## 6 · Una afirmación sobre la política sin una sola comilla

**Lo que se observó.** Después de tocar la recuperación, el banco del Carril 0
bajó de 2 aciertos de caché sobre 5 a 0. La causa inmediata era conocida: N1 solo
cachea una respuesta cuyas citas pasaron O1, y esta respuesta no tenía ninguna.

La respuesta era esta, y es **correcta**:

> La cobertura de maternidad tiene un periodo de carencia de 300 días calendario
> contados desde el inicio de vigencia.
> FUENTES: carencias_y_preexistencias-v2026_09-c03

Correcta, con la fuente bien declarada, y sin una sola comilla. Es exactamente lo
que la regla 2 del prompt prohíbe, y **la respuesta salía al usuario tal cual**.

**Por qué, en dos capas.**

La primera fue una sorpresa. Con temperatura 0, el modelo omitía las comillas
**6 de 6 veces**; no era azar. Con el mismo prompt, la misma pregunta y un juego
de fragmentos que solo cambiaba **en el quinto** —un fragmento que la respuesta
ni usa— las ponía. El cumplimiento de una regla del prompt dependía de algo
completamente ajeno a la pregunta. Reforzar la regla en el sistema subió el
cumplimiento de 5 sobre 7 a 6 sobre 7. No a 7.

La segunda es la que importa. **O1 solo puede rechazar las citas que existen.**
Si el modelo no entrecomilla nada, no hay nada que verificar, el control recorre
una lista vacía y aprueba. Es el mismo agujero que en la emisión se había cerrado
con `exige_al_menos_una=True`, y en el Carril 0 —el que atiende el 41% del
volumen— estaba abierto desde el principio. El invariante **R2** dice que ninguna
afirmación sobre política sale sin cita textual de la versión vigente, y durante
todo el MVP eso fue una instrucción en un prompt, no un control.

**Lo que se hizo.** R2 pasa a ser código: si no sobrevivió ninguna cita y el
texto no es ya la frase de «no tengo la cláusula», la respuesta **se sustituye**
por esa frase. Se pierde una respuesta correcta, y se pierde a propósito: entre
devolver una afirmación sobre la póliza que nadie puede rastrear hasta un
artículo y decir que hay que preguntarle a la mesa, el caso ya eligió —es la
asimetría del error, el veto V1—.

Con las dos capas, el banco vuelve a **2 aciertos sobre 5, 0 falsos aciertos
sobre 3 cuasi-aciertos y 40.0% menos de costo**, ahora con **10 citas verificadas
y 0 rechazadas** en lugar de las 8 de la corrida anterior.

---

## 7 · Una prueba que dependía de qué hubiera en la cola

**Lo que se observó.** El caso A de `prueba_api` —una carta editada por una
persona con una cita inventada— exigía que bloqueara **exactamente** `['O1']`.
Empezó a fallar con `['O1', 'O6']`.

**Por qué.** Los dos controles tenían razón, y por motivos distintos: O1 porque
la frase entrecomillada no existe en el corpus; O6 porque la carta firma
`carencias_y_preexistencias-c03` en su línea `FUENTES:` y ese fragmento **no
estaba en el contexto de ese expediente** —era una hernioplastía con la
afiliación suspendida, no un parto—. Cuando el expediente que quedaba en cola era
la cesárea, esa cláusula sí era suya, O6 pasaba y bloqueaba solo O1.

Es decir: el resultado de la aserción dependía de qué expediente hubiera dejado
la corrida anterior. Una prueba así no falla cuando el sistema se rompe; falla
cuando cambia el decorado.

**Lo que se hizo.** A exige lo que A demuestra —**O1 entre los que bloquean**— y
O6 se prueba aparte, en un caso nuevo **A2** donde es deliberado: se toma el
cuerpo que el guardrail ya aprobó, con sus citas buenas intactas, y se le añade a
la línea `FUENTES:` una cláusula de reembolsos que jamás estuvo en ese
expediente. O1 sigue pasando; cae O6 y solo O6.

```
OK   A  · carta editada por una persona, cita inventada → HTTP 409, bloquearon ['O1']
OK   A2 · cita buena, fuente ajena al expediente        → HTTP 409, bloquearon ['O6']
```

A2 cubre el huérfano de O6 que no se ve leyendo el párrafo: la carta que cita
bien y respalda con un documento que quien fiscalice no puede abrir.

---

## Lo que los siete tienen en común

Ninguno es un error de lógica. Los siete están en **fronteras**: entre el
vocabulario del usuario y el de la norma (1), entre dos listas que hay que fundir
(2), entre la conexión lógica y el backend físico (3), entre la petición y la
norma citada dentro de ella (4), entre lo que la skill sabe y lo que el detector
puede ver (5), entre lo que el prompt pide y lo que el control comprueba (6),
entre una prueba y el estado que la precede (7).

Y cuatro de ellos —1, 2, 3 y 6— no estaban en la capa MCP. Estaban en código
compartido con la interfaz y con el Carril 0, aprobado y con evidencia
publicada. Aparecieron ahora porque exponer el sistema como herramientas es la
primera vez que algo lo usa **fuera del guion**: sin la pantalla que ordena los
pasos, sin el analista que sabe cómo se escriben las cosas, sosteniendo una
conexión a través de una llamada al modelo. *Una frontera que no se ve no se
audita*, y una capa nueva es, sobre todo, un juego de fronteras nuevas.

El de fondo es el 6, y conviene decirlo sin adornos: **una regla que el prompt
pide y nadie comprueba es una regla que se cumple casi siempre.** R2 no admite
«casi». La diferencia entre pedirle algo a un modelo y garantizarlo no es de
grado, y en este proyecto la línea que las separa tiene nombre —el guardrail de
salida— y ahora también cubre el carril por donde entra el 41% del volumen.

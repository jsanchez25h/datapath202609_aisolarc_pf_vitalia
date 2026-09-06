# Hallazgos de la puesta en marcha del Carril 0

**Fecha:** 2026-09-05 · **Alcance:** N1 consulta anticipada, extremo a extremo
**Evidencia asociada:** `E01_E02_router_y_cache.json`, `E09_red_team_guardrail.json`

La primera corrida completa del Carril 0 terminó sin excepciones y con todos los
indicadores en verde salvo los que importaban. Este documento registra los cinco
defectos que expuso, porque cuatro de ellos son del tipo que no levanta una
alarma: el sistema respondía, medía y guardaba evidencia mientras hacía algo
distinto de lo que decía hacer.

| # | Síntoma observado | Causa raíz | Estado |
|---|---|---|---|
| 1 | 0 aciertos de caché en 5 consultas | El umbral por similitud no es separable en este dominio | Corregido por diseño |
| 2 | Q3 respondía «No tengo la cláusula» | La capa PII borraba `REEM-06` de la consulta | Corregido |
| 3 | O1 retiraba 2 citas correctas | Guion tipográfico y negritas del corpus | Corregido |
| 4 | 12,596 ms contra un SLO de 2,000 ms | Clientes TLS reconstruidos en cada llamada | Corregido, con brecha residual |
| 5 | Q2 devolvía texto vacío | Respuesta truncada leída como respuesta corta | Corregido |
| 6 | Una afirmación correcta sobre la política, sin una sola comilla | O1 no puede rechazar las citas que no existen: aprobaba por vacío | Corregido después, en `E13_hallazgos_del_mcp.md` §6 |

---

## 1 · El caché semántico no puede decidir por similitud

**Lo que se midió.** Tomando como ancla *«¿Cuántos días de carencia tiene la
cobertura de maternidad?»* y calculando el coseno con `text-embedding-3-large`:

| Coseno | Clase | Consulta |
|---|---|---|
| 0.5982 | reformulación legítima | cuanto tiempo debo esperar desde que me afilio para que me cubran el parto |
| 0.6471 | reformulación legítima | periodo de espera de la cobertura de maternidad en Vitalia |
| **0.7786** | **cuasi-acierto peligroso** | **¿Cuántos días de carencia tiene la cobertura de salud mental?** |
| 0.4689 | cuasi-acierto peligroso | ¿Cuál es el copago de un parto por cesárea? |
| 0.2824 | ajena | ¿Qué documentos exige Vitalia para una artroscopia? |
| 0.2755 | ajena | ¿Qué significa el código REEM-06? |

La pregunta por la carencia de **salud mental** se parece más al ancla (0.7786)
que **cualquiera** de sus reformulaciones legítimas. Las dos franjas no se tocan:
se solapan por completo. No existe un umbral que admita las primeras y rechace
la tercera.

**Por qué.** Lo que distingue una respuesta de otra en este dominio —«maternidad»
frente a «salud mental», «carencia» frente a «copago»— es exactamente el token
que el embedding pesa poco, porque el resto de la oración es idéntico.

**Lo que se hizo.** No bajar el umbral. Bajarlo a 0.60 «para conseguir aciertos»
habría servido *300 días* a quien preguntaba por salud mental, cuya carencia son
*90*. Eso es el veto V1 en su forma más literal.

La clave del caché pasó a ser determinista y discriminante:

    version_politica | plan | cobertura | intencion

`cobertura` e `intencion` se deducen con un léxico del dominio, sin modelo. La
similitud queda como segundo filtro **dentro** de la clave, con umbral 0.55 —el
mínimo medido entre reformulaciones legítimas fue 0.5982—. Si la consulta no se
puede clasificar, no se lee ni se escribe caché: *fail-close*.

Dos asimetrías declaradas:

- Un empate de **intención** se resuelve por especificidad (`carencia` gana a
  `cobertura`, que es el cajón de sastre). Equivocarla manda la consulta a otro
  cajón y a lo sumo cuesta un acierto.
- Un empate de **cobertura** no se resuelve: no hay caché. Equivocarla da la
  respuesta de otra pregunta.

**Resultado.** 2 aciertos sobre 5 consultas legítimas, **0 falsos aciertos sobre
3 cuasi-aciertos**, 40.0% menos de costo. Esas mismas tres cifras son las de la
corrida vigente: el hallazgo 6 las hizo bajar a 0 aciertos durante un rato —una
respuesta sin cita verificada no se cachea— y volvieron al cerrarlo. El tercer control (`N3`) es el ancla
palabra por palabra con otro plan: coseno 1.0000 y aun así no acierta, porque el
plan está en la clave.

## 2 · La capa de privacidad borraba el objeto de la consulta

Ante *«¿Qué significa el código REEM-06 en un rechazo de reembolso?»*, el
reconocedor de entidades etiquetó `REEM-06` como `PERSON` y la anonimización lo
sustituyó por `<PERSON>`. La consulta llegó al modelo **sin el código sobre el
que preguntaba**, y el modelo respondió correctamente que no tenía la cláusula.
La recuperación había traído los fragmentos correctos; el fallo estaba una etapa
antes. El mismo efecto convertía el diagnóstico `K80.2` en `<PERSON>`.

Una capa de privacidad que borra el objeto de la solicitud no protege a nadie:
rompe el trámite y el afiliado vuelve a llamar.

Se añadió una lista de identificadores del negocio que nunca son datos
personales —`REEM-nn`, `AUT-nnn`, `PRC-nnnn`, `AF-nnnnnn`, `SOL-…`, planes
`VIT-*`, códigos CIE-10— y toda entidad que se solape con uno de ellos se
descarta. El resto de la anonimización no se tocó: el red team sigue en 16/16 y
`R16` (datos de un tercero) sigue bloqueado.

## 3 · O1 rechazaba citas que sí existían

Las dos citas retiradas de la consulta de artroscopia no eran alucinaciones:

- una traía `CIE‑10` con guion U+2011 donde el corpus tiene el guion ASCII;
- la otra había perdido los `**` con que el corpus marca la negrita, y además
  omitía texto intermedio con «…».

La comparación normalizaba mayúsculas, tildes y espacios, y nada más. Un falso
positivo en O1 no es inocuo: sustituye una respuesta correcta por
`[cita no verificada, retirada]`, es decir, destruye la respuesta sin ganar
nada.

`_compactar` ahora neutraliza también la familia de guiones Unicode, las
comillas tipográficas y las marcas de énfasis. Y una cita con puntos suspensivos
se verifica **por tramos**: cada tramo debe existir literalmente y *en orden*
dentro del mismo fragmento, lo que admite una elisión honesta y sigue rechazando
el empalme de dos cláusulas distintas.

Comprobado con cinco casos: las dos citas reales verifican; la paráfrasis, el
empalme fuera de orden y la cita tomada de otro fragmento siguen fallando.
En la corrida final: **8 citas verificadas, 0 rechazadas**. Con el control R2
añadido más tarde —hallazgo 6, documentado en `E13_hallazgos_del_mcp.md`— la
corrida vigente da **10 verificadas y 0 rechazadas**: dos de las respuestas que
antes salían afirmando sin comillas ahora citan.

## 4 · Dos tercios de la latencia eran apretones de manos

Desglose medido de los 12,596 ms iniciales. `config.cliente_qdrant()` costaba
~630 ms y `config.cliente_openai()` ~430 ms **cada vez que se construían**, y una
recuperación híbrida los construía cuatro veces. Además, la expansión de
consulta embebía cada variante en una llamada distinta, y la consulta al caché
volvía a embeber la misma pregunta que la recuperación embebía después.

Cuatro cambios, todos de fontanería:

1. Los dos clientes se memorizan (`lru_cache`).
2. Las variantes de la consulta se embeben en un solo lote — medido: 331 ms
   frente a 665 ms.
3. El vector que calcula el caché se le pasa a la recuperación en vez de
   pedirlo dos veces.
4. Las capas 7 y 8 del guardrail —las dos llamadas de red, independientes entre
   sí— se lanzan en paralelo. El veredicto es idéntico; solo cambia el reloj.

**Resultado y brecha residual, sin maquillar:**

| Ruta | Antes | Ahora | J1 |
|---|---|---|---|
| Respuesta desde caché | — | **1,380–1,489 ms** | ✅ < 2,000 ms |
| Respuesta generada, en caliente | ~12,600 ms | 3,019–4,231 ms | ❌ |
| Respuesta generada, primera del proceso | 12,596 ms | 5,627 ms | ❌ |

El desglose de una respuesta generada en caliente es guardrail ~900 ms + caché
~550 ms + recuperación ~600 ms + generación ~1,100 ms. **Ninguno de esos cuatro
componentes es cómputo: los cuatro son viajes de red a tres nubes distintas.**
El MVP corre desde Lima contra OpenAI, Qdrant Cloud y Groq, todos fuera del
país; el diseño sitúa estos servicios en `southamerica-west1` junto a la
aplicación. La brecha contra J1 en la ruta generada es atribuible a esa
diferencia y no se declara cerrada.

## 5 · Una respuesta truncada no es una respuesta corta

La consulta de artroscopia devolvió texto vacío con 700 tokens de salida
facturados. El modelo `gpt-oss-20b` razona antes de contestar y ese razonamiento
consume el mismo presupuesto que la respuesta: al agotarse `max_tokens`, el
`content` llega vacío y la llamada parece exitosa.

Es el mismo modo de fallo que ya había aparecido en la capa 8 del guardrail, y
merece la misma respuesta. `completar()` —la única puerta de generación del
MVP— ahora marca `truncada` cuando `finish_reason == "length"` o el texto viene
vacío, y el Carril 0 devuelve la frase declarada de «no tengo la cláusula» en
lugar de una pantalla en blanco, y no la cachea. El presupuesto de la ruta N1
subió de 700 a 1,400 tokens.

---

## Lo que estos cinco defectos tienen en común

Ninguno se manifestó como un error. El proceso terminaba con código 0, escribía
su evidencia y mostraba un resumen verde. El caché reportaba 0% de ahorro, no un
fallo; la capa PII reportaba una transformación exitosa; O1 reportaba dos citas
retiradas, que es justo lo que debe reportar cuando funciona; el router
reportaba 700 tokens de salida facturados.

Los cinco se encontraron leyendo el JSON de evidencia y comparándolo contra lo
que el diseño decía que debía pasar, no mirando la consola. Es la razón por la
que cada corrida persiste el detalle y no solo el agregado.

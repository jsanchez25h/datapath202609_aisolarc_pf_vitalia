# Índice de anexos

**Vitalia Salud EPS · mesa de preautorización · fase 1 (diseño)**

La rúbrica pide seis anexos, **A–F**. Este proyecto los entrega completos y añade cuatro propios,
**G–J**, porque el caso los exige: un rediseño de proceso que hay que sustentar, una matriz de
riesgos, la auditoría del *baseline* del que salen todas las cifras, y el benchmark de mercado que
justifica la postura regulatoria.

> **Nota de rutas.** Este índice nombra los archivos como estaban en el repositorio de trabajo.
> Dentro de este paquete, todos viven bajo `02_material_adicional/`:
>
> | El índice dice… | Aquí es… |
> |---|---|
> | `2_documentacion/…` | `02_material_adicional/01_analisis_y_diseno/…` |
> | `3_diagramas/…` | `02_material_adicional/01_analisis_y_diseno/diagramas/…` |
> | `fase2/evidencias/…` · `fase2/codigo/…` | `02_material_adicional/02_mvp/…` |
> | `fase2/presentacion/Vitalia_anexo_K*.pdf` | `01_presentacion_final/02_…` y `03_…` |

A los diez se suma, en la fase 2, el **Anexo K** —las evidencias del MVP funcionando—. **No
modifica ninguno de los anteriores:** A–J describen el diseño comprometido, K enseña corriendo la
rebanada que el MVP implementa.

---

## Los seis de la rúbrica

### Anexo A · Detalle de costos y assumptions

| | |
|---|---|
| **Documento** | `2_documentacion/05a_costeo_cloud.md` (completo) · `05_caso_de_negocio.md` §6–§7 |
| **Plano** | `3_diagramas/pdf/D-12_estructura_de_costos.pdf` |

Costeo servicio por servicio a precio de lista (us-central1, tarifas 2026-09-05, FX S/ 3.75/USD):
GCP $756.88 + terceros $649.50 = **$1,406.38/mes**; con no-producción y soporte, **S/ 6,700/mes =
S/ 0.86 por solicitud**. Estructura **75% fija / 25% variable** y sus cinco consecuencias.
Los tokens de LLM son el **3.8%** de la factura; toda la capa de IA, el 12%. §9 rehace el ROI
bottom-up y explica por qué el ahorro **no** se descuenta del caso comprometido. §11 lista los tres
supuestos que sostienen el modelo y qué prueba los cierra.

### Anexo B · Arquitectura física / cloud y networking

| | |
|---|---|
| **Documento** | `2_documentacion/04_to_be.md` §3 · `3_diagramas/LEEME_diagramas.md` |
| **Planos** | **D-11** arquitectura cloud · D-06 arquitectura lógica por capas |

Proyecto, VPC y tres subredes, Private Service Connect, Cloud NAT con IP fija de egreso (requisito
de Acredita Salud), API Gateway con Cloud Armor e Identity Platform en el borde, Cloud Run con
`min-instances=1` en los tres servicios de la ruta caliente, Secret Manager, Artifact Registry y
la conectividad con el core de Vitalia a través de un adaptador propio.

### Anexo C · Modelo de datos, pipeline y metadata

| | |
|---|---|
| **Documento** | `2_documentacion/08_modelo_de_datos.md` (completo) · **ADR-18 a ADR-21** |
| **Planos** | **D-13** modelo de datos · D-07 ingesta y RAG |

Empieza por lo que la plataforma **no** posee: no es sistema de registro de casi nada, y el maestro
de afiliados no se copia —solo se referencia—, porque replicarlo reproduciría la misma fuga de
copago que el proyecto existe para eliminar. Los invariantes se modelan como restricciones de base
de datos, no como lógica de aplicación: `CHECK (tipo <> 'niega_necesidad_medica' OR firma_id IS NOT
NULL)`. Corpus segmentado **por cláusula** (~4,800 fragmentos), `texto_literal` en el *payload*,
**una colección por versión** publicada por alias, linaje de 13 pasos, clasificación y retención.

### Anexo D · ADRs y alternativas evaluadas

| | |
|---|---|
| **Documentos** | `02_matriz_de_decision.md` §3–§4 · `06` §12 · `07` §12 · `08` §11 |
| **Plano** | D-03 matriz de decisión |

**Veintiún ADRs con un solo formato:** decisión · alternativa descartada · trade-off · condición
de reversión.

| Rango | Dónde | Sobre qué deciden |
|---|---|---|
| ADR-01 – ADR-07 | `02` §3 y §4 | Flujo orquestado vs. agente · fine-tuning · solo-prompt · multi-agente · GraphRAG · búsqueda densa sola · HITL |
| ADR-08 – ADR-12 | `06` §12 | Guardrail propio + Model Armor · capas 7–8 en Groq · el sistema no puede negar · verificación literal de la cita · Presidio local |
| ADR-13 – ADR-17 | `07` §12 | Fallback al carril manual · `min-instances` · caché semántico · Pub/Sub + DLQ · LangSmith + Cloud Monitoring |
| ADR-18 – ADR-21 | `08` §11 | Propiedad del dato · segmentación por cláusula · texto literal en el payload · colección por versión |

Seis de ellos —**ADR-07, ADR-10, ADR-11, ADR-15, ADR-18 y ADR-21**— tienen como condición de
reversión la palabra *nunca*. Son exactamente los que sostienen los invariantes R2 y R3 y el veto V1.
Si alguno se revierte, lo que cambia no es el diseño: es la promesa regulatoria.

### Anexo E · Golden set, evals y red-team cases

| | |
|---|---|
| **Documento** | `2_documentacion/06_seguridad_y_evaluacion.md` §8–§10 (y §1–§7 para el modelo de amenazas) |
| **Plano** | D-08 gobierno, guardrails y LLMOps |

**Golden set de 430 casos**: 300 expedientes (210 del núcleo, 90 de la cola), 60 preguntas de
política, 40 adversariales y 30 de regresión por endoso. Doble anotación ciega con **κ de Cohen
≥ 0.75** —si κ baja de ahí, el problema no es el modelo, es que el criterio humano no está definido.
Métricas por componente (recuperación, extracción, adjudicación, guardrail, agente) y el trío que
se reporta siempre junto: **% de automatización, % de reversiones al apelar, % de negaciones sin
firma médica**. **Red team R1–R16**, agrupado por invariante atacado, con criterio de aprobación
**100% en invariantes** y ≥95% en el resto.

### Anexo F · Sizing, load test, SLOs y observabilidad

| | |
|---|---|
| **Documento** | `2_documentacion/07_operacion_y_produccion.md` §2, §5, §6, §9 |
| **Plano** | **D-14** secuencia end-to-end y presupuesto de latencia |

**SLOs J1–J8** declarados sobre el proceso y no sobre la automatización —con el argumento de
disponibilidad compuesta, porque Groq no publica SLA—, error budget de 3.6 h/mes y política de
consumo en cuatro escalones. **Degradación N0–N5**, con N4 en *fail-close* y todas las rutas
terminando en el mismo lugar: la mesa, que no desaparece. Presupuesto de latencia de 90 s repartido
**8 / 25 / 6 / 30 / 5** con 16 s de holgura. Sizing real: **≈4.6 solicitudes/minuto ≈ 0.08 req/s** —
el sistema no tiene un problema de escala, tiene un problema de picos (lunes 2.4×). Pruebas P1–P7,
seis alertas con dueño, RPO 5 min en Neon y **RPO 0 en Qdrant** porque el índice es derivado.

---

## Los cuatro propios

### Anexo G · Rediseño del proceso y gestión del cambio

| | |
|---|---|
| **Documentos** | `04a_rediseno_del_proceso.md` · `04_to_be.md` §6 |
| **Plano** | D-10 |

La pregunta no fue «¿en cuál de los ocho pasos entra IA?» sino «¿siguen siendo ocho pasos?».
Dos se eliminan, cuatro se unifican en E2, uno cambia de dueño, y aparecen tres que hoy no existen.
Incluye el plan de gestión del cambio: el rol nuevo de **curador de política** (0.5 FTE, S/ 6,000/mes)
y el compromiso de que la capacidad médica liberada se reinvierte, no se recorta.

### Anexo H · Riesgos y mitigaciones

| | |
|---|---|
| **Documento** | `04_to_be.md` §9 |

Incluye el hito externo innegociable —integración con **Acredita Salud al 31-oct-2026**—, la
dependencia contractual que bloquea la fase F5 (endoso a la póliza) y la constatación de que el
riesgo del proyecto está en el factor de captura de horas, no en la tarifa de ningún servicio.

### Anexo I · Auditoría del baseline

| | |
|---|---|
| **Documento** | `05_caso_de_negocio.md` §8 |

De dónde sale cada cifra del AS-IS, con qué método se obtuvo y con qué nivel de confianza. Es el
anexo que permite discutir el caso de negocio en lugar de creerlo.

### Anexo J · Benchmark de mercado y precedentes

| | |
|---|---|
| **Documento** | `03_benchmark_mercado.md` (completo) |

Qué está resolviendo el mercado con IA en preautorización, qué precedentes regulatorios existen
—incluido el que hundió a PXDX— y por qué este diseño adopta la firma médica obligatoria **antes**
de que la norma peruana la exija.

---

## El de la fase 2

### Anexo K · Evidencias del MVP

| | |
|---|---|
| **Documento** | `fase2/09_ANEXO_K_evidencias.md` |
| **Apoyo** | `fase2/01_bitacora_de_ejecucion.md` · `fase2/02_configuracion_entorno.md` |
| **Láminas** | `fase2/presentacion/Vitalia_anexo_K.html` y `.pdf` — cinco láminas de cierre, mazo aparte del de la fase 1 |
| **Álbum** | `fase2/presentacion/Vitalia_anexo_K_capturas.html` y `.pdf` — **29 páginas A4**, una por captura, a tamaño completo y con la explicación encima. Es la pieza que se adjunta; el mazo es la que se proyecta |
| **Evidencias** | `fase2/evidencias/` — 15 archivos, **7 capturas de la interfaz** y **14 de las consolas** de los proveedores |
| **Guardrail** | Motor propio de 8 capas contra **Model Armor** de GCP sobre los mismos 20 casos: 16/16 el propio, 11/16 el gestionado. Model Armor se suma, no sustituye. La plantilla `vitalia-preauth` está retratada en la consola con sus umbrales exactos |
| **Despliegue** | Cloud Run `vitalia-mesa` · `us-central1` · imagen en Artifact Registry y claves en Secret Manager. Cerrado por IAM: la política de organización no permite `allUsers` |
| **Código** | `fase2/codigo/` — 7,524 líneas de Python en 8 paquetes |

El MVP recorta el TO-BE a una rebanada que se puede terminar: el **Carril 0** completo y el
**Carril 1** de extremo a extremo sobre tres de las 24 combinaciones del núcleo, elegidas porque
cubren los tres desenlaces que el diseño promete —autorización automática, subsanación y
escalamiento a la mesa—. El anexo trae **una fila por sesión del curso** con el punto exacto de la
aplicación donde se ve cada servicio y el archivo que lo prueba: **siete sesiones cerradas, tres
parciales y una pendiente**, dicho así y no de otra manera.

Lo que hay que mirar primero es la **pantalla 4a**: una carta de negación escrita, aprobada por los
seis controles O1–O6 y **sin emitir**, con el expediente detenido en `hitl`. Es el **ADR-10**
—el sistema nunca niega solo— en una imagen. En la misma página se ve **R1 leído del dato**: la
columna determinista declara `modelo = NULL` y su tramo de `metrica_costo` vale **US$ 0.000000**,
mientras la columna de extracción declara `gpt-4o-mini`.

Números de la corrida: red team **16/16** con **0 falsos positivos**; **112 fragmentos** de
política segmentados por cláusula; caché semántico con **40% de aciertos** y **0 falsos
aciertos**; **5 de 5 citas verificadas literalmente**; **0 fallos** en las seis suites. Y **21
defectos encontrados y corregidos**, cada uno documentado con su porqué en los cuatro archivos de
hallazgos —incluido el más incómodo: que **ningún umbral de similitud es seguro por sí solo** para
decidir un acierto de caché.

Las **veintiuna capturas** van en dos partes. Las **siete de la interfaz** enseñan lo que el sistema
hace; las **catorce de las consolas** —Qdrant, Neon, Cloud Run, Cloud Build, Cloud Storage, Secret
Manager, Model Armor y Groq— enseñan dónde corre y con qué está configurado, y permiten contrastar
cada afirmación contra algo que no escribimos nosotros: los 112 puntos los cuenta Qdrant, el
`modelo = NULL` del tramo determinista lo enseña Neon, y las cinco claves aparecen en Secret Manager
**por nombre y nunca por valor**.

§K.6 lista sin adornos lo que el MVP **no** demuestra: sin integración con el core, sin firma
digital real, sin Identity Platform, sin la **salida** del modelo pasando por Model Armor, sin
medición de los SLOs bajo carga, y con **S03, S05, S06 y S10** todavía parciales o pendientes.

---

## Mapa inverso: de la lámina al anexo

| Pág. | Lámina | Contenido | Anexos que la sustentan |
|---|---|---|---|
| 2 | Contexto | Sector, cliente y proceso | I · J |
| 4 | 01 | El problema | I · J |
| 6 | 02 | KPIs y valor | A · I |
| 7 | 03 | Qué hará y por qué IA | D · J |
| 9 | 03b | Rediseño del proceso | G |
| 11 | 04 | Arquitectura | B · C |
| 13 | 05 | Patrones y decisiones | D |
| 14 | 06 | Seguridad y evals | E |
| 16 | 07 | Costos, SLOs y go-live | A · F |
| 17 | 08 | Caso de negocio y roadmap | A · H · I |
| 19 | 08b | Economía de la plataforma | A |
| 21 | 09 | Cierre: el MVP funcionando | **K** |

## Los siete planos que van dentro de la presentación

Estos siete se imprimen **a página completa** dentro del PDF de la presentación, junto a la lámina
que sustentan, además de estar en `3_diagramas/pdf/` como planos sueltos. Los otros siete
—D-04, D-05, D-06, D-07, D-12, D-13 y D-14— viven en las láminas o solo en la carpeta de planos.

| Pág. | Plano | Apoya a | Anexo |
|---|---|---|---|
| 3 | **D-01** contexto de negocio y mapa de impacto | Contexto · lámina 02 | I |
| 5 | **D-02** proceso AS-IS con minutos por paso | Lámina 01 | I |
| 8 | **D-03** matriz de decisión | Lámina 03 | D |
| 10 | **D-10** rediseño del proceso | Lámina 03b | G |
| 12 | **D-11** vista de la plataforma en la nube | Lámina 04 | **B** |
| 15 | **D-08** gobierno, guardrails y LLMOps | Lámina 06 | E |
| 18 | **D-09** roadmap por fases y retorno | Lámina 08 | H |

# Proyecto final — Matriz de decisión: qué lleva IA y qué no

- **Proyecto final** · DataPath · AI Solutions Architect
- **Fecha:** 2026-09-04 · **Depende de:** `00_modelo_del_problema.md` · `01_caso_y_as_is.md`
- **Propósito:** dejar por escrito el instrumento con el que se decidió la arquitectura, para
  que las decisiones se puedan auditar y discutir — no solo mostrar el resultado.

---

## 1. El instrumento

Siete preguntas, **en orden**, y gana la primera que responda que sí. El orden no es arbitrario:
va de lo más barato, determinista y auditable a lo más caro, probabilístico y difícil de
explicar. Escalar antes de tiempo es el error de diseño más común en proyectos de IA.

| # | Pregunta de ruteo | Si es SÍ → | Costo · Auditabilidad |
|---|---|---|---|
| **D1** | ¿La respuesta ya está en un sistema, sin ambigüedad? | Consulta / integración. **Sin IA** | Mínimo · Total |
| **D2** | ¿Se calcula con una fórmula o una tabla cerrada? | Motor de reglas. **Sin IA** | Mínimo · Total |
| **D3** | ¿La entrada es lenguaje o imagen no estructurada, pero la tarea es acotada y la salida verificable? | **LLM dentro de un flujo** (extracción / clasificación) | Bajo · Alta si se valida contra catálogo |
| **D4** | ¿La respuesta vive en conocimiento propio que cambia, y hay que citar la fuente? | **RAG** | Medio · Alta (la cita *es* la evidencia) |
| **D5** | ¿El camino de resolución varía por caso y hay que decidir en runtime qué consultar? | **Agente** | Alto · Baja |
| **D6** | ¿Hay roles con objetivos distintos que deban negociar? | **Multi-agente** | Muy alto · Muy baja |
| **D7** | ¿La acción es irreversible, regulada, o el error es asimétrico? | **HITL / gate** — *se suma* a lo anterior, no lo reemplaza | — |

### Tres vetos que pueden tumbar la respuesta anterior

- **V1 · Asimetría del error.** ¿Cuánto cuesta equivocarse, y quién lo paga? Si lo paga el
  afiliado o el regulador y no la empresa, sube el umbral de confianza o entra HITL.
- **V2 · Reconstruibilidad.** ¿Se puede explicar esta decisión seis meses después, con la
  política que estaba vigente ese día? Si no, la solución no sirve aunque acierte.
- **V3 · Economía.** ¿El volumen justifica el TCO? Un sub-problema del 4% del volumen no paga
  una arquitectura propia; se queda manual y no pasa nada.

---

## 2. El proceso descompuesto y ruteado

| # | Sub-problema | % del esfuerzo hoy | Ruta | Regla que aplicó |
|---|---|---|---|---|
| **S1** | Recibir la solicitud del portal / app / correo y normalizarla | — | Integración convencional | D1 |
| **S2** | Extraer del expediente: diagnóstico CIE-10, código de procedimiento, fecha, clínica, médico tratante | 21% | **LLM — extracción estructurada**, validada contra catálogo | D3 |
| **S3** | ¿El sustento está completo para este tipo de procedimiento? | *(causa el 23% de observaciones)* | **Híbrido**: la lista de requisitos es una tabla cerrada (D2); verificar que el adjunto *sea* lo que dice ser es D3 | D2 + D3 |
| **S4** | Vigencia, plan, deuda, acumulado de deducible y tope de bolsillo | 16% | **Consulta al core. Sin IA** | D1 |
| **S5** | ¿Cumplió la carencia? | 11% | **Motor de reglas. Sin IA** | D2 |
| **S6** | ¿El plan cubre este procedimiento? ¿aplica exclusión? ¿qué copago? | **37%** | **RAG con cita obligatoria** | D4 + V2 |
| **S7** | Casos límite: preexistencia, exclusión con excepción, procedimiento no listado, extranjero | *(causa el 21% de derivaciones)* | **HITL — médico auditor**, con el expediente ya armado | D7 + V1 |
| **S8** | Emitir la carta y la carta de garantía en el core; notificar | 16% | **Transaccional convencional + gate de aprobación** | D1 + D7 |

### Las dos decisiones de "no IA", que son las que hay que defender

**S4 — elegibilidad.** La tentación es preguntarle al LLM "¿está vigente este afiliado?". Es una
mala decisión: el dato es determinista, está en el core, y meter un modelo probabilístico entre
la pregunta y la respuesta **agrega riesgo sin agregar capacidad**. Además vuelve la decisión
no reproducible (V2). Se resuelve con una consulta.

**S5 — carencia.** Aritmética de fechas contra una tabla cerrada (0 / 30 / 60 / 90 / 180 / 300
días calendario desde el inicio de vigencia). Un LLM aquí falla justamente donde importa —los
bordes— y no hay forma de auditar por qué. Motor de reglas.

Juntas son el 27% del esfuerzo actual y **el 100% de la fuga por copago mal aplicado (P3)**: el
mayor retorno del proyecto viene de la parte que *no* lleva IA. Decirlo explícitamente es más
valioso que cualquier diagrama.

---

## 3. La decisión de cabecera: por qué esto **no** es un agente

Aplicando D5: ¿el camino de resolución varía por caso? **No.** Toda solicitud recorre las mismas
seis verificaciones, en el mismo orden, contra la misma política. El proceso está escrito en
`autorizaciones.md` y es un procedimiento regulado — su valor está precisamente en que *no*
varíe.

Un agente aportaría autonomía donde el negocio necesita determinismo, y a cambio traería:

| Costo de irse por agente | Impacto en este caso |
|---|---|
| Camino de ejecución no reproducible | Rompe V2: no se puede sustentar una negación ante SUSALUD |
| Latencia y costo por token variables | Rompe el SLA de 48h de urgentes en el peor caso |
| Superficie de prompt injection ampliada | El expediente lo redacta un tercero (el prestador) |
| Difícil de testear | No hay golden set estable si el camino cambia |

**ADR-01 · Decisión: flujo orquestado explícito (máquina de estados), no agente.**

### La excepción honesta

Hay **un** sub-proceso donde el agente sí gana según D5: la **subsanación** (P1). Cuando falta
sustento, el camino sí varía — hay que decidir qué documento pedir, a quién, revisar lo que
llegue, y volver a evaluar. Ahí hay herramientas, iteración y un objetivo abierto.

> **Agente acotado a la subsanación. Nunca a la decisión de autorizar.**

Ese recorte es la decisión de arquitectura más importante del proyecto: no es "no usé agentes",
es "los usé exactamente donde pagan y los prohibí donde no".

---

## 4. Alternativas evaluadas y descartadas

| ADR | Alternativa | Por qué se descartó | Qué la haría volver |
|---|---|---|---|
| **ADR-02** | **Fine-tuning del modelo con la política** | La política cambia ~6 veces al año (P7). Reentrenar por cada endoso es insostenible, y el modelo no puede citar su fuente → rompe V2 | Si la política se congelara y la latencia fuera crítica |
| **ADR-03** | **Solo prompt con la política en el contexto** | El corpus completo no cabe con presupuesto sano, y crece; además no hay control de versión por decisión emitida | Corpus pequeño y estable |
| **ADR-04** | **Multi-agente (D6)** | No hay roles con objetivos distintos que negociar. Analista y auditor no negocian: uno escala al otro | Si entraran negociación con el prestador o co-decisión clínica |
| **ADR-05** | **GraphRAG** | Las relaciones plan–cobertura–nivel de clínica ya son tablas relacionales en el core. El grafo aportaría en las exclusiones con excepción encadenada (reconstructiva post-accidente, patología vs. infertilidad) | Queda en el roadmap si el error residual se concentra ahí |
| **ADR-06** | **Búsqueda densa sola** | Medido sobre el corpus normativo de Vitalia: las consultas por identificador exacto puntúan 0,56 frente a 0,74 de la misma consulta en lenguaje natural. Aquí los códigos de procedimiento son identificadores | Se adopta **híbrido denso + BM25** por esta razón medida |
| **ADR-07** | **Automatizar el 100% sin HITL** | V1: negar mal un procedimiento oncológico no es un error de software, es un problema regulatorio y humano | Nunca |

---

## 5. Cómo se valida cada decisión

Cada elección de arriba necesita una métrica que pueda desmentirla. Sin esto, la matriz es
opinión.

| Decisión | Métrica de validación | Umbral | Si falla |
|---|---|---|---|
| S2 · extracción con LLM | Exactitud de campo contra 300 expedientes anotados a mano | ≥ 97% en CIE-10 y código de procedimiento | Baja a plantillas + OCR con validación humana |
| S3 · checklist de sustento | Reducción de observaciones tardías | 23% → ≤ 9% | Se mantiene la observación a 24h |
| S6 · RAG con cita | Precisión de recuperación sobre golden set + tasa de cita correcta | recall@k ≥ 0,95 · cita verificable 100% | No se emite carta automática; solo asiste |
| S6 · híbrido vs. denso | Score en consultas por código de procedimiento | Mejora medible sobre el 0,56 del baseline | Se queda denso y se acepta el costo |
| S7 · umbral de escalamiento | % de derivaciones que el auditor confirma como necesarias | ≥ 85% | Se sube el umbral de confianza |
| Flujo vs. agente | p95 de latencia y varianza de costo por solicitud | p95 estable dentro del SLA | Se revisa (no se cambia a agente por gusto) |
| Global | Straight-through processing sin toque humano | 55–60% del volumen | El caso de negocio se recalcula |

---

## 6. Lo que este documento deja listo para la presentación

- **Slide 3 (¿realmente necesito IA?):** la tabla de la sección 2, con los dos "sin IA".
- **Slide 5 (patrones y decisiones):** la sección 3 y la 4 — problema resuelto, alternativa
  descartada, trade-off y métrica de validación, que es literalmente lo que pide la rúbrica.
- **Anexo D (ADRs):** este documento aporta **ADR-01 a ADR-07** — la decisión de cabecera de la
  sección 3 y cada fila de la sección 4, todas con su condición de reversión. El anexo se completa
  con los catorce ADRs que viven en los documentos posteriores:

  | Rango | Dónde vive | Sobre qué decide |
  |---|---|---|
  | **ADR-01 – ADR-07** | `02_matriz_de_decision.md` §3 y §4 | Flujo orquestado vs. agente, fine-tuning, RAG, multi-agente, GraphRAG, búsqueda híbrida y HITL |
  | **ADR-08 – ADR-12** | `06_seguridad_y_evaluacion.md` §12 | Guardrail propio + Model Armor, capas 7–8 en Groq, **el sistema no puede negar**, verificación literal de la cita, Presidio local |
  | **ADR-13 – ADR-17** | `07_operacion_y_produccion.md` §12 | Fallback al carril manual, `min-instances`, caché semántico, Pub/Sub + DLQ, LangSmith + Cloud Monitoring |
  | **ADR-18 – ADR-21** | `08_modelo_de_datos.md` §11 | Propiedad del dato, segmentación por cláusula, texto literal en el payload, colección por versión |

  **Veintiún ADRs, un solo formato:** decisión · alternativa descartada · trade-off · condición de
  reversión. Seis de ellos —ADR-07, ADR-10, ADR-11, ADR-15, ADR-18 y ADR-21— tienen como condición
  de reversión la palabra *nunca*, y no por comodidad: son los que sostienen los invariantes R2
  (reconstruibilidad) y R3 (firma médica) y el veto V1 (asimetría del error). Si alguno de esos
  seis se revierte, lo que cambia no es el diseño: es la promesa regulatoria.
- **Anexo E (evals):** la columna de métricas de la sección 5 es el punto de partida del golden
  set, que `06_seguridad_y_evaluacion.md` §8 desarrolla a 430 casos.

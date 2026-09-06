# Fase 2 — Plan del MVP y mapa de evidencias

- **Proyecto final** · DataPath · AI Solutions Architect · cohorte 2026-08
- **Caso:** mesa de preautorización de procedimientos programados — Vitalia Salud EPS (Perú)
- **Autor:** Jonatan Sánchez · **Fecha:** 2026-09-05
- **Relación con la fase 1:** este documento **no modifica nada** de lo comprometido en el diseño.
  El MVP y sus evidencias se adjuntan al paquete existente como **Anexo K**.

---

## 1. Qué pide la fase 2, literalmente

Dos cosas, y hay que responder a las dos por separado:

| | Qué se pide | Cómo se responde |
|---|---|---|
| **(a)** | **Interfaz final** | Una aplicación web real, desplegada, con las pantallas que usaría la mesa de Vitalia: el portal de consulta anticipada y la bandeja de adjudicación |
| **(b)** | **Los servicios principales de cada sesión del curso** | El MVP se diseña *para que cada sesión tenga un punto de la aplicación donde se la ve funcionando*, y cada uno produce un artefacto de evidencia nombrado |

El riesgo de esta fase es construir un chatbot RAG bonito que demuestre dos sesiones de diez.
Por eso el orden de trabajo es al revés de lo habitual: **primero el mapa de evidencias (§5),
después el código**. Si una sesión no tiene fila en ese mapa, no está demostrada.

---

## 2. El principio: el MVP demuestra una rebanada, no el sistema

El TO-BE de la fase 1 tiene tres carriles, cuatro estados, 24 combinaciones diagnóstico–procedimiento
en el núcleo y un roadmap de 56 semanas. Un MVP que intente eso es un MVP que no se termina.

> **La rebanada:** el **Carril 0 (N1, consulta anticipada)** completo, y el **Carril 1** end-to-end
> —guardrail → E1 extracción → E2 adjudicación → E3 ruteo → E4 emisión— limitado a **tres de las 24
> combinaciones del núcleo**: colecistectomía laparoscópica, artroscopia de rodilla y cesárea programada.

Tres combinaciones bastan porque cubren los tres caminos que el diseño promete y que hay que
poder *ver*:

| Combinación | Qué demuestra |
|---|---|
| Colecistectomía laparoscópica, plan VIT-INT, afiliado con 14 meses | **Autorización automática (STP)**: determinista puro, sin modelo, con copago calculado y carta sellada |
| Artroscopia de rodilla, plan VIT-ESE, sin informe de fisioterapia previa | **Subsanación por el agente**: falta un documento, el único agente del diseño entra en acción |
| Cesárea programada, afiliada con 220 días de afiliación | **Ruteo a médico auditor**: carencia de 300 días → el sistema **no puede negar** (ADR-10), escala con la cita textual y el borrador |

El tercer caso es el importante: es el que demuestra el invariante R3 y el veto V1 delante del
docente. Un MVP que solo enseñe el caso feliz no demuestra la tesis del proyecto.

---

## 3. Qué se reutiliza y qué se construye

No se parte de cero. El inventario en disco:

| Origen | Qué aporta | Estado |
|---|---|---|
| `Modulo05/Sesion10/repo_demo_rag_agent_full/` (rama `full_lab`) | El esqueleto completo: Next.js + Identity Platform, `rag_api`, `agent_api` con las 8 capas de guardrail y RAGAS, `mcp_server`, `DEPLOYMENT.md` de 660 líneas | Clonado, sin ejecutar |
| `Modulo03/Sesion06/Tarea/01_fuente_de_conocimiento/` | **El corpus de política de Vitalia: 10 documentos Markdown** ya escritos y coherentes con el caso | Listo |
| `Modulo04/Sesion07/repo_modulo4_sesion1_lab/` | Agente LangChain con tools MCP y la variante con Google ADK | Clonado, sin ejecutar |
| `Modulo02/Sesion03/` | `kind` + Helm + Ollama: model serving en Kubernetes | Lab corrido el 2026-08-18 |
| `Modulo03/Sesion05/M3_S1_vector_search_lab.ipynb` | FAISS vs Qdrant, métricas de similitud, recall/latencia | Nunca corrido, no pide claves |
| Cuentas vivas | OpenAI, Qdrant Cloud, Neon, LangSmith, GCP | ✅ |

**Lo que se construye nuevo** —y es donde está el valor propio del proyecto, no del curso—:
el **motor determinista** (elegibilidad, carencia, copago), el **cross-check O3**, la **ingesta
por cláusula con colección versionada**, el **caché semántico con la clave del diseño**, y la
**interfaz de la mesa**, que no existe en ningún lab.

---

## 4. Arquitectura del MVP

Cinco componentes desplegables, que son un subconjunto fiel de D-06 y D-11:

```
   NAVEGADOR
       |
       v
   [ app-mesa ]            Next.js 16 · Identity Platform · 2 pantallas
       |                   (portal de consulta anticipada + bandeja de adjudicación)
       v
   [ api-preauth ]         FastAPI · guardrail 8 capas · E1 extracción ·
       |    |    |         E2 adjudicación (determinista | interpretativo) ·
       |    |    |         E3 ruteo · E4 emisión · O1-O6 salida · caché semántico
       |    |    +-------> [ mcp-vitalia ]   MCP propio: consultar_politica,
       |    |                                calcular_copago, verificar_carencia,
       |    |                                emitir_carta  (+ skills y hooks)
       |    +------------> [ api-rag ]       recuperación híbrida densa+BM25 sobre
       |                                     la colección versionada
       v
   Qdrant Cloud (política por versión, alias politica_actual + cache_semantico)
   Neon Postgres (expedientes, trazas, feedback, evaluaciones RAGAS)
   LangSmith (trazas con PII anonimizada, costo por span)
   Groq (capas 7 y 8 del guardrail) · OpenAI (embeddings + generación)
   kind + Ollama (motor local de degradación N3)
```

**Lo que deliberadamente NO entra al MVP:** WhatsApp/WAHA. El canal del diseño de Vitalia es el
**portal de prestadores**, no WhatsApp; además WAHA en Cloud Run exige instancia siempre activa y
un número real con QR. Lo que sí se demuestra de la sesión 08 —Skills y Hooks— se demuestra en el
lugar donde el diseño sí los usa (§5, fila S08). Si aun así se quiere la evidencia de WhatsApp,
es media jornada extra y hay que decirlo antes de empezar.

---

## 5. El mapa: sesión → servicio → dónde se ve → evidencia

Esta es la tabla que responde la pregunta (b). Una fila por sesión, sin excepciones.

| Sesión | Servicio / técnica que se demuestra | Dónde vive en el MVP | Artefacto de evidencia |
|---|---|---|---|
| **S01** · Patrones de arquitectura y selección de modelos | Enrutamiento por complejidad y la matriz de selección **ejecutada de verdad** contra el caso | `api-preauth/services/model_router.py` | `E01_seleccion_modelo.md` — tabla de 3 modelos × latencia, costo, acierto sobre el set reducido, y qué modelo queda en cada ruta |
| **S02** · AI FinOps | **Caché semántico** con la clave del diseño (`dx × procedimiento × plan × versión_política`), ruteo barato/caro y **atribución de costo por span** | Colección `cache_semantico` en Qdrant + panel de costos en la UI | `E02_finops.png` + corrida en frío vs. caliente: hit-rate, ahorro y S/ por solicitud medido |
| **S03** · Model serving en Kubernetes | `kind` + Helm + **Ollama** sirviendo un modelo local, cableado como **motor de degradación N3** del plan de contingencia | Clúster local + `MODEL_PROVIDER=ollama` | `E03_k8s.png` (`kubectl get pods`, `helm list`) y la UI con el banner *modo degradado N3* respondiendo sin proveedor externo |
| **S04** · Data pipelines y document processing | Ingesta documental: 10 documentos → **segmentación por cláusula** → `sha256` + versión → publicación por alias | `ingesta/pipeline_politica.py` | `E04_ingesta.log` con el conteo de fragmentos, y la publicación de una **v2** de la política que cambia una regla, para ver el versionado en vivo |
| **S05** · Vector databases y semantic search | Qdrant Cloud, HNSW, métrica de similitud y **densa vs. híbrida densa+BM25** | `api-rag` + notebook | `E05_busqueda.ipynb` — recall@k y latencia. **Aquí se cierra el defecto conocido de la tarea S06**: `REEM-06` no se recuperaba con búsqueda densa |
| **S06** · RAG avanzado y evals | RAG con **cita textual verificada** (O2), query expansion, reranking, y **RAGAS** | `api-rag` + `/evaluate` | `E06_ragas.json` — faithfulness, answer relevancy y context precision sobre 20 preguntas de política |
| **S07** · Agentes y orquestación multi-agente | El **único agente del diseño**: subsanación. LangChain + **MCP propio** con catálogo cerrado de 4 tools | `mcp-vitalia` + `agent_service.py` | `E07_traza_agente.json` + captura de LangSmith: el agente detecta el documento faltante, redacta el pedido y **no sale del catálogo** |
| **S08** · Skills, Hooks y production-grade | **Skill** de emisión de carta (`SKILL.md`) y **Hooks** como middleware: idempotencia, enmascarado de PII y tope de reintentos | `mcp-vitalia/skills/` + `api-preauth/hooks/` | `E08_hooks.txt` — test que muestra el hook cortando el reintento nº 4, y la carta emitida por la skill |
| **S09** · Guardrails y red teaming | **InputGuardrail de 8 capas** (Groq en 7 y 8, Presidio local en 5) + guardrail de salida O1–O6 con el **cross-check O3 de copago** | `api-preauth/services/guardrails/` | `E09_redteam.md` — 16 casos R1–R16 reducidos, veredicto por capa; criterio: **100% en los que atacan invariantes** |
| **S10** · LLMOps y observabilidad | LangSmith con **anonimización de PII antes de salir**, costo por span, **feedback loop** persistido, y medición de SLOs | Cloud Run + LangSmith + Neon | `E10_slos.md` — J1 (N1 p95 < 2 s), J3 (adjudicación p95 < 90 s) y J4 (e2e p95 < 5 min) medidos con carga, más capturas de trazas y del feedback en base |

---

## 6. La interfaz final: cinco pantallas

| # | Pantalla | Para quién | Qué demuestra |
|---|---|---|---|
| 1 | **Ingreso** (Identity Platform, correo/clave) | Prestador y analista | Autenticación en el borde, no en la aplicación |
| 2 | **Consulta anticipada (N1)** — elijo diagnóstico y procedimiento, y el portal responde *cubierto / no cubierto / falta X* con la **cita textual** y el copago estimado | Prestador | El Carril 0: el cambio que evita que la solicitud incompleta entre a la cola |
| 3 | **Bandeja de la mesa** — expedientes con su estado, semáforo de ruta y tiempo en cola | Analista | E3, el ruteo medido |
| 4 | **Detalle del expediente** — extracción E1, adjudicación E2 con la separación visible entre *lo determinista* y *lo interpretativo*, la cita, el copago desglosado, el borrador de carta y el **sello de versión de política** | Analista y médico auditor | El corazón del diseño: R1, R2, R3 y el cross-check O3 |
| 5 | **Panel de operación** — costo por solicitud, hit-rate del caché, latencias p50/p95, y el pulgar arriba/abajo del feedback | Supervisor | S02 y S10 en la misma vista |

La pantalla 4 es la que hay que enseñar en la defensa: es donde se ve, en la misma página, que
el copago lo calculó una regla y no un modelo, y que la carta cita el artículo de la versión
vigente ese día.

---

## 7. Plan de ejecución en tres etapas

| Etapa | Qué corre | Dónde | Costo |
|---|---|---|---|
| **A · Local** | Ingesta, RAG híbrido, guardrails, motor determinista, MCP, agente, UI en modo desarrollo, notebook de S05, clúster `kind` de S03 | Mi máquina + Qdrant/Neon/OpenAI/Groq | Solo consumo de API |
| **B · GCP** | Artifact Registry + **tres Cloud Run** (`app-mesa`, `api-preauth`, `mcp-vitalia`) + API Gateway + Secret Manager + Identity Platform + política de Cloud Armor | Proyecto GCP del curso | Pequeño, con `min-instances=0` y borrado al terminar |
| **C · Evidencia** | Golden set reducido, red team, RAGAS, prueba de carga y captura de todo | Contra el despliegue de B | — |

**Reducción de alcance declarada, para que nadie la descubra después:** el golden set del diseño
son 430 casos; el MVP corre **60** (40 expedientes + 20 preguntas de política). El red team son 16
de los R1–R16, uno por familia. La prueba de carga es de minutos, no de horas. Es un MVP: sirve
para demostrar que el diseño funciona, no para certificar que está listo para producción.

**Sobre `min-instances=0`:** el diseño comprometido usa `min-instances=1` en la ruta caliente
(ADR-14) justamente para no pagar arranque en frío. El MVP lo baja a 0 por costo, y por eso la
medición del SLO J1 se reporta **descontando el arranque en frío y diciéndolo**. Es una diferencia
entre el MVP y el diseño, no una corrección del diseño.

---

## 8. Lo que necesito de ti

| Qué | Por qué | Cómo |
|---|---|---|
| **`GROQ_API_KEY`** | Es la **única credencial que falta** de todo lo pendiente. Sostiene las capas 7 y 8 del guardrail (Prompt Guard 2 y Llama Guard 4). Sin ella, por política *fail-close*, el pipeline bloquearía todo | Gratis en `console.groq.com` → API Keys. Formato `gsk_…`. Va a `variables.sh` y a los `.env`, nunca al chat ni a un documento |
| *(opcional)* `NEON_API_KEY` | El MCP de Neon de la sesión 07. **No bloquea**: sin ella el agente arranca igual, solo pierde esa tool remota | `console.neon.tech` → Account settings → API keys |
| Confirmar el alcance | Para no construir de más | Basta con decir si las tres combinaciones de §2 y las cinco pantallas de §6 son lo que esperas ver |

Todo lo demás —OpenAI, Qdrant, Neon, LangSmith y GCP— ya está vivo y configurado.

---

## 9. Lo que el MVP NO demuestra

Decirlo por adelantado vale más que esconderlo:

- **No hay integración con el core de Vitalia.** El maestro de afiliados y el tarifario se simulan
  con un servicio de prueba. El diseño ya declara que la plataforma no es dueña de ese dato.
- **No hay firma digital real** del médico auditor: se simula el acto de firma y se registra en la
  traza. Lo que sí es real es que **el sistema no puede emitir una negación sin ella**.
- **Model Armor** quedó como variante y **se activó**: implementado en `guardrails/model_armor.py`, medido contra las ocho capas propias en `E16` y documentado en `02_configuracion_entorno.md` §10. El motor por defecto sigue siendo el propio, porque el gestionado detecta 11 de los 16 ataques y el propio, 16.
- **No hay integración con Acredita Salud** ni IP fija de egreso: eso es F1 del roadmap.
- **El volumen es de demostración**, no las 7,800 solicitudes/mes del caso.

---

## 10. Entregable

```
fase2/
├── 00_PLAN_fase2.md            ← este documento
├── 01_bitacora_de_ejecucion.md   qué comandos se corrieron, en qué orden y qué salió mal
├── 02_configuracion_entorno.md   cuentas, proyectos, variables y despliegue (sin claves)
├── 09_ANEXO_K_evidencias.md      el anexo que se adjunta al paquete de la fase 1
├── codigo/                       app-mesa · api-preauth · api-rag · mcp-vitalia · ingesta
└── evidencias/                   E01 … E10, en el orden del mapa de §5
```

El Anexo K se suma al índice de anexos de la fase 1 sin tocar A–J, y la presentación gana una
lámina de cierre con el mapa de §5 y las capturas de la interfaz.

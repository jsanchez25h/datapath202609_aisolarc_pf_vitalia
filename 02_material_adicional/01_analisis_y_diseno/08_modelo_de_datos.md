# Proyecto final — Modelo de datos, pipeline y metadata

- **Proyecto final** · DataPath · AI Solutions Architect
- **Fecha:** 2026-09-05
- **Viene de:** `04_to_be.md` §3 (estados del proceso) · `06_seguridad_y_evaluacion.md` (verificación de citas y PII) · `07_operacion_y_produccion.md` §9 (continuidad)
- **Cubre:** **Anexo C** (modelo de datos, pipeline y metadata) · parte del **Anexo D** (ADR-18 a ADR-21)
- **Diagramas:** **D-07** (ingesta y RAG) · **D-13** (modelo de datos)

> **La tesis de este documento.** La plataforma **no es sistema de registro de casi nada**. El
> afiliado, la póliza y el saldo viven en el core; los documentos y la política viven en GCS
> firmados; el índice vectorial es un artefacto derivado y desechable. Lo único de lo que la
> plataforma sí es dueña es **la decisión y su justificación** — y eso se modela para que sea
> reconstruible seis meses después, que es el requisito R2.

---

## 1. Quién es dueño de qué

| Almacén | Es sistema de registro de | **No** es dueño de | Si se pierde |
|---|---|---|---|
| **Core de Vitalia** *(externo)* | Afiliado, póliza, plan, deuda, acumulados, carta emitida | — | Fuera de alcance del proyecto |
| **Acredita Salud** *(externo, obligatorio 31-oct-2026)* | Elegibilidad interoperable, AUT-100 | — | Adaptador cae a consulta al core |
| **GCS** | **Expedientes** y **corpus normativo firmado** | El estado del proceso | Catastrófico — es la fuente de verdad documental |
| **Neon (PostgreSQL)** | **El proceso**: solicitud, estados, extracción, adjudicación, citas, firma, traza de decisión | El afiliado y la póliza (solo los referencia) | Grave: RPO 5 min, PITR |
| **Qdrant** | Nada. **Índice derivado** | Todo | Se reconstruye en 2 h por $0.10 |
| **BigQuery** | Analítica y costos | Operación | Se rehidrata desde trazas y Neon |

**La regla que evita el error más común de estos proyectos:** *no se copia el maestro de
afiliados.* Neon guarda `afiliado_ref` — el identificador del core y nada más. Cualquier atributo
del afiliado se consulta en el momento de decidir, porque **una copia desactualizada de la
vigencia produce exactamente el error P3 que el proyecto viene a eliminar.**

---

## 2. Modelo relacional del proceso (Neon)

### 2.1 Vista de entidades

```
┌──────────────────────┐        ┌───────────────────────┐
│ politica_version     │        │ catalogo_procedimiento│
│ PK version_id        │        │ PK codigo             │
│    sha256            │        │    descripcion        │
│    vigencia_desde    │        │    vigente_desde/hasta│
│    vigencia_hasta    │        └───────────┬───────────┘
│    aprobado_por      │                    │
│    diff_vs_anterior  │        ┌───────────┴───────────┐
└──────────┬───────────┘        │ catalogo_cie10        │
           │                    └───────────┬───────────┘
           │  (sella)                       │ (valida)
           v                                v
┌───────────────────────────────────────────────────────────────┐
│ solicitud                                                     │
│ PK  solicitud_id            afiliado_ref     (→ core)         │
│     prestador_id            plan_codigo      (→ core)         │
│     dx_cie10  ────────────────────────────── (→ catálogo)     │
│     procedimiento_codigo ─────────────────── (→ catálogo)     │
│     tipo (programado|urgente|extranjero)     canal (N1|portal)│
│     estado_actual (E1..E4|auto|hitl|agente)  creada_en        │
│     hash_expediente         idempotency_key                   │
│     sla_vence_en            version_politica_aplicada (FK)    │
└──┬─────────┬──────────┬──────────┬───────────┬────────────────┘
   │1:N      │1:N       │1:1       │1:N        │1:N
   v         v          v          v           v
┌──────────┐┌─────────┐┌────────────┐┌──────────────┐┌──────────────┐
│documento ││evento_  ││adjudicacion││evaluacion_   ││turno_agente  │
│          ││estado   ││            ││guardrail     ││              │
│PK doc_id ││PK ev_id ││PK adj_id   ││PK eval_id    ││PK turno_id   │
│ tipo     ││ desde   ││ elegible   ││ capa (1..8)  ││ n_turno      │
│ gcs_uri  ││ hacia   ││ carencia_ok││ categoria    ││ tool_llamada │
│ sha256   ││ actor   ││ copago_pen ││ decision     ││ destinatario │
│ paginas  ││ motivo  ││ cobertura  ││ confianza    ││ resultado    │
│ recibido ││ ts      ││ confianza  ││ posicion     ││ ts           │
└────┬─────┘└─────────┘│ ruta       ││ ts           │└──────────────┘
     │1:1               │ modelo+ver │└──────────────┘
     v                  │ prompt_sha │
┌──────────────┐        └─────┬──────┘
│ extraccion   │              │1:N
│ PK extr_id   │              v
│  campo       │        ┌──────────────────────────────────┐
│  valor       │        │ cita                             │
│  confianza   │        │ PK cita_id     chunk_id          │
│  validado_cat│        │    doc_id      version_id (FK)   │
│  modelo+ver  │        │    articulo    texto_literal     │
│  prompt_sha  │        │    offset_ini / offset_fin       │
└──────────────┘        │    verificada_literal (bool)     │
                        └──────────────────────────────────┘
┌───────────────────────┐        ┌────────────────────────────┐
│ firma_medica          │        │ carta                      │
│ PK firma_id           │───────►│ PK carta_id                │
│    adj_id (FK)        │  1:0..1│    solicitud_id (FK)       │
│    colegiatura_cmp    │        │    tipo (autoriza|niega|obs)│
│    medico_id          │        │    version_politica (FK)   │
│    ts   ip   hash_doc │        │    citas[] (FK cita)       │
└───────────────────────┘        │    firma_id (FK, NULLABLE) │
                                 │    core_folio  emitida_en  │
                                 └────────────────────────────┘
```

### 2.2 Los invariantes, escritos como restricciones

No como buenas intenciones: como constraints que la base rechaza.

| Invariante | Implementación |
|---|---|
| **R3** · ninguna negación clínica sin firma | `CHECK (tipo <> 'niega_necesidad_medica' OR firma_id IS NOT NULL)` sobre `carta` |
| **R2** · ninguna carta sin versión de política | `version_politica NOT NULL` + FK a `politica_version` |
| Ninguna cita sin verificación literal | `CHECK (verificada_literal = true)` para toda cita referenciada por una carta emitida |
| Todo código emitido existe en catálogo vigente | FK a `catalogo_*` con validación de vigencia a la fecha de la solicitud |
| Sin duplicados de emisión | `UNIQUE (solicitud_id, idempotency_key)` |
| La máquina de estados no admite saltos | Transición validada contra tabla `transicion_valida (desde, hacia)` |

> Que R3 sea un `CHECK` y no una validación de aplicación es deliberado. **Un invariante
> regulatorio no puede depender de que el código lo respete;** tiene que ser imposible de violar
> aunque alguien escriba directamente en la base.

### 2.3 `evento_estado` es *append-only*

Nunca se actualiza ni se borra: cada transición inserta una fila con actor, motivo y marca de
tiempo. `solicitud.estado_actual` es una vista materializada de conveniencia. Es lo que responde
la pregunta de una fiscalización — *quién movió esto, cuándo y por qué* — sin depender de las
trazas técnicas, que se retienen 400 días y estos datos más.

### 2.4 Volumen y crecimiento

| Entidad | Filas/mes | A 3 años |
|---|---:|---:|
| `solicitud` | 7,800 | ~281 K |
| `documento` | ~62,400 (8 por expediente) | ~2.2 M |
| `extraccion` | ~78,000 (10 campos) | ~2.8 M |
| `evaluacion_guardrail` | ~62,400 | ~2.2 M |
| `cita` | ~7,000 | ~252 K |
| `evento_estado` | ~31,000 | ~1.1 M |

Total estimado con índices: **< 50 GB a tres años**, que es exactamente el dimensionamiento de
Neon en `05a` §4. Los documentos no viven en la base — en `documento` solo hay el `gcs_uri` y el
`sha256`.

---

## 3. El corpus normativo y su versionado

Es el activo que el proyecto crea. Hoy el manual de política es un documento que cambia ~6 veces
al año y **nadie sabe qué se emitió bajo qué versión** (P7). Eso deja de ser cierto aquí.

### 3.1 Qué entra al corpus

| Fuente | Volumen aprox. | Cadencia de cambio |
|---|---:|---|
| Manual de política de coberturas y exclusiones | ~180 pág. | ~6 endosos/año |
| Condiciones particulares por plan (VIT-INT, VIT-ESE, VIT-PRE) | ~40 pág. c/u | Anual + endosos |
| Tabla de carencias y preexistencias | ~15 pág. | Anual |
| Directivas de SUSALUD aplicables | ~60 pág. | Irregular |
| Convenios con la red de prestadores (niveles y tarifas) | ~90 pág. | Trimestral |

**Lo que NO entra:** nada con datos personales. El corpus es normativo y no contiene PII — que es
lo que permite alojarlo en Qdrant Cloud sin abrir un frente de cumplimiento (`06` §5).

### 3.2 Ciclo de vida de una versión

```
documento fuente (PDF/DOCX)
   │
   ├─► GCS  gs://vitalia-corpus/politica/v{N}/{archivo}     ← inmutable, con versionado de objeto
   │
   ├─► registro en politica_version:
   │      version_id · sha256 · vigencia_desde · vigencia_hasta
   │      aprobado_por (el CURADOR DE POLÍTICA) · diff_vs_anterior
   │
   ├─► extracción de texto  (Document AI · layout, no solo OCR)
   ├─► segmentación por CLÁUSULA  (ADR-19)
   ├─► embeddings  text-embedding-3-large · 3,072 dims
   ├─► carga a colección  politica_v{N}   ← colección nueva, la anterior sigue viva (ADR-21)
   │
   ├─► 30 casos de regresión de política  → las respuestas DEBEN cambiar donde corresponde
   ├─► invalidación total del caché semántico
   └─► el alias  politica_actual  apunta a  politica_v{N}
```

**Nada se publica sin la firma del curador.** Es el control contra A4 (envenenamiento del corpus)
y es la razón por la que ese rol se presupuestó como 0.5 FTE en `05_caso_de_negocio.md` §3: sin
dueño humano del corpus, el versionado es una carpeta con nombres de archivo.

### 3.3 Segmentación

| Decisión | Valor |
|---|---|
| Unidad | **La cláusula o el artículo**, no un número fijo de tokens (ADR-19) |
| Tamaño resultante | ~350–700 tokens, con la cláusula completa siempre íntegra |
| Ventana | *Sentence-window*: se recupera la cláusula y se entrega con la anterior y la siguiente como contexto |
| Solapamiento | Solo el encabezado jerárquico (título → capítulo → artículo), repetido en cada fragmento |
| Total | **~4,800 fragmentos** para el corpus completo — 59 MB de vectores; con 12 versiones vivas, ~700 MB |

Repetir la jerarquía en cada fragmento resuelve el problema clásico del corpus normativo: una
cláusula que dice *"lo señalado en el numeral anterior no aplica"* es inútil fuera de contexto.

---

## 4. La colección vectorial

### 4.1 Payload de cada punto

```json
{
  "chunk_id":      "pol-v12-c4-art18-p2",
  "doc_id":        "manual-coberturas",
  "version_id":    "v12",
  "sha256_doc":    "9f2a…",
  "vigencia_desde":"2026-07-01",
  "vigencia_hasta":null,
  "jerarquia":     "Título III > Capítulo 4 > Artículo 18",
  "planes":        ["VIT-INT","VIT-ESE"],
  "tipo_norma":    "exclusion",
  "pagina":        73,
  "offset_ini":    18422,
  "offset_fin":    19105,
  "texto_literal": "No se cubre el tratamiento de …"
}
```

**`texto_literal` en el payload es una decisión, no un descuido** (ADR-20): es lo que permite
verificar la cita literalmente (control O1 de `06` §4) sin ir a buscar el documento a GCS en la
ruta crítica. Cuesta ~40 MB de almacenamiento y ahorra ~200 ms por cita.

### 4.2 Recuperación

| Elemento | Decisión | Por qué |
|---|---|---|
| **Búsqueda** | **Híbrida**: densa + BM25 | Medido: las consultas por código exacto puntúan 0.56 con densa sola y 0.74 en lenguaje natural. Los códigos de procedimiento **son** identificadores (`02` §4) |
| **Filtro obligatorio** | `vigencia_desde ≤ fecha_solicitud ≤ vigencia_hasta` **y** `planes ∋ plan_del_afiliado` | Sin fecha no hay consulta. Es el control contra A5 |
| **Top-k** | 20 candidatos → **rerank** con Vertex AI Ranking → top-5 al contexto | El rerank es donde se separa el artículo correcto del que solo comparte vocabulario |
| **Salida obligatoria** | `chunk_id` + `offset` + `texto_literal` de cada cita | Alimenta la verificación O1 y la tabla `cita` |

### 4.3 Por qué colección por versión y no un filtro

Ver **ADR-21**. En resumen: el filtro por versión sobre una colección única es más barato en
almacenamiento y **más frágil en lo único que importa** — basta olvidar el filtro una vez para
citar política derogada. Una colección por versión hace que el error sea imposible en lugar de
improbable.

---

## 5. Almacenamiento de objetos (GCS)

```
gs://vitalia-corpus/          política firmada · inmutable · versionado de objeto · 400 d + retención legal
gs://vitalia-expedientes/     documentos del expediente · CMEK · retención sectorial
gs://vitalia-derivados/       texto extraído, JSON de layout · regenerable · 90 d
gs://vitalia-golden/          golden set, red team y casos de regresión · versionado
gs://vitalia-artefactos/      prompts publicados, esquemas, snapshots de índice · inmutable
```

Reglas: `vitalia-corpus` y `vitalia-artefactos` son **inmutables y con retención bloqueada** —
nadie, ni un administrador, puede alterar una versión ya publicada. `vitalia-derivados` es
desechable por definición. Ningún bucket es público; el acceso es por *Private Google Access*
desde la VPC (D-11).

---

## 6. Analítica (BigQuery)

Cuatro tablas particionadas por día. Es el destino donde se cruzan operación y costo.

| Tabla | Grano | Alimenta |
|---|---|---|
| `hechos_solicitud` | 1 fila por solicitud cerrada | El **trío**, TAT, STP, tasa de derivación |
| `hechos_span` | 1 fila por span con tokens y costo | Costo por solicitud, por prompt y por tipo (`07` §6.2) |
| `hechos_evaluacion` | 1 fila por corrida de golden set | Deriva de calidad entre versiones |
| `hechos_guardrail` | 1 fila por evaluación de capa | FPR/TPR y ajuste de capas |

Ninguna contiene PII: `afiliado_ref` viaja como *hash* con sal por proyecto. Se puede analizar
"cuántas solicitudes por afiliado" sin poder saber de quién.

---

## 7. Linaje de un documento, de punta a punta

```
1. El médico adjunta el informe en el portal
      → GCS vitalia-expedientes/{solicitud}/{doc}.pdf     sha256 registrado en `documento`
2. Guardrail de 8 capas                                   → filas en `evaluacion_guardrail`
3. Document AI: OCR + layout                              → GCS vitalia-derivados/  (regenerable)
4. E1 extrae campos                                       → filas en `extraccion`
                                                             con modelo+versión y prompt_sha
5. Validación contra catálogo                             → `validado_cat`; si falla, no se autocompleta
6. E2 determinista consulta el core / Acredita Salud      → `adjudicacion.elegible/carencia/copago`
7. E2 interpretativo consulta el índice con fecha y plan  → devuelve chunk_id + texto_literal
8. Verificación literal O1 y de vigencia O2               → filas en `cita`, `verificada_literal=true`
9. Contraste O3: copago del texto == copago del motor     → si difiere, no se emite
10. E3 rutea                                              → `adjudicacion.ruta`
11. Si niega por criterio clínico → firma                 → `firma_medica`
12. E4 emite contra el core con idempotency_key           → `carta` + `core_folio`
13. Todo el recorrido queda en `evento_estado` (append-only) y en la traza
```

**La pregunta que este linaje responde**, y que hoy en Vitalia no tiene respuesta (P7):

> *"El 12 de marzo se negó el caso X. ¿Con qué versión de la política, qué artículo se citó, quién
> lo firmó y qué decía ese artículo ese día?"*

Se contesta con un `JOIN` de cinco tablas y sin depender de que nadie recuerde nada.

---

## 8. Metadata obligatoria — y por qué cada campo existe

Ningún campo está por completitud. Cada uno responde a un requisito nombrado:

| Campo | Existe por |
|---|---|
| `version_politica` en solicitud, cita y carta | **R2** · reconstruibilidad · falla F4 |
| `sha256` de documento y de versión | Integridad y detección de sustitución (A4) |
| `prompt_sha` y `modelo+version` en cada salida de LLM | Reproducibilidad y atribución de una regresión a un cambio concreto |
| `confianza` por campo extraído | Umbral de HITL (`06` §7) |
| `verificada_literal` en cita | Control **O1** — sin esto, R2 es una aspiración |
| `offset_ini/fin` | Permite resaltar al auditor exactamente el fragmento, no el documento |
| `idempotency_key` | Evita la carta duplicada |
| `sla_vence_en` | Es el reloj contractual: 5 días / 48 h / 15 días |
| `canal` (N1 vs. portal) | Mide si N1 está funcionando — es la palanca de observaciones ≤ 9% |
| `ruta` (auto / hitl / agente) | Es el numerador del STP, y va siempre con el trío |

---

## 9. Clasificación, retención y PII

| Categoría | Ejemplos | Clasificación | Dónde vive | Retención |
|---|---|---|---|---|
| **Datos sensibles de salud** | Informe clínico, diagnóstico, exámenes | **Sensible** (Ley 29733) | GCS con CMEK · Neon | Según norma sectorial y política documental de Vitalia — el proyecto la **hereda**, no la define |
| Identificadores del afiliado | DNI, nombre, teléfono | Personal | **Solo en el core.** En la plataforma, `afiliado_ref` | — |
| Normativa | Manual, condiciones, directivas | **Público interno** | GCS · Qdrant | Permanente + 400 d de versiones retiradas |
| Decisión y justificación | Adjudicación, citas, firma, carta | Sensible por asociación | Neon | Igual que el expediente |
| Trazas técnicas | Spans, tokens, costos | Interno, **sin PII** | LangSmith · BigQuery | 90 d caliente / 400 d frío |
| Golden set | 300 expedientes anotados | **Sensible — anonimizado** | GCS `vitalia-golden` | Vida del sistema |

> **El golden set es el punto de privacidad más delicado del proyecto** y el más fácil de pasar
> por alto: son 300 expedientes clínicos reales que se copian, se anotan y se reusan en cada
> corrida de CI durante años. Se anonimizan en el momento de la anotación (mismo enmascarado de
> la capa 5), se guardan con control de acceso propio y **nunca salen a un entorno de desarrollo
> local**. Los ejecuta el pipeline, no una persona en su laptop.

---

## 10. Contratos de integración

| Sistema | Dirección | Contrato | Nota |
|---|---|---|---|
| **Core de Vitalia** | Lectura: afiliado, plan, deuda, acumulado, tope · Escritura: carta y carta de garantía | API REST tras **adaptador propio** | La escritura es idempotente por `idempotency_key` |
| **Acredita Salud** | Lectura: elegibilidad interoperable · AUT-100 | Especificación SUSALUD | **E2 se diseña contra el adaptador, no contra el proveedor** — si la fecha del 31-oct-2026 se corre, se sigue consumiendo el core con la misma interfaz |
| **Portal del prestador** | Entrada de solicitudes y consulta N1 | API propia | Es el canal que sostiene observaciones ≤ 9% |
| **Correo del prestador** | Agente de subsanación | Entrada tratada como no confiable: pasa por el guardrail completo | A8 |

El adaptador de Acredita Salud es la pieza que convierte un riesgo regulatorio de fecha en una
decisión de configuración. Está en `04_to_be.md` §9 como mitigación y aquí como contrato.

---

## 11. ADRs de datos

### ADR-18 · Neon es sistema de registro del proceso; el core lo es del afiliado

- **Decide:** no se replica el maestro de afiliados ni la póliza. Se referencia y se consulta en
  el momento de decidir.
- **Alternativa descartada:** réplica local con sincronización nocturna. Baja la latencia de E2 y
  evita depender del core.
- **Trade-off:** cada adjudicación depende de la disponibilidad del core (nivel N5 de degradación).
- **Se revierte si:** nunca por rendimiento. **Una vigencia desactualizada reproduce exactamente
  la fuga de copago P3 que el proyecto viene a eliminar** — sería pagar el ahorro con el problema.

### ADR-19 · Segmentación por cláusula, no por número fijo de tokens

- **Decide:** el fragmento es la unidad normativa (artículo/cláusula), con la jerarquía repetida.
- **Alternativa descartada:** ventana fija de 512 tokens con solapamiento del 15%. Es el defecto
  de casi todo pipeline de RAG y es más simple.
- **Trade-off:** fragmentos de tamaño desigual (350–700 tokens) y un preprocesamiento propio que
  hay que mantener cuando cambia el formato del manual.
- **Se revierte si:** el corpus dejara de ser prosa normativa numerada.

### ADR-20 · El texto literal del fragmento se guarda en el payload

- **Decide:** `texto_literal` viaja en el payload de Qdrant.
- **Alternativa descartada:** guardar solo el `offset` y leer de GCS al verificar.
- **Trade-off:** ~40 MB extra y la obligación de reindexar si el documento cambiara — que no puede
  pasar, porque las versiones publicadas son inmutables.
- **Se revierte si:** el corpus creciera dos órdenes de magnitud y el almacenamiento pesara más
  que los 200 ms por cita.

### ADR-21 · Una colección por versión de política, con alias

- **Decide:** `politica_v12` como colección propia; `politica_actual` es un alias. Las versiones
  anteriores siguen consultables.
- **Alternativa descartada:** una sola colección con `version_id` en el payload y filtro en cada
  consulta. Ahorra memoria y es lo que recomienda el manual del proveedor.
- **Trade-off:** ~700 MB con 12 versiones vivas, y publicación por conmutación de alias.
- **Se revierte si:** nunca mientras exista R2. **Un filtro olvidado una sola vez cita política
  derogada; una colección equivocada no existe.** Es la diferencia entre improbable e imposible.

---

## 12. Lo que hay que validar

| Supuesto | Cómo se cierra |
|---|---|
| 4,800 fragmentos para el corpus completo | Se sabe al procesar el manual real en F1 |
| 8 documentos por expediente | Muestreo de 200 expedientes reales — cierra también el supuesto de `05a` §2 |
| El manual es segmentable por cláusula automáticamente | Prueba sobre las 180 páginas en F1. Si el formato es irregular, hay trabajo manual de curaduría |
| < 50 GB en Neon a tres años | Medición trimestral; es el driver del plan Scale |
| La retención documental sectorial aplicable | **Se hereda de Vitalia** — hay que pedírsela a legal, no inventarla |

---

## 13. Para la presentación

- **Anexo C:** §2 (modelo relacional e invariantes como constraints), §3–§4 (corpus, versionado y
  colección), §7 (linaje) y §9 (clasificación y retención).
- **Anexo D:** ADR-18 a ADR-21.
- **En la lámina principal no va nada de esto** — el modelo de datos es anexo por definición. Lo
  único que sube a la presentación es una frase: *la plataforma no es dueña del afiliado; es dueña
  de la decisión y de su justificación.*
- **Diagramas:** **D-13** (entidades e invariantes) · **D-07** (el pipeline que las llena).

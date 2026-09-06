# Proyecto final — Operación y preparación para producción

- **Proyecto final** · DataPath · AI Solutions Architect
- **Fecha:** 2026-09-05
- **Viene de:** `04_to_be.md` §3 y §7 (flujo y secuencia) · `05a_costeo_cloud.md` (dimensionamiento y FinOps) · `06_seguridad_y_evaluacion.md` (compuertas de calidad)
- **Va hacia:** `08_modelo_de_datos.md` (entidades, linaje y metadata)
- **Cubre:** slide principal 07 · **Anexo F** (sizing, prueba de carga, SLOs y observabilidad) · parte del **Anexo D** (ADR-13 a ADR-17)

> **La tesis de este documento.** Este sistema no es de alto tráfico: en el pico de lunes recibe
> **menos de cinco solicitudes por minuto**. Su desafío operativo no es escalar — es **degradar
> bien**. Cada dependencia externa que cae tiene que dejar el proceso funcionando, y el destino
> de toda degradación es el mismo: **la mesa humana, que no desaparece.**

---

## 1. Qué significa "producción" en este caso

| | |
|---|---|
| **Criticidad** | Alta por consecuencia, baja por volumen. Una caída de 2 horas no rompe nada; una decisión mal emitida sí |
| **El proceso nunca se detiene** | Los 16 analistas siguen existiendo en el TO-BE. La plataforma automatiza el 55–60%; el 100% del proceso puede correr sin ella |
| **Lo que sí es intolerable** | Emitir una decisión indefendible, perder una solicitud, o incumplir el TAT contractual de 5 días / 48 h |
| **Reloj real** | El SLA de negocio se mide en **días**, no en milisegundos. La única ruta con latencia percibida por una persona es la consulta anticipada N1, en el portal del prestador |

Esta asimetría es la que ordena los SLOs: **exigentes donde hay un humano esperando, holgados
donde el reloj es de días.** Poner p95 < 2 s en la adjudicación completa sería sobre-ingeniería
pagada con dinero real.

---

## 2. SLOs

### 2.1 Por recorrido

| # | Recorrido | Naturaleza | Latencia objetivo | Disponibilidad | Ventana |
|---|---|---|---|---|---|
| **J1** | **Consulta anticipada N1** — el médico elige diagnóstico + procedimiento y el portal responde | Síncrona, humano esperando | **p95 < 2 s** · p99 < 4 s | **99.5%** | Horario hábil extendido 06:00–22:00 |
| **J2** | Ingreso del expediente + guardrail de 8 capas | Síncrona | p95 < 3 s · p99 < 6 s | 99.5% | Ídem |
| **J3** | Adjudicación unificada E2 (determinista + RAG + cita) | Asíncrona | **p95 < 90 s** | 99.0% | 24×7 |
| **J4** | Extremo a extremo del carril automático (ingreso → carta emitida) | Asíncrona | **p95 < 5 min** | 99.0% | 24×7 |
| **J5** | Emisión E4 con sello (transaccional contra el core) | Síncrona | p95 < 10 s | 99.9% | 24×7 |
| **J6** | Turno del agente de subsanación | Asíncrona | p95 < 45 s por vuelta | 99.0% | 24×7 |
| **J7** | **TAT de negocio, programados** | Proceso | **p95 ≤ 2.5 días** | — | Mensual |
| **J8** | **TAT de negocio, urgentes** | Proceso | **p95 ≤ 24 h** | — | Mensual |

### 2.2 Error budget y qué se hace con él

99.5% mensual = **3.6 horas de presupuesto de error**. La política:

| Consumo del presupuesto | Consecuencia |
|---|---|
| < 50% | Se despliega normal. Canary de 24 h |
| 50–90% | Se congela todo cambio que no sea corrección. El canary sube a 72 h |
| > 90% | **Alto de despliegues.** El trabajo del sprint pasa a fiabilidad hasta recuperar presupuesto |
| Agotado | Revisión con el sponsor. Se evalúa si el SLO estaba mal puesto o si la arquitectura no lo sostiene |

### 2.3 La disponibilidad compuesta, dicha honestamente

El carril automático encadena Cloud Run (99.95%) → Vertex AI (99.9%) → Qdrant (99.95%) →
Neon (99.95%) → **Groq (sin SLA publicado)**. Multiplicado en serie, la disponibilidad teórica del
carril automático queda **por debajo de 99.5%**, y no hay ingeniería que lo arregle sin
redundar proveedores.

**Por eso el SLO de disponibilidad no se pone sobre la automatización, se pone sobre el proceso.**
El proceso está disponible 100% del tiempo porque la mesa existe. Lo que se mide y se compromete
es **el porcentaje de solicitudes que pudieron resolverse por el carril automático**, con meta
≥ 95% del volumen elegible. Una caída de Groq no baja la disponibilidad: baja el STP ese día, y
eso se ve en el tablero como lo que es.

> Es la diferencia entre prometer que el sistema no se cae y prometer que **el negocio no se
> detiene cuando se cae**. Solo la segunda es defendible con esta cadena de dependencias.

---

## 3. Estrategia de modelos

| Decisión | Elección | Por qué |
|---|---|---|
| **Modelo principal** | **Gemini 2.5 Flash** para extracción (E1), redacción con cita (E2) y el agente (subsanación) | Costo/latencia adecuados; el trabajo es extracción y redacción sujeta a fuente, no razonamiento abierto |
| **Escalón superior** | **Gemini 2.5 Pro**, solo en casos marcados como interpretativos complejos | Se activa **únicamente si RAGAS demuestra que Flash no alcanza** en ese estrato. Hoy no está activado: +23% de factura (`05a` §8) |
| **Embeddings** | `text-embedding-3-large` (OpenAI), 3,072 dims | Elegido en el curso y validado sobre el corpus; cuesta **$0.10/mes** — no es una variable económica |
| **Reranking** | Vertex AI Ranking sobre el top-20 del híbrido | Sube precisión donde el código exacto compite con la prosa |
| **Guardrail 7–8** | Llama Prompt Guard 2 (86M) + Llama Guard 4 (12B) en Groq, `temp=0.0` | Latencia y costo; ver ADR-09 |
| **Temperatura** | `0.0` en todo el camino de decisión. La única salida con temperatura > 0 es el borrador de redacción de cortesía de la carta, que el humano puede editar | Reproducibilidad (V2) |
| **Routing** | Por **tipo de sub-problema**, no por dificultad estimada: determinista → motor de reglas; interpretativo → RAG; camino variable → agente | El ruteo es la matriz de decisión de `02`, no una heurística en runtime |
| **Caching** | **Caché semántico** sobre las 24 combinaciones recurrentes (71% del volumen), con clave `dx × procedimiento × plan × versión_política`. Invalidación total ante cada endoso | Es lo que mantiene las consultas al RAG en ~3,500/mes pese a que N1 se ejecuta muchas más veces |
| **Fallback** | **Al carril manual, nunca a otro proveedor de LLM** | ADR-13 |

> **El caché es el supuesto económico más apalancado del diseño.** N1 se invoca cada vez que un
> médico explora una opción — bastante más que las 7,800 solicitudes. Si el *hit rate* del caché
> resultara mucho menor que la concentración del 71%, la parte variable de la factura sube; el
> efecto está acotado en `05a` §8 y es del orden de +$60/mes, no del orden de romper el caso.

---

## 4. Resiliencia

### 4.1 Patrones aplicados, con su disparador

| Patrón | Dónde | Configuración | Qué falla si no está |
|---|---|---|---|
| **Timeout escalonado** | Toda llamada saliente | Presupuesto total de J3 = 90 s, repartido: guardrail 8 s · extracción 25 s · retrieval 6 s · redacción 30 s · verificación 5 s | Un cuelgue de un tercero consume la cola entera |
| **Retry con backoff exponencial + jitter** | Solo operaciones **idempotentes**: retrieval, extracción, embeddings | Máx. 3 intentos · base 400 ms · jitter completo · nunca excede el presupuesto del recorrido | Reintentar en tormenta amplifica la caída |
| **Circuit breaker** | Una instancia **por dependencia**: Vertex, Qdrant, Neon, Groq, Document AI, core | Abre con 5 fallos en 30 s · abierto 60 s · medio-abierto con 1 sonda | Se siguen pagando llamadas a un servicio caído y se agota el presupuesto de tiempo |
| **Fallback chain** | Modelos y retrieval | Flash región primaria → Flash región secundaria → **carril manual** | Ver ADR-13 |
| **Bulkhead** | Pools separados por recorrido | El agente de subsanación no puede consumir la concurrencia de N1 | Un lote de subsanaciones degrada la experiencia del portal |
| **Idempotencia** | Ingreso y emisión | Clave `id_solicitud + version_politica + sha256(expediente)`; E4 emite contra el core con clave de idempotencia | Cartas duplicadas — que en este dominio es un incidente, no un detalle |
| **DLQ** | Pub/Sub, entre estados | 5 reintentos → DLQ → **cola de revisión del supervisor** con alerta | Una solicitud perdida es un incumplimiento de SLA contractual |
| **Cuotas y presupuesto por caso** | Borde y orquestador | Tope de páginas por expediente, máx. 3 pedidos y 8 iteraciones del agente, presupuesto de tokens por solicitud | A7 (DoS económico) |

### 4.2 Degradación por niveles

Explícita, con criterio de activación y efecto medible. **Ningún nivel apaga el proceso.**

| Nivel | Disparador | Comportamiento | Efecto |
|---|---|---|---|
| **N0** | Normal | Todo el carril automático | STP 55–60% |
| **N1** | Vertex AI Ranking degradado | Se sirve sin *rerank* y **sube el umbral de confianza** | STP ≈ −5 pp; más HITL |
| **N2** | Qdrant no disponible | Solo el motor determinista. Los casos interpretativos van al analista con el expediente ya armado | STP ≈ 25%. El copago y la elegibilidad **siguen automáticos** — que es donde está el 58% del valor |
| **N3** | Vertex AI no disponible | Sin extracción ni redacción. N1 responde solo con caché + determinista | STP ≈ 15%. La mesa absorbe el resto |
| **N4** | **Groq no disponible** | **Fail-close:** ninguna solicitud entra al carril automático | STP = 0%. Proceso en modo AS-IS |
| **N5** | Neon o core no disponibles | No se emite nada. Las solicitudes se encolan con acuse al prestador | Se consume TAT, no se pierde nada |

> **N2 es la degradación que mejor defiende el diseño.** Con el vector store caído, el sistema
> sigue cerrando la fuga de copago — porque esa parte nunca dependió de la IA. Es la misma tesis
> del caso de negocio, vista desde el runbook.

---

## 5. Dimensionamiento y prueba de carga

### 5.1 El volumen real, calculado

| Cálculo | Valor |
|---|---|
| Solicitudes/mes | 7,800 |
| Días hábiles/mes | 22 |
| Promedio por día hábil | **355** |
| **Pico de lunes** — P6, 2.4× el promedio | **852/día** |
| Concentración 08:00–13:00 (~65%) | 554 en 5 h → **111/h** |
| Cuarto de hora más cargado (≈2.5× la media horaria) | **≈ 4.6 solicitudes/minuto** |
| **Pico sostenido en req/s** | **≈ 0.08 req/s** |

**El pico de este sistema cabe en una instancia.** El dimensionamiento no lo manda el throughput
— lo mandan tres cosas distintas:

1. **Cuotas por minuto** de Vertex AI (RPM y TPM), Document AI (páginas/min) y Groq. Con 4.6
   solicitudes/minuto y ~8 páginas cada una, el pico son ~37 páginas/min en Document AI y ~14
   llamadas/min a Gemini: holgado, pero **hay que solicitar la cuota antes del go-live**, no
   descubrirla en el pico.
2. **Concurrencia de N1**, que es mucho mayor que la de solicitudes y es la que justifica
   `min-instances=1` en el portal del prestador.
3. **Pool de conexiones a Neon** — 1.5 CU con `pgbouncer`; el enemigo aquí es una fuga de
   conexiones del orquestador, no el tráfico.

### 5.2 Plan de prueba de carga (F2)

| Prueba | Objetivo | Perfil | Criterio de aprobación |
|---|---|---|---|
| **P1 · Nominal** | Confirmar SLOs en régimen | 355 solicitudes distribuidas en 9 h | Todos los SLO de §2.1 |
| **P2 · Pico de lunes** | El escenario real que hoy incumple | 852 en un día, con 65% en 5 h | p95 de J1 < 2 s durante todo el pico · cero DLQ |
| **P3 · Ráfaga** | Reapertura tras caída del portal | 300 solicitudes en 10 min | Encola sin pérdida; J4 se degrada pero no falla |
| **P4 · Resistencia** | Fugas de memoria y de conexiones | 72 h a volumen nominal | Sin crecimiento de RSS ni del pool; sin reinicios |
| **P5 · Caos por dependencia** | Validar §4.2 nivel por nivel | Se corta Qdrant, luego Vertex, luego Groq, 20 min cada uno | Cada nivel se comporta como la tabla dice, y **vuelve solo** |
| **P6 · Expediente patológico** | A7 | 400 páginas · 60 adjuntos · PDF corrupto | Rechazo limpio con mensaje al prestador; sin costo desbocado |
| **P7 · Costo bajo carga** | Validar `05a` | Se mide costo/solicitud real en P1 y P2 | Dentro de ±20% de S/ 0.86 |

**P5 y P7 son las dos que casi nadie corre y las dos que más valen aquí:** una valida que la
degradación diseñada existe de verdad, la otra convierte el costeo de estimación en medición.
El resultado de P7 es lo que cierra el supuesto de dimensionamiento de Qdrant y Neon declarado
en `05a` §11.

---

## 6. Observabilidad

### 6.1 La traza

Una traza por solicitud, un *span* por estado (`guardrail`, `E1`, `E2.determinista`,
`E2.rag`, `E3`, `agente.turno_n`, `E4`). **Atributos obligatorios en todo span que toque un modelo:**

```
id_solicitud · version_politica · prompt_id + sha256 · modelo + version
tokens_in · tokens_out · costo_usd · latencia_ms · decision_guardrail
confianza · ruta (auto | hitl | agente) · cache_hit · citas_verificadas
```

Sin `version_politica` y `prompt_id` una traza no sirve para reconstruir una decisión — y
reconstruir decisiones es el requisito R2, no una comodidad de depuración.

**Herramientas:** LangSmith para la traza de razonamiento y la evaluación continua; Cloud Trace y
Cloud Monitoring para infraestructura y red; BigQuery como destino analítico donde ambas se
cruzan (ADR-17). El texto clínico **nunca** viaja crudo a la traza (`06` §5).

### 6.2 Atribución de costo

Cada *span* lleva su costo. Agregado en BigQuery da **costo por solicitud, por tipo de
procedimiento y por versión de prompt** — que es la métrica que se reporta al comité, no el total
de la factura. Es también la que permite responder *"¿cuánto costó cambiar el prompt?"* con un
número en vez de una opinión.

### 6.3 Tableros, por audiencia

| Tablero | Quién | Qué muestra |
|---|---|---|
| **Operación** | Supervisor de mesa | El **trío** (STP · reversiones · negaciones sin firma), cola por estado, casos en DLQ, TAT proyectado del día |
| **Fiabilidad** | Arquitecto / ingeniería | SLO y error budget por recorrido, estado de cada circuit breaker, nivel de degradación activo |
| **Economía** | FinOps / sponsor | Costo por solicitud, fijo vs. variable, desvío contra `05a`, alerta de presupuesto |
| **Cumplimiento** | Curador de política / legal | 100% de cartas con versión sellada · 0 negaciones sin firma · % de citas verificadas · edad del corpus |

### 6.4 Alertas — seis, y con dueño

Deliberadamente pocas. Una alerta que nadie atiende entrena a ignorar el resto.

| Alerta | Umbral | Dueño | Severidad |
|---|---|---|---|
| Invariante roto (negación sin firma, carta sin versión) | **cualquier ocurrencia** | Arquitecto + cumplimiento | **P1** |
| Solicitud en DLQ | > 0 durante 15 min | Supervisor | P1 |
| Reversiones al apelar | > 0.7% semanal | Producto + auditor médico | P2 |
| Nivel de degradación ≥ N3 | > 10 min | Ingeniería de guardia | P2 |
| SLO de J1 en riesgo | 50% del error budget mensual | Ingeniería | P3 |
| Costo diario | > 130% de la media móvil de 7 días | FinOps | P3 |

**Deriva** (cambio en la distribución de combinaciones dx–procedimiento, o caída del acuerdo con
el golden set) no es alerta: es un **informe semanal** al curador de política. No se despierta a
nadie por una deriva, se decide qué hacer con ella.

---

## 7. Despliegue y compuertas de publicación

| Etapa | Compuerta para pasar |
|---|---|
| Desarrollo → CI | Promptfoo (60 rápidos + 40 adversariales) en verde. **Invariantes al 100%** |
| CI → Staging | Golden set completo + RAGAS sobre los umbrales de `06` §10.1 |
| Staging → Canary | Red team manual completo · P1 y P5 de la prueba de carga · revisión del curador si cambió el corpus |
| Canary 5% | 24 h · el trío estable · sin regresión de latencia |
| Canary 25% | 72 h · reversiones ≤ base · error budget < 50% |
| Canary 100% | Aprobación del supervisor de mesa |
| **Retroceso automático** | Reversiones al alza · invariante roto · p95 de J1 fuera de SLO 15 min |

**Publicación de un endoso de política** (que ocurre ~6 veces al año y es el cambio más riesgoso
del sistema, más que un despliegue de código):

```
endoso recibido → curador valida y firma (sha256, vigencia_desde/hasta, diff vs vN-1)
   → reindexado a colección nueva en Qdrant (la anterior queda viva)
   → 30 casos de regresión de política: las respuestas DEBEN cambiar donde corresponde
   → invalidación total del caché semántico
   → publicación por alias de colección  → la versión anterior se retiene 400 días
```

Que la colección anterior siga viva es lo que permite responder *"¿qué habría dicho el sistema el
12 de marzo?"*. No es histórico: es el requisito de reconstruibilidad.

---

## 8. Runbook — los seis incidentes probables

| # | Síntoma | Diagnóstico rápido | Acción | Quién |
|---|---|---|---|---|
| **I1** | STP cae en picada | Tablero de fiabilidad: ¿qué breaker está abierto? | Confirmar el nivel de degradación; comunicar a la mesa que absorba; **no** desactivar el guardrail | Guardia |
| **I2** | Solicitudes en DLQ | Causa del último reintento en la traza | Reprocesar por lote tras corregir; si es de datos, va a la cola del supervisor | Guardia + supervisor |
| **I3** | Citas no verificables suben | ¿Se publicó un endoso? ¿cambió el *chunking*? | Congelar emisión automática (queda como asistente); reindexar; correr los 30 de regresión | Curador + ingeniería |
| **I4** | Costo diario disparado | Atribución por span: ¿qué prompt, qué tipo? | Buscar bucle del agente o caché invalidado; aplicar cuota; revisar el tope de páginas | FinOps + ingeniería |
| **I5** | **Invariante roto** | Traza completa del caso | **Detener emisión automática de inmediato.** Reconstruir el caso, notificar a cumplimiento, caso permanente de regresión | Arquitecto (P1) |
| **I6** | Latencia de J1 fuera de SLO | ¿*Cold start*, caché frío o Qdrant lento? | Verificar `min-instances`; precalentar el caché; escalar el cluster si es sostenido | Guardia |

**Regla transversal:** ante cualquier duda, la acción segura es **bajar de nivel de
automatización**, nunca relajar un control. La mesa absorbe; el guardrail no se apaga.

---

## 9. Continuidad

| Componente | RPO | RTO | Mecanismo |
|---|---|---|---|
| **Neon** (estado del proceso) | **5 min** | 30 min | PITR de la rama productiva + réplica |
| **Qdrant** (índice vectorial) | **0** | 2 h | **Es un artefacto derivado.** El corpus firmado en GCS es la fuente de verdad; el índice se reconstruye |
| **GCS** (corpus y expedientes) | 0 | inmediato | Multi-región + versionado de objetos |
| **Core / Acredita Salud** | — | — | Fuera de alcance: son sistemas de terceros. E2 los consume tras un adaptador |
| **Trazas** | 24 h | — | No críticas para operar; sí para auditar |

Que el índice vectorial tenga RPO 0 sin réplica cara es consecuencia directa de una decisión de
diseño: **el corpus versionado y firmado, no el índice, es el sistema de registro.** Reindexar
cuesta $0.10 y dos horas.

**Prueba de recuperación:** semestral, reconstrucción completa del índice desde GCS en un
proyecto limpio, cronometrada. Un RTO que no se ensaya es un número en una diapositiva.

---

## 10. FinOps operativo

El detalle está en `05a_costeo_cloud.md` §10; lo que corre en la operación diaria es:

| Control | Cadencia |
|---|---|
| Etiquetas obligatorias (`app`, `entorno`, `fase`, `componente`) — sin etiqueta no se despliega | Continuo |
| Alertas de presupuesto al 50 / 80 / 100 / 120% | Mensual |
| Costo por solicitud desde la atribución por span, reportado junto al trío | Semanal |
| Cuotas duras por servicio y presupuesto de tokens por solicitud | Continuo |
| Retención escalonada de logs (90 d caliente / 400 d frío) | Continuo |
| Revisión de dimensionamiento de Qdrant y Neon — el 35% de la factura | Trimestral |
| CUDs cuando haya 3 meses de facturación real | A partir del mes 4 de producción |

---

## 11. Lista de verificación de go-live

Ninguna fase pasa a producción sin las diez marcas. Es la traducción operativa del checklist del
proyecto.

| # | Verificación | Estado hoy |
|---|---|---|
| 1 | Cuotas de Vertex AI, Document AI y Groq solicitadas y confirmadas | ⬜ F2 |
| 2 | SLOs instrumentados y visibles en tablero (no en un documento) | ⬜ F2 |
| 3 | P1, P2 y **P5** de la prueba de carga aprobadas | ⬜ F2 |
| 4 | Los seis breakers probados con caos real, con retorno automático | ⬜ F2 |
| 5 | DLQ con dueño, alerta y procedimiento de reproceso | ⬜ F2 |
| 6 | Golden set anotado, con κ reportado | ⬜ F1 |
| 7 | Red team en verde, invariantes al 100% | ⬜ F2 |
| 8 | Runbook ensayado con la guardia — al menos I1, I2 e I5 | ⬜ F3 |
| 9 | Recuperación del índice cronometrada | ⬜ F3 |
| 10 | Tablero del supervisor aceptado **por el supervisor** | ⬜ F3 |

---

## 12. ADRs de operación

### ADR-13 · El fallback es el carril manual, no otro proveedor de LLM

- **Decide:** ante indisponibilidad del modelo, la solicitud va a la mesa. No hay conmutación a
  un LLM de otro proveedor.
- **Alternativa descartada:** cadena multi-proveedor (Gemini → Claude → GPT). Da continuidad
  técnica, pero **rompe R2**: dos solicitudes idénticas decididas por modelos distintos no son
  reconstruibles con un mismo criterio, y el golden set se evaluó contra uno.
- **Trade-off:** el STP cae a 0 mientras dure la caída. Se acepta porque el proceso no se detiene
  y el SLA de negocio está en días.
- **Se revierte si:** el SLA de negocio bajara a horas, o si el golden set se evaluara y sostuviera
  contra dos modelos en paralelo — con el costo de evaluación duplicado que eso implica.

### ADR-14 · `min-instances=1` en tres servicios, aceptando el 73% del gasto de Cloud Run

- **Decide:** portal del prestador, consola de la mesa y app del afiliado corren siempre calientes.
- **Alternativa descartada:** escalado a cero en todo. Ahorra ~$115/mes (8% de la factura).
- **Trade-off:** 2–3 s de arranque en frío en J1, justo en la pantalla que sostiene la meta de
  observaciones ≤ 9%. Se paga la disponibilidad instantánea.
- **Se revierte si:** la medición muestra que el arranque en frío no afecta la adopción del portal,
  o si el tráfico se vuelve continuo y las instancias ya no se apagan.

### ADR-15 · Caché semántico por combinación, invalidado por endoso

- **Decide:** clave `dx × procedimiento × plan × versión_política`; invalidación **total** ante
  cada endoso.
- **Alternativa descartada:** TTL por tiempo. Más simple, pero abre una ventana donde se responde
  con política vencida — que es exactamente A5.
- **Trade-off:** seis veces al año el caché arranca frío y la latencia y el costo suben unos días.
- **Se revierte si:** nunca mientras R2 esté vigente. La invalidación por versión es el punto.

### ADR-16 · Pub/Sub con DLQ entre estados, no una cola en la base de datos

- **Decide:** las transiciones entre E1–E4 viajan por Pub/Sub con reintentos y DLQ.
- **Alternativa descartada:** tabla de cola en Neon. Menos piezas y transaccional con el estado,
  pero acopla la disponibilidad del proceso a la de la base y no da DLQ ni reintento gestionado.
- **Trade-off:** consistencia eventual entre estados; obliga a idempotencia explícita (§4.1).
- **Se revierte si:** el volumen se mantuviera bajo y la simplicidad pesara más que la resiliencia
  — hoy no, porque perder una solicitud es un incumplimiento contractual.

### ADR-17 · LangSmith para la traza de razonamiento, Cloud Monitoring para infraestructura

- **Decide:** dos sistemas, un destino analítico común en BigQuery.
- **Alternativa descartada:** todo en Cloud Trace con atributos propios. Ahorra $156/mes, pero no
  da evaluación continua contra el golden set ni comparación entre versiones de prompt.
- **Trade-off:** un tercero más en el diagrama, un asiento por persona y correlación de `trace_id`
  entre ambos sistemas.
- **Se revierte si:** Cloud Trace incorpora evaluación con conjunto de referencia, o si el equipo
  baja de 4 personas y el costo por asiento deja de justificarse.

---

## 13. Lo que hay que validar

| Supuesto | Cómo se cierra |
|---|---|
| *Hit rate* del caché ≈ concentración del 71% | Se mide en F2 con tráfico real de N1. Es el supuesto económico más apalancado |
| Cuotas por minuto de Vertex, Document AI y Groq alcanzan el pico de lunes | Solicitud formal de cuota antes del go-live de F2 |
| El pico de lunes 2.4× se mantiene tras N1 | N1 debería **aplanar** el pico al resolver en el acto; si no, el sizing se rehace |
| Dimensionamiento de Qdrant y Neon | Prueba P7, que además cierra el pendiente de `05a` §11 |
| p95 de J1 < 2 s con caché frío | Es el peor caso real, el lunes siguiente a un endoso. Se prueba explícitamente |

---

## 14. Para la presentación

- **Slide 7 (costos y go-live):** la tabla de degradación de §4.2 y la lista de verificación de
  §11, junto al costo por solicitud de `05a`. Es lo que convierte "está diseñado" en "puede
  entrar a producción".
- **Anexo F:** §2 (SLOs), §5 (sizing y prueba de carga), §6 (observabilidad) y §9 (continuidad).
- **Anexo D:** ADR-13 a ADR-17.
- **La frase de cierre:** *el reto de este sistema no es escalar, es degradar bien — y toda
  degradación termina en el mismo lugar: la mesa, que no desaparece.*
- **Diagramas:** **D-08** (ciclo de vida y compuertas) · **D-11** (dónde vive cada servicio) ·
  **D-14** (secuencia con objetivo de latencia por tramo).

# Proyecto final — Proceso objetivo (TO-BE)

- **Proyecto final** · DataPath · AI Solutions Architect
- **Fecha:** 2026-09-04
- **Viene de:** `00_modelo_del_problema.md` (fallas F1–F4) · `01_caso_y_as_is.md` (línea base) ·
  `02_matriz_de_decision.md` (ruteo S1–S8) · `03_benchmark_mercado.md` (referencias)
- **Va hacia:** `05_caso_de_negocio.md` (el dinero) · `06_arquitectura.md` (el cómo técnico)

> **Revisión 1.1 — 2026-09-04.** Las secciones 3, 4 y 7 se reescribieron después del análisis de
> `04a_rediseno_del_proceso.md`. La primera versión conservaba los ocho sub-procesos del AS-IS y
> les cambiaba el motor: eso era automatizar, no rediseñar. El proceso objetivo pasa de diez
> estados (E0–E9) a **cuatro estados en tres carriles**, con tres capacidades que antes no
> existían. El razonamiento completo está en `04a`.

---

## 1. El principio de diseño

> **El expediente llega al humano ya armado, no el humano al expediente.**

Hoy el analista es quien recolecta: abre PDFs, consulta tres pantallas, busca en un manual y
recién ahí decide. En el TO-BE el sistema hace la recolección completa —extracción, elegibilidad,
carencia, cobertura con cita textual, copago calculado, borrador de carta— y el humano hace lo
único que un humano hace mejor: **juzgar el caso difícil y firmar.**

De ahí se derivan tres reglas que no se negocian en el diseño:

| Regla | Origen |
|---|---|
| **R1 · Lo determinista nunca pasa por un modelo.** Elegibilidad y carencia se resuelven por integración y reglas | F3 · matriz D1/D2 |
| **R2 · Ninguna afirmación sobre la política se emite sin cita textual de la versión vigente ese día** | F4 · veto V2 · nH Predict |
| **R3 · Ninguna negación por necesidad médica se emite sin firma de médico colegiado** | Veto V1 · SB 1120 |

R3 se adopta aunque el Perú **todavía no lo exija**. Es una decisión de postura: la norma
estadounidense va en esa dirección y SUSALUD sanciona precisamente por cobertura indebidamente
negada. Es más barato nacer cumpliendo que migrar después.

---

## 2. El cambio que ocurre antes de todo: prevenir en el origen

El hallazgo más incómodo del benchmark es que los mercados maduros **no optimizaron la cola —
evitaron que la solicitud incompleta entrara a la cola.** Eso es CRD + DTR.

En el Perú no hay CDS Hooks ni EHR que los dispare. Pero el *efecto* sí se puede replicar dentro
del propio portal de prestadores, que es nuestro:

```
   AS-IS                                   TO-BE
   -----                                   -----
   El prestador envía          →           El portal, al elegir diagnóstico
   lo que cree que hace falta               y procedimiento, RESPONDE
        |                                  (cubierto / no cubierto / falta X),
        v                                  muestra la cita y el copago estimado
   Entra a la cola                              |
        |                                       v
        v                                  El caso limpio se autoriza AHÍ MISMO;
   24h después: OBSERVACIÓN                 el resto entra a la cola ya completo
        |                                       |
        v                                       v
   El prestador pierde un día              (el 23% de observaciones tardías
   y el cupo de quirófano                    colapsa a un residuo)
```

Esto tiene **dos mitades con naturaleza distinta**, y conviene no confundirlas:

- **La mitad barata y sin IA (F0a):** la tabla de requisitos por tipo de procedimiento —que ya
  existe en la política— expuesta en el formulario, bloqueando el envío incompleto. Es el cambio
  de mayor impacto sobre F1 y el más barato del proyecto. **Si el proyecto se quedara sin
  presupuesto después de esta pieza, ya habría pagado.**
- **La mitad con IA (N1, en F2):** *responder* la pregunta de cobertura con la cita textual antes
  de que exista la solicitud. Esto es lo que convierte la prevención en rediseño, y necesita el
  RAG — por eso no puede ir en la primera fase.

Lo que también lleva IA es verificar que el adjunto **sea** lo que dice ser (que el PDF rotulado
"riesgo anestésico" efectivamente lo contenga). Eso es D3 y ocurre dentro del flujo.

> **Por qué esto es rediseño y no optimización.** Hoy nadie responde consultas de cobertura
> porque contestar una cuesta lo mismo que resolver un expediente: 7 minutos de búsqueda en el
> manual. Cuando responder cuesta céntimos, la pregunta deja de tener que convertirse en
> solicitud para ser respondida. **La restricción que daba forma al proceso era económica, no
> funcional.**

---

## 3. El flujo objetivo

Es una **máquina de estados explícita**, no un agente (justificación en `02_matriz_de_decision.md` §3).
Y es un **rediseño**, no una automatización del flujo actual: tres carriles y cuatro estados,
donde el AS-IS tenía ocho sub-procesos en una sola secuencia (análisis en `04a`).

```
╔═ CARRIL 0 ═ EN EL PUNTO DE LA ORDEN ════════════════════════════════════════╗
║  N1 · CONSULTA DE COBERTURA ANTICIPADA     [RAG con cita + motor de copago] ║
║  Al elegir diagnóstico + procedimiento + plan, el portal responde ANTES     ║
║  de que exista la solicitud: cubierto / no cubierto / falta el sustento X,  ║
║  con la cita textual y el copago estimado al afiliado                       ║
╚════════╤═════════════════════════════════════════════════╤══════════════════╝
         │ caso limpio + sustento adjunto                  │ no resoluble aquí
         v                                                 v
   AUTORIZADO EN EL ACTO ──────────────────┐    ╔═ CARRIL 1 ═ EXPEDIENTE ═════╗
                                           │    ║ GUARDRAIL DE ENTRADA        ║
                                           │    ║ 8 capas · barato→caro       ║
                                           │    ║ fail-close                  ║
                                           │    ╚══════════════╤══════════════╝
                                           │                   v
                                     ┌─────────────────────────────────────────┐
                                     │ E1 · EXTRACCIÓN        [con IA · D3]    │
                                     │ solo documentos clínicos: informe,      │
                                     │ exámenes, riesgo anestésico             │
                                     │ (los campos administrativos ya vienen   │
                                     │  capturados desde N1)                   │
                                     └───────────────────┬─────────────────────┘
                                                         v
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  E2 · ADJUDICACIÓN UNIFICADA DE PÓLIZA          ← fusiona S4 + S5 + S6        │
 │  Una sola evaluación devuelve, en una llamada:                                │
 │  ┌──────────────────────────────┬──────────────────────────────────────────┐  │
 │  │ DETERMINISTA  [SIN IA]       │ INTERPRETATIVO  [CON IA · D4]            │  │
 │  │ · elegibilidad (D1)          │ · cobertura y exclusión redactadas en    │  │
 │  │   Acredita Salud + core      │   prosa, resueltas por RAG híbrido       │  │
 │  │ · carencia y preexistencia   │   (denso + BM25) sobre la versión        │  │
 │  │   (D2) tabla 0/30/…/300 d    │   vigente ese día                        │  │
 │  │ · copago: plan × atención ×  │ · CITA TEXTUAL OBLIGATORIA (V2)          │  │
 │  │   nivel × acumulado × tope   │                                          │  │
 │  └──────────────────────────────┴──────────────────────────────────────────┘  │
 │  Estaban separados porque eran tres pantallas y tres personas, no porque      │
 │  sean tres decisiones                                                         │
 └───────────────────────────────┬───────────────────────────────────────────────┘
                                 v
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  E3 · RUTEO MEDIDO         ← reemplaza la derivación defensiva del analista   │
 └───┬──────────────────────┬─────────────────────────┬──────────────────────────┘
     │ confianza alta       │ criterio clínico        │ sustento incompleto
     │ sin exclusión        │ o negación por          │ (residuo)
     v                      │ necesidad médica        v
 ┌──────────────┐           v                 ┌──────────────────────────┐
 │ AUTOMÁTICO   │  ┌───────────────────┐      │ AGENTE DE SUBSANACIÓN    │
 │ 55-60%       │  │ HITL              │      │ decide qué pedir, a      │
 │              │  │ médico auditor    │      │ quién, revisa lo que     │
 │ decisión y   │  │ ── R3: su firma   │      │ llega y reevalúa —       │
 │ carta son el │  │    es obligatoria │      │ EN SESIÓN, no como carta │
 │ MISMO acto   │  │    para negar ──  │      │ de observación a 24 h    │
 └──────┬───────┘  └─────────┬─────────┘      └────────────┬─────────────┘
        │                    │                             │ completo
        │                    v                             │
        │        ┌───────────────────────────┐             │
        └───────►│ E4 · EMISIÓN CON SELLO    │◄────────────┘
                 │ [transaccional + gate]    │
                 │ carta + carta de garantía │
                 │ SELLO DE VERSIÓN + citas  │
                 └─────────────┬─────────────┘
                               v
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  TRAZA INMUTABLE   ── responde F4 ──                                          │
 │  qué se decidió · con qué versión de política · qué se citó · quién firmó     │
 └───────────────────────────────────────────────────────────────────────────────┘

╔═ CARRIL 2 ═ EPISODIO ═══════ requiere endoso a la póliza · fase condicional ══╗
║  N2 · AUTORIZACIÓN DEL PLAN DE TRATAMIENTO COMPLETO                          ║
║  Esquema oncológico o plan de terapias autorizado una vez, con control de     ║
║  consumo y REVALIDACIÓN AUTOMÁTICA de elegibilidad en cada ejecución.         ║
║  Es seguro solo porque E2 volvió gratuita la revalidación.  ≈ −1,400 sol./mes ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

> **Por qué E4 no es un estado en el carril automático.** Cuando no hay firma humana de por
> medio, decidir y emitir son la misma transacción. E4 solo existe como estado separado cuando
> hay un gate humano que esperar. Mantenerlo siempre separado era un residuo del AS-IS, donde el
> analista copiaba a mano el resultado a la carta.

### El único lugar donde hay un agente

**La subsanación.** Es el sub-proceso donde el camino sí varía por caso: decidir qué falta,
a quién pedírselo, evaluar lo que llegue y volver a entrar al flujo. Tiene herramientas,
iteración y un objetivo abierto — es exactamente D5.

> **El agente persigue documentos. Nunca decide la autorización.**

Ese recorte es la decisión de arquitectura más defendible del proyecto. No es "no usé agentes";
es "los usé donde pagan y los prohibí donde el negocio necesita determinismo".

---

## 4. Sub-problema por sub-problema: qué cambia

La columna **acción** es lo que distingue este cuadro de una tabla de automatización: no dice con
qué se reemplaza cada paso, dice **si el paso sigue existiendo**.

| # | Sub-problema AS-IS | Acción | TO-BE | Falla |
|---|---|---|---|---|
| S1 | Recepción y normalización | **ELIMINAR** | Deja de existir: la solicitud nace estructurada en **N1**, con catálogo, no con texto libre | F1 |
| S2 | Extracción del expediente | **REDUCIR** | **E1** sobrevive solo para documentos clínicos; los campos administrativos ya no se extraen | F1 |
| S3 | ¿Sustento completo? | **ELIMINAR EL ESTADO** | "Observación" pasa de estado del expediente a **condición de envío**. No hay carta a las 24 h | F1 |
| S4 | Elegibilidad | **UNIFICAR** | ↓ | F3 |
| S5 | Carencia y preexistencia | **UNIFICAR** | Los tres colapsan en **E2 · adjudicación unificada**: una llamada devuelve elegibilidad + carencia + cobertura + exclusión + copago con cita | F3 |
| S6 | Cobertura, exclusión, copago | **UNIFICAR** | ↑ | F2 + F3 |
| S7 | Casos límite | **REDISTRIBUIR** | **E3**: el ruteo lo hace el sistema por umbral medido, no el analista por miedo. El auditor deja de ser válvula de escape | F2 |
| S8 | Emisión | **ABSORBER** | En el carril automático, decidir y emitir son el mismo acto. **E4** solo es un estado cuando hay firma humana | F4 |

**Tres pasos desaparecen, tres se funden en uno, uno se reduce y uno cambia de dueño: ocho
sub-procesos → cuatro estados.**

Y las dos filas que hay que subrayar en la presentación siguen siendo **S4 y S5**: no llevan IA,
y entre las dos concentran el 27% del esfuerzo actual y el 100% de la fuga por copago mal
aplicado. Que ahora vivan **dentro** de E2 no cambia el argumento: dentro de E2, la parte
determinista resuelve el 63% de la evaluación.

---

## 5. Metas operativas

| Métrica | AS-IS | Meta TO-BE | Palanca principal |
|---|---|---|---|
| **STP** — solicitudes resueltas sin toque humano | 0% | **55–60%** | N1 + E1 + E2 encadenados |
| Touch time medio ponderado | 19 min | **7 min** | 57% a 0 min · el 43% restante ~16 min (son los difíciles) |
| Observaciones tardías | 23% | **≤ 9%** | F0a (bloqueo del envío incompleto) + N1 (respuesta anticipada) |
| **Volumen de entrada a la mesa** | 7,800/mes | **≈ 6,400/mes** | N2 · autorización por episodio — **holgura, no compromiso** (§8 de `04a`) |
| Derivación al auditor | 21% | **≤ 10%** | Cita a la vista elimina la derivación defensiva |
| — de ellas, confirmadas necesarias | ~45% | **≥ 85%** | Umbral de confianza calibrado |
| Error de copago | 3.8% | **≤ 0.4%** | Motor determinista (sin IA) |
| Reversiones al apelar | 1.4% | **≤ 0.7%** | Decisión sustentada con cita |
| Tiempo de respuesta (TAT) programados, p95 | 6.8 días ❌ | **≤ 2.5 días** ✅ | Compromiso contractual: 5 días hábiles |
| Tiempo de respuesta urgentes, p95 | 61 h ❌ | **≤ 24 h** ✅ | Compromiso contractual: 48 horas |
| Curva de aprendizaje de un analista | 11 semanas | **≤ 4 semanas** | El conocimiento deja de ser tácito (F2/P5) |
| **Negaciones por necesidad médica sin firma médica** | no medido | **0% — invariante** | R3 |
| **Cartas con versión de política sellada** | 0% | **100% — invariante** | R2 |

### Por qué 55–60% de STP y no 85–90%

Cohere Health reporta hasta 90% de aprobación automática y 85% en tiempo real. Nuestra meta es
deliberadamente la mitad, y la brecha se explica sin excusas:

| Ellos | Nosotros |
|---|---|
| Entrada estructurada FHIR desde el EHR | PDF escaneado desde un portal web |
| Reglas del pagador ya digitalizadas y publicadas (DTR) | Política en prosa, que cambia 6 veces al año |
| Volumen de millones de autorizaciones para calibrar | 7,800/mes — el golden set se construye a mano |
| Cifra reportada por el proveedor, sin auditoría independiente | Meta que hay que sostener frente a SUSALUD |

**Prometer 85% aquí sería el error de diseño de nH Predict:** adoptar la métrica de eficiencia
de otro contexto y forzar la operación a alcanzarla. El 71% del volumen concentrado en 24
combinaciones recurrentes es lo que hace alcanzable el 55–60%; ese supuesto está declarado como
pendiente de validar y **es del que depende esta meta entera**.

### La regla de reporte

> **`% STP` nunca se reporta solo.** Siempre en trío con `% de reversiones al apelar` y
> `% de negaciones sin firma médica`.

Un STP que sube mientras suben las reversiones no es una mejora: es PXDX. Ese trío va en el
tablero del supervisor y en el comité, no en un anexo.

---

## 6. Lo que el TO-BE cambia en la organización

La tecnología no es lo único que cambia. Tres cosas nuevas, y hay que decirlas porque un
blueprint que solo describe cajas de software es incompleto:

| Cambio | Qué implica |
|---|---|
| **Rol nuevo: curador de política** | Alguien es dueño del corpus versionado. Cada endoso se publica con versión, fecha de vigencia y diff. Sin este rol, R2 y F4 no se sostienen |
| **El analista deja de transcribir y pasa a revisar** | Cambia el perfil y la métrica de desempeño: ya no es solicitudes/hora, es calidad de la excepción |
| **El médico auditor recibe menos y mejor** | Su capacidad liberada se reinvierte en los casos que sí requieren criterio, no se recorta |

---

## 7. Secuencia de implementación

El orden no es por dificultad técnica: es por **valor entregado temprano y riesgo retirado
temprano**.

```
  F0a ─ Requisitos por procedimiento en el formulario   [sin IA]      ~4 sem
  │     bloquea el envío incompleto. Ataca el 23% de observaciones.
  │     Si el proyecto parara aquí, ya pagó.
  │
  F1 ── E2 · adjudicación unificada, parte determinista  [sin IA]      ~8 sem
  │     elegibilidad + carencia + motor de copago
  │     ► INCLUYE LA INTEGRACIÓN CON ACREDITA SALUD
  │     ► HITO EXTERNO INNEGOCIABLE: 31-oct-2026
  │     cierra la fuga de copago, la mayor pérdida monetaria del AS-IS
  │     ► ES LA PRECONDICIÓN DE N2: sin revalidación automática y barata,
  │       la autorización por episodio no es defendible
  │
  F2 ── E1 extracción + E2 parte RAG + N1 respuesta anticipada
  │                                             [aquí entra la IA]     ~10 sem
  │     modo sombra primero: el sistema propone, el analista decide,
  │     y se mide el acuerdo contra el golden set antes de habilitar nada
  │
  F3 ── E3 ruteo + carril automático + E4 sello de versión [STP real]  ~6 sem
  │     canary 5% → 25% → 100%, con gates automáticos por métrica
  │
  F4 ── Agente de subsanación                    [el agente]           ~6 sem
  │     lo último, porque es lo de mayor varianza y menor volumen
  │
  F5 ── N2 · autorización por episodio          [CONDICIONAL]          ~6 sem
        BLOQUEADA POR EL ENDOSO A LA PÓLIZA — no es una decisión de arquitectura.
        Si el endoso no se aprueba, la fase no se ejecuta y no se pierde nada
        de lo comprometido: su valor está registrado como holgura, no como meta.
```

**Las dos primeras fases no llevan IA.** Esa secuencia es el argumento del proyecto hecho
cronograma: primero se agota lo determinista, y la IA entra recién cuando queda el problema que
solo ella resuelve.

**Y la fase de mayor retorno por solicitud —F5— es la de menor control del equipo técnico.**
Decirlo en el roadmap, y no esconderlo, es parte del trabajo: el rediseño que más volumen elimina
se aprueba en una mesa contractual, no en una revisión de arquitectura.

---

## 8. Decisión pendiente del sponsor: el carril de gold-carding

El benchmark trae una alternativa **no tecnológica** que ataca el volumen en vez del costo
unitario: eximir de preautorización al prestador con historial de aprobación alto (modelo Texas
HB 3459 — ≥90% de aprobación sostenida en una ventana móvil, por procedimiento).

| A favor | En contra |
|---|---|
| Reduce volumen de entrada, no solo su costo | Cede control de gasto sobre el prestador exento |
| El sistema del TO-BE **ya produce el dato** que lo alimenta (tasa de aprobación por prestador y procedimiento) | Requiere decisión comercial y contractual, no de arquitectura |
| Mejora la relación con la red prestadora | La evidencia de impacto en Texas es modesta y de alcance limitado |

**No se incorpora al alcance sin decisión explícita.** Se deja registrado porque un arquitecto
que propone un sistema sin haber puesto sobre la mesa la alternativa que lo haría innecesario en
parte no está haciendo su trabajo. Si se aprueba, es un consumidor de las métricas del TO-BE, no
un componente nuevo.

---

## 9. Riesgos del TO-BE y su mitigación

| Riesgo | Mitigación de diseño |
|---|---|
| El LLM extrae mal un código y se autoriza lo que no era | Validación contra catálogo: campo no validado = no se autocompleta, va a revisión |
| El RAG cita una versión de política que ya no está vigente | El índice se versiona con la política; la consulta lleva fecha de vigencia como filtro |
| Prompt injection en el expediente (lo redacta un tercero) | Guardrail de 8 capas antes de E1; el contenido del expediente nunca es instrucción |
| El STP sube a costa de negar mal | Trío de métricas + gate automático: si las reversiones suben, el canary retrocede |
| Acredita Salud se atrasa o cambia de especificación | E2 se diseña con adaptador: core hoy, Acredita Salud cuando esté, misma interfaz |
| El 71% de concentración resulta ser menor | La meta de STP se recalcula; F0 y F1 (sin IA) no dependen de ese supuesto |
| Deriva del modelo tras un cambio de política | Evaluación online continua contra golden set + alerta por caída de acuerdo |

---

## 10. Lo que este documento deja listo

- **Slide 3b (rediseño del proceso):** la tabla de la sección 4, con la columna *acción*. Es la
  lámina que demuestra que se rediseñó y no solo se automatizó — desarrollo en `04a`.
- **Slide 4 (propuesta / blueprint):** el diagrama de la sección 3.
- **Slide 6 (resultados esperados):** la tabla de metas de la sección 5, con la regla del trío.
- **Slide 7 (roadmap):** la sección 7, con el hito del 31-oct-2026 marcado.
- **Anexo G (rediseño del proceso y gestión del cambio):** la sección 6, junto a `04a`.
- **Anexo H (riesgos y mitigaciones):** la sección 9.

**Siguiente:** `05_caso_de_negocio.md` — cuánto de estas metas se convierte en dinero, y cuánto
cuesta operarlas.

# Proyecto final — Mesa de preautorización médica, Vitalia Salud EPS

- **Curso:** DataPath · AI Solutions Architect · cohorte 2026-08
- **Autor:** Jonatan Sánchez
- **Fecha:** 2026-09-05 · **Estado:** diseño cerrado · el MVP en Google Cloud es **fase 2**
- **Diagramas:** `diagramas/` — catorce láminas draw.io, versión 1.3

> **De qué va el caso.** Vitalia Salud EPS procesa **7,800 solicitudes de preautorización al mes**
> con 16 analistas, dos turnos y cuatro médicos auditores. El p95 del TAT en programados es de
> **6.8 días contra un compromiso de 5**, y en urgentes **61 horas contra 48**. El proyecto no
> automatiza la mesa: **rediseña el proceso** de ocho sub-procesos a cuatro estados y tres
> carriles, y coloca IA únicamente donde una solución más simple no alcanza.

---

## Los diez documentos, en el orden en que se leen

| # | Documento | Qué establece | No se salta porque… |
|---|---|---|---|
| 00 | `00_modelo_del_problema.md` | Quién es Vitalia, en qué proceso está el dolor y a quién le duele | Es el único que explica el caso a alguien que no sabe de EPS |
| 01 | `01_caso_y_as_is.md` | El AS-IS cuantificado: volumen, tiempos, dolores P1–P7, economía | Todas las cifras del proyecto nacen aquí |
| 02 | `02_matriz_de_decision.md` | Qué lleva IA y qué no · **ADR-01 a ADR-07** | Contiene la decisión de cabecera: **esto no es un agente** |
| 03 | `03_benchmark_mercado.md` | Qué hace el mercado y qué precedentes regulatorios existen | Justifica la postura de firma médica antes de que la norma peruana la exija |
| 04 | `04_to_be.md` | El proceso objetivo: tres carriles, cuatro estados, invariantes y vetos | Es el diseño |
| 04a | `04a_rediseno_del_proceso.md` | Qué paso se elimina, cuál se unifica y cuál cambia de dueño | Demuestra rediseño, no automatización |
| 05 | `05_caso_de_negocio.md` | Valor potencial → capturable → neto · payback · VAN · TIR | Es el 20% de la nota |
| 05a | `05a_costeo_cloud.md` | El costeo servicio por servicio del cloud y los controles FinOps | Convierte "el cloud cuesta" en una factura defendible |
| 06 | `06_seguridad_y_evaluacion.md` | Amenazas A1–A10, guardrails, golden set, red team · **ADR-08 a ADR-12** | Es el 20% de la nota |
| 07 | `07_operacion_y_produccion.md` | SLOs J1–J8, degradación N0–N5, sizing, observabilidad · **ADR-13 a ADR-17** | Es el 15% de la nota |
| 08 | `08_modelo_de_datos.md` | Propiedad del dato, entidades, corpus versionado, linaje · **ADR-18 a ADR-21** | Cierra el Anexo C |

---

## Las cuatro decisiones que ordenan todo lo demás

Si alguien solo puede leer una pantalla de este proyecto, que sea esta.

1. **No es un agente.** Toda solicitud recorre las mismas seis verificaciones, en el mismo orden,
   contra la misma política. Un agente aportaría autonomía donde el negocio necesita determinismo.
   **El único agente del sistema es el de subsanación** — el único sub-proceso donde el camino sí
   varía por caso. *(ADR-01)*
2. **El sistema automático puede autorizar o escalar; no puede negar por necesidad médica.** No
   es una regla de negocio: es la ausencia de la transición en el catálogo de herramientas. Un
   atacante que convenza al modelo de negar un caso no consigue una negación: consigue un
   escalamiento al auditor. *(ADR-10, invariante R3)*
3. **Nada se afirma sobre la política sin cita textual de la versión vigente**, y esa cita se
   verifica literalmente contra el corpus firmado antes de emitir. *(ADR-11, ADR-21, invariante R2)*
4. **La mesa no desaparece.** Toda degradación del sistema —de N0 a N5— termina en el mismo
   lugar: el carril manual. Por eso el SLO se declara sobre el proceso y no sobre la
   automatización. *(ADR-13)*

---

## Mapa a la entrega que pide el docente

### Presentación principal · 8–10 slides (+2 permitidas)

Ocho láminas de rúbrica más tres extras —contexto, 03b rediseño y 08b economía—, dentro de la
holgura que el docente permite. Entre ellas se intercalan **siete planos a página completa**, que
no son slides de discurso sino evidencia de anexo puesta donde se necesita mirarla: se pasan de
largo sin romper el hilo.

| Slide | Contenido | Fuente | Plano a página completa |
|---|---|---|---|
| **Contexto** | Sector, cliente y proceso, para quien no viene de seguros *(extra)* | `00` §0–§1 | **D-01** después |
| **01** | El problema, el usuario y el proceso | `00` §2–§3 · `01` §3–§6 | **D-02** después |
| **02** | AS-IS → TO-BE → KPI → valor | `05` §1–§3 | — |
| **03** | Qué hará la solución y por qué necesita IA | `02` §2–§3 | **D-03** después |
| **03b** | **Rediseño del proceso** (extra) | `04a` | **D-10** después |
| **04** | Arquitectura end-to-end | `04` §3 · `08` | D-06 en lámina · **D-11** después |
| **05** | Patrones y trade-offs | `02` §3–§4 | — |
| **06** | Seguridad y evals | `06` §1–§11 | **D-08** después |
| **07** | Costos, SLOs y go-live | `05a` · `07` | D-14 en lámina |
| **08** | Caso de negocio y roadmap | `05` §4–§7 · `04` §7 | **D-09** después |
| **08b** | **Economía de la plataforma** (extra) | `05a` §3–§9 | D-12 en lámina |
| **Cierre** | Anexos A–J, supuestos declarados y fase 2 | — | — |

### Anexos

Los seis que pide la rúbrica, **A–F**, más cuatro propios que el caso justifica.

| Anexo | Contenido | Dónde vive | Láminas |
|---|---|---|---|
| **A** | Detalle de costos y assumptions | `05a` completo · `05` §6–§7 | D-12 |
| **B** | Arquitectura física/cloud y networking | `04` §3 · `diagramas/README.md` | **D-11** · D-06 |
| **C** | Modelo de datos, pipeline y metadata | `08` completo | **D-13** · D-07 |
| **D** | ADRs y alternativas evaluadas | `02` §3–§4 · `06` §12 · `07` §12 · `08` §11 | D-03 |
| **E** | Golden set, evals y red-team cases | `06` §8–§10 | D-08 |
| **F** | Sizing, load test, SLOs y observabilidad | `07` §2, §5, §6, §9 | **D-14** |
| **G** | Rediseño del proceso y gestión del cambio | `04a` · `04` §6 | D-10 |
| **H** | Riesgos y mitigaciones | `04` §9 | — |
| **I** | Auditoría del baseline | `05` §8 | — |
| **J** | Benchmark de mercado y precedentes | `03` completo | — |

---

## Los veintiún ADRs

Un solo formato en los cuatro documentos que los contienen: **decisión · alternativa descartada ·
trade-off · condición de reversión.**

| Rango | Documento | Sobre qué deciden |
|---|---|---|
| ADR-01 – ADR-07 | `02` §3 y §4 | Flujo orquestado vs. agente · fine-tuning · solo-prompt · multi-agente · GraphRAG · búsqueda híbrida · HITL |
| ADR-08 – ADR-12 | `06` §12 | Guardrail propio + Model Armor · capas 7–8 en Groq · el sistema no puede negar · verificación literal de la cita · Presidio local |
| ADR-13 – ADR-17 | `07` §12 | Fallback al carril manual · `min-instances` · caché semántico · Pub/Sub + DLQ · LangSmith + Cloud Monitoring |
| ADR-18 – ADR-21 | `08` §11 | Propiedad del dato · segmentación por cláusula · texto literal en el payload · colección por versión |

Seis —ADR-07, ADR-10, ADR-11, ADR-15, ADR-18 y ADR-21— tienen como condición de reversión la
palabra **nunca**. Son los que sostienen R2, R3 y el veto V1.

---

## Las cifras que no pueden variar entre documentos

Si una lámina o un anexo dice otra cosa, el error está en la lámina.

| | |
|---|---|
| Volumen | **7,800 solicitudes/mes** · 165,000 afiliados · 16 analistas · 4 médicos auditores |
| Concentración | **71% del volumen en 24 combinaciones** diagnóstico–procedimiento *(supuesto por validar)* |
| Touch time hoy | 19 min (p50 14 · p95 52) |
| TAT hoy | programados p95 **6.8 d** vs. 5 ❌ · urgentes p95 **61 h** vs. 48 ❌ · extranjero p50 9 d vs. 15 ✅ |
| Costo AS-IS | **S/ 235,200/mes** → TO-BE **S/ 80,000/mes** |
| Metas TO-BE | STP **55–60%** · touch **7 min** · observaciones **≤ 9%** · reversiones **≤ 0.7%** · TAT p95 **≤ 2.5 d / ≤ 24 h** |
| Invariantes | **0%** negaciones sin firma · **100%** cartas con versión de política sellada |
| Costo de la plataforma | **S/ 6,700/mes** = **S/ 0.86 por solicitud** · 75% fijo / 25% variable · FX S/ 3.75 |
| Retorno | payback **8.6 meses** · VAN **S/ 1.17 M** · TIR **88%** · TCO 3 años ≈ S/ 219,000 |
| SLOs | J3 adjudicación p95 **< 90 s** · J4 e2e p95 **< 5 min** · J1 consulta N1 p95 **< 2 s** |

---

## Lo que está declarado como supuesto, no como hecho

El proyecto es honesto sobre su propio piso. Estos son los supuestos que un revisor debe poder
señalar sin encontrar una defensa inventada:

- La **concentración del 71%** en 24 combinaciones y el **55% de derivación defensiva** (`01`).
- Los tres drivers del costeo: **8 páginas por expediente**, **45% de las solicitudes al RAG**,
  y el dimensionamiento de Qdrant y Neon (`05a` §11 — la prueba **P7** de `07` §5.2 lo cierra).
- El **κ de Cohen ≥ 0.75** entre anotadores, el **FPR ≤ 0.5%** del guardrail y el umbral de
  confianza de **0.90** (`06` §13).
- El **hit rate del caché semántico**, que es el supuesto más apalancado de todos: sostiene las
  3,500 consultas RAG/mes del modelo de costos (`07` §13).
- Que el manual de política sea **segmentable por cláusula** automáticamente (`08` §12).

---

## El paquete listo para enviar

`entrega_fase1/` es la copia autocontenida que se manda al docente. Se arma desde este directorio
y no se edita a mano: si cambia un documento o un plano, se vuelve a exportar.

```
entrega_fase1/
├── LEEME.md · INDICE_DE_ANEXOS.md
├── 1_presentacion/   Vitalia_presentacion.pdf (20 pág. 16:9) · .html navegable · img/D-01..D-14.png
├── 2_documentacion/  los once documentos + 00_INDICE_del_proyecto.md
└── 3_diagramas/      drawio/ (15 editables) · pdf/ (14 + el consolidado) · LEEME_diagramas.md
```

Cómo se regenera:

```bash
# 1 · los planos, desde diagramas/
python _generar_diagramas.py
# 2 · PNG para la presentación y PDF para el anexo
#     escala 2 porque siete planos se imprimen a página completa: a escala 1 quedan en ~155 DPI
"/c/Program Files/draw.io/draw.io.exe" --no-sandbox -x -f png -s 2 -o ../entrega_fase1/1_presentacion/img/D-XX.png D-XX.drawio
"/c/Program Files/draw.io/draw.io.exe" --no-sandbox -x -f pdf --crop -o ../entrega_fase1/3_diagramas/pdf/D-XX.pdf D-XX.drawio
# 3 · el PDF de la presentación, desde entrega_fase1/1_presentacion/
msedge --headless=new --no-pdf-header-footer --run-all-compositor-stages-before-draw \
       --virtual-time-budget=15000 --print-to-pdf=Vitalia_presentacion.pdf Vitalia_presentacion.html
```

El PDF sale en 960 × 540 pt —16:9 exacto— porque la hoja se declara en el `@media print` del HTML.
No se exporta a SVG: los iconos van empotrados como data URI y una sola lámina pesa 2 MB.

---

## Fase 2 — fuera del alcance de esta entrega

Implementación del MVP en Google Cloud con anexos de evidencia: despliegue real de los servicios,
corrida del golden set, pruebas de carga P1–P7 y captura de las trazas. Este documento y sus
catorce láminas son **nivel de diseño**.

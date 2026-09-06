# Proyecto final — Costeo de la plataforma cloud y efecto sobre el ROI

- **Proyecto final** · DataPath · AI Solutions Architect
- **Fecha:** 2026-09-05
- **Viene de:** `04_to_be.md` (arquitectura) · `05_caso_de_negocio.md` §3 (costo de run agregado)
- **Sustenta:** las láminas **D-06**, **D-07** y **D-11** — cada servicio dibujado tiene aquí su
  precio y su driver

> **Qué responde este documento.** `05_caso_de_negocio.md` presenta el costo de operar como tres
> líneas agregadas (inferencia S/ 3,000 · infraestructura S/ 4,500 · observabilidad S/ 1,200).
> Eso alcanza para un comité, no para arquitectura. Aquí se **dimensiona servicio por servicio,
> con el driver físico de cada uno**, se reconcilia contra el presupuesto y se mide qué pasa con
> el ROI. La conclusión adelantada: la factura cloud es **menor** de lo presupuestado, y el 75%
> de ella **no depende del volumen**.

---

## 1. Reglas del costeo

| Regla | Valor |
|---|---|
| **Región** | `us-central1` — multi-zona. Se costea a **precio de lista público**, sin descuentos negociados |
| **Tipo de cambio** | **S/ 3.75 por USD**. Declarado, no proyectado: si se mueve, la factura se mueve igual |
| **Fecha de las tarifas** | consultadas el **2026-09-05** (fuentes en §11) |
| **Alcance** | producción + no productivos + soporte. **No** incluye personas — el curador de política y el mantenimiento evolutivo siguen en `05` §3 |
| **Qué es esto** | una **estimación de diseño**, no una cotización. El instrumento que la desmiente es la facturación real etiquetada por servicio desde el primer mes de F1 |

**Lo que NO se costea aquí y hay que decirlo:** transferencia de datos entre regiones (no hay,
todo es `us-central1`), egreso a internet del usuario final (lo cubre el ALB, ya contado), y
licencias de terceros no cloud. El costo de salida de la plataforma (*lock-in*) se trata en §10.

---

## 2. Drivers de dimensionamiento

Todo el costeo cuelga de estos seis números. Los tres primeros vienen del caso; los tres últimos
son supuestos de ingeniería que hay que validar en F1.

| Driver | Valor | Origen |
|---|---:|---|
| Solicitudes de preautorización | **7,800 / mes** | Medido — `01_caso_y_as_is.md` |
| STP (sin toque humano) | **57%** | Meta del TO-BE |
| Derivación a auditor médico | **10%** | Meta del TO-BE |
| Páginas escaneadas por expediente | **8** | *Supuesto.* Orden médica + informe + exámenes |
| Consultas al RAG interpretativo | **3,500 / mes (45%)** | *Supuesto.* El resto lo resuelve el motor determinista sin tocar el LLM |
| Casos que abren agente de subsanación | **700 / mes**, ~5 turnos | *Supuesto.* Derivado de la meta de observaciones ≤ 9% |

> Los tres supuestos marcados mueven **solo la parte variable de la factura**, que es el 25%. Por
> eso el costeo es robusto aunque los supuestos no lo sean: equivocarse en un 50% en las páginas
> por expediente mueve la factura total un 3%.

---

## 3. Costeo de Google Cloud

### 3.1 Tabla completa

| Servicio | Driver del mes | Cálculo | USD/mes |
|---|---|---|---:|
| **Document AI** · Enterprise OCR | 7,800 × 8 = **62,400 páginas** | 62.4 mil-pág × $1.50 | **93.60** |
| **Vertex AI · Gemini 2.5 Flash** — extracción E1 | 7,800 llamadas | 46.8 M tok-in × $0.15 + 19.5 M tok-out × $1.25 | **31.40** |
| **Vertex AI · Gemini** — RAG E2 con cita | 3,500 consultas | 20.3 M in + 5.3 M out | **9.65** |
| **Vertex AI · Gemini** — agente de subsanación | 3,500 llamadas (700 casos × 5 turnos) | 14.0 M in + 2.1 M out | **4.73** |
| **Vertex AI Ranking** — reranking | 3,500 consultas | ≈ $1 / 1,000 req | **3.50** |
| **Model Armor** | 11,300 inspecciones | tarifa por unidad — *estimada* | **25.00** |
| **Cloud Run** · 12 servicios | ver §3.2 | min-instances + escalado | **235.00** |
| **External Application LB** | 1 regla + ~200 GB | $0.025/h + proceso de datos | **21.00** |
| **Cloud Armor** · Standard | 1 política + 12 reglas + 0.8 M req | $5 + $12 + $0.75/M | **18.00** |
| **Cloud CDN** | ~50 GB de estáticos del portal | | **5.00** |
| **Cloud NAT** | 1 gateway + 30 GB de egreso | $0.044/h + $0.045/GB | **34.00** |
| **Cloud VPN** · HA, 2 túneles al core | enlace permanente | 2 × $0.05/h × 730 | **73.00** |
| **Private Service Connect** | 2 endpoints (Qdrant, Neon) | 2 × $0.01/h × 730 | **16.00** |
| **Cloud Storage** | 375 GB Standard + archivo regulatorio | Standard $0.020/GB + Coldline | **17.00** |
| **BigQuery** | 1 TB activo + ~4 TB consultados | $0.02/GB + $6.25/TB con particionado | **45.00** |
| **Pub/Sub · Tasks · Workflows · Eventarc · Scheduler** | 234 K pasos de workflow | casi todo en tramo gratuito | **3.00** |
| **Secret Manager** | 20 secretos activos | $0.06/secreto + accesos | **2.00** |
| **Logging · Monitoring · Trace · Error Reporting** | ~120 GiB de logs, ~3 M spans | $0.50/GiB sobre 50 GiB libres | **50.00** |
| **Artifact Registry · Cloud Build · Cloud Deploy** | 50 GB + 1 pipeline | Build dentro del tramo gratuito | **20.00** |
| **Identity Platform** | ~9,200 MAU (1,200 prestadores + 8,000 afiliados) | | **50.00** |
| **API Gateway** | 0.8 M llamadas | tramo gratuito de 2 M | **0.00** |
| | | **Subtotal GCP** | **756.88** |

### 3.2 Cómo se dimensiona Cloud Run — el renglón que hay que saber defender

Es el servicio más caro de GCP en esta arquitectura, y **no por el tráfico**:

| Concepto | Cálculo | USD/mes |
|---|---|---:|
| **3 servicios con `min-instances=1`** (portal de prestadores, consola de la mesa, app del afiliado) — 24×7, facturación por instancia | 3 × 2.59 M s × ($0.000018/vCPU-s + 2 GiB × $0.000002/GiB-s) | **171.00** |
| **12 servicios con escalado bajo demanda** — facturación por solicitud, ~800 K req y ~960 K vCPU-s | ($0.000024/vCPU-s + $0.0000025/GiB-s) menos tramo gratuito | **64.00** |
| | | **235.00** |

**El 73% del gasto de Cloud Run es no tener *cold start* en tres pantallas.** Es una decisión de
experiencia de usuario, no de capacidad: al volumen de Vitalia (≈ 11 solicitudes por hora hábil)
el cómputo real es casi gratis. Si el negocio acepta 2–3 s de arranque en frío en la app del
afiliado, ese renglón baja a ~$120 y la factura total baja 8%. Se deja como está porque el portal
del prestador es el canal que sostiene la meta de observaciones ≤ 9%.

---

## 4. Costeo de terceros

| Servicio | Dimensionamiento | Por qué ese tamaño | USD/mes |
|---|---|---|---:|
| **Qdrant Cloud** | 2 nodos × 2 GB RAM | El corpus completo son **~59 MB de vectores** (4,800 chunks × 3,072 dims). Con 12 versiones vivas, ~700 MB. **El cluster se dimensiona por disponibilidad, no por datos ni por consultas** | **230.00** |
| **Neon** · plan Scale | ~1.5 CU promedio + 50 GB | Scale, no Launch, por **Private Link + SLA 99.95% + HIPAA**. Launch costaría la mitad y no da el enlace privado que exige D-11 | **260.00** |
| **LangSmith** | 4 asientos Plus | Trazas por decisión y evaluación continua (`05` §8) | **156.00** |
| **Groq** | 11,300 inspecciones — capas 7–8 del guardrail (Llama Prompt Guard 2 + Llama Guard 4) | ~17 M tokens | **3.40** |
| **OpenAI** · `text-embedding-3-large` | 6 reindexaciones del corpus al año + 3,500 embeddings de consulta | 570 K tokens × $0.13/M | **0.10** |
| | | **Subtotal terceros** | **649.50** |

> **El renglón que sorprende:** los *embeddings* de OpenAI cuestan **diez centavos de dólar al
> mes**. El corpus normativo de una EPS es pequeño y cambia seis veces al año. Todo el peso
> económico del "componente vectorial" no está en generar los vectores: está en **mantener un
> cluster encendido** para servirlos.

---

## 5. El total

| Concepto | USD/mes | S/mes |
|---|---:|---:|
| Google Cloud (§3) | 756.88 | 2,838 |
| Terceros (§4) | 649.50 | 2,436 |
| **Producción** | **1,406.38** | **5,274** |
| No productivos — dev + staging *(sin `min-instances`, Qdrant en tramo gratuito, rama de Neon en Launch, sin CDN ni VPN dedicada)* | ~352 | 1,320 |
| Soporte Google Cloud **Standard** | 29 | 109 |
| **TOTAL RUN CLOUD** | **≈ 1,787** | **≈ S/ 6,700** |

**S/ 80,400 al año.** **S/ 0.86 por solicitud.**

### TCO a tres años

| Año | S/ | Nota |
|---|---:|---|
| 1 | 55,000 | Rampa: no productivos desde el mes 1, producción en canary desde el mes 4 |
| 2 | 80,400 | Régimen |
| 3 | 84,000 | Régimen + crecimiento del archivo regulatorio (retención 5 años) |
| **Total** | **≈ S/ 219,000** | |

---

## 6. Reconciliación con el caso de negocio

| Línea de `05` §3 | Presupuestado | Bottom-up | Diferencia |
|---|---:|---:|---:|
| Inferencia (E1 + RAG) | 3,000 | 643 | −2,357 |
| Infraestructura cloud | 4,500 | 5,201 | +701 |
| Observabilidad, tracing y guardrails | 1,200 | 856 | −344 |
| **Total cloud** | **8,700** | **6,700** | **−2,000** |

Dos lecturas, y la segunda importa más que la primera:

1. **El presupuesto sobreestima el cloud en S/ 2,000/mes (23%).** Hay holgura.
2. **Estaba mal repartido.** Se presupuestó 3.4× de más en inferencia y de menos en
   infraestructura. Es el error clásico de costear un sistema de IA: **se presupuestan los tokens
   y se olvida la conectividad.** El VPN al core, los enlaces privados a Qdrant y Neon, el NAT con
   IP fija y las instancias mínimas suman S/ 1,480/mes — **más del doble que toda la inferencia.**

> **Decisión: `05_caso_de_negocio.md` NO se modifica.** El costo de run comprometido sigue siendo
> **S/ 21,700/mes**. Un costeo de diseño no es una medición, y el sentido de la diferencia
> (menor gasto) la convierte en **contingencia, no en una promesa nueva**. Se libera recién
> cuando la facturación etiquetada de tres meses consecutivos lo confirme. Es la misma disciplina
> que se aplicó a la reducción de volumen en `04a`: **holgura, no compromiso.**

### Validación de la inversión

La línea *"Infraestructura y licencias durante la construcción — S/ 35,000"* de `05` §4 se
verifica desde abajo: 6 meses × (no productivos S/ 1,320 + producción en canary desde el mes 4,
promedio S/ 2,600) ≈ S/ 23,500, más herramental de construcción y anotación ≈ S/ 6,000, más
reserva ≈ S/ 5,000 → **S/ 34,500**. La cifra del caso de negocio **se sostiene**.

---

## 7. Economía unitaria: qué mueve realmente la factura

| Naturaleza | USD/mes | % | Qué contiene |
|---|---:|---:|---|
| **Fijo** — no depende del volumen | 1,051 | **75%** | Qdrant, Neon, LangSmith, `min-instances`, VPN, NAT, PSC, ALB, Cloud Armor, Identity, CI/CD |
| **Variable** — escala con solicitudes | 355 | **25%** | Document AI, Gemini, Ranking, Model Armor, Groq, logs, BigQuery, GCS, escalado de Cloud Run |

Consecuencias directas, y las tres son decisiones de arquitectura, no de finanzas:

| Si… | Entonces… |
|---|---|
| **El volumen se duplica** a 15,600 solicitudes/mes | La factura sube **25%**, no 100%. El costo unitario cae de **S/ 0.86 a S/ 0.52** |
| **Se cambia Gemini Flash por Gemini Pro** (8× la tarifa) | La factura sube **23%** (+$329). *Se puede pagar un modelo ocho veces más caro y la cuenta sube menos de un cuarto* |
| **Se optimiza el prompt a la mitad de tokens** | La factura baja **1.9%**. No vale el esfuerzo de ingeniería |

> **El hallazgo que hay que llevarse:** en esta arquitectura, **los tokens de LLM son el 3.8% de
> la factura cloud** (Gemini + Groq + OpenAI + Ranking = $52.78 de $1,406). Sumando Document AI y
> Model Armor, toda la capa de IA es el **12%**. Optimizar prompts es intervenir sobre la doceava
> parte del problema; la palanca real son `min-instances`, el dimensionamiento de Qdrant y Neon,
> y la retención de logs.

### Y frente al costo total del proceso

| | S/ por solicitud |
|---|---:|
| Costo AS-IS del proceso completo | **30.15** |
| Costo TO-BE del proceso completo (`05` §1) | **10.26** |
| — del cual, **cloud** | **0.86** *(8%)* |
| — del cual, **personas** (curador + mantenimiento + mesa residual) | **≈ 9.40** *(92%)* |

**La plataforma cloud es el 8% del costo unitario del proceso rediseñado.** Ese es el dato que
cierra la tesis del proyecto desde el lado económico: el problema de Vitalia nunca fue el costo
de la tecnología, y la solución tampoco se sostiene por abaratarla.

---

## 8. Sensibilidad de la factura

| Escenario | Efecto | Factura S/mes | Decisión |
|---|---|---:|---|
| **Base** | | **6,700** | — |
| Volumen ×2 (15,600 sol/mes) | +25% | 8,050 | Absorbible sin rediseño |
| Soporte **Enhanced** en vez de Standard | mínimo de $500/mes | 8,470 | **Recomendado desde F2**, cuando el sistema emite cartas vinculantes |
| Gemini **Pro** en lugar de Flash | +23% | 8,180 | Solo si RAGAS muestra que Flash no alcanza en los casos interpretativos |
| Sin `min-instances` | −8% | 6,140 | Se rechaza: rompe la experiencia del portal |
| **Cloud Armor Enterprise** | +$3,000/mes | **17,900** | **Se rechaza.** Standard cubre WAF, reglas y rate-limiting al volumen actual. Enterprise solo si aparece exposición DDoS real |
| Tipo de cambio a S/ 4.10 | +9% | 7,325 | Riesgo declarado, no cubierto |

**El único escenario que rompe el presupuesto es Cloud Armor Enterprise**, y es una decisión
comercial de Google, no una necesidad técnica de este volumen. Todo lo demás cabe dentro de los
S/ 8,700 presupuestados.

---

## 9. Efecto sobre el ROI

Manteniendo el valor capturable de `05` §2 (**S/ 96,600/mes**) y sustituyendo solo el costo de
run cloud:

| | `05` (comprometido) | Con costeo bottom-up |
|---|---:|---:|
| Costo de run total (cloud + personas) | 21,700 | 19,700 |
| **Valor neto mensual** | **74,900** | **76,900** |
| Payback | 8.8 meses | **8.6 meses** |
| VAN @ 12% a 3 años | S/ 1.13 M | **S/ 1.17 M** |
| TIR | ≈ 85% | **≈ 88%** |

**La conclusión no cambia, y eso es exactamente lo que se quería comprobar.** Un caso de negocio
cuyo veredicto dependiera de si el cloud cuesta S/ 6,700 u S/ 8,700 sería un caso frágil. Aquí la
factura cloud completa es el **7% del valor capturable mensual**: puede triplicarse y el proyecto
sigue siendo positivo. El riesgo del proyecto está en el factor de captura de horas (`05` §8), no
en la tarifa de ningún servicio.

---

## 10. Controles FinOps — cómo se evita que esto se desvíe

| Control | Cómo | Desde |
|---|---|---|
| **Etiquetado obligatorio** | `label: servicio / entorno / fase` en todo recurso; sin etiqueta no pasa el pipeline de Terraform | F1 |
| **Presupuesto y alerta** | Budget de S/ 8,700/mes con alertas al 50 / 80 / 100% | F1 |
| **Costo por solicitud** | *Cost attribution* por span en LangSmith → BigQuery. Es la métrica que se reporta, no el total mensual | F2 |
| **Cuotas duras** | Límite de requests/día por servicio en API Gateway: acota el daño de un bucle de agente | F2 |
| **Retención escalonada de logs** | 30 días en Logging, luego BigQuery; el archivo regulatorio a Coldline | F2 |
| **Descuentos por uso comprometido** | CUD a 1 año en Cloud Run una vez estabilizado el consumo (≈ −17%) | F4 |
| **Revisión de dimensionamiento** | Qdrant y Neon se revisan cada trimestre: son el 35% de la factura y están dimensionados por SLA, no por carga | Trimestral |

**Sobre el *lock-in*.** Lo que ata a la plataforma no es el cómputo — los 12 servicios son
contenedores y se mueven. Ata el **corpus vectorial versionado** y la traza histórica en
BigQuery. Por eso el diseño mantiene los PDF originales y el markdown fuente en Cloud Storage
(D-07, banda A): el corpus es **reconstruible desde el origen**, y una migración de motor
vectorial cuesta una reindexación de S/ 0.10, no un proyecto.

---

## 11. Lo que hay que validar antes de comprometer estas cifras

| Cifra | Estado | Cómo se cierra |
|---|---|---|
| Tarifas de **Model Armor** y **Vertex AI Ranking** | **Estimadas** — no confirmadas en lista pública | Google Cloud Pricing Calculator con el SA de cuenta |
| Tarifa de **Identity Platform** por MAU | Estimada — depende del tramo y del método de autenticación | Ídem |
| **8 páginas por expediente** | Supuesto | Muestreo de 200 expedientes reales en F1 |
| **45% de solicitudes que llegan al RAG** | Supuesto | Se mide sola desde F2, es un contador |
| Dimensionamiento de **Qdrant** y **Neon** | Estimado por SLA | Prueba de carga en F2 con el volumen real |
| **Tipo de cambio S/ 3.75** | Declarado | Se refija en cada revisión trimestral |

**Fuentes de tarifas** (consultadas 2026-09-05, precio de lista `us-central1`):
[Cloud Run](https://cloud.google.com/run/pricing) ·
[Document AI](https://cloud.google.com/document-ai/pricing) ·
[Vertex AI / Gemini](https://ai.google.dev/gemini-api/docs/pricing) ·
[Cloud Armor](https://cloud.google.com/armor/pricing) ·
[Cloud Load Balancing](https://cloud.google.com/load-balancing/pricing) ·
[Qdrant Cloud](https://qdrant.tech/pricing/) ·
[Neon](https://neon.com/pricing)

---

## 12. Para la presentación

- **Slide 8 (caso de negocio):** la reconciliación de la sección 6 — presupuestado S/ 8,700 vs
  bottom-up S/ 6,700, y la frase *"se presupuestaron los tokens y se olvidó la conectividad"*.
- **Slide 8b (economía de la plataforma):** la partición **75% fijo / 25% variable** de la
  sección 7 y sus tres consecuencias. Es la lámina que demuestra criterio de arquitecto y no de
  planilla de cálculo.
- **Slide 9 (riesgo):** la sensibilidad de la sección 8, cerrando con que **el único escenario
  que rompe el presupuesto es una decisión comercial (Cloud Armor Enterprise), no técnica**.
- **Anexo A (detalle de costos y assumptions):** la tabla completa de la sección 3, los supuestos
  de la sección 2 y los controles FinOps de la sección 10.

**La frase de cierre del bloque económico:** *los tokens de LLM son el 3.8% de la factura y el
0.3% del costo del proceso. Si el proyecto se justificara por abaratar la inferencia, no se
justificaría.*

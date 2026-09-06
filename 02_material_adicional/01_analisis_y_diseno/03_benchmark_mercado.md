# Proyecto final — Benchmark de mercado: cómo se está resolviendo esto afuera

- **Proyecto final** · DataPath · AI Solutions Architect
- **Fecha:** 2026-09-04 · **Depende de:** `01_caso_y_as_is.md`, `02_matriz_de_decision.md`
- **Propósito:** contrastar nuestras decisiones con lo que ya existe publicado —estándares,
  regulación, productos y fracasos documentados— antes de cerrar la arquitectura.

> **Sesgo de las fuentes.** Casi todo el material serio sobre preautorización viene de
> **EE.UU.**, donde el proceso está estandarizado y regulado. Las cifras de proveedores
> (Cohere, etc.) son **autorreportadas por el vendor**, sin publicación revisada por pares.
> Se citan como lo que son: referencia de orden de magnitud, no evidencia.

---

## 1. Existe un modelo de referencia publicado — y no es de IA

**HL7 Da Vinci** define el proceso completo de preautorización en tres guías de
implementación FHIR que se encadenan:

| Guía | Qué hace | Equivale a nuestro |
|---|---|---|
| **CRD** — Coverage Requirements Discovery | Muestra al médico las reglas de cobertura del pagador **en tiempo real, dentro de su propio flujo**, vía CDS Hooks, en el momento en que ordena el procedimiento | **S6** (cobertura y copago) — pero determinista y aguas arriba |
| **DTR** — Documentation Templates and Rules | Captura la documentación de sustento que la solicitud va a necesitar, guiada por plantillas y reglas del pagador | **S3** (¿el sustento está completo?) |
| **PAS** — Prior Authorization Support | Envía la solicitud vía la operación `Claim $submit` | **S1** y **S8** |

Encima está la regulación: **CMS-0057-F** entró en vigor el **1 de enero de 2026**, y obliga a
los pagadores afectados a exponer **APIs de preautorización a partir del 1 de enero de 2027**,
con plazos de decisión acotados.

### Lo que esto le hace a nuestro diseño — y no es cómodo

El mercado maduro **no resuelve el sustento incompleto en la mesa: lo previene en el origen.**
CRD y DTR le dicen al médico qué se requiere *antes* de que envíe la solicitud. Nuestro P1
—23% de observaciones, 1,148 retrabajos/mes— es en buena medida un problema que ellos ya no
tienen, y no lo resolvieron con IA sino con un estándar y un hook en el punto de la orden.

> **Cambio 1 al diseño.** S3 deja de ser solo un validador reactivo dentro de la mesa y se
> **expone como servicio al portal de prestadores**, en el momento del envío: el checklist de
> sustento se evalúa y se devuelve al prestador antes de que la solicitud entre a la cola.
> Es el patrón CRD/DTR adaptado a nuestro contexto.

---

## 2. La regulación ya prohibió exactamente lo que nosotros descartamos por criterio

**California SB 1120 — "Physicians Make Decisions Act"**, vigente desde el 1 de enero de 2025:
toda denegación, demora o modificación de un servicio **por necesidad médica** debe ser
revisada y decidida por un **médico licenciado** competente en el tema clínico concreto. La ley
**no** prohíbe usar IA para tareas administrativas ni para organizar información clínica —
prohíbe que la IA sea quien decide. Texas, Arizona y Maryland tienen normas del mismo signo:
la IA no puede ser el fundamento único de una denegación por necesidad médica.

**Implicación para nosotros:** la decisión S7 (HITL con el médico auditor) y la regla *"el
agente nunca decide"* no son preferencia de arquitecto — en varias jurisdicciones son
**requisito normativo**. En Perú todavía no existe norma equivalente.

> **Cambio 2 al diseño.** Se declara explícitamente la postura de cumplimiento: *ninguna
> denegación por necesidad médica se emite sin firma de médico auditor*, alineado con SB 1120
> aunque el regulador peruano aún no lo exija. Diseñar *compliance-ready* antes de que llegue
> la norma es más barato que retrofitear la trazabilidad después.

---

## 3. Los fracasos públicos definen el anti-patrón mejor que los éxitos

**UnitedHealth / nH Predict.** Demanda colectiva (nov. 2023, aún viva) por denegaciones a
afiliados de Medicare Advantage. Se alega una **tasa de error del ~90%** —nueve de cada diez
denegaciones apeladas se revirtieron—, metas internas para mantener las estancias dentro del 1%
de lo que proyectaba el modelo, y sanciones a empleados que se desviaran de la predicción. En
**marzo de 2026 un tribunal ordenó revelar el algoritmo**. UnitedHealth sostiene que nH Predict
es una guía y no la base de la decisión de cobertura.

**Cigna / PXDX.** Se alega la revisión y denegación de **más de 300,000 reclamos en dos meses**,
con un promedio de **1,2 segundos por caso**. Cigna responde que no hay algoritmo ni ML, sino
una tecnología de emparejamiento de códigos.

**La lectura correcta no es "la IA es peligrosa".** Los dos casos fallan por lo mismo:
**optimizaron la productividad de la denegación en lugar de la calidad de la decisión**, y no
dejaron rastro reconstruible. Y "un tribunal ordenó revelar el algoritmo" es, literalmente,
el escenario de auditoría de nuestro veto V2.

> **Cambio 3 al diseño.** La métrica de éxito nunca va sola. **`% STP` se reporta siempre
> emparejado con `% de reversiones al apelar` y `% de denegaciones sin firma médica`.** Un
> tablero que solo muestra automatización es el tablero que produjo estos dos casos.

---

## 4. Los números del mercado calibran nuestras metas

**Cohere Health** (proveedor de preautorización para pagadores, socio de planes grandes) reporta:

| Cifra autorreportada | Valor |
|---|---|
| Autorizaciones aprobadas automáticamente | hasta 90% |
| Resueltas en tiempo real | 85% |
| Autorizaciones FHIR procesadas en un año | 9 millones |
| Reducción del tiempo de digitación del prestador | 61% |
| Revisión de necesidad médica más rápida | 50% |
| Geisinger Health Plan: reducción del gasto médico total | ~15% |
| Geisinger Health Plan: **reducción de denegaciones** | **63%** |

**Cómo leerlo.** Nuestro objetivo de **STP 55–60% queda validado como prudente** frente al
85–90% de un líder con años de datos, integración FHIR nativa y decenas de pagadores. Conviene
declararlo así en la presentación —meta conservadora, con la brecha explicada— en lugar de
inflarlo para impresionar.

Y hay un dato que reordena la narrativa: **la reducción del 63% es de *denegaciones*, no de
tiempos.** El valor grande no está en aprobar más rápido, está en **dejar de negar mal**. Eso
conecta directo con nuestro P4 (rechazos revertidos) y con el riesgo regulatorio, que es donde
el caso de negocio deja de ser un ahorro de horas y pasa a ser gestión de riesgo.

---

## 5. La alternativa que no es tecnológica: *gold-carding*

**Texas HB 3459** (2021) creó la exención continua de preautorización: el médico que alcanza
**≥90% de aprobación en un servicio durante 6 meses** (con mínimo 5 solicitudes evaluables)
queda exonerado de pedir preautorización para ese servicio. Varios pagadores tienen programas
voluntarios equivalentes.

**Su límite, documentado:** el impacto real fue más modesto de lo esperado. Aplica solo a planes
comerciales HMO/PPO/EPO regulados por el estado —alrededor del 20% de los tejanos— y no cubre
Medicaid ni CHIP.

**Por qué importa aquí.** Es la respuesta más honesta a la pregunta del slide 3, *"¿realmente
necesito IA?"*: **la mejor solicitud es la que no existe.** Si el 71% de nuestro volumen se
concentra en 24 combinaciones diagnóstico–procedimiento y en un grupo acotado de prestadores
con historial limpio, **exonerar sale más barato que automatizar**.

> **Cambio 4 al diseño.** Se agrega un **carril de exoneración tipo gold-card**, alimentado por
> las métricas del propio sistema (tasa de aprobación por prestador y por procedimiento, en
> ventana móvil). Ataca el **volumen**, no el costo unitario — que es una palanca distinta y
> más barata. Su límite es honesto: solo funciona donde hay historial suficiente; la cola larga
> sigue necesitando el proceso completo.

---

## 6. El contexto local: Perú ya tiene una pieza obligatoria con fecha

**Acredita Salud** (SUSALUD) es el modelo electrónico estandarizado de intercambio de
información que permite a los establecimientos **verificar la condición de aseguramiento, el
plan y la cobertura disponible** antes de la atención — reemplazando el trámite manual y el
antiguo SITEDS.

| | |
|---|---|
| Norma de origen | Resolución N.° 034-2025-SUSALUD/S (febrero 2025) |
| Prórroga vigente | Res. de Superintendencia N.° 000143-2026-SUSALUD/SUP (26-ago-2026) |
| **Plazo final** | **31 de octubre de 2026** |
| Avance IAFAS | 43 de 48 migradas (90%) |
| Avance IPRESS | 386 de 508 en migración desde SITEDS |

**Esto valida y mejora nuestro S4.** La verificación de elegibilidad no es solo una consulta a
nuestro core: es una **integración con un modelo de interoperabilidad nacional obligatorio, con
fecha**. Vitalia, como IAFAS, tiene que estar ahí de todos modos.

> **Cambio 5 al diseño.** S4 se replantea como integración con Acredita Salud, y el **31 de
> octubre de 2026 entra al roadmap del go-live** como hito externo no negociable. Un plan de
> despliegue anclado a una fecha regulatoria real es mucho más creíble que uno anclado a
> trimestres genéricos.

---

## 7. Entonces, ¿qué aportamos nosotros?

Es la pregunta correcta, y la respuesta honesta tiene dos partes.

**Lo que no inventamos.** El modelo de proceso ya existe y está publicado (Da Vinci CRD/DTR/PAS).
La postura de HITL ya es ley en varios estados. La arquitectura por capas
—experiencia / inteligencia / datos / gobernanza, con controles HITL y bitácora de auditoría—
es consenso de mercado, igual que el patrón *sugerir → validar → ejecutar*. Adoptarlo y citarlo
es mejor arquitectura que reinventarlo.

**Dónde sí está el aporte:**

1. **Portar el modelo a un contexto de baja madurez de interoperabilidad.** Cohere, Availity y
   los demás están construidos sobre EHR + FHIR + CDS Hooks. **En Perú ese sustrato no existe**:
   el portal del prestador no tiene hooks, no hay DTR, y el sustento llega como **PDF escaneado**.
   Ahí es donde nuestra capa de extracción (S2) y el RAG con cita (S6) hacen el trabajo que allá
   hace un estándar estructurado. **Ese es el problema de arquitectura real, y no está resuelto
   en la literatura**: no es "aplicar IA a preautorización", es "conseguir el resultado de un
   estándar que no tenemos, con IA, sin perder auditabilidad".

2. **Trazabilidad por versión de política (nuestro P7).** Los vendors hablan de tasas de
   aprobación; casi nadie habla de poder reconstruir *bajo qué versión de la política* se emitió
   cada carta. Es exactamente lo que un tribunal le exigió a UnitedHealth en marzo de 2026.
   Versionar el corpus y sellar cada decisión con el hash de la política vigente es barato de
   diseñar al inicio y carísimo de agregar después.

3. **Reducir el problema antes de aplicarle tecnología** (el carril gold-card de la §5), que es
   la decisión que más valor genera y la que menos se ve en las demos de producto.

---

## 8. Resumen de cambios que este benchmark introduce

| # | Cambio | Origen | Afecta |
|---|---|---|---|
| 1 | S3 se expone aguas arriba al portal de prestadores | Da Vinci CRD/DTR | Blueprint, ataca P1 |
| 2 | Postura declarada: sin médico no hay denegación por necesidad médica | SB 1120 y análogas | Slide de seguridad, Anexo D |
| 3 | `% STP` se reporta siempre junto a `% reversiones` y `% denegaciones sin firma` | nH Predict, PXDX | Slide de evals, Anexo E |
| 4 | Carril de exoneración tipo gold-card | Texas HB 3459 | Blueprint y caso de negocio |
| 5 | S4 como integración con Acredita Salud; 31-10-2026 al roadmap | SUSALUD | Arquitectura y go-live |
| 6 | Meta de STP 55–60% declarada como conservadora, con la brecha explicada | Cohere / Geisinger | Caso de negocio |

---

## Fuentes

- HL7 Da Vinci — Prior Authorization Support (PAS) IG: https://hl7.org/fhir/us/davinci-pas/
- Da Vinci PAS, especificación formal (v2.2.0-ballot): https://build.fhir.org/ig/HL7/davinci-pas/specification.html
- Implementación de referencia Da Vinci: https://github.com/HL7-DaVinci/prior-auth
- CRD explicado (Firely): https://fire.ly/blog/prior-authorization-with-crd-explained/
- Arquitectura FHIR CRD/DTR/PAS (CapMinds): https://www.capminds.com/blog/fhir-prior-authorization-architecture-pack-crd-dtr-pas-sequence-diagrams-and-readiness-checklist/
- California SB 1120, análisis (Fenwick): https://www.fenwick.com/insights/publications/californias-sb-1120-regulates-ai-in-health-plan-utilization-review-and-management-activities-starting-in-january
- SB 1120, nota oficial del Senado de California: https://sd13.senate.ca.gov/news/press-release/september-30-2024/governor-signs-physicians-make-decisions-act-keeping-medical
- Demandas por denegaciones asistidas por IA (Thompson Coburn): https://www.thompsoncoburn.com/insights/class-actions-highlight-ai-assisted-payer-denials-102jebl/
- Avance de la demanda contra UnitedHealth (Healthcare Finance News): https://www.healthcarefinancenews.com/news/class-action-lawsuit-against-unitedhealths-ai-claim-denials-advances
- Orden judicial de revelar el algoritmo (marzo 2026): https://distilinfo.com/2026/03/12/court-orders-unitedhealth-to-disclose-ai-denial-algorithm/
- Perfil de Cohere Health (IntuitionLabs): https://intuitionlabs.ai/articles/cohere-health-ai-prior-authorization
- Cohere Health, solución de decisión automatizada: https://www.coherehealth.com/decision
- Texas HB 3459 / gold card (The Rheumatologist): https://www.the-rheumatologist.org/article/texas-establishes-gold-card-for-prior-authorization-exemption/
- Gold carding, estado 2026 (Linear Health): https://linear.health/blog/gold-carding-prior-authorization
- Acredita Salud, prórroga a octubre 2026 (ConsultorSalud): https://consultorsalud.com/peru-susalud-acredita-salud-plazo-octubre-2026/
- Acredita Salud, nota oficial (El Peruano): https://www.elperuano.pe/noticia/282226-susalud-lanza-acredita-salud-agiliza-la-atencion-medica-y-elimina-tramites-manuales-informate
- Blueprint de IA agéntica en claims y prior auth (MobiHealthNews): https://www.mobihealthnews.com/news/creating-blueprint-agentic-ai-claims-and-prior-authorization
- CMS-0057-F y automatización de PA (Flexbone): https://flexbone.ai/blog/how-to-automate-prior-authorization-2026/

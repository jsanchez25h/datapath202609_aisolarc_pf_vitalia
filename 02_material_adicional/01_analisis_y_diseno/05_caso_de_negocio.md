# Proyecto final — Caso de negocio

- **Proyecto final** · DataPath · AI Solutions Architect
- **Fecha:** 2026-09-04
- **Viene de:** `01_caso_y_as_is.md` (línea base) · `04_to_be.md` (metas operativas)
- **Va hacia:** `05a_costeo_cloud.md` (costeo detallado de la plataforma y efecto sobre el ROI)

> **Disciplina de este documento.** No se presenta el ahorro bruto como si fuera caja. Se
> recorre la cadena completa: **valor potencial → valor capturable → valor neto**. Un ahorro de
> horas de analista solo es dinero si esas horas se convierten en algo — reducción de plantilla,
> absorción de crecimiento sin contratar, o reasignación a trabajo que hoy no se hace.

---

## 1. Línea base y estado objetivo

7,800 solicitudes/mes. Costos cargados: analista S/ 31/h · médico auditor S/ 110/h · gestión de
un expediente de reclamo S/ 340.

| Concepto | AS-IS · S/mes | TO-BE · S/mes | Diferencia |
|---|---:|---:|---:|
| Operación de la mesa | 76,600 | 28,200 | −48,400 |
| Retrabajo por observación (P1) | 11,300 | 3,700 | −7,600 |
| Auditoría médica (P2) | 48,000 | 22,900 | −25,100 |
| Fuga por copago mal aplicado (P3) | 62,200 | 6,600 | **−55,600** |
| Gestión de reclamos por reversión (P4) | 37,100 | 18,600 | −18,500 |
| **Total** | **235,200** | **80,000** | **−155,200** |

**Valor potencial = S/ 155,200/mes ≈ S/ 1.86 M/año.**

### Cómo se construye cada cifra del TO-BE

> *STP* = solicitudes resueltas de punta a punta sin que las toque una persona.

| Concepto | Cálculo |
|---|---|
| Mesa | 7,800 × **7 min** × S/ 31/h — el ponderado de 57% a cero toque (STP) y 43% a ~16 min |
| Retrabajo | observaciones 23%→9% = 702/mes, 64% resubsana = **449** × 16 min × S/ 31/h |
| Auditoría | derivación 21%→10% = **780**/mes × 16 min × S/ 110/h |
| Copago | error 3.8%→**0.4%** = 31 cartas/mes × S/ 210 |
| Reclamos | reversiones 1.4%→**0.7%** = 55/mes × S/ 340 |

---

## 2. De potencial a capturable

No todo ahorro es caja. Cada línea lleva un factor de captura explícito y su razón:

| Concepto | Ahorro potencial | Factor | Capturable | Por qué ese factor |
|---|---:|---:|---:|---|
| **Fuga por copago** | 55,600 | **100%** | **55,600** | Es dinero que hoy se paga de más. Dejar de pagarlo es caja inmediata, no productividad |
| Gestión de reclamos | 18,500 | 60% | 11,100 | Parte es tiempo de personal que se reabsorbe; parte son costos externos reales |
| Mesa + retrabajo | 56,000 | 40% | 22,400 | No se despide a 16 analistas. Se absorbe el crecimiento de cartera sin contratar y se reduce sobretiempo del pico de lunes |
| Auditoría médica | 25,100 | 30% | 7,500 | La capacidad médica liberada **se reinvierte** en casos complejos y segunda opinión — decisión explícita del TO-BE §6 |
| | **155,200** | | **96,600** | |

**Valor capturable = S/ 96,600/mes ≈ S/ 1.16 M/año.**

> El dato que ordena la discusión: **el 58% del valor capturable viene de la fuga de copago, que
> se resuelve con un motor de reglas determinista — sin nada de IA.** Es la evidencia numérica
> de la tesis del proyecto.

---

## 3. Costo de operar el TO-BE

| Concepto | S/mes | Nota |
|---|---:|---|
| Inferencia (extracción E1 + RAG E4) | 3,000 | ≈ S/ 0.38 por solicitud |
| Infraestructura cloud (cómputo, vector store, almacenamiento, logs) | 4,500 | |
| Observabilidad, tracing y guardrails | 1,200 | Incluye el guardrail de 8 capas |
| **Curador de política (0.5 FTE)** | 6,000 | **Rol nuevo.** Sin él no se sostienen R2 ni F4 |
| Mantenimiento evolutivo (0.5 FTE) | 7,000 | Cambios de política, catálogos, golden set |
| **Total run** | **21,700** | **≈ S/ 260 K/año** |

Que el rol humano nuevo (S/ 6,000) cueste el doble que la inferencia (S/ 3,000) es un dato
deliberado: **en este tipo de sistema el costo dominante no son los tokens, es la gobernanza del
conocimiento.** Un caso de negocio que solo presupuesta la API está subestimando el run.

> **Detalle del costo cloud → `05a_costeo_cloud.md`.** Las tres primeras líneas de esta tabla
> están costeadas servicio por servicio, con el driver físico de cada uno y las tarifas de lista
> vigentes. El bottom-up da **S/ 6,700/mes** contra los S/ 8,700 presupuestados aquí. **Esa
> diferencia no se descuenta:** el costo de run comprometido sigue siendo S/ 21,700/mes y los
> S/ 2,000 quedan como contingencia hasta que tres meses de facturación etiquetada lo confirmen.
> Lo que sí corrige el costeo es el *reparto*: se presupuestó 3.4× de más en inferencia y de
> menos en conectividad (VPN, PSC, NAT, instancias mínimas).

**Valor neto = 96,600 − 21,700 = S/ 74,900/mes ≈ S/ 0.90 M/año.**

---

## 4. Inversión

| Concepto | S/ |
|---|---:|
| Equipo de construcción (≈4 personas × 6 meses) | 432,000 |
| Integración y certificación con Acredita Salud | 60,000 |
| Anotación del golden set (300 expedientes) y versionado inicial del corpus | 45,000 |
| Infraestructura y licencias durante la construcción | 35,000 |
| Contingencia 15% | 88,000 |
| **Total** | **660,000** |

---

## 5. El resultado, por fase

Aquí es donde el caso de negocio deja de ser un número y se vuelve un argumento de secuencia:

| Fase | Qué entrega | Inversión | Capturable/mes | Payback |
|---|---|---:|---:|---|
| **F0** · pre-validación en el origen · *sin IA* | Observaciones 23%→9% | 75,000 | 3,000 | **No se paga en caja.** Su retorno es SLA y relación con la red prestadora |
| **F1** · elegibilidad + carencia + copago · *sin IA* | Cierra la fuga de copago e integra Acredita Salud | 225,000 | 63,700 | **3.5 meses** |
| **F2–F4** · extracción, RAG, STP y agente · *con IA* | STP 55–60%, trazabilidad, subsanación | 360,000 | 29,900 | **12 meses** |
| **Total** | | **660,000** | **96,600** | **8.8 meses** |

**Lo que hay que decir en voz alta:** la fase que **no** lleva IA se paga en 3.5 meses; la que sí
la lleva tarda 12. Ambas valen la pena, pero en ese orden — y por eso el roadmap del TO-BE pone
lo determinista primero. Invertir la secuencia habría triplicado el tiempo hasta el primer
retorno.

F0 merece una nota aparte: **no se justifica por caja y aun así entra primero.** Su retorno es el
cumplimiento del SLA contractual y dejar de hacerle perder un día al prestador — que en el nivel
2 del modelo del problema es exactamente la infracción que más sanciona SUSALUD.

### Retorno a tres años

| Año | Flujo neto S/ |
|---|---:|
| 0 | −660,000 |
| 1 | +480,000 *(año de rampa: construcción solapada + canary)* |
| 2 | +899,000 |
| 3 | +899,000 |

- **VAN @ 12% ≈ S/ 1.13 M**
- **TIR ≈ 85%**
- **Payback ≈ 9 meses**

---

## 6. Sensibilidad: los dos supuestos de los que cuelga todo

El caso de negocio depende de dos números que hoy son **estimaciones, no mediciones** (declarados
en `01_caso_y_as_is.md` §8): la concentración del 71% del volumen en 24 combinaciones
recurrentes, y el 55% de derivación defensiva. Se modelan explícitamente:

| Variable | Pesimista | Base | Optimista |
|---|---:|---:|---:|
| Concentración del volumen | 55% | **71%** | 80% |
| STP alcanzable | 42% | **57%** | 65% |
| Derivación defensiva real | 35% | **55%** | 70% |
| Factor de captura de horas | 20% | **40%** | 60% |
| | | | |
| **Capturable S/mes** | 73,900 | **96,600** | 125,100 |
| Costo de run S/mes | 21,700 | 21,700 | 21,700 |
| **Neto S/mes** | **52,200** | **74,900** | **103,400** |
| **Payback** | **12.6 meses** | **8.8 meses** | **6.4 meses** |

**El proyecto es positivo incluso en el escenario pesimista.** Y la razón importa: en ese
escenario, **el 75% del valor capturable sigue viniendo del motor de copago determinista**, que
no depende de ninguno de los dos supuestos en duda. El piso del caso de negocio está en la parte
sin IA; la IA es lo que separa el escenario base del pesimista, no lo que lo sostiene.

Ese es el argumento que hay que poder defender: **no se está apostando el caso de negocio a que
el modelo funcione.**

---

## 7. Lo que no está en la tabla

Tres impactos reales que ninguna hoja de cálculo captura, y que en este dominio pesan más que el
VAN:

| Impacto | Por qué no se monetiza aquí |
|---|---|
| **Procedimientos médicos postergados o abandonados** | Es el costo del nivel 1: 95% de demora reportada, 79% de abandono, 26% de evento adverso serio. Ponerle precio sería deshonesto; ignorarlo, peor |
| **Exposición regulatoria** | 74 sanciones frente a 7,000+ reclamos en el sector sugiere que la mayor parte del daño no llega a multa. El riesgo real es mayor que la multa esperada — por eso el caso **no** se sostiene en "evitar sanciones" |
| **El conocimiento deja de ser tácito** | Hoy 3 seniors resuelven el 70% de los casos difíciles con 38% de rotación. El corpus versionado convierte a personas en un activo de la empresa |

---

## 8. Cómo se audita este caso de negocio

Cada cifra prometida tiene un instrumento que puede desmentirla. Sin esto, es una presentación,
no un caso:

| Se prometió | Se mide con | Cuándo |
|---|---|---|
| Error de copago ≤ 0.4% | Muestreo mensual de 200 cartas emitidas contra recálculo independiente | Desde F1 |
| Observaciones ≤ 9% | Métrica directa del portal | Desde F0 |
| STP 55–60% | Conteo de expedientes sin toque humano · **siempre junto a reversiones y firma médica** | Desde F3 |
| Derivación ≤ 10% con ≥85% confirmada necesaria | Marcado del auditor al cerrar cada caso derivado | Desde F3 |
| Factor de captura de horas 40% | Plantilla real vs. plantilla proyectada sin proyecto, revisada trimestralmente | Trimestral |
| Costo de run S/ 21,700 | Cost attribution por span en el tracing (S10) | Mensual |

El **factor de captura del 40% es el compromiso más frágil del documento** y por eso se audita
contra plantilla real: si en 12 meses la plantilla no bajó ni absorbió crecimiento, ese ahorro
nunca existió y hay que decirlo.

---

## 9. Para la presentación

- **Slide 2 (impacto del problema):** la tabla AS-IS de la sección 1.
- **Slide 8 (caso de negocio):** la cadena potencial → capturable → neto de las secciones 1–3,
  y la tabla por fase de la sección 5.
- **Slide 9 (riesgo del caso):** la sensibilidad de la sección 6, con la frase de cierre: el
  piso del caso está en la parte sin IA.
- **Slide 8b (economía de la plataforma):** la partición 75% fijo / 25% variable de
  `05a_costeo_cloud.md` §7 — el cloud es el 8% del costo unitario del proceso, y los tokens de
  LLM el 3.8% de la factura cloud.
- **Anexo A (detalle de costos y supuestos):** el costeo servicio por servicio, la sensibilidad
  y los controles FinOps de `05a_costeo_cloud.md`, más los supuestos declarados de este documento.
- **Anexo I (auditoría del baseline):** la tabla de la sección 8 — de dónde salió cada cifra y
  con qué grado de confianza.

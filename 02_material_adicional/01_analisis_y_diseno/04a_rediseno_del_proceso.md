# Proyecto final — Rediseño del proceso: ¿siguen siendo ocho pasos?

- **Proyecto final** · DataPath · AI Solutions Architect
- **Autor:** Jonatan Sánchez · **Fecha:** 2026-09-04
- **Viene de:** `01_caso_y_as_is.md` (el flujo actual) · `02_matriz_de_decision.md` (el ruteo S1–S8)
- **Va hacia:** `04_to_be.md` (que este documento corrige) · `05_caso_de_negocio.md`

---

## 0. La pregunta y la respuesta corta

> **La pregunta.** En el AS-IS se marcan ocho sub-procesos y se evalúa, uno por uno, si necesitan
> IA. ¿Pero se evaluó si el **proceso mismo** mejora — si se unifican pasos, si se rediseña por
> efecto de la automatización?

**Respuesta corta: no, y era una omisión real.** La matriz de decisión hizo bien su trabajo —
elegir la tecnología correcta para cada sub-problema— pero **arrastró la descomposición del AS-IS
al TO-BE casi uno a uno.** Eso es automatizar un proceso, no rediseñarlo.

Al forzar el análisis de rediseño, el resultado es:

| | AS-IS | TO-BE anterior | **TO-BE rediseñado** |
|---|---:|---:|---:|
| Sub-procesos / estados de negocio | 8 | 10 (E0–E9) | **4** |
| Toques humanos por solicitud típica | 1,23 | 0,43 | **0,40** |
| Solicitudes que entran a la mesa / mes | 7,800 | 7,800 | **≈ 6,400** |
| Momento en que el prestador conoce la respuesta | 2–7 días | 2,5 días | **en el acto, antes de enviar** |

**No son ocho procesos. Son cuatro, más tres capacidades que hoy no existen.**

---

## 1. Por qué la omisión ocurrió (y por qué importa admitirla)

Los ocho sub-problemas S1–S8 no son el proceso: son un **instrumento de diagnóstico**. Se
construyeron para poder preguntar «¿esto lleva IA?» ocho veces con respuestas distintas, y eso
funcionó — dos de ellos respondieron *no*.

El error fue tratar ese instrumento como si fuera también el diseño del proceso objetivo. La
máquina de estados E0–E9 es, leída con honestidad, **la misma secuencia del AS-IS con un motor
distinto detrás de cada paso**. Se automatizó cada casilla y se conservó el tablero.

Es el error clásico de la automatización: *paving the cow path*. Y en este caso tenía un
agravante — el proyecto se presenta como un ejercicio de **criterio de arquitectura**, y un
arquitecto que automatiza sin preguntar si el proceso debía existir así no está ejerciendo
criterio, está ejecutando un pedido.

---

## 2. El mecanismo que habilita el rediseño

Antes del análisis paso a paso, la observación que lo ordena todo:

> **Lo que rediseña el proceso no es «la IA». Es que el costo marginal de una decisión cae de
> 19 minutos de analista a segundos y céntimos.**
>
> Cuando decidir es casi gratis, tres cosas que hoy son estructuralmente imposibles se vuelven
> obvias:
>
> 1. **Responder antes de que exista la solicitud** — hoy no se hace porque contestar una
>    consulta cuesta lo mismo que resolver un expediente (7 minutos de búsqueda en el manual).
> 2. **Autorizar un episodio completo en vez de un evento** — hoy no se hace porque revalidar
>    la elegibilidad en cada ciclo cuesta 3 minutos, y sin revalidación la aseguradora perdería
>    control del gasto.
> 3. **Eximir al prestador que ya demostró que no hace falta revisarlo** — hoy no se hace porque
>    nadie tiene el dato de tasa de aprobación por prestador y procedimiento.
>
> Las tres son rediseños de proceso, no piezas de software. Y las tres **solo son seguras
> después** de que lo determinista esté automatizado.

Ese es el argumento que faltaba: la automatización no acelera el proceso viejo, **retira la
restricción económica que obligaba a que el proceso fuera así.**

---

## 3. El análisis, sub-proceso por sub-proceso

Se aplica el criterio clásico de rediseño en este orden — **eliminar → unificar → reordenar →
automatizar** — porque automatizar primero congela el desperdicio.

| # | Sub-proceso AS-IS | Acción | Resultado en el proceso rediseñado |
|---|---|---|---|
| **S1** | Recepción y normalización de la solicitud | **ELIMINAR** | Deja de existir como paso. La solicitud **nace estructurada** en el punto de la orden: el médico elige diagnóstico y procedimiento de un catálogo, no escribe texto libre. No hay nada que recibir y normalizar |
| **S2** | Extracción de datos del PDF | **REDUCIR ALCANCE** | Sobrevive, pero solo sobre lo que seguirá llegando como documento: informes clínicos, exámenes, riesgo anestésico. Los campos administrativos ya no se extraen porque ya vienen capturados. Deja de ser el 21% del esfuerzo y pasa a ser la cola larga |
| **S3** | ¿El sustento está completo? | **ELIMINAR EL ESTADO** | «Observación» deja de ser un **estado del expediente** y pasa a ser una **condición de envío**. No hay carta de observación 24 h después: o el envío se completa en la sesión, o no se envía |
| **S4** | Vigencia, plan, deuda, acumulado | **UNIFICAR** | ↓ |
| **S5** | Carencia y preexistencia | **UNIFICAR** | Los tres colapsan en **una sola evaluación de póliza** que devuelve, en una llamada, elegibilidad + carencia + cobertura + exclusión + copago, con la cita textual. Estaban separados porque eran **tres pantallas y tres personas**, no porque sean tres decisiones |
| **S6** | Cobertura, exclusión y copago | **UNIFICAR** | ↑ |
| **S7** | Casos límite | **REDISTRIBUIR** | Deja de ser una decisión discrecional del analista («ante la duda, derivo») y pasa a ser un **ruteo del sistema con criterio medido**. El médico auditor deja de ser válvula de escape y pasa a ser especialista de excepción |
| **S8** | Emisión de la carta | **ABSORBER** | En el carril automático no es un paso posterior: la decisión y la carta son **el mismo acto transaccional**. Solo sigue siendo un paso separado cuando hay firma humana de por medio |

**Tres pasos desaparecen (S1, S3, S8-como-paso), tres se funden en uno (S4+S5+S6), uno se
reduce (S2) y uno cambia de dueño (S7).**

---

## 4. Los pasos que no existían

Un rediseño que solo quita pasos es un recorte, no un rediseño. Estos son los que aparecen:

| | Capacidad nueva | Qué la habilita | Qué elimina aguas abajo |
|---|---|---|---|
| **N1** | **Respuesta de cobertura en el punto de la orden.** Al elegir diagnóstico + procedimiento + plan, el portal responde *cubierto / no cubierto / requiere sustento X* con la cita y el copago estimado, **antes de que exista la solicitud** | El RAG con cita hace que responder cueste céntimos | El 23% de observaciones tardías y buena parte de las consultas telefónicas a la mesa |
| **N2** | **Autorización por episodio**, no por evento: el esquema oncológico completo o el plan de terapias completo, con control de consumo y revalidación automática de elegibilidad en cada ejecución | Que E2 (elegibilidad) sea determinista y gratuita hace segura la revalidación continua | ≈ 1,400 solicitudes/mes que hoy son renovaciones del mismo tratamiento |
| **N3** | **Estimación de costo de bolsillo al afiliado** antes del procedimiento | El motor de copago determinista ya calcula el número; solo hay que mostrarlo | El daño de `AUT-100` y buena parte de los reclamos por copago |
| **N4** | **Curaduría de la política como proceso continuo** (rol nuevo, ya registrado en `04_to_be.md` §6) | El corpus versionado | La imposibilidad de saber qué se emitió bajo qué versión (F4) |
| **N5** | **Carril de exención por desempeño del prestador** (gold-carding) — *decisión pendiente del sponsor* | El sistema produce la tasa de aprobación por prestador y procedimiento, que hoy no existe | Volumen de entrada completo, no solo su costo unitario |

**N1 y N2 son los dos que de verdad rediseñan.** N3 es una consecuencia barata. N4 es una
obligación de gobierno. N5 es una decisión de negocio que el sistema habilita pero no toma.

---

## 5. El proceso rediseñado

De ocho sub-procesos secuenciales a **tres carriles y cuatro estados**:

```
 CARRIL 0 ── EN EL PUNTO DE LA ORDEN ──────────────────────────────────────────
   N1 · Consulta de cobertura anticipada          [RAG con cita + motor de copago]
        el prestador obtiene la respuesta y la lista exacta de requisitos
        ├─ caso limpio y sustento adjunto  ──────────────►  autorizado en el acto
        └─ caso no resoluble aquí  ─────────────┐
                                                │
 CARRIL 1 ── EXPEDIENTE ────────────────────────▼──────────────────────────────
   GUARDRAIL de entrada (8 capas, fail-close)
        │
   E1 · EXTRACCION                   [con IA]   solo documentos clínicos
        │
   E2 · ADJUDICACION UNIFICADA DE POLIZA
        │   elegibilidad + carencia + cobertura + exclusión + copago
        │   ├─ determinista (integración y reglas)   ← el 63% de la evaluación
        │   └─ RAG con cita obligatoria              ← solo la prosa interpretable
        │
   E3 · RUTEO MEDIDO
        ├─ automático (55-60%) ──┐
        ├─ HITL médico auditor ──┤
        └─ agente de subsanación ┘
        │
   E4 · EMISION CON SELLO DE VERSION   →   TRAZA INMUTABLE

 CARRIL 2 ── EPISODIO ─────────────────────────────────────────────────────────
   N2 · Autorización del plan de tratamiento completo, con control de consumo
        y revalidación automática de elegibilidad en cada ejecución
```

### Qué cambió respecto de E0–E9

| Antes | Ahora | Por qué |
|---|---|---|
| E0 pre-validación (bloquea el envío incompleto) | **N1 responde**, no solo bloquea | Bloquear evita la observación; responder evita la solicitud |
| E2 + E3 + E4 como tres estados | **E2 único** | La separación era organizativa, no lógica |
| E9 emisión como estado posterior | **absorbida en el carril automático** | Decidir y emitir son el mismo acto cuando no hay firma |
| (no existía) | **Carril 2 · episodio** | Ataca volumen, no costo unitario |

---

## 6. Lo que el rediseño **no** cambia

Tres cosas se evaluaron y se mantienen. Decirlas importa tanto como decir lo que cambia:

| Se evaluó | Se descartó | Razón |
|---|---|---|
| Fusionar el guardrail dentro de E1 | **No** | El guardrail debe correr **antes** de que el contenido del expediente toque un modelo. Fusionarlo es exactamente la vulnerabilidad que evita |
| Fusionar E3 (ruteo) con E2 | **No** | El ruteo consume la salida de E2 pero también el histórico del prestador y la carga de la mesa. Son decisiones con insumos distintos |
| Que el agente de subsanación absorba el ruteo | **No** | Volvería a poner un componente no determinista en el camino de la decisión. El veto V1 sigue vigente |
| Eliminar el HITL para casos límite | **Nunca** | Es el invariante R3. No es un paso ineficiente: es el control que separa esta solución de nH Predict |
| Reducir las 8 capas de guardrail | **No** | El orden barato→caro ya hace que las capas 7–8 se ejecuten sobre un residuo pequeño. El costo no está en las capas, está en las llamadas que ya se evitaron |

**El HITL es el único paso del proceso que se conserva por razones que no son de eficiencia.**
Eso es deliberado y hay que poder defenderlo en la presentación.

---

## 7. El límite honesto: dos rediseños no dependen de la arquitectura

Aquí está el hallazgo más incómodo del análisis, y es el que hay que poner sobre la mesa del
sponsor:

### 7.1 N2 (autorización por episodio) requiere cambiar la póliza, no el sistema

La póliza vigente exige preautorización **por procedimiento**, y la autorización emitida tiene
**30 días calendario de vigencia**. Un esquema oncológico de seis ciclos abarca ~5 meses. Para
que N2 exista hacen falta tres cambios **contractuales**:

1. Un tipo de autorización *por plan de tratamiento* con vigencia extendida.
2. Un mecanismo de control de consumo (sesiones o ciclos ejecutados contra autorizados).
3. Un disparador de revalidación si cambia la elegibilidad a mitad de tratamiento — afiliación,
   deuda, tope de bolsillo.

El punto 3 es la razón por la que esto es un rediseño *habilitado por la automatización*: hoy
sería temerario ceder una autorización a cinco meses porque revalidar cuesta 3 minutos de
analista por evento. **Con E2 automatizado, revalidar cuesta milisegundos, y ceder la
autorización deja de ser ceder el control.**

### 7.2 N1 solo alcanza hasta donde llega el portal

En el Perú no hay CDS Hooks ni integración con el HIS de la clínica (ver `03_benchmark_mercado.md`).
N1 funciona **dentro del portal de prestadores de Vitalia**, que es nuestro. No se puede
incrustar en el sistema del prestador. Eso acota el alcance real: la respuesta anticipada llega
al médico solo si el médico entra al portal — que es lo que hoy hace de todos modos para enviar.

**Consecuencia de diseño:** N1 no puede ser una pantalla más. Tiene que ser *el* formulario de
envío, de modo que obtener la respuesta anticipada y enviar la solicitud sean el mismo acto.

---

## 8. Efecto sobre la volumetría y sobre el caso de negocio

**Supuesto declarado, pendiente de validar** (se suma a los cinco de `01_caso_y_as_is.md` §8):

| Origen | Volumen hoy | Supuesto | Reducción |
|---|---:|---|---:|
| Terapias > 12 sesiones (22%) | 1,716/mes | ≈ 2,2 solicitudes por curso de tratamiento; con N2 queda 1 | **−940/mes** |
| Oncológicos por ciclo (11%) | 858/mes | Esquema medio de 4 ciclos; con N2 queda 1 | **−640/mes** |
| Ajuste conservador (−25% por casos que igual requieren autorización por evento) | | | +395 |
| | | **Neto** | **≈ −1,200 a −1,600/mes** |

**7,800 → ≈ 6,400 solicitudes/mes: entre 15% y 20% del volumen de entrada desaparece antes de
automatizar nada.** A ello se suma, sin cuantificar aquí, el efecto de N1 sobre las consultas
que hoy entran como solicitud solo para averiguar si algo está cubierto.

### Cómo se trata en el caso de negocio

**No se monetiza.** `05_caso_de_negocio.md` sigue calculado sobre 7,800 solicitudes/mes y no se
modifica. Razones:

- El supuesto de solicitudes por curso de tratamiento **no está medido**, y el caso de negocio ya
  cuelga de dos supuestos sin medir. Agregar un tercero lo debilita.
- N2 depende de un **cambio contractual** que el proyecto no controla.

Se registra como **holgura, no como compromiso**: si se valida, aporta del orden de
**S/ 6,000–7,000/mes adicionales** de valor capturable (≈1,400 solicitudes × S/ 10,3 de costo
unitario TO-BE × factor de captura). El valor real de N2 no es ese ahorro: es que **el paciente
oncológico deja de pedir permiso cada 21 días para continuar el mismo tratamiento.** Ese es el
impacto del nivel 1 del modelo del problema, y no tiene precio en la hoja de cálculo.

---

## 9. Efecto sobre el roadmap

La secuencia de `04_to_be.md` §7 no se rompe, pero se corrige en dos puntos:

| Fase | Antes | Ahora |
|---|---|---|
| **F0** | E0 pre-validación (bloquear el envío incompleto) | **F0 se parte.** F0a: la tabla de requisitos en el formulario (sin IA, ~4 sem). F0b: N1 respuesta anticipada — **se mueve a F2**, porque necesita el RAG con cita |
| **F1** | E2 + E3 elegibilidad y carencia | Igual, pero se declara explícitamente que **es la precondición de N2**: sin revalidación automática y barata, la autorización por episodio no es defendible |
| **F2** | E1 extracción + E4 RAG | Igual + **N1** |
| **F3** | E5 ruteo + E6 auto + E9 sello | Igual, con E9 absorbida en el carril automático |
| **F4** | E8 agente | Igual |
| **F5** *(nueva, condicional)* | — | **N2 autorización por episodio**, ~6 sem, **bloqueada por el endoso a la póliza**. Si el endoso no se aprueba, la fase no se ejecuta y el proyecto no pierde nada de lo comprometido |

Que F5 sea condicional y no comprometida es deliberado: **es la fase de mayor retorno y la de
menor control por parte del equipo de arquitectura.**

---

## 10. Conclusión para la presentación

Tres frases, en este orden:

1. **«El proceso no se automatizó: se rediseñó. Pasa de ocho sub-procesos a cuatro estados, y
   aparecen tres capacidades que hoy no existen.»**
2. **«El rediseño no lo trae la IA. Lo trae que decidir deje de costar 19 minutos. La IA es lo
   que hace que decidir deje de costar 19 minutos.»**
3. **«Y el rediseño de mayor impacto —autorizar el tratamiento completo en vez de cada ciclo—
   no requiere un componente más: requiere un endoso a la póliza. Está sobre la mesa del
   sponsor, no en el diagrama de arquitectura.»**

La tercera frase es la que distingue un informe de arquitectura de un catálogo de tecnologías.

---

**Diagrama asociado:** `diagramas/D-10_rediseno_del_proceso.drawio`
**Documento corregido por este:** `04_to_be.md` §3, §4 y §7.

# Proyecto final — Modelo del problema

- **Proyecto final** · DataPath · AI Solutions Architect
- **Autor:** Jonatan Sánchez · **Fecha:** 2026-09-04
- **Este documento va primero.** Antes de proponer arquitectura hay que estar de acuerdo en cuál
  es el problema. Se presenta la organización, y luego se modela el problema en tres niveles:
  el mundo, el Perú y nuestro cliente.

---

## 0. Antes de empezar: de qué negocio estamos hablando

Este caso ocurre en una aseguradora de salud. Si vienes de banca, telco, retail o industria,
esta sección alcanza para entender todo lo demás sin saber nada del sector.

### 0.1 Cómo funciona el negocio, en cuatro líneas

Una aseguradora de salud cobra una **cuota mensual fija** por persona cubierta y, a cambio, paga
las atenciones médicas que esa persona necesite, dentro de los límites de su plan. Gana dinero
si lo que cobra supera lo que paga en atenciones más lo que gasta en administrarlas.

```
   INGRESO                    COSTO PRINCIPAL              COSTO OPERATIVO
   Cuota mensual        −     Atenciones médicas      −    Administrar todo esto
   por afiliado               que efectivamente paga       (mesas, sistemas, personal)
       │                              │                             │
       └──── comercial ───────────────┴──── control del gasto ──────┴─── eficiencia
```

**El proceso de este proyecto —la preautorización— vive exactamente en la bisagra entre las dos
últimas columnas:** existe para controlar el gasto, y hoy cuesta caro administrarlo.

### 0.2 Diccionario de equivalencias

| En seguros de salud | Qué es | Equivalente aproximado en otro sector |
|---|---|---|
| **Prima** | Pago mensual por estar cubierto | La cuota del plan o la suscripción mensual |
| **Afiliado** | La persona cubierta | El cliente titular del servicio |
| **Prestador** | Clínica u hospital que atiende | El comercio afiliado donde se consume |
| **Red** | Los prestadores con los que hay contrato | Los comercios donde la tarjeta es aceptada |
| **Suma asegurada** | Tope anual que el plan cubre | La línea de crédito anual |
| **Copago / deducible** | La parte que paga el afiliado en cada atención | La franquicia o el cargo por transacción |
| **Carencia** | Tiempo que hay que esperar tras contratar antes de poder usar un beneficio | El período mínimo de permanencia antes de habilitar un beneficio |
| **Preexistencia** | Condición de salud anterior a la contratación | El riesgo declarado antes del alta del servicio |
| **Siniestralidad** | Porcentaje de la cuota que se va en pagar atenciones | El costo de servicio sobre el ingreso |
| **Exclusión** | Lo que el contrato explícitamente no cubre | Las condiciones del contrato en letra pequeña |
| **Preautorización** | **Permiso previo del asegurador antes de un procedimiento caro** | **La autorización de una transacción antes de que se ejecute el consumo** |

### 0.3 La analogía que resume el problema

> En banca, cuando pasas la tarjeta, el comercio le pregunta al banco *"¿autoriza este consumo,
> para este cliente, por este monto?"*. La respuesta llega en **milisegundos**, es automática,
> queda registrada y se puede reconstruir después.
>
> **La preautorización médica es exactamente esa pregunta.** La diferencia es que aquí demora
> **cinco días**, la responde **una persona leyendo PDFs escaneados** y buscando la regla en un
> manual de texto, y frecuentemente **no se puede reconstruir** con qué versión de las reglas se
> respondió.
>
> Y mientras esa autorización no llega, hay un paciente esperando una cirugía.

Ese es el problema completo. Todo lo demás es detalle.

---

## 1. La organización del caso: Vitalia Salud EPS

> **Aviso.** Vitalia Salud EPS es una organización ficticia construida para este proyecto. Su
> política —planes, coberturas, exclusiones, carencias, plazos y códigos— está documentada en el
> corpus normativo que acompaña al proyecto. La volumetría, la estructura y los costos son
> **supuestos declarados**, no datos reales; están calibrados para ser defendibles y su origen se
> indica en cada caso (`01_caso_y_as_is.md` §8).

### 1.1 Ficha de la empresa

| | |
|---|---|
| **Rubro** | Aseguramiento privado en salud. Es una **EPS** (Entidad Prestadora de Salud): una figura regulada peruana que complementa a la seguridad social pública. La empresa contratante redirige parte de su aporte obligatorio para dar a sus trabajadores una cobertura privada |
| **Cliente que paga** | Mayoritariamente **empresas** (contratos corporativos para sus trabajadores y familiares), y en menor medida personas naturales |
| **Cliente que usa** | El **afiliado**: el trabajador y su familia |
| **Tamaño** | 165,000 afiliados vigentes |
| **Portafolio** | Tres planes: **Esencial** (básico, red acotada, copago alto), **Integral** (el corporativo típico, 62% de la cartera), **Premium** (sin copago, red completa) |
| **Cómo gana dinero** | Margen entre la cuota cobrada y lo que paga en atenciones más el gasto administrativo |
| **Regulador** | **SUSALUD** — la superintendencia del sector, que fiscaliza plazos, cobertura y sanciona |

### 1.2 Dónde vive la preautorización dentro de la organización

```
   COMERCIAL          OPERACIONES              AUDITORÍA        FINANZAS      CUMPLIMIENTO
   vende y renueva    │                        MÉDICA           liquida       responde a
   contratos          │                        4 médicos        y paga        SUSALUD
   corporativos       │                             ▲              ▲              ▲
        │             │                             │              │              │
        │      ┌──────┴───────────────────┐         │              │              │
        │      │  MESA DE AUTORIZACIONES  │─────────┘              │              │
        │      │  16 analistas · 2 turnos │                        │              │
        │      │  1 supervisor            │────────────────────────┘              │
        │      └──────────────────────────┘                                       │
        │                    │                                                    │
        └────────────────────┴────────────────────────────────────────────────────┘
                    cuando este proceso falla, todos se enteran
```

La **mesa de autorizaciones** es un equipo de 16 analistas en dos turnos, con un supervisor, que
responde por un compromiso contractual: **resolver en 5 días hábiles** los procedimientos
programados y en **48 horas** los urgentes. Se apoya en un equipo de **4 médicos auditores**
cuando el caso requiere criterio clínico.

### 1.3 El proceso, en una frase

> Cada vez que un médico indica un procedimiento caro y programable —una cirugía, una resonancia,
> un tratamiento oncológico, una serie de terapias— la clínica **no lo ejecuta hasta que Vitalia
> diga que sí**. La mesa de autorizaciones es quien dice sí o no, y con qué copago.

Requieren ese permiso: hospitalizaciones programadas, cirugías electivas, imágenes de alto costo,
estudios genéticos, medicina nuclear, terapias de más de 12 sesiones, prótesis y órtesis,
tratamientos oncológicos y la atención en el extranjero.

**No** lo requieren las consultas ambulatorias, los análisis de rutina ni las emergencias —
aunque la emergencia que termina en hospitalización se regulariza dentro de 48 horas.

### 1.4 Quién depende de este proceso

Esta es la parte que normalmente no se dice y que explica por qué el proyecto importa. El proceso
parece una mesa administrativa interna; en realidad es un cuello de botella del que cuelga una
cadena larga.

```
                      ┌─────────────────────────────────┐
                      │   MESA DE PREAUTORIZACIÓN       │
                      └─────────────────────────────────┘
                                    │
        ┌───────────── IMPACTO DIRECTO ─────────────────┐
        │                                                │
   EL PACIENTE          EL MÉDICO Y LA CLÍNICA      EL EQUIPO INTERNO
   espera, reprograma,  pierde el cupo de           analistas saturados,
   a veces desiste,     quirófano, no factura,      médicos auditores
   a veces paga todo    reprograma agenda           resolviendo lo que
   de su bolsillo                                   no les corresponde
        │                        │                          │
        └──────────── IMPACTO INDIRECTO ───────────────────┘
                                 │
   ┌─────────────┬───────────────┼──────────────┬──────────────────┐
   │             │               │              │                  │
 LA EMPRESA   COMERCIAL      FINANZAS      CUMPLIMIENTO      LA RED DE
 CONTRATANTE  pierde         paga de más   responde ante     PRESTADORES
 su trabajador renovaciones  por errores   SUSALUD por       negocia peor
 falta al      corporativas  de cálculo    cada reclamo      con quien le
 trabajo                                                     hace perder
                                                             quirófanos
```

Traducido a lenguaje de negocio de cualquier sector:

| Quién | Qué le pasa cuando la preautorización falla | Cómo se llama esto en otro sector |
|---|---|---|
| **El afiliado** | Posterga un procedimiento médico, o lo hace y paga todo | Falla de servicio con daño al cliente final |
| **El prestador** | Un quirófano vacío que ya estaba reservado | Capacidad instalada desperdiciada en el canal |
| **La empresa contratante** | Su trabajador se queja a Recursos Humanos y falta al trabajo | Insatisfacción del cliente B2B que paga la factura |
| **Comercial** | En la renovación anual, RR.HH. recuerda ese caso | **Riesgo de churn de una cuenta completa** — cientos de afiliados a la vez, no uno |
| **Finanzas** | Se paga de más por errores de cálculo del copago | Fuga por error operativo |
| **Cumplimiento** | Un reclamo formal ante el regulador | Exposición regulatoria y sancionatoria |
| **La red de prestadores** | Menos disposición a negociar tarifas con quien le complica la operación | Deterioro del poder de negociación con proveedores |

**El punto clave para un lector de otro sector:** una demora en esta mesa no es un ticket
atrasado. Es un cliente B2B que puede llevarse **cientos de afiliados de golpe** en la
renovación, y un paciente que puede no operarse.

---

## 2. El problema, en una frase

> **La preautorización médica existe para controlar el gasto, pero se ejecuta como un trámite
> manual de lectura de documentos contra reglas escritas en prosa. El resultado es que un control
> de costos termina retrasando o cancelando atención médica.**

Todo lo demás de este proyecto —el estado actual, la matriz de decisión, el proceso objetivo, la
arquitectura— existe para atacar esa frase. Si una decisión de diseño no mueve esa aguja, no
entra.

A partir de aquí el problema se modela en tres niveles: **el mundo** (§3), **el Perú** (§4) y
**nuestro cliente** (§5).

---

## 3. Nivel 1 — El problema en el mundo

### 3.1 Por qué existe la preautorización y por qué duele

Es el permiso previo que un financiador exige antes de un procedimiento costoso o electivo. Su
propósito es legítimo: evitar procedimientos innecesarios, verificar cobertura antes de generar
deuda y contener el gasto.

El problema no es que exista. El problema es **cómo se ejecuta**: como intercambio de documentos
entre dos organizaciones que no comparten datos, resuelto por personas que leen PDFs y buscan
reglas en un manual.

```
        EL FINANCIADOR                                    EL PRESTADOR
   (quiere controlar el gasto)                     (quiere atender al paciente)
              │                                              │
              │          ◄── solicitud en PDF ──             │
              │          ── pide más documentos ─►           │
              │          ◄── reenvía documentos ──           │
              │          ── aprueba / niega ─►               │
              │                                              │
              └─────────────── EN EL MEDIO ─────────────────┘
                                    │
                              EL PACIENTE
                     (espera, no sabe, a veces desiste)
```

La fricción es estructural: los incentivos de ambos lados son opuestos y el canal entre ellos es
documental. **El paciente no participa de la negociación pero paga el costo del tiempo.**

### 3.2 La magnitud, medida

Datos de la encuesta anual de la *American Medical Association* sobre preautorización (mercado
estadounidense, que es donde el proceso está mejor medido):

| Dimensión | Dato | Lectura |
|---|---|---|
| Carga por médico | **40 solicitudes/semana** | Es un proceso de alto volumen, no excepcional |
| Tiempo consumido | **13 horas/semana** entre médico y personal | Más de un día laboral por médico |
| Estructura dedicada | **40%** de las prácticas emplea personal exclusivo para esto | El costo administrativo se institucionalizó |
| Demora en la atención | **95%** de médicos reporta que retrasa atención necesaria | El daño es casi universal, no marginal |
| Abandono de tratamiento | **79%** reporta que pacientes abandonan el tratamiento | La demora funciona, de hecho, como negación |
| Evento adverso serio | **26%** reporta que la preautorización derivó en uno | Uno de cada cuatro médicos lo ha visto |
| — hospitalización | 19% | |
| — riesgo de vida o intervención para evitar daño permanente | 13% | |
| — **discapacidad, daño permanente, anomalía congénita o muerte** | **7%** | |

**La conclusión que ordena todo el proyecto:** el costo de la preautorización lenta no es
administrativo, es **clínico**. Esto cambia qué se optimiza. Un diseño que solo minimiza costo
por solicitud está optimizando la variable equivocada.

### 3.3 Cómo lo está respondiendo el mercado maduro

No estamos frente a un problema sin respuestas publicadas. Hay cuatro líneas, y conviene
distinguirlas porque **solo dos son tecnológicas**:

```
   RESPUESTAS AL PROBLEMA DE LA PREAUTORIZACIÓN
   │
   ├── (A) INTEROPERABILIDAD  ─► HL7 Da Vinci: CRD / DTR / PAS
   │       "que el prestador sepa qué se necesita ANTES de pedirlo"
   │
   ├── (B) REGULACIÓN         ─► CMS-0057-F (APIs obligatorias desde 2027)
   │                             SB 1120 California (la IA no decide, el médico sí)
   │
   ├── (C) ELIMINAR VOLUMEN   ─► gold-carding (Texas HB 3459)
   │       "al prestador con buen historial no se le exige preautorización"
   │
   └── (D) AUTOMATIZAR        ─► Cohere Health y similares
           "resolver más rápido lo que sí hay que resolver"
```

- **(A) Da Vinci** define tres perfiles: **CRD** (descubrir en tiempo real, en el momento de la
  orden, qué exige el pagador), **DTR** (rellenar la documentación con plantillas y reglas) y
  **PAS** (enviar la solicitud como transacción estructurada, no como PDF). La idea central es
  **prevenir la solicitud incompleta en el origen** en vez de observarla después en la cola.
- **(B)** El regulador estadounidense obliga a los pagadores a exponer APIs de preautorización
  desde 2027 (CMS-0057-F, vigente desde 2026-01-01). En paralelo, California prohíbe que un
  algoritmo decida una negación por necesidad médica: puede asistir y ordenar información, pero
  la decisión la firma un médico colegiado.
- **(C)** El *gold-carding* exime de preautorización al prestador con historial de aprobación
  alto. **Ataca el volumen sin tecnología.** Es la alternativa que un arquitecto honesto tiene
  que poner sobre la mesa antes de proponer un sistema.
- **(D)** La automatización con IA reporta, en cifras de proveedor, hasta 90% de aprobación
  automática y 85% en tiempo real.

### 3.4 El anti-patrón: cuando la IA optimiza la variable equivocada

Dos casos públicos definen lo que **no** se debe construir:

| Caso | Qué hizo | Por qué es un anti-patrón |
|---|---|---|
| **nH Predict** (UnitedHealth) | Modelo predictivo para terminar cobertura post-aguda; una demanda colectiva alega ~90% de error, con metas internas de mantenerse a 1% de la proyección del modelo | Sustituyó el criterio clínico por la predicción y ató al revisor humano a la salida del modelo. En marzo de 2026 un tribunal ordenó revelar el algoritmo |
| **PXDX** (Cigna) | Revisión masiva de reclamos: 300,000+ en dos meses, ~1.2 segundos por caso | Optimizó **productividad de negación**, no calidad de decisión |

**La lección de diseño:** en este dominio, la métrica de eficiencia sin su métrica de contrapeso
es peligrosa. Por eso en este proyecto **`% de automatización` nunca se reporta solo**: siempre
va junto a `% de reversiones al apelar` y `% de negaciones sin firma médica`.

---

## 4. Nivel 2 — El escenario peruano

### 4.1 Quién es quién

```
                        SUSALUD  (regulador)
                        fiscaliza plazos, cobertura y sustento
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
        IAFAS                                   IPRESS
  (quien financia: EPS,                  (quien atiende: clínicas,
   seguros, EsSalud, SIS)                 hospitales, consultorios)
          │                                       │
          │  ◄──── preautorización ───────────    │
          │                                       │
          └─────────────── AFILIADO ──────────────┘
                    (paciente / usuario)
```

- **IAFAS** = quien administra el fondo y paga. Aquí entra Vitalia Salud EPS.
- **IPRESS** = quien atiende: clínicas, hospitales, consultorios.
- **SUSALUD** = la superintendencia del sector. Recibe el reclamo del afiliado, fiscaliza y
  sanciona.

### 4.2 Por qué la respuesta del mercado maduro no se puede copiar y pegar

Esta es la diferencia que hace interesante el caso peruano, y es un problema de arquitectura, no
de presupuesto:

| Supuesto del modelo Da Vinci | Realidad peruana | Consecuencia de diseño |
|---|---|---|
| El prestador tiene una historia clínica electrónica que consulta al pagador en el momento de la orden | El portal de prestadores es un formulario web; no hay integración en el punto de la orden | **CRD no se puede implementar como está.** Hay que replicar su *efecto* dentro del propio portal |
| La documentación viaja estructurada | El sustento llega como **PDF escaneado**: orden médica, informe, exámenes | La extracción no es opcional; es el primer problema técnico real |
| Existe un intercambio transaccional estándar | No existe un estándar nacional de preautorización | El estándar hay que construirlo internamente, y será propietario |
| Hay obligación regulatoria con fecha | Sí la hay, pero **para elegibilidad, no para preautorización** (ver §4.3) | La palanca regulatoria disponible es distinta |

> **Este es el hueco donde el proyecto aporta:** no inventar un modelo de proceso —ya existe y
> está publicado— sino **portarlo a un contexto de baja madurez de interoperabilidad sin perder
> auditabilidad**. Ahí es donde la IA hace un trabajo que ninguna otra tecnología hace: convertir
> el PDF escaneado y las reglas en prosa en algo estructurado y citable.

### 4.3 La única pieza que ya es obligatoria y tiene fecha: Acredita Salud

SUSALUD estableció **Acredita Salud**, el modelo estandarizado de intercambio electrónico para
verificar, antes de la atención, el **estado de afiliación, el plan y la cobertura disponible**
del asegurado. Reemplaza al antiguo mecanismo SITEDS.

| Hito | Dato |
|---|---|
| Norma que lo establece | Res. N.° 034-2025-SUSALUD/S (feb-2025) |
| Prórroga vigente | Res. de Superintendencia N.° 000143-2026-SUSALUD/SUP (26-ago-2026) |
| **Fecha límite de adopción** | **31 de octubre de 2026** |
| Avance IAFAS | 43 de 48 migradas (≈90%) |
| Avance IPRESS | 386 de 508 en proceso de migración |

**Impacto directo en el diseño:** verificar si el afiliado está vigente y qué plan tiene deja de
ser una consulta interna al sistema central y pasa a ser una **integración normada con fecha
externa e innegociable**. Ese hito entra al roadmap del proyecto no como mejora, sino como
restricción.

### 4.4 Qué pasa cuando la preautorización falla: el circuito del reclamo

En el Perú el afiliado tiene un canal formal, y ese canal tiene relojes:

```
  El afiliado no recibe respuesta a tiempo, o le niegan cobertura
                        │
                        ▼
        ┌── LIBRO DE RECLAMACIONES (la aseguradora o la clínica) ──┐
        │   la institución tiene 30 días para responder            │
        └──────────────────────────────────────────────────────────┘
                        │
              ¿respuesta insatisfactoria o ninguna?
                        │
                        ▼
        ┌─────────── SUSALUD ──────────────────────────┐
        │  abre investigación en 24-48 horas            │
        │  el proceso dura 30-60 días hábiles           │
        │  puede terminar en sanción y multa            │
        └───────────────────────────────────────────────┘
```

Tres distinciones que importan porque definen contra qué se defiende el sistema:

- **Reclamo** — se vulneró un derecho: negación de cobertura, cobro indebido, atención denegada.
  *Aquí caen los errores de nuestra mesa.*
- **Queja** — mala atención del personal, infraestructura, demoras injustificadas.
- **Denuncia** — vulneración masiva o sistemática.

**Cómo se ve esto en la práctica (reportaje de Ojo Público, período 2019–2023):**

| Dato | Valor |
|---|---|
| Aseguradoras sancionadas | al menos **27** |
| Sanciones impuestas por SUSALUD | **74** |
| Monto aproximado en multas | **≈ S/ 6 millones** |
| Reclamos de usuarios contra aseguradoras ya sancionadas (ene–sep 2023) | **7,000+** |
| **Infracciones más recurrentes** | **no otorgar cobertura oportuna** y **no respetar las preexistencias** |

Léase con cuidado: **la infracción número uno del sector es exactamente el fallo que produce una
mesa de preautorización lenta.** El problema no es hipotético ni importado — es el motivo
principal por el que el regulador sanciona a una aseguradora en el Perú.

Y hay un segundo dato incómodo: 74 sanciones frente a 7,000+ reclamos sugiere que **la mayor
parte del daño no llega a sanción**. La exposición regulatoria real es mayor que la multa
esperada, y por eso el argumento del proyecto no puede sostenerse solo en "evitar multas".

---

## 5. Nivel 3 — Cómo aterriza esto en Vitalia Salud

### 5.1 Del mundo al escritorio del analista

| Nivel 1 — el mundo | Nivel 2 — el Perú | Nivel 3 — Vitalia |
|---|---|---|
| El sustento llega incompleto y se descubre tarde | El portal no valida nada al recibir | **23% de las solicitudes se observan** a las 24h |
| El proceso consume tiempo clínico | No hay estándar de intercambio; todo es lectura manual | **19 min de trabajo por solicitud**, de los cuales **7 min buscando en el manual** |
| La demora niega de hecho el tratamiento | "Cobertura no oportuna" es la infracción más sancionada | **6.8 días en el 95% peor de los casos, contra un compromiso contractual de 5** |
| Se exige que la decisión sea reconstruible | El regulador pide el sustento de la negación en la fiscalización | **Las reglas cambian ~6 veces al año y no se sabe qué carta se emitió bajo qué versión** |
| La elegibilidad debería resolverse por dato, no por criterio | Acredita Salud lo vuelve obligatorio al 31-oct-2026 | **16% del esfuerzo se va en validar vigencia, plan y deuda a mano** |

### 5.2 El proceso de hoy, tal como ocurre

**Vista de carriles — quién toca qué:**

```
 PRESTADOR          PORTAL          ANALISTA (mesa)             AUDITOR MÉDICO      AFILIADO
    │                 │                   │                           │                │
 (1)│── solicitud ───►│                   │                           │                │
    │   + PDFs        │─── a la cola ────►│                           │                │
    │                 │                   │                           │                │
    │                 │              (2) descarga y transcribe    [4 min]              │
    │                 │              (3) valida en el sistema     [3 min]              │
    │                 │                  central: vigencia, plan, deuda                │
    │                 │              (4) calcula la carencia      [2 min]              │
    │                 │              (5) BUSCA EN EL MANUAL       [7 min]  ◄── 37%     │
    │                 │                  cobertura / exclusión / copago                │
    │                 │                   │                           │                │
    │◄── (6a) OBSERVACIÓN ────────────────│                           │                │
    │    "falta el examen preoperatorio"  │   23% del volumen         │                │
    │    [el plazo se suspende]           │                           │                │
    │                 │                   │                           │                │
    │                 │              (6b) │───── deriva ─────────────►│                │
    │                 │                   │   21% del volumen    evalúa criterio       │
    │                 │                   │◄──── devuelve ────────────│                │
    │                 │                   │                           │                │
    │                 │              (7) redacta y emite la carta [3 min]              │
    │◄── carta de garantía a la clínica ──│────────── notificación ──────────────────►│
```

**El detalle que explica el desperdicio:** los pasos (3), (4) y (5) se ejecutan en **tres
pantallas distintas y un PDF**, y sus resultados se copian a mano a la carta. Nada de eso está
integrado.

### 5.3 Dónde se pierde el tiempo y por qué

```
  TIEMPO DE TRABAJO POR SOLICITUD = 19 min
  │
  │  Leer adjuntos y transcribir        ████          4 min  → lectura no estructurada
  │  Validar elegibilidad               ███           3 min  → dato que ya existe
  │  Calcular la carencia               ██            2 min  → aritmética contra una tabla
  │  BUSCAR EN EL MANUAL                ███████       7 min  → reglas propias escritas en prosa
  │  Redactar y emitir la carta         ███           3 min  → generación + registro
  │
  └─► los 7 min de búsqueda son el 37% del esfuerzo
      y además causan los dos desperdicios más caros del proceso
```

Los 7 minutos no son solo costo directo. Son la causa de:

- **derivación defensiva** — el analista no encuentra la regla, o la encuentra pero no quiere
  firmarla solo, y escala al médico auditor;
- **error de copago** — cinco variables cruzadas a mano (plan, tipo de atención, nivel de la
  clínica, acumulado del año y tope de gasto de bolsillo).

### 5.4 Los siete dolores, en orden de lo que cuestan

| # | Dolor | Magnitud | Consecuencia |
|---|---|---|---|
| **P1** | Observación tardía por sustento incompleto | 23% del volumen — 1,794/mes, 64% vuelve = **1,148 retrabajos/mes** | El prestador pierde un día y el cupo de quirófano |
| **P2** | Derivación defensiva al auditor médico | 21% — 1,638/mes, de las cuales **55% no requería criterio clínico** (900/mes) | Capacidad médica desperdiciada + alarga el plazo de los casos que sí la necesitan |
| **P3** | Error de copago en la carta emitida | 3.8% — 296/mes × S/ 210 | Fuga económica directa y reclamo potencial |
| **P4** | Rechazos revertidos al reclamar | 1.4% — 109/mes | Expediente de reclamo + exposición ante el regulador |
| **P5** | Conocimiento tácito y rotación | 3 analistas senior resuelven el 70% de los casos difíciles; rotación 38%, curva 11 semanas | El proceso depende de personas, no de un activo de la empresa |
| **P6** | Pico de lunes 2.4× el promedio | — | El incumplimiento se concentra ahí: es capacidad elástica, no productividad media |
| **P7** | Cambios de reglas sin trazabilidad | ~6 cambios/año | **No se puede reconstruir bajo qué versión se emitió una carta** — justo lo que pide una fiscalización |

### 5.5 La regla que convierte un retraso en un daño

La cláusula más estricta del contrato: un procedimiento programado realizado **sin**
preautorización se rechaza con el código **`AUT-100`**, y el gasto queda **íntegramente a cargo
del afiliado**, aunque el procedimiento estuviera cubierto.

```
   La mesa no responde dentro del plazo comprometido
                │
     ┌──────────┴──────────┐
     │                     │
  el paciente          el paciente
  posterga             opera igual
  el procedimiento           │
     │                       ▼
     ▼                  AUT-100: paga todo de su bolsillo
  daño clínico              │
  (el 26% de la AMA)        ▼
                       reclamo ─► SUSALUD ─► "cobertura no oportuna"
```

**Por eso el plazo no es una métrica de servicio: es el mecanismo por el cual un problema
operativo se transfiere al paciente.** Las dos ramas del diagrama son, respectivamente, el dato
mundial del nivel 1 y la infracción más sancionada del nivel 2.

### 5.6 El costo, sumado

| Concepto | S/ mes |
|---|---|
| Operación de la mesa | 76,600 |
| Retrabajo por observación (P1) | 11,300 |
| Auditoría médica total (P2) — de la cual S/ 26,400 es defensiva | 48,000 |
| Fuga por copago mal aplicado (P3) | 62,200 |
| Gestión de reclamos por reversión (P4) | 37,100 |
| **Total** | **235,200** |
| | **≈ S/ 2.82 M / año** |

Y lo que no está en la tabla: el incumplimiento del compromiso contractual, el riesgo regulatorio
de negaciones sin sustento reconstruible, y los procedimientos médicos postergados.

---

## 6. El problema, ya modelado

Uniendo los tres niveles, el problema de Vitalia se descompone en **cuatro fallas
estructurales**. Esta es la salida de este documento y la entrada de todo lo demás:

| # | Falla estructural | Se ve en | Nivel donde se originó |
|---|---|---|---|
| **F1** | **La solicitud entra incompleta y nadie lo detecta al recibirla** | P1, 23% de observaciones | Mundo: es lo que Da Vinci resuelve con CRD/DTR |
| **F2** | **El conocimiento de las reglas vive en prosa y en la cabeza de tres personas** | P2, P5, los 7 min de búsqueda | Cliente: manual no estructurado |
| **F3** | **Lo determinista se resuelve a mano** | P3, los 5 min de elegibilidad y carencia, el 16% del esfuerzo | Perú: Acredita Salud lo vuelve obligatorio con fecha |
| **F4** | **Una decisión emitida no se puede reconstruir después** | P4, P7 | Mundo + Perú: es lo que exigió el tribunal en nH Predict y lo que pide SUSALUD |

### Cómo se leen estas cuatro fallas

- **F3 no necesita IA.** Es integración y motor de reglas. Y es donde está la fuga económica más
  grande del cuadro (P3, S/ 62,200/mes). El mayor retorno del proyecto viene de la parte que *no*
  lleva IA — y decirlo explícitamente vale más que cualquier diagrama.
- **F1 y F2 sí necesitan IA**, pero de tipos distintos: F1 es leer documentos no estructurados,
  F2 es recuperar conocimiento propio que cambia y hay que citar.
- **F4 no es un problema de modelo, es de arquitectura**: versionado de las reglas, trazabilidad
  de la decisión y firma médica. Ningún modelo lo resuelve; se resuelve con diseño.

---

## 7. Lo que este documento deja definido

- **La frontera:** software convencional bien hecho resuelve F3 completa y parte de F1. La IA
  empieza donde hay **PDF escaneado** (F1) y **reglas en prosa que hay que citar** (F2). El
  diseño se construye sobre esa frontera, no sobre la ambición de usar todas las tecnologías
  disponibles.
- **La métrica que no se puede optimizar sola:** automatización sin reversiones ni firma médica.
  Es la lección del anti-patrón del nivel 1.
- **La restricción externa con fecha:** Acredita Salud, 31-oct-2026.
- **La alternativa no tecnológica que hay que evaluar honestamente:** el *gold-carding* — eximir
  de preautorización a los prestadores con historial de aprobación alto. Ataca el volumen, no el
  costo unitario, y compite por el mismo presupuesto.

**Siguiente:** `01_caso_y_as_is.md` cuantifica el estado actual · `02_matriz_de_decision.md` rutea
cada sub-problema · `03_benchmark_mercado.md` sustenta las referencias de mercado ·
`04_to_be.md` define el proceso objetivo · `05_caso_de_negocio.md` lo traduce a dinero.

---

## Fuentes

- American Medical Association — *Prior Authorization Physician Survey* (carga, demora, eventos adversos).
- HL7 Da Vinci Project — Implementation Guides **CRD**, **DTR**, **PAS**.
- CMS-0057-F — *Interoperability and Prior Authorization Final Rule* (vigencia 2026-01-01, APIs 2027-01-01).
- California SB 1120 — *Physicians Make Decisions Act* (vigencia 2025-01-01).
- Texas HB 3459 — gold-carding.
- Demanda colectiva **nH Predict** (UnitedHealth) y reportaje sobre **PXDX** (Cigna).
- SUSALUD — Res. N.° 034-2025-SUSALUD/S y Res. de Superintendencia N.° 000143-2026-SUSALUD/SUP (Acredita Salud).
- SUSALUD — libro de reclamaciones: reclamo / queja / denuncia y plazos.
- Ojo Público — *Seguros de salud: miles de reclamos y escasas sanciones* (2019–2023).

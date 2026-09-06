# Proyecto final — Caso de estudio y situación actual (AS-IS)

- **Proyecto final** · DataPath · AI Solutions Architect
- **Autor:** Jonatan Sánchez · **Fecha:** 2026-09-04
- **Empresa del caso:** Vitalia Salud EPS — aseguradora privada de salud (organización ficticia)
- **Viene de:** `00_modelo_del_problema.md` — la ficha de la organización, el encuadre en tres
  niveles (mundo · Perú · cliente) y las cuatro fallas estructurales F1–F4. Este documento
  cuantifica el nivel 3.

> **Aviso.** Vitalia Salud EPS no existe. Planes, montos, plazos, códigos y clínicas provienen
> del corpus normativo que acompaña al proyecto. La volumetría y los costos de este documento
> son **supuestos declarados**, no datos reales; están calibrados para ser defendibles y su
> origen se indica en cada caso.

---

## 1. El proceso elegido

**Mesa de preautorización de procedimientos programados.**

No es la atención al asegurado por canales digitales. Es el proceso interno que
decide, para cada solicitud que llega de un prestador, si Vitalia autoriza el procedimiento,
lo observa por falta de sustento, lo aprueba parcialmente o lo rechaza — y con qué copago.

Se eligió este proceso, y no otro, porque **no tiene una sola respuesta técnica**: al
descomponerlo aparecen ocho sub-problemas cuya solución correcta es distinta entre sí, y en
dos de ellos la respuesta correcta es *no usar IA*. Esa heterogeneidad es la que permite
demostrar criterio de arquitectura en lugar de acumular tecnologías (ver `02_matriz_de_decision.md`).

### Qué exige preautorización (según la política vigente)

Hospitalizaciones programadas, cirugías electivas, procedimientos ambulatorios de alto costo
(TAC y RM en plan Esencial cuando superan S/ 900, estudios genéticos, medicina nuclear),
terapias de más de 12 sesiones, prótesis y órtesis, tratamientos oncológicos, atención
programada en el extranjero y cualquier atención en el Instituto Cardiovascular Andino.

**No** la exigen las consultas ambulatorias, los exámenes de laboratorio de rutina ni las
emergencias — aunque la emergencia que deriva en hospitalización se regulariza dentro de 48h.

### Por qué el proceso importa al negocio

La regla más estricta de la póliza es que el procedimiento programado hecho **sin** la
preautorización se rechaza con el código `AUT-100` y el gasto queda íntegramente a cargo del
afiliado, aun cuando estuviera cubierto. Es decir: si la mesa no responde a tiempo, el afiliado
no tiene una molestia — tiene un problema financiero, o posterga un procedimiento médico.

---

## 2. Actores

| Actor | Rol en el proceso | Qué le duele hoy |
|---|---|---|
| **Médico tratante / prestador** | Presenta la solicitud por el portal de prestadores con diagnóstico, código de procedimiento, fecha tentativa y clínica | Le observan la solicitud 24h después por un documento faltante; pierde el cupo de quirófano |
| **Afiliado** | Espera la respuesta; puede presentar la solicitud desde la app | No sabe en qué estado está; reprograma la cirugía |
| **Analista de autorizaciones** | Recibe, valida elegibilidad, consulta la política, emite la carta | Busca a mano en un manual que cambia; ante la duda, deriva |
| **Médico auditor** | Resuelve casos que requieren criterio clínico | Recibe casos que no necesitaban criterio clínico, solo lectura de la póliza |
| **Supervisor de mesa** | Distribuye carga, responde por el SLA | No tiene visibilidad de por qué se incumple el p95 |
| **Regulador (SUSALUD)** | Fiscaliza plazos y sustento de las negaciones | — (pero exige poder reconstruir por qué se negó) |

---

## 3. El flujo actual, paso a paso

```
Prestador                Mesa de autorizaciones                  Auditoría médica
    |                              |                                     |
 (1) Envía solicitud ------------> |
    |                        (2) Descarga adjuntos y transcribe
    |                        (3) Valida en el sistema central (core): vigencia, plan, deuda
    |                        (4) Calcula carencia (tabla, días calendario)
    |                        (5) Busca en el manual: cobertura,
    |                            exclusión, copago, ¿requiere junta?
    |                              |
    | <---- (6a) Observación ------|  (falta sustento)  [23% del volumen]
    |                              |
    |                              |---- (6b) Deriva ------------------> |
    |                              |    [21% del volumen]                |
    |                              | <--------------- Devuelve criterio --|
    |                              |
    | <---- (7) Carta: aprobación / parcial / rechazo, y carta de garantía a la clínica
```

Los pasos (3), (4) y (5) se hacen **en tres pantallas distintas y un PDF**, y su resultado se
copia a mano a la carta.

---

## 4. Volumetría y desempeño actual

> **Supuestos declarados.** Cartera de 165,000 afiliados vigentes (62% VIT-INT mayormente
> corporativo, 26% VIT-ESE, 12% VIT-PRE). Tasa de preautorización ≈ 0,57 solicitudes por
> afiliado al año. Equipo: 16 analistas en dos turnos, 4 médicos auditores, 1 supervisor.

**7,800 solicitudes/mes.** Composición:

| Tipo de solicitud | % del volumen | Complejidad |
|---|---|---|
| Imágenes de alto costo (TAC/RM/medicina nuclear) | 31% | Baja — muy repetitiva |
| Terapias de más de 12 sesiones | 22% | Baja |
| Cirugías electivas y hospitalización programada | 19% | Alta |
| Tratamientos oncológicos (por ciclo) | 11% | Alta |
| Prótesis y órtesis | 8% | Media |
| Regularizaciones post-emergencia (48h) | 5% | Alta, con reloj corto |
| Extranjero, genéticos, Instituto Cardiovascular Andino | 4% | Muy alta |

**Dato que ordena todo el diseño: el 71% del volumen se explica por 24 combinaciones
diagnóstico–procedimiento recurrentes.** La cola larga —el 29% restante— es la que
verdaderamente consume criterio.

### Tiempos

| Métrica | Valor actual | Meta contractual |
|---|---|---|
| Touch time por solicitud | 19 min (p50 14 · p95 52) | — |
| **Tiempo de respuesta (TAT)** — procedimientos programados | p50 2,1 días · **p95 6,8 días** | **5 días hábiles** ❌ |
| TAT — urgentes calificados | p50 26h · **p95 61h** | **48 horas** ❌ |
| TAT — atención en el extranjero | p50 9 días | 15 días hábiles ✅ |

> *TAT* (turnaround time) es el tiempo entre que la solicitud entra y se emite la respuesta.
> *p50* es la mitad de los casos; *p95* es el 95% peor — que es donde vive el incumplimiento.

Desglose del touch time — importa porque señala dónde está el dinero:

| Paso | Minutos | Naturaleza |
|---|---|---|
| Leer adjuntos y transcribir a la hoja de trabajo | 4 | Lectura no estructurada |
| Validar vigencia, plan, deuda, acumulado de deducible | 3 | Consulta a sistema |
| Calcular carencia | 2 | Aritmética de fechas |
| **Buscar en el manual: cobertura, exclusión, copago** | **7** | **Búsqueda en conocimiento propio** |
| Redactar y emitir la carta | 3 | Generación + registro |

El paso de 7 minutos es el 37% del esfuerzo y es, además, el que produce los dos desperdicios
más caros del proceso.

---

## 5. Puntos de dolor, cuantificados

**P1 · Observación tardía por sustento incompleto — 23% del volumen.**
1,794 solicitudes/mes se observan; el 64% se subsana y vuelve, generando un segundo toque
completo (1,148 retrabajos/mes). La política dice que las incompletas se observan *dentro de
las primeras 24 horas* y que el plazo se suspende: el prestador pierde un día entero por un
examen preoperatorio faltante que se pudo detectar al recibir.

**P2 · Derivación defensiva al auditor médico — 21% del volumen.**
1,638 derivaciones/mes. El supervisor estima que **el 55% no requería criterio clínico**: era
una exclusión o una carencia escrita en el manual que el analista no ubicó, o que ubicó pero no
quiso firmar solo. Son **900 derivaciones/mes de capacidad médica desperdiciada**, y además
alargan el TAT de los casos que sí necesitan al auditor.

**P3 · Error de copago o coaseguro en la carta emitida — 3,8%.**
296 cartas/mes con el copago mal aplicado, diferencia media S/ 210. La causa no es ignorancia:
es que el copago depende del plan, del tipo de atención, del nivel de la clínica, del acumulado
del año y del tope de gasto de bolsillo — cinco variables cruzadas a mano.

**P4 · Rechazos revertidos al reclamar — 1,4%.**
109 casos/mes. Cada uno es un expediente de reclamo, un procedimiento médico postergado y
exposición ante el regulador, que puede exigir el sustento de la negación.

**P5 · Conocimiento tácito y rotación.**
Tres analistas senior resuelven el 70% de los casos difíciles. Rotación anual 38%, curva de
aprendizaje 11 semanas. El proceso depende de personas, no de un activo de la empresa.

**P6 · Pico de lunes 2,4× el promedio.**
El incumplimiento del p95 no está repartido: se concentra en la cola que se forma los lunes.
Un problema de capacidad elástica, no de productividad media.

**P7 · La política cambia y nadie sabe qué se emitió con la versión anterior.**
El manual se actualiza unas 6 veces al año (endosos, nuevos códigos, cambios de red). Hoy el
analista se entera por correo. **No existe forma de saber qué cartas se emitieron bajo qué
versión de la política** — que es exactamente lo que un regulador pediría en una fiscalización.

---

## 6. Impacto económico del AS-IS

> Costo cargado: analista S/ 31/hora, médico auditor S/ 110/hora. Costo de gestión de un
> expediente de reclamo: S/ 340.

| Concepto | Cálculo | S/ mes |
|---|---|---|
| Operación de la mesa | 7,800 × 19 min × S/ 31/h | 76,600 |
| Retrabajo por observación (P1) | 1,148 × 19 min × S/ 31/h | 11,300 |
| Auditoría médica total (P2) | 1,638 × 16 min × S/ 110/h | 48,000 |
| — *de la cual, derivación defensiva* | *900 × 16 min × S/ 110/h* | *(26,400)* |
| Fuga por copago mal aplicado (P3) | 296 × S/ 210 | 62,200 |
| Gestión de reclamos por reversión (P4) | 109 × S/ 340 | 37,100 |
| **Total del proceso** | | **235,200** |
| | | **≈ S/ 2,82 M / año** |

**Costo no monetizado, pero real:** incumplimiento del p95 en el SLA contractual de 5 días,
riesgo regulatorio en las negaciones sin sustento reconstruible, y procedimientos médicos
postergados — que es el impacto que de verdad importa y que ninguna hoja de cálculo captura.

---

## 7. La pregunta que hay que responder antes de diseñar

> ¿Cuánto de estos S/ 2,82 M lo resuelve **software convencional bien hecho**, sin nada de IA?

Bastante. Integrar las tres pantallas en una sola, y automatizar la validación de elegibilidad
y el cálculo de carencia y copago —todo determinista— ya recorta buena parte de P3 y de los 5
minutos de los pasos (3) y (4).

Lo que **no** resuelve el software convencional es:
- leer un informe médico en PDF escaneado para saber si trae el riesgo anestésico (P1),
- decidir si un procedimiento cae bajo una exclusión redactada en prosa, con sus excepciones (P2),
- y sustentar la respuesta con la cita textual de la política vigente en esa fecha (P4, P7).

**Ahí, y solo ahí, empieza el caso de IA.** El diseño se construye sobre esa frontera, no sobre
la ambición de usar todas las tecnologías disponibles.

---

## 8. Supuestos a validar

1. Volumetría (7,800/mes) y composición por tipo de solicitud.
2. Costos cargados de analista y auditor, y el costo de gestión de un reclamo.
3. La concentración del 71% en 24 combinaciones recurrentes — es el supuesto del que depende
   el caso de negocio entero.
4. El 55% de derivación defensiva: es una estimación del supervisor, no una medición.
5. Que la política (el corpus) sea la fuente única y esté completa y vigente.

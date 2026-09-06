# Juego de planos del proyecto

- **Proyecto final** · DataPath · AI Solutions Architect
- **Caso:** Mesa de preautorización médica — Vitalia Salud EPS
- **Fecha:** 2026-09-05 · **Versión del juego:** 1.3 — *añade D-13 (modelo de datos) y D-14
  (secuencia end-to-end con presupuesto de latencia), que cierran los dos pendientes abiertos*
- *Revisión 1.2 (2026-09-05): añadió D-12 (estructura de costos) e incorporó la iconografía
  oficial de producto en D-06, D-07, D-11 y D-12*
- *Revisión 1.1 (2026-09-04): añadió D-10 (rediseño del proceso) y D-11 (arquitectura técnica
  cloud); D-04 se rehízo sobre el proceso rediseñado*
- **Alcance:** nivel de **diseño**. La implementación del MVP en Google Cloud y los anexos de
  evidencia son fase 2.

---

## Convención de dibujo

Todas las láminas comparten la misma normativa gráfica, tipo plano:

| Elemento | Regla |
|---|---|
| Formato | Lámina apaisada 1700 × 1150 px, con doble marco perimetral (excepto **D-11**, 2400 × 1500) |
| Rótulo superior | Franja azul con el nombre del diagrama |
| **Cajetín** (esquina inferior derecha) | Proyecto · Diagrama · Nivel · Código · Versión · Fecha |
| **Leyenda** (esquina inferior izquierda) | Código de colores + notas de lectura de la lámina |
| Geometría | Solo cajas y contenedores **rectangulares**. Sin rombos, sin óvalos, sin redondeos (excepción declarada: **D-11**, ver más abajo) |
| Conectores | Solo ortogonales (`orthogonalEdgeStyle`): tramos horizontales y verticales. **Ninguna diagonal** |
| Puntos de decisión | Se dibujan como caja rectangular con la pregunta, y dos flechas rotuladas `si` / `no` |

### Código de colores (constante en todo el juego)

| Color | Significado |
|---|---|
| Azul | Componente o capacidad **sin IA** — integración, motor de reglas, software convencional |
| Naranja | Componente o capacidad **con IA** — extracción, RAG, agente, modelos |
| Verde | Control humano (HITL), datos y salidas hacia el afiliado o el prestador |
| Rojo | Desperdicio, punto de dolor, guardrail, seguridad o restricción externa |
| Morado | Gobierno, trazabilidad, versionado y observabilidad |
| Gris | Contexto externo, regulatorio o infraestructura de soporte |
| Ámbar | Punto de decisión o compuerta |

Que el azul y el naranja se distingan a simple vista es deliberado: la tesis del proyecto es
que **la mayor parte de la solución no lleva IA**, y el juego de planos tiene que poder
demostrarlo sin leer una sola línea de texto.

---

## Las catorce láminas

| Código | Lámina | Nivel | Responde a | Fuente |
|---|---|---|---|---|
| **D-01** | Contexto de negocio y mapa de impacto | Conceptual — negocio | Qué empresa es, en qué proceso está el problema y quién depende de él | `00_modelo_del_problema.md` §1 |
| **D-02** | Proceso actual (AS-IS) | Lógico — proceso | Qué pasa hoy, con minutos por paso y los porcentajes de retrabajo y derivación | `00` §5.2 · `01_caso_y_as_is.md` §3–§6 |
| **D-03** | Matriz de decisión — qué lleva IA y qué no | Conceptual — arquitectura | Por qué cada sub-problema va por una ruta distinta, y por qué esto **no** es un agente | `02_matriz_de_decision.md` |
| **D-04** | Proceso objetivo (TO-BE) | Lógico — proceso | La máquina rediseñada: **tres carriles y cuatro estados**, con el guardrail, el HITL y la traza | `04_to_be.md` §3 |
| **D-05** | Blueprint de la solución — mapa de capacidades | Lógico — capacidades | Las seis capas de capacidad y cuáles de ellas requieren IA | `04_to_be.md` §4 |
| **D-06** | Arquitectura de solución IA — vista por capas (GCP) | Físico — despliegue | Los componentes reales por capa: ecosistema digital, canales, borde, integración, backend, modelos y datos | `04_to_be.md` §3 + stack del curso |
| **D-07** | Ingesta documental, corpus versionado y RAG | Físico — flujo de datos | Cómo entra un documento, cómo se procesa y cómo se recupera con cita | `04_to_be.md` §3 y §9 |
| **D-08** | Gobierno — guardrails, HITL y LLMOps | Lógico — control | Las 8 capas de guardrail, los patrones de control humano, el versionado y el ciclo de vida | `04_to_be.md` §1 y §9 |
| **D-09** | Roadmap de implementación, hitos y retorno por fase | Ejecutivo — plan | En qué orden se construye y cuándo se paga cada fase | `04_to_be.md` §7 · `05_caso_de_negocio.md` §5 |
| **D-10** | Rediseño del proceso — de ocho sub-procesos a cuatro estados | Lógico — proceso | Qué paso se **elimina**, cuál se **unifica**, cuál cambia de dueño, y qué capacidades aparecen que hoy no existen | `04a_rediseno_del_proceso.md` |
| **D-11** | Arquitectura técnica cloud — red, servicios y plano de IA | Físico — despliegue | En qué VPC y subred vive cada servicio, con qué identidad llama y por qué camino sale el tráfico | `04_to_be.md` §3 + stack del curso |
| **D-12** | Estructura de costos de la plataforma y efecto en el retorno | Económico — run y ROI | Cuánto cuesta cada servicio, qué parte de la factura es fija, cómo cae el costo unitario con el volumen y qué le pasa al payback | `05a_costeo_cloud.md` |
| **D-13** | Modelo de datos — propiedad, entidades, versionado y retención | Lógico — datos | De qué es dueña la plataforma y de qué no, las entidades del proceso, los invariantes escritos como restricciones y el ciclo de vida de una versión de política | `08_modelo_de_datos.md` |
| **D-14** | Secuencia end-to-end y presupuesto de latencia | Lógico — comportamiento | El recorrido T1–T11 del portal a la carta sellada, por carril de actor, con el objetivo p95 de cada tramo | `07_operacion_y_produccion.md` §2 y §4 |

---

## Las dos láminas nuevas (revisión 1.1)

### D-10 — el rediseño, no la automatización

Existe porque una revisión detectó un defecto real en la primera versión del TO-BE: conservaba
los ocho sub-procesos del AS-IS y les cambiaba el motor detrás. Eso es *pavimentar el camino de
la vaca* — automatizar el desperdicio en vez de quitarlo.

La lámina aplica **ESIA en el orden correcto —eliminar → unificar → reordenar → automatizar—**
y muestra el resultado paso por paso: tres sub-procesos desaparecen, tres se funden en el estado
único **E2 · adjudicación unificada de póliza**, uno se reduce, uno cambia de dueño. Debajo, la
banda de las cinco capacidades que hoy no existen (N1–N5) y el efecto medible:

| | AS-IS | Rediseñado |
|---|---:|---:|
| Sub-procesos / estados de negocio | 8 | **4** |
| Toques humanos por solicitud | 1.23 | **0.40** |
| Solicitudes que entran a la mesa | 7,800/mes | **≈6,400/mes** |
| El prestador conoce la respuesta | 2 a 7 días | **en el acto** |

La lámina también dibuja **lo que se evaluó y no se cambió** (el guardrail no se funde en E1, el
ruteo no se funde en la adjudicación, el agente no absorbe el ruteo, el HITL no se elimina), que
es la mitad honesta del ejercicio: sin ella, un rediseño solo parece un recorte.

### D-11 — la vista cloud, adicional a D-06

D-11 **no reemplaza a D-06, la complementa**. La diferencia es la pregunta que responde cada una:

- **D-06** responde *qué capacidad vive en cada capa del ecosistema* (canales, integración,
  backend, modelos, datos). Es la vista para el comité.
- **D-11** responde *en qué red, con qué identidad y por qué camino viaja cada llamada*. Es la
  vista para quien va a construirla.

Lo que aparece solo en D-11:

| | |
|---|---|
| **Red real** | VPC `vpc-vitalia` 10.20.0.0/16 con tres subredes: `snet-hibrida` (túnel al core), `snet-servicios` (Cloud Run con *direct VPC egress*), `snet-privada` (salida controlada) |
| **Borde separado de la VPC** | Cloud DNS → CDN → **Cloud Armor** → App LB → Identity Platform → API Gateway, encadenados en orden real de tránsito |
| **Endpoints privados** | **Private Service Connect** hacia Qdrant Cloud y Neon; **Private Google Access** hacia Vertex AI, GCS y Secret Manager |
| **Egreso controlado** | Todo lo que sale a terceros pasa por **Cloud NAT con IP fija**, declarada en la lista blanca de OpenAI, Groq y Acredita Salud. Ningún servicio tiene IP pública |
| **Los 12 servicios agrupados por plano** | A experiencia · B orquestación · C **plano de IA** · D determinista y control — y se ve a simple vista que el plano de IA son 3 de 12 |
| **Recorrido numerado ①–⑩** | Una solicitud, de extremo a extremo, con el número puesto sobre el componente que la atiende |
| **Decisiones de despliegue** | Ingress, service account por servicio, grant por secreto, residencia del dato, colección por versión en Qdrant, RPO/RTO |

**Excepción de convención declarada.** D-11 se aparta a propósito de la regla de *solo
rectángulos*: usa tarjetas con esquina redondeada, el icono oficial de cada producto y círculos
numerados. Es exactamente lo que se pidió — una vista cloud moderna, al estilo de las
arquitecturas de referencia de AWS y Azure. Los círculos son la única geometría no rectangular
del juego completo y no representan componentes: marcan el recorrido.

**Convención de insignia (*badge*).** Las doce tarjetas de servicio llevan el icono de **Cloud
Run**, porque las doce *son* Cloud Run. Lo que las distingue va como logo pequeño en la esquina
inferior derecha: dice qué corre **dentro** del contenedor (LangChain, LangGraph, Cloud
Workflows, Document AI) o con quién habla el endpoint (Qdrant, Neon, Groq). Así la lámina no
miente sobre qué es cada componente y aun así se ve el stack completo.

---

## La lámina de la revisión 1.2

### D-12 — la lámina económica

Es la única lámina del juego que no dibuja componentes ni pasos: dibuja **la factura**. Nace de
una pregunta directa —*¿está el costo de los servicios de GCP, la inversión y el ROI?*— cuya
respuesta honesta era que el caso de negocio tenía la inversión y el retorno, pero el cloud
aparecía en tres renglones agregados. `05a_costeo_cloud.md` costea servicio por servicio; D-12 es
su versión de una sola mirada.

Cinco bloques, y cada uno responde una pregunta distinta:

| Bloque | Pregunta | Qué muestra |
|---|---|---|
| **Franja de KPI** | ¿Cuánto y qué proporción? | S/ 6,700/mes · S/ 0.86 por solicitud · 75% fijo · 3.8% en tokens · 8% del costo unitario del proceso |
| **A · composición** | ¿Quién se lleva la plata? | 13 renglones ordenados de mayor a menor, con el logo del producto y la barra partida en fijo (azul) y variable (naranja) |
| **B · fijo vs. variable** | ¿Qué pasa si baja el volumen? | Una barra apilada única y las tres consecuencias de que tres cuartas partes de la factura no dependan del tráfico |
| **C · costo unitario vs. volumen** | ¿Escala bien? | El unitario cae de S/ 1.55 a S/ 0.34 entre 3,900 y 31,200 solicitudes/mes: la plataforma se paga mejor cuanto más se usa |
| **D · reconciliación + ROI** | ¿Se rompió el caso de negocio? | Presupuestado vs. costeado línea por línea, y el efecto en payback, VAN y TIR |
| **E · sensibilidad** | ¿Qué lo rompería? | Siete escenarios contra la línea de presupuesto, incluido **Cloud Armor Enterprise** — el único que se sale de rango, y por eso se descarta |

**Por qué las barras se colorean por naturaleza y no por familia de producto.** Sería más
vistoso pintar de un color lo de Google y de otro lo de terceros, pero eso no responde ninguna
pregunta de gestión. La partición **fijo / variable** sí: dice qué parte de la factura sobrevive
a un mes flojo, qué palancas existen (las instancias mínimas son S/ 640/mes de los S/ 880 de
Cloud Run) y por qué duplicar el volumen no duplica el costo. El logo, en la etiqueta, ya
identifica al proveedor sin gastar el color en ello.

Los dos hallazgos que la lámina hace visibles sin leer texto: **los tokens de LLM son el 3.8% de
la factura**, y el error del presupuesto no fue el monto sino el *reparto* — 3.4× de más en
inferencia y de menos en conectividad (VPN, PSC, NAT e instancias mínimas suman más que toda la
inferencia junta). Coherente con la disciplina del resto del juego, **el ahorro no se descuenta
del caso de negocio**: los S/ 2,000/mes de diferencia quedan como contingencia hasta que tres
meses de facturación etiquetada los confirmen.

---

## Las dos láminas nuevas (revisión 1.3)

Cierran los dos únicos pendientes que quedaban abiertos en la lista del final, y no por
completitud: son las dos láminas que sostienen los anexos **C** y **F**, que hasta la revisión
1.2 existían como texto sin plano.

### D-13 — el modelo de datos, empezando por lo que la plataforma *no* posee

La tentación al diagramar datos es dibujar todas las tablas. D-13 empieza al revés, con una
franja de cinco bloques que responde una pregunta anterior: **quién es dueño de qué**.

| Bloque | Es dueño de | Consecuencia de diseño |
|---|---|---|
| Core de Vitalia | Afiliado, póliza, deuda, acumulados | Se **consulta**, no se copia |
| Cloud Storage | Expedientes y corpus normativo firmado | Fuente de verdad documental, inmutable |
| Neon | El **proceso**: estados, adjudicación, citas, firma | RPO 5 min · < 50 GB a tres años |
| Qdrant | Nada — es un **artefacto derivado** | RPO 0: se reconstruye en 2 h por $0.10 |
| BigQuery | Hechos de operación, calidad y costo | Sin PII: el afiliado viaja hasheado |

Esa primera franja es la que evita el error más caro del modelo: replicar el maestro de
afiliados. **Una copia desactualizada de la vigencia reproduce exactamente la fuga de copago P3
que el proyecto viene a eliminar** — se pagaría el ahorro con el problema.

**Por qué los invariantes aparecen como restricciones y no como reglas de negocio.** El bloque 4
no lista políticas: lista `CHECK` y `UNIQUE`. R3 —ninguna negación por necesidad médica sin firma
de médico colegiado— está escrito como `CHECK (tipo <> 'niega_necesidad_medica' OR firma_id IS NOT
NULL)` sobre la tabla `carta`. Un invariante regulatorio no puede depender de que el código lo
respete; tiene que ser **imposible de violar aunque alguien escriba directamente en la base**.

La columna derecha dibuja el ciclo de vida de una versión de política, de siete pasos, del PDF
firmado al alias `politica_actual`. Ahí se ve por qué el corpus se segmenta **por cláusula** y no
por ventana fija de tokens, y por qué cada endoso crea una **colección nueva** en vez de un filtro:
un filtro olvidado una sola vez cita política derogada; una colección equivocada no existe.

### D-14 — la secuencia, y el presupuesto de latencia que la ordena

Siete carriles de actor —canal, frontera, orquestación, guardrails, modelos e índice, sistemas de
registro y humano— y once tramos **T1–T11**, del expediente adjuntado en el portal a la carta
sellada notificada al prestador. Es la lámina que faltaba para defender los SLOs: hasta ahora el
p95 existía como número, no como recorrido.

Lo que la banda inferior hace explícito es que **el presupuesto de 90 segundos del SLO J3 no se
reparte a partes iguales**:

| Tramo | Presupuesto p95 | Por qué |
|---|---:|---|
| Guardrail de entrada | 8 s | Ocho capas, de barata a cara; la primera que bloquea corta |
| Extracción (Document AI + E1) | 25 s | Es donde pesa el documento, no el modelo |
| Adjudicación determinista | 6 s | Depende del core, no de inferencia |
| **Adjudicación interpretativa** | **30 s** | Un tercio del total: es el único tramo que genera prosa que luego hay que verificar |
| Emisión sellada | 5 s | Escritura idempotente contra el core |
| Holgura | 16 s | No se reparte: absorbe la cola |

Y el corolario operativo: **si un tramo agota su timeout no se reintenta indefinidamente**, se
baja de nivel de automatización (N0–N5) y el caso cae al carril manual. Toda derivación sale en
T10 y termina en el mismo lugar —la mesa—, que en este diseño no desaparece. La fila HUMANO
existe por una razón estructural: ninguna transición del carril automático puede emitir una
negación por necesidad médica; esa flecha solo existe pasando por ahí.

---

## Iconografía

Cinco láminas (**D-06**, **D-07**, **D-11**, **D-12** y **D-13**) llevan la iconografía oficial
de cada producto, no un chip de color con iniciales. En las tres primeras el icono identifica el
componente; en **D-12** identifica el renglón de la factura y en **D-13**, el almacén dueño del
dato y el paso del pipeline de indexación.

| | |
|---|---|
| **De dónde salen** | `_descargar_iconos.py` los baja de la API de [Iconify](https://api.iconify.design) a `iconos/*.svg` — 54 iconos, con lista de sustitutos por si un id no resuelve |
| **Google Cloud** | colección `gcp` — *Google Cloud Icons*, autoría de Google Cloud, **Apache-2.0**, 214 iconos a color: el icono por servicio (Cloud Run, Vertex AI, Document AI, Cloud Armor, Pub/Sub, BigQuery, Secret Manager, PSC, Cloud NAT…) |
| **Terceros** | *SVG Logos* de Gil Barbara (**CC0-1.0**) para **Qdrant**, **Neon**, **OpenAI**, PostgreSQL y Looker; logotipos a color para **Groq**, **LangChain**, **LangGraph** y **LangSmith** |
| **Personas e infra propia** | *Material Design Icons* (**Apache-2.0**), coloreados con la paleta de Google: médico, afiliado, analista, auditor, core on-premise, directorio, firewall on-premise, SUSALUD |
| **Cómo se empotran** | base64 dentro del `style` de la celda (`shape=image;…;image=data:image/svg+xml,<B64>`). El alfabeto base64 no contiene `;` ni `"`, así que es seguro dentro del *style* y dentro del atributo XML |

Consecuencia práctica: **los `.drawio` son autocontenidos**. Se ven igual en draw.io web, en la
app de escritorio y en la extensión de VS Code, y **funcionan sin internet**. Ese era justo el
problema de usar los *stencils* `mxgraph.gcp2.*`: si el nombre de la forma no existe, draw.io
degrada en silencio a un rectángulo plano y queda media lámina con icono y media sin él.

En **D-06** y **D-07** el icono no reemplaza la caja: `marca()` lo estampa 20×20 en la esquina
inferior derecha del rectángulo existente. La convención de plano — *solo cajas rectangulares,
flechas ortogonales* — sigue intacta, y aun así se lee de un vistazo qué producto es cada caja.

El generador se autodiagnostica: al terminar imprime `iconos empotrados: N` y, si algún icono
falta en disco, nombra cuáles degradaron a chip y recuerda ejecutar `_descargar_iconos.py`.

---

## Lo que resuelve la lámina de arquitectura (D-06)

La lámina está organizada en **bloques tipo ecosistema**, en el orden que pidió el encargo:

```
ECOSISTEMA DIGITAL   ->  quién usa el sistema (6 perfiles, incluido el rol nuevo)
CANALES              ->  portal de prestadores, app del afiliado, consola de la mesa,
                         bandeja del auditor, tablero ejecutivo
BORDE Y SEGURIDAD    ->  Cloud Load Balancing, Cloud Armor, Identity Platform, API Gateway
INTEGRACION Y APIs   ->  API interna, Acredita Salud (SUSALUD), core on-premise, notificaciones
BACKEND              ->  10 servicios en Cloud Run (contenedores)
MODELOS DE IA        ->  Vertex AI Gemini, Document AI, OpenAI embeddings, Ranking, Model Armor
DATOS                ->  Qdrant, Neon PostgreSQL, Cloud Storage, BigQuery, Secret Manager
```

Con una **columna vertical de gobierno** a la derecha (LangSmith/LangFuse, Cloud Monitoring,
RAGAS, Cloud Build/Deploy con canary, registro de versiones de política y el gate de firma
médica) que atraviesa todas las capas.

### Decisiones de stack que la lámina deja explícitas

| Pregunta del encargo | Respuesta en el plano |
|---|---|
| **¿En qué contenedores?** | Diez servicios **Cloud Run**, uno por responsabilidad del flujo E0–E9: `svc-intake`, `svc-guardrails`, `svc-extraction`, `svc-eligibility`, `svc-rules`, `svc-rag`, `svc-decision`, `svc-agent`, `svc-issuance` y el bus asíncrono |
| **¿Base vectorial?** | **Sí — Qdrant**, con una colección por versión de política (`politica_vN`). No se sobrescribe al cambiar la norma: es lo que permite reconstruir una carta emitida meses antes |
| **¿LangChain?** | **Sí, pero acotado.** LangChain solo en `svc-rag` (recuperación híbrida y citación) y **LangGraph** solo en `svc-agent` (subsanación). El resto del flujo es una máquina de estados explícita, no una cadena |
| **¿Cloud Armor?** | **Sí**, en la capa de borde junto al Load Balancer: WAF, anti-DDoS, rate limiting y reglas OWASP. Primera línea antes de que la solicitud llegue al guardrail de 8 capas |
| **¿OpenAI?** | Solo para **embeddings** (`text-embedding-3-large`). La generación es **Vertex AI — Gemini** |
| **¿Neon?** | Sí, como PostgreSQL gestionado: expedientes, campos extraídos, decisiones y catálogos CIE-10 |
| **¿Qué se queda fuera de GCP?** | El sistema central del asegurador permanece on-premise; se alcanza por **Cloud VPN + Private Service Connect** |

### Ingesta → procesamiento → interacción

El recorrido que pidió el encargo se lee entre dos láminas:

- **D-07** muestra las tres tuberías: ingesta del **corpus normativo** (lote, ~6 veces al año),
  ingesta del **expediente** (tiempo real, 7,800/mes) y **recuperación con cita** en el momento
  de decidir. Las tres convergen en el repositorio compartido y salen como *decisión sellada*.
- **D-06** muestra dónde vive cada pieza de esas tuberías dentro de la plataforma.

---

## Cómo usarlas

### Abrir y editar

Los archivos son XML de draw.io sin comprimir. Se abren en:

- [app.diagrams.net](https://app.diagrams.net) → *File · Open from · Device*
- La extensión **Draw.io Integration** de VS Code (doble clic sobre el `.drawio`)
- La app de escritorio de draw.io

`00_TODOS_los_diagramas.drawio` contiene las catorce láminas como páginas de un solo archivo,
que es lo cómodo para revisar; los archivos individuales son lo cómodo para exportar.

### Exportar para las láminas del informe

En draw.io: *File · Export as · PNG* con **Zoom 200%**, *Border width 0* y **Selection Only
desmarcado**. Para el informe impreso, *Export as · PDF* respeta mejor el cajetín.

### Regenerar

Si cambia un número del caso, se edita `_generar_diagramas.py` y se ejecuta:

```powershell
cd Modulo05\Sesion10\Proyecto\diagramas
python _descargar_iconos.py      # solo si falta la carpeta iconos\ o se añadió un icono nuevo
python _generar_diagramas.py
```

El script reescribe las catorce láminas y el consolidado. Los estilos, colores, marco y cajetín
están centralizados arriba del archivo, de modo que un cambio de convención se aplica a todo el
juego de una sola vez.

`iconos\*.svg` se puede borrar y volver a bajar en cualquier momento: es un artefacto derivado,
no una fuente. Lo que hay que conservar son los dos `.py`.

---

## Mapa lámina → estructura del informe

| Lámina del informe | Diagrama |
|---|---|
| Contexto y organización | **D-01** |
| El problema y su impacto | **D-01** + **D-02** |
| Situación actual cuantificada | **D-02** |
| Criterio de decisión tecnológica | **D-03** |
| **Rediseño del proceso** (slide 3b) | **D-10** |
| Propuesta / proceso objetivo | **D-04** |
| Blueprint de la solución | **D-05** |
| Arquitectura de solución — vista ejecutiva por capas | **D-06** |
| **Arquitectura técnica — vista cloud y de red** | **D-11** |
| Flujo de datos y RAG | **D-07** |
| Seguridad, gobierno y operación | **D-08** |
| Plan y caso de negocio | **D-09** + tablas de `05_caso_de_negocio.md` |
| **Economía de la plataforma** (slide 8b) | **D-12** + `05a_costeo_cloud.md` (Anexo A) |
| **Modelo de datos y metadata** (Anexo C) | **D-13** + `08_modelo_de_datos.md` |
| **Secuencia, SLOs y latencia** (Anexo F) | **D-14** + `07_operacion_y_produccion.md` |

---

## Pendientes conocidos de este juego

1. ~~**D-06 es una vista lógica de despliegue, no un diagrama de red.**~~ **Cerrado por D-11**,
   que añade VPC, tres subredes con rango, reglas de firewall, endpoints privados (PSC / PGA) y
   egreso por Cloud NAT con IP fija. D-06 se mantiene tal cual: sigue siendo la vista ejecutiva.
2. ~~**No hay diagrama de secuencia.**~~ **Cerrado por D-14**: siete carriles de actor, once
   tramos T1–T11 del portal a la carta sellada y el presupuesto de latencia p95 repartido
   (8 · 25 · 6 · 30 · 5 segundos, más 16 de holgura sobre los 90 del SLO J3).
3. ~~**El modelo de datos** (entidades de `Neon`) todavía no está diagramado.~~ **Cerrado por
   D-13**, que además dibuja lo que ninguna otra lámina decía: de qué **no** es dueña la
   plataforma. Queda pendiente menor la vista física de particionado en BigQuery.

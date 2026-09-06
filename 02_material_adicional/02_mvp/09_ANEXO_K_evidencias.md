# Anexo K · Evidencias del MVP

**Vitalia Salud EPS · mesa de preautorización de procedimientos programados**
**Proyecto final · DataPath · AI Solutions Architect · cohorte 2026-08**
**Autor:** Jonatan Sánchez · **Fecha:** 2026-09-06 · **Política vigente:** `v2026_09`

> Este anexo **se suma** al paquete de la fase 1. No modifica ni una línea de los anexos A–J: el
> diseño comprometido allí sigue siendo el mismo, y aquí se enseña funcionando la rebanada que el
> MVP implementa.

---

## K.0 · Qué se pidió y qué se entrega

La fase 2 pide dos cosas, y se responden por separado:

| | Lo pedido | Lo entregado | Dónde mirarlo |
|---|---|---|---|
| **(a)** | **La interfaz final** | Una aplicación web real servida por el mismo proceso que la API, con las cinco pantallas del diseño | §K.2 — siete capturas |
| **(b)** | **Los servicios principales de cada sesión del curso** | Un mapa de una fila por sesión, con el punto exacto del MVP donde se ve cada servicio y el archivo de evidencia que lo prueba | §K.1 — diez filas |
| **(b')** | *—lo que hacía falta para que (b) fuera comprobable—* | Las consolas de los cinco proveedores retratadas: Qdrant, Neon, GCP (Cloud Run, Cloud Build, Cloud Storage, Secret Manager, Model Armor) y Groq | §K.2.2 — catorce capturas |

El riesgo evidente de esta fase era construir un chatbot RAG bonito que demostrase dos sesiones de
diez. Por eso el orden de trabajo fue el inverso al habitual: **primero el mapa de evidencias,
después el código**. Si una sesión no tenía fila en el mapa, no estaba demostrada.

**La rebanada:** el **Carril 0** (consulta anticipada N1) completo, y el **Carril 1** de extremo a
extremo —guardrail → E1 extracción → E2 adjudicación → E3 ruteo → E4 emisión— limitado a tres de
las 24 combinaciones del núcleo, elegidas porque cubren los tres desenlaces que el diseño promete:
autorización automática, subsanación y escalamiento a la mesa.

**Cifras de cabecera del MVP corriendo:** 7,524 líneas de Python en 8 paquetes · 112 fragmentos de
política ingestados desde 11 documentos · 7 suites de prueba ejecutables · 15 archivos de
evidencia · **21 capturas** —7 de la interfaz y 14 de las consolas de los proveedores— ·
**21 defectos encontrados y corregidos**, cada uno con su explicación escrita.

---

## K.1 · El mapa: una fila por sesión

| Sesión | Servicio que se demuestra | Dónde vive en el MVP | Evidencia | Estado |
|---|---|---|---|---|
| **S01** · Patrones y selección de modelos | Enrutamiento por complejidad: la tarea elige el modelo, no al revés | `comun/router_modelos.py` | `E01_E02_router_y_cache.json` → `ruta_elegida` | ✅ |
| **S02** · AI FinOps | **Caché semántico** con clave determinista, ruteo barato/caro y **costo por span** | `comun/cache_semantico.py` + pantalla 5 | `E01_E02_router_y_cache.json`, `P5_panel.png` | ✅ |
| **S03** · Model serving en Kubernetes | `kind` + Helm + Ollama como motor de degradación **N3** | — | — | ⬜ diseñado, no montado |
| **S04** · Data pipelines y document processing | Ingesta: 11 docs → segmentación **por cláusula** → `sha256` + versión → publicación por **alias** | `ingesta/pipeline_politica.py` | `E04_ingesta_v2026_09.json` | ✅ |
| **S05** · Vector databases y semantic search | Qdrant Cloud, HNSW, recuperación con `texto_literal` en el payload | `comun/recuperacion.py` | `E13_hallazgos_del_mcp.md` §1–§2 | 🟡 parcial — falta el contraste denso vs. híbrido |
| **S06** · RAG avanzado y evals | RAG con **cita textual verificada**; guardrail de salida O1–O6 sobre cada respuesta | `flujo/consulta_n1.py`, `guardrails/salida.py` | `E03_carril1_e1_a_e4.json`, `E11_servicio_y_mesa.json` | 🟡 parcial — falta RAGAS |
| **S07** · Agentes y orquestación | El **único agente del diseño**: subsanación. **Servidor MCP propio** con catálogo cerrado de 4 tools | `mcp_vitalia/` | `E13_mcp_skills_y_ganchos.json`, `E13_conexion_cliente_mcp.md` | ✅ |
| **S08** · Skills, Hooks y production-grade | Skills **versionadas** y **seis ganchos** como middleware: solo-lectura, idempotencia, PII, traza | `mcp_vitalia/ganchos.py`, `mcp_vitalia/skills/` | `E13_mcp_skills_y_ganchos.json` (12 casos, 0 fallos) | ✅ |
| **S09** · Guardrails y red teaming | **Guardrail de entrada de 8 capas** (Groq en 7–8, Presidio local en 5) + guardrail de salida **O1–O6**, y el motor gestionado **Model Armor** de GCP medido contra ellas | `guardrails/entrada.py`, `guardrails/salida.py`, `guardrails/model_armor.py` | `E09_red_team_guardrail.json` — **16/16**, 0 falsos positivos · `E16_model_armor_vs_capas_propias.json` — el gestionado, **11/16** | ✅ |
| **S10** · LLMOps y observabilidad | Costo por span persistido, latencias p50/p95, feedback loop y sello de versión de política | `metrica_costo` en Neon + pantalla 5 | `E11_servicio_y_mesa.json` → `panel`, `P5_panel.png` | 🟡 parcial — falta LangSmith y la medición de SLOs bajo carga |

**Siete sesiones cerradas, tres parciales, una pendiente.** Lo parcial y lo pendiente está dicho
en §K.6 con nombre y apellido: un anexo que declara diez de diez cuando son siete de diez no es un
anexo, es una lámina de ventas.

---

## K.2 · La interfaz final: siete capturas, siete URLs

Las imágenes están en `fase2/evidencias/pantallas/`, con `INDICE.json` al lado. **Cada captura es
una URL**: la interfaz enruta por *hash*, así que cualquiera reabre exactamente la misma pantalla
sin reproducir una secuencia de clics que nadie anotó. Eso es el **veto V2** aplicado a la
evidencia: *una captura que no se puede rehacer no es evidencia.*

| # | Archivo | Ruta | Qué hay que mirar |
|---|---|---|---|
| 1 | `P1_ingreso.png` | `#/ingreso` | La pantalla de entrada. **La autenticación es del borde, no de la aplicación** (ADR-15); en el MVP es de demostración |
| 2 | `P2_consulta_n1.png` | `#/n1/<pregunta>` | El Carril 0: respuesta **`desde caché`**, `US$ 0.000000`, coseno 1.0000, y la cita `carencias_y_preexistencias-v2026_09-c03` verificada contra el corpus |
| 3 | `P3_bandeja.png` | `#/bandeja` | Cuatro expedientes, su ruta (automática · subsanación · mesa · mesa), su estado y el reloj del SLA **calculado en la base**: un solo reloj para todos los analistas |
| 4a | `P4a_expediente_pendiente.png` | `#/expediente/SOL-450ee590fdef` | **La pantalla de la defensa.** Cesárea con 220 días de 300 de carencia: el sistema redactó la negación, la dejó en `hitl` y **no la emitió** |
| 4b | `P4b_expediente_emitido.png` | `#/expediente/SOL-689ce3eab0e9` | El ciclo cerrado: carta `autoriza`, folio del core, copago S/ 1,210.00 y bitácora completa `recibida → … → emitida` |
| 4c | `P4c_expediente_subsanacion.png` | `#/expediente/SOL-13f58ae117e3` | El único agente: pide el informe que falta en vez de rechazar por falta de papeles |
| 5 | `P5_panel.png` | `#/panel` | Costo por solicitud, hit-rate del caché, p50/p95 por span, ruteo, guardrail, feedback y versión de política vigente |

> Los identificadores `SOL-…` cambian en cada repoblado. `demo/capturar.py` **no lleva ninguno
> escrito**: los resuelve de la bandeja viva buscando por *estado*, porque una lista fija convierte
> la captura en algo que solo funciona el día que se escribió.

### K.2.1 · Por qué la pantalla 4 es la que hay que enseñar

La pantalla del expediente pone en la misma página, y en dos columnas contiguas, las dos naturalezas
que el diseño se negó a mezclar:

| Columna izquierda — **lo determinista** | Columna derecha — **lo interpretativo** |
|---|---|
| Etiquetas `sin modelo` · `reproducible` · `R1` | Etiqueta `gpt-4o-mini` · *«propone, no dispone»* |
| Elegibilidad, carencia (`220 días de 300 exigidos`), cobertura y copago con su desglose | Campos extraídos con su confianza **y su contraste contra catálogo** |
| Nota al pie: *«Esta columna no pasó por ningún modelo. La fila de `metrica_costo` del tramo `adjudicacion` vale **US$ 0.000000**, y esa fila en cero es la prueba —no un hueco en los datos»* | Nota al pie: *«La confianza que declara el modelo **no decide nada**: se guarda para la traza. Lo que decide es la columna «contraste», que es una consulta al catálogo»* |

**R1 no se afirma: se lee en el dato.** `extraccion.modelo = 'gpt-4o-mini'` frente a
`adjudicacion.modelo = NULL, determinista = true`, y el costo del tramo de adjudicación en cero.
Quien audite no tiene que creerle a la documentación.

Debajo, en la misma página: las cláusulas que sostienen la decisión con su `chunk_id` y la etiqueta
**verificada literal**; los **seis controles O1–O6** con lo que verificó cada uno y su resultado;
el borrador de carta marcado *«todavía no es de nadie»* con los dos botones —*Emitir sin cambios* /
*Emitir con mis correcciones*— y la advertencia de que **editar el texto no salta el guardrail**; y
la bitácora *append-only* con cada transición, su actor y su motivo.

### K.2.2 · La configuración técnica: catorce consolas de los proveedores

Las siete capturas de arriba enseñan lo que hace el sistema. Estas catorce enseñan **dónde corre y
con qué está configurado**, y están en `fase2/evidencias/consolas/` con su propio `INDICE.json`.
No repiten a las anteriores: las contrastan contra algo que no escribimos nosotros.

| # | Archivo | Consola | Qué prueba |
|---|---|---|---|
| C01 | `C01_qdrant_coleccion_politica.png` | Qdrant Cloud | `vitalia_politica_v2026_09`: **112 puntos**, `size 3072`, Cosine, HNSW `m=16 / ef_construct=100`, `status green`, y el bloque **Aliases con `politica_actual`** — el ADR-21 visible |
| C02 | `C02_qdrant_cache_semantico.png` | Qdrant Cloud | `vitalia_cache_semantico` abierto en un punto real: la **clave determinista** `v2026_09\|todos\|salud_mental\|carencia`, las `citas` guardadas junto a la respuesta y el `version_id` que invalida solo |
| C03 | `C03_neon_adjudicacion.png` | Neon | **La tabla que prueba R1**: `determinista = true`, `modelo = NULL`, la carencia guardada y no recalculada, el copago con su desglose |
| C04 | `C04_neon_politica_version.png` | Neon | `v2026_09` con su `sha256`, vigencia, `aprobado_por` y `fragmentos = 112` — la fila apunta a la colección de C01 |
| C05 | `C05_neon_borrador_carta.png` | Neon | Tres borradores `aprobada_guardrail = true` frente a **una sola carta emitida**: el ADR-10 leído en el dato |
| C06 | `C06_neon_metrica_costo.png` | Neon | 30 filas span a span; las de `adjudicacion` con proveedor `ninguno`, `modelo NULL` y 0 tokens. **Una fila en cero es la prueba; un tramo ausente sería un hueco** |
| C07 | `C07_cloud_run_revision_y_variables.png` | Cloud Run | Revisión `vitalia-mesa-00001-srk` y **14 variables de entorno**, cinco de ellas como `Secreto: …:latest`. También `QDRANT_COLLECTION_ALIAS=politica_actual` y los dos modelos del guardrail |
| C08 | `C08_cloud_run_observabilidad.png` | Cloud Run | Latencias p50/p95/p99 e instancias facturables: la capa exterior de la observabilidad, **que no sustituye** a `metrica_costo` |
| C09 | `C09_cloud_build_historial.png` | Cloud Build | La compilación `1a3e7826` del 5/9/26, 1 min 32 s: **la imagen no se construyó en esta máquina** |
| C10 | `C10_cloud_storage_cloudbuild.png` | Cloud Storage | El bucket `datapath-labs-202608_cloudbuild`, que cierra la cadena contexto → build → Artifact Registry → revisión |
| C11 | `C11_secret_manager_secretos.png` | Secret Manager | Los cinco secretos `vitalia-*`, **por nombre**. `QDRANT_URL` también es secreto, no configuración |
| C12 | `C12_model_armor_plantilla.png` | Seguridad · Model Armor | La plantilla `vitalia-preauth` existe, con recurso, ubicación `us-central1`, residencia de datos *Aplicada* y fecha |
| C13 | `C13_model_armor_detecciones.png` | Seguridad · Model Armor | Los umbrales exactos contra los que se midió E16 — y al pie, **Configuración de registros: Inhabilitado**, dicho en vez de supuesto |
| C14 | `C14_groq_consumo.png` | Groq | **US$ 0.06** de gasto en septiembre, con `gpt-oss-safeguard-20b` como principal contribuyente: la contrapartida del proveedor a las cifras de C06 |

> **Ninguna de las catorce muestra el valor de una clave.** Secret Manager enseña nombres; Cloud Run,
> referencias montadas. Ni la URL del clúster de Qdrant ni la cadena de conexión de Neon aparecen en
> ninguna imagen. Era una condición para que la captura pudiera viajar dentro del entregable, y está
> escrita en `consolas/INDICE.json` bajo `regla_de_seguridad`.

**Dónde se llega a Model Armor en la consola:** *Seguridad → Model Armor*, dentro de Security
Command Center. No está en la sección de IA, y por eso cuesta encontrarlo. Además el servicio es
**regional**: `gcloud model-armor …` pega al endpoint global y devuelve `PERMISSION_DENIED` aun
siendo *owner* con la API habilitada. Hay que usar `modelarmor.us-central1.rep.googleapis.com`.

---

## K.3 · Los invariantes, vistos funcionando

No es una lista de intenciones: cada fila apunta a un archivo donde se puede comprobar.

| Invariante | Cómo se demuestra | Dónde |
|---|---|---|
| **R1** · Lo determinista nunca pasa por un modelo | El tramo `adjudicacion` de `metrica_costo` tiene `modelo = NULL`, 0 tokens y **US$ 0.000000** en las cuatro solicitudes | `E02_motor_determinista.json`, `P4a/P4b/P4c` |
| **R2** · Ninguna afirmación sobre política sin cita textual de la versión vigente | O1 exige **al menos una** cita y la compara carácter por carácter; O2 comprueba la vigencia. En el Carril 0 el control `sin_cita` sustituye la respuesta sin cita por la frase SIN_CLÁUSULA | `E03`, `E11`, `E00` §3 |
| **R3** · Ninguna negación por necesidad médica sin firma de médico colegiado | Es una **restricción de base de datos**, no una validación de aplicación: `CHECK (tipo <> 'niega_necesidad_medica' OR firma_id IS NOT NULL)` | `sql/01_esquema.sql` |
| **V1** · Asimetría del error | El caché **no lee ni escribe** cuando no puede clasificar la pregunta: prefiere no responder a responder de otra cobertura | `E00` §1 |
| **V2** · Reconstruibilidad | Tres comandos rehacen el estado entero y las siete capturas desde una base vacía | `codigo/demo/`, §K.5 |
| **V3** · Economía | El guardrail de entrada **cortocircuita** en la primera capa que bloquea: no se paga Groq si una regex ya decidió. Y las 4 entradas legítimas del red team dan 0 falsos positivos | `E09_red_team_guardrail.json` |
| **ADR-10** · El sistema nunca niega solo | La cesárea de `P4a`: borrador escrito, guardrail aprobado, **estado `hitl`**. Y en la superficie MCP no existe herramienta que emita, niegue o cambie estado — no está restringida, **no está escrita** | `P4a`, `E13_conexion_cliente_mcp.md` §2 |
| **ADR-21** · Acceso por alias | La aplicación lee `politica_actual` y nunca el nombre de la colección. Publicar una versión es mover el alias | `E04`, `P5_panel.png` |

---

## K.4 · Inventario de evidencias

Quince archivos en `fase2/evidencias/`, más las siete capturas.

### Las corridas

| Archivo | Sesión | Titular |
|---|---|---|
| `E01_E02_router_y_cache.json` | S01 · S02 | Router: Groq / `openai/gpt-oss-20b` para N1 — *«J1 exige p95 < 2 s: manda la latencia, no la capacidad»*. Caché: **40% de aciertos**, **40% de ahorro**, 10 citas verificadas, **0 falsos aciertos** |
| `E02_motor_determinista.json` | — | Los tres casos de la rebanada resueltos sin modelo. Campo `invariante`: *«R1 · ningún modelo de lenguaje participa de estas cifras»* |
| `E03_carril1_e1_a_e4.json` | S06 · S08 | E1→E2→E3→E4 completo: 10 fundamentos resueltos y **0 sin resolver**, 14 eventos de estado, 11 cartas forzadas contra el guardrail, idempotencia OK, **0 fallos**. US$ 0.01865 · **S/ 0.0233 por solicitud** |
| `E04_ingesta_v2026_09.json` | S04 | 11 documentos → **112 fragmentos** · `text-embedding-3-large` 3,072 dims · `sha256` del corpus · alias publicado · 10.0 s |
| `E09_red_team_guardrail.json` | S09 | **16 ataques R01–R16, 16 detectados (100%)**; 4 entradas legítimas, **0 falsos positivos**; p_max 2,622 ms |
| `E11_servicio_y_mesa.json` | S10 | Las seis escenas de la mesa (A, A2, B, C, D, E, F) con **0 fallos**, más el volcado del panel |
| `E13_mcp_skills_y_ganchos.json` | S07 · S08 | 12 casos sobre 4 skills, 6 ganchos y los disyuntores. **0 fallos** |
| `E14_bandeja_de_la_demo.json` | — | El estado exacto que retratan las capturas: 5 expedientes, 7 consultas, resumen por estado |
| `E16_model_armor_vs_capas_propias.json` | S09 | Los **mismos** 20 casos del red team por tres motores. Propio **16/16**, gestionado (**Model Armor**) **11/16**, mixto **16/16**; 0 falsos positivos en los tres. Las once detecciones del gestionado salieron **todas** de `pi_and_jailbreak`: `rai`, `malicious_uris` y `sdp` no marcaron ni un caso |
| `E15_despliegue_cloud_run.json` | — | La etapa B: el servicio corriendo en **Cloud Run** con la imagen de Artifact Registry y las claves en **Secret Manager**. `/salud` ok en 1,171 ms y una consulta N1 resuelta **desde caché con 2 citas verificadas** en 2,473 ms, desde un contenedor que **no tiene `variables.sh`** |

### Los hallazgos — **21 defectos, cada uno con su porqué**

| Archivo | Nº | Los que más enseñan |
|---|---|---|
| `E00_hallazgos_carril0.md` | 5 | **El caché semántico no puede decidir por similitud**: las reformulaciones legítimas miden 0.598–0.787 y una pregunta de *otra cobertura* mide 0.780 — las bandas se solapan, ningún umbral es seguro solo |
| `E01_hallazgos_carril1.md` | 6 | **«Las 0 citas coinciden carácter por carácter»**: O1 se cumplía por vacuidad. Y **un encabezado no es una norma** |
| `E12_hallazgos_de_la_interfaz.md` | 3 | **El carril que lleva el 41% del volumen no aparecía en la cuenta**: el panel medía solo el Carril 1 |
| `E13_hallazgos_del_mcp.md` | 7 | **Un gancho que confía en la skill no es un control**. Y el `SET search_path` que sobrevive a la sesión lógica pero no al pooler |

### Las hojas de método

| Archivo | Qué explica |
|---|---|
| `E13_conexion_cliente_mcp.md` | Cómo se conecta el servidor MCP a un cliente real, con la transcripción JSON-RPC y por qué el bloque `env` va vacío |
| `pantallas/INDICE.json` | Fecha, URL base, versión de política, expedientes resueltos y la URL exacta de cada captura |
| `consolas/INDICE.json` | Las catorce capturas de consola con su proveedor, el objeto retratado, la sesión del curso a la que responden y **qué prueba cada una** — más la regla de seguridad bajo la que se tomaron |

### Las láminas y el álbum

| Archivo | Qué es |
|---|---|
| `fase2/presentacion/Vitalia_anexo_K.html` | Cinco láminas para la defensa: portada, el mapa de §K.1 sesión por sesión, el mosaico de la interfaz, la pantalla 4a a doble página y los invariantes de §K.3. Se navega con ← → y se imprime con Ctrl/Cmd+P |
| `fase2/presentacion/Vitalia_anexo_K.pdf` | Las mismas cinco láminas en PDF, 33.87 × 19.05 cm, el mismo formato que la presentación de la fase 1 |
| `fase2/presentacion/Vitalia_anexo_K_capturas.html` | **El álbum**: 29 páginas A4 verticales, una por captura, con la imagen a tamaño completo y encima —no debajo— qué hay que mirar en ella. Parte 1, las siete pantallas (las tres del expediente a doble página, para que el texto se lea en papel); Parte 2, las catorce consolas |
| `fase2/presentacion/Vitalia_anexo_K_capturas.pdf` | El mismo álbum en PDF, 21 × 29.7 cm, 29 páginas. Es el documento que se adjunta; el mazo de cinco láminas es lo que se proyecta |

Es un **mazo aparte**, no un añadido a `Vitalia_presentacion.html`. La presentación de la fase 1
está cerrada y entregada: se proyecta primero ella y después estas cinco. Reutiliza su hoja de
estilo carácter por carácter, de modo que en la defensa se lee como una continuación y no como
otro documento.

Y son **dos piezas con dos oficios distintos**, que es la razón de no fundirlas: el mazo se
proyecta —cinco láminas apaisadas, poco texto, se leen desde el fondo de la sala— y el álbum se
entrega —A4 vertical, la captura entera y la explicación encima, para quien lo abra después sin
nadie que se lo cuente. La misma paleta y la misma tipografía en las dos.

---

## K.5 · Cómo se reproduce todo esto

```bash
cd fase2/codigo

# 1 · la base y el corpus (una sola vez)
psql "$DATABASE_URL" -f sql/01_esquema.sql
psql "$DATABASE_URL" -f sql/02_datos_semilla.sql
psql "$DATABASE_URL" -f sql/02_bandeja.sql
../.venv/Scripts/python.exe -u -m ingesta.pipeline_politica

# 2 · las siete suites que producen las evidencias
../.venv/Scripts/python.exe -u -m pruebas.prueba_motor        # E02
../.venv/Scripts/python.exe -u -m pruebas.prueba_n1           # E01/E02 + E00
../.venv/Scripts/python.exe -u -m pruebas.prueba_guardrail    # E09
../.venv/Scripts/python.exe -u -m pruebas.prueba_carril1      # E03 + E01 hallazgos
../.venv/Scripts/python.exe -u -m pruebas.prueba_api          # E11 + E12
../.venv/Scripts/python.exe -u -m pruebas.prueba_mcp          # E13
../.venv/Scripts/python.exe -u -m pruebas.prueba_model_armor  # E16 · tarda: corre 20 casos x 3 motores

# 3 · dejarlo desplegado y rehacer las siete capturas
../.venv/Scripts/python.exe -u -m demo.servidor    # :8088, y se queda vivo
../.venv/Scripts/python.exe -u -m demo.poblar      # vacía y repuebla, por HTTP
../.venv/Scripts/python.exe -u -m demo.capturar    # las siete imágenes

# 4 · la etapa B: la misma imagen en Cloud Run (desde PowerShell, no desde Git Bash)
gcloud builds submit --tag us-central1-docker.pkg.dev/datapath-labs-202608/vitalia-mvp/mesa:v1
gcloud run deploy vitalia-mesa --region us-central1 --no-allow-unauthenticated   --image us-central1-docker.pkg.dev/datapath-labs-202608/vitalia-mvp/mesa:v1   --set-secrets DATABASE_URL=vitalia-database-url:latest,QDRANT_URL=vitalia-qdrant-url:latest,QDRANT_API_KEY=vitalia-qdrant-api-key:latest,OPENAI_API_KEY=vitalia-openai-api-key:latest,GROQ_API_KEY=vitalia-groq-api-key:latest
../.venv/Scripts/python.exe -u -m demo.evidencia_despliegue   # E15

# y para verlo en el navegador sin abrirlo al público:
gcloud run services proxy vitalia-mesa --region us-central1   # queda en :8080
```

Las capturas se pueden rehacer contra el servicio remoto sin tocar el código —`demo.capturar` y
`demo.poblar` leen el destino del entorno, que es lo que exige el veto V2 (*una captura que no se
puede rehacer no es evidencia*):

```bash
VITALIA_BASE=https://vitalia-mesa-465408735025.us-central1.run.app   ../.venv/Scripts/python.exe -u -m demo.capturar
```

`demo.poblar` puebla **entero por HTTP**, no por SQL: así la captura prueba que el servicio
funciona, no que la base tiene filas. La secuencia completa, con lo que falló y por qué, está en
`01_bitacora_de_ejecucion.md`; las cuentas y variables, en `02_configuracion_entorno.md`.

Dos advertencias que ahorran una tarde y están en la bitácora §10: **un uvicorn viejo escuchando en
8088 sirve código anterior sin dar ningún error** —da capturas correctas de un sistema
equivocado—, y **capturar la pantalla 2 hace una consulta N1**, así que el hit-rate del panel sube
entre `poblar` y `capturar`; el orden de captura forma parte de la evidencia.

**Las catorce capturas de consola son manuales, y eso no es un descuido:** son la interfaz web de
cinco proveedores distintos y no hay comando que las produzca. Lo que sí es reproducible es **el
estado que retratan**, y por eso cada fila de `consolas/INDICE.json` nombra el objeto exacto —la
colección, la tabla, el servicio, la plantilla— en vez de describir la pantalla. Quien quiera
rehacerlas abre ese objeto y vuelve a ver lo mismo:

| Consola | Cómo se llega |
|---|---|
| Qdrant Cloud | Clúster `datalab_aisa_modulo01_jfsh` → *Collections* → `vitalia_politica_v2026_09` / `vitalia_cache_semantico` |
| Neon | Proyecto `datapath-labs` → rama `production` → base `neondb` → esquema **`vitalia_mvp`** → la tabla |
| Cloud Run | `datapath-labs-202608` → Cloud Run → `vitalia-mesa` (`us-central1`) → *Revisiones* / *Observabilidad* |
| Cloud Build · Storage · Secret Manager | El mismo proyecto, cada producto en su sección |
| Model Armor | **Seguridad → Model Armor** (Security Command Center), plantilla `vitalia-preauth` en `us-central1` |
| Groq | *Settings → Usage*, mes de septiembre de 2026 |

Antes de copiar cada imagen al entregable se revisó una por una que **no dejara ver el valor de
ninguna clave, ni la URL del clúster, ni una cadena de conexión**. Las tres de más riesgo —las
variables de Cloud Run y las dos vistas de Qdrant— se reabrieron a propósito para comprobarlo.

---

## K.6 · Lo que este MVP **no** demuestra

Declarado antes de que nadie lo busque, y sin adornos:

**De alcance —ya estaba en el plan (§9):**

- **No hay integración con el core de Vitalia.** El maestro de afiliados y el tarifario son tablas
  semilla. El diseño ya declara que la plataforma **lee** el core y no lo administra (ADR-18).
- **No hay firma digital real** del médico auditor: se simula el acto y se registra en la traza. Lo
  que sí es real es que **el sistema no puede emitir una negación sin ella** — es un `CHECK`.
- **Model Armor ya no falta**, pero no es el motor por defecto: está implementado y medido, y la
  medición dice que **sustituir** las capas propias por él baja la detección de 16/16 a 11/16. Se
  deja como motor `mixto` documentado. Lo que sigue sin hacerse es pasarle también la **salida**
  del modelo (`sanitize_model_response`): el guardrail de salida O1–O6 sigue siendo solo propio.
- **No hay Identity Platform**: la pantalla 1 es de demostración. ADR-15 sigue en pie como diseño.
- **No hay Acredita Salud ni IP fija de egreso**: es F1 del roadmap.
- **El volumen es de demostración**, no las 7,800 solicitudes/mes del caso. Los S/ 0.02 por
  solicitud del panel son la medición de esta corrida, **no** el S/ 0.86 costeado en el Anexo A,
  que incluye la infraestructura fija de producción.

**De ejecución — pendiente, no descartado:**

- **S05**: falta el contraste **densa vs. híbrida densa+BM25** con recall@k, que es donde se cierra
  el defecto conocido `REEM-06` de la tarea de la sesión 06.
- **S06**: falta **RAGAS** (faithfulness, answer relevancy, context precision) sobre las preguntas
  de política.
- **S03**: falta montar `kind` + Helm + **Ollama** como motor de degradación **N3**.
- **S10**: falta la instrumentación con **LangSmith** —con anonimización previa— y la medición de
  **J1, J3 y J4** bajo carga.
- Falta publicar **`v2026_10`** para ver el versionado en vivo moviendo el alias `politica_actual`.
- **La URL de Cloud Run no es pública.** El servicio está desplegado y sano, pero cerrado por IAM:
  la organización aplica `constraints/iam.allowedPolicyMemberDomains` y rechaza `allUsers` con
  `FAILED_PRECONDITION`. Abrirlo exige una excepción a nivel de organización, que no está en
  manos del proyecto. La política efectiva está **copiada literal** en el campo
  `acceso.politica_efectiva` de `E15_despliegue_cloud_run.json`, leída del propio GCP: un límite
  que se afirma sin poder comprobarlo no vale más que una excusa. Para verlo hay que invocarlo con
  token o levantar el proxy de §K.5.

**Huecos del propio diseño, encontrados construyendo y dejados a la vista:**

- `prestador_id` se valida **solo por forma**: no hay catálogo de prestadores. *El modelo propone,
  el catálogo dispone* — y donde no hay catálogo, no hay disposición.
- **Nada comprueba que el diagnóstico tenga que ver con el procedimiento** (`E12` §3). Un
  CIE-10 válido y un procedimiento válido pueden ser incoherentes entre sí y el sistema los acepta.
- Una pregunta que no nombra ninguna cobertura del léxico —*«¿cuánto es el deducible anual del plan
  VIT-ESE?»*— **nunca** puede usar el caché. Se dejó en el juego de la demostración, y repetida, para
  que el hueco se vea en el panel en lugar de esconderlo.

---

## K.7 · Dónde encaja este anexo en el paquete de la fase 1

Se añade como **Anexo K** al `INDICE_DE_ANEXOS.md` existente. Los diez anexos A–J no cambian.

| | Anexo de la fase 1 | Qué le aporta el Anexo K |
|---|---|---|
| **A** | Costos y assumptions | La medición real de costo por span y por solicitud del MVP, que da un orden de magnitud contra el modelo costeado |
| **C** | Modelo de datos, pipeline y metadata | El esquema **ejecutado** en Neon, con R2 y R3 como restricciones de base y la bitácora *append-only* como `RULE` |
| **D** | ADRs y alternativas | ADR-10, ADR-15, ADR-18 y ADR-21 vistos funcionando; ADR-19 (segmentación por cláusula) medido en 112 fragmentos |
| **E** | Golden set, evals y red-team | Los 16 casos R01–R16 ejecutados: **16/16 detectados, 0 falsos positivos** |
| **F** | Sizing, SLOs y observabilidad | Latencias p50/p95 por span reales y el panel de operación que las muestra |

| **G** | Seguridad, guardrails y cumplimiento | Model Armor **activado y medido**, no declarado: la plantilla `vitalia-preauth` retratada en C12/C13 y el 11/16 frente al 16/16 de las capas propias |
| **I** | Despliegue e infraestructura | El servicio en Cloud Run con su revisión, sus catorce variables y sus cinco secretos montados por referencia (C07, C09, C10, C11) |

Y la presentación gana **dos piezas**: el mazo de cinco láminas con el mapa de §K.1 y el mosaico
de la interfaz —para proyectar—, y el **álbum de 29 páginas A4** con las 21 capturas a tamaño
completo y su explicación —para adjuntar—.

---

## K.8 · La frase con la que se cierra

El MVP no demuestra que el sistema sea capaz de decidir. Demuestra lo contrario, que es lo que
este diseño vino a sostener: en la pantalla 4a hay una carta de negación **escrita, controlada y
sin emitir**, esperando a una persona. El expediente está en `hitl` y la máquina de estados no
tiene ninguna transición que lo saque de ahí sin que alguien firme.

Eso es el ADR-10, y no depende de que nadie se acuerde de aplicarlo.

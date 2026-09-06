# Configuración del entorno — fase 2

**Vitalia Salud EPS · mesa de preautorización · MVP**
**Autor:** Jonatan Sánchez · **Fecha:** 2026-09-05 · **Política vigente:** `v2026_09`

Esta hoja dice **qué cuentas, qué servicios y qué variables** hacen falta para que el MVP
arranque, y cómo quedó configurado el equipo donde se produjeron las evidencias del Anexo K.
Es la pieza que acompaña a `01_bitacora_de_ejecucion.md`: aquella cuenta *qué se corrió*, esta
cuenta *contra qué*.

> **Aquí no hay ni una clave.** Lo que aparece son **nombres de variable**. Los valores viven en
> `fase2/variables.sh`, que está en `.gitignore` y no se copia a ningún documento, ni a este ni a
> la presentación. Un anexo que se manda por correo con una credencial dentro deja de ser
> documentación y pasa a ser un incidente.

---

## 1. El mapa de servicios: quién hace qué

| Servicio | Para qué se usa en el MVP | Sesión del curso |
|---|---|---|
| **Neon** (Postgres serverless) | Estado del proceso: expedientes, extracciones, adjudicaciones, citas, borradores, cartas, bitácora, métricas de costo y feedback | S04 · S10 |
| **Qdrant Cloud** | Dos colecciones: el corpus normativo vectorizado y el **caché semántico** del Carril 0 | S05 · S02 |
| **OpenAI** | `text-embedding-3-large` (3,072 dims) para ingesta y recuperación; `gpt-4o-mini` para la extracción E1; `gpt-4o` para la redacción de cartas en E4 | S01 · S06 |
| **Groq** | Motor del **guardrail de entrada** (capas 7 y 8: Prompt Guard y Llama Guard) y modelo de baja latencia del **Carril 0**, elegido por J1 (`p95 < 2 s`) | S09 · S01 |
| **Presidio + spaCy** (local) | Capa 5 del guardrail de entrada y gancho **G5** del servidor MCP: detección y enmascarado de PII sin salir de la máquina | S09 |
| **GCP** (`datapath-labs-202608`) | Etapa B: **Artifact Registry** guarda la imagen, **Cloud Build** la construye, **Cloud Run** la sirve y **Secret Manager** inyecta los cinco valores sensibles. El MVP sigue corriendo también en local, con el mismo código | S03 · S10 |
| **Model Armor** (`us-central1`) | Motor gestionado del guardrail: la plantilla `vitalia-preauth` sustituye —o suma— las capas 2, 3, 6, 7 y 8. Medido contra las propias en `E16`; el MVP se queda en el motor propio y lo documenta | S09 |

Lo que **no** hay, y conviene decirlo antes de que alguien lo busque: no hay integración con el
core de Vitalia (el maestro de afiliados y el tarifario son tablas semilla), no hay Identity
Platform —la pantalla de ingreso es de demostración— y no hay firma digital real del médico
auditor. Está declarado en `00_PLAN_fase2.md` §9. **Model Armor sí se activó**, después de
escribir eso: está implementado, medido contra las capas propias y descrito en §10; lo que no
está es *puesto como motor por defecto*, y el §10 explica por qué con números.

---

## 2. Aislamiento: dos entornos GCP que no se cruzan

En este equipo conviven dos configuraciones de `gcloud`. La del curso **no** vive en la ruta por
defecto, precisamente para que un comando distraído no opere sobre el proyecto equivocado:

| | Cuenta | Proyecto | Dónde vive su config |
|---|---|---|---|
| **Curso** | `jonatan@hotelassetmanagement.ai` | `datapath-labs-202608` (nº 465408735025) | `fase2/../.gcp` vía `CLOUDSDK_CONFIG` |
| **Personal** | *(otra cuenta)* | *(otro proyecto)* | `%APPDATA%\gcloud\` — el default |

```powershell
# Siempre desde PowerShell; gcloud no se comporta igual invocado desde Git Bash.
$env:CLOUDSDK_CONFIG = "F:\...\datapath_ai_solutions_architech_202608\.gcp"
gcloud config list
```

`.gcp/` guarda tokens OAuth **en claro**. Está en el `.gitignore` de la raíz junto con
`variables.sh`, `.env` y `*.json.key`, y no se empaqueta con la entrega.

Zona de trabajo `us-central1-a`, facturación `billingAccounts/0174C9-703A70-BC30F1` (habilitada).

---

## 3. Las variables: solo los nombres

`fase2/variables.sh` es un script `sh` de asignaciones. `comun/config.py` lo lee al importarse y
usa **`setdefault`**: lo que ya venga del entorno manda, y el archivo solo rellena lo que falta.
Esa dirección importa —en Cloud Run los valores vendrán de Secret Manager y el archivo no
existirá— y hace que el mismo código sirva en los dos sitios sin bifurcarse.

### 3.1 · Las que el MVP lee de verdad

| Variable | Qué es | Quién la usa |
|---|---|---|
| `DATABASE_URL` | Cadena de conexión de Neon, con `sslmode=require&channel_binding=require` | `comun/repositorio.py` |
| `DB_SCHEMA` | `vitalia_mvp` — el esquema propio, para no tocar lo de las sesiones 04 y 06 | `comun/repositorio.py` |
| `QDRANT_URL` · `QDRANT_API_KEY` | Clúster de Qdrant Cloud | `comun/recuperacion.py`, `comun/cache_semantico.py`, `ingesta/` |
| `QDRANT_COLLECTION_NAME` | Colección de la versión: `vitalia_politica_v2026_09` | `ingesta/pipeline_politica.py` |
| `QDRANT_COLLECTION_ALIAS` | **`politica_actual`** — por aquí lee la aplicación (ADR-21) | `comun/recuperacion.py` |
| `QDRANT_CACHE_COLLECTION` | Colección del caché semántico del Carril 0 | `comun/cache_semantico.py` |
| `OPENAI_API_KEY` · `OPENAI_MODEL` · `OPENAI_EMBEDDING_MODEL` | Embeddings y los dos modelos de generación | `router_modelos`, `ingesta`, `flujo/` |
| `GROQ_API_KEY` | Carril 0 y capas 7–8 del guardrail | `comun/router_modelos.py`, `guardrails/entrada.py` |
| `GROQ_PROMPT_GUARD_MODEL` · `GROQ_LLAMA_GUARD_MODEL` | Los dos modelos guardián, declarados por nombre y no cableados | `guardrails/entrada.py` |
| `VERSION_POLITICA` | `v2026_09`. Prefija la clave del caché: **una versión nueva invalida el caché entero** | `comun/config.py`, `cache_semantico` |
| `RETRIEVAL_LIMIT` | Fragmentos que devuelve la recuperación | `comun/recuperacion.py` |

### 3.2 · Las que están en el archivo y este MVP no consume

Vienen de los laboratorios de las sesiones anteriores y se conservan porque el mismo
`variables.sh` sirve a todo el curso: `PROJECT_ID`, `PROJECT_NUMBER`, `REGION`, `LOCATION`,
`AR_REPO`, `NEON_API_KEY`, `NEON_PROJECT_ID`, `LANGSMITH_*`, `MODEL_ARMOR_*`,
`NEXT_PUBLIC_FIREBASE_*`, `GUARDRAIL_ENGINE`, `CUSTOM_REGEX_TIMEOUT_SECONDS`,
`GROQ_TIMEOUT_SECONDS`, `HISTORY_LIMIT`, `ASSISTANT_NAME`, `DEMO_MCP_SERVER_URL`.

Se listan aquí para que quien abra el archivo no busque dónde se usa `LANGSMITH_API_KEY`: **no se
usa todavía**. La instrumentación de LangSmith es trabajo pendiente de la sesión 10; la
observabilidad que el MVP sí tiene está en Neon (`metrica_costo`) y se ve en la pantalla 5.

---

## 4. Neon: el esquema y el detalle que costó una tarde

- Base `neondb`, rol `neondb_owner`, endpoint `ep-<id>-**pooler**.c-4.us-east-2.aws.neon.tech`
  (el identificador va enmascarado por la misma razón que `QDRANT_URL` es un secreto y no una
  variable de configuración: el destino identifica el recurso. El valor completo está en
  `variables.sh`, que no se versiona, y en el secreto `vitalia-database-url`).
- Todo el MVP vive en el esquema **`vitalia_mvp`**. `public` sigue teniendo las tablas de las
  sesiones 04 y 06 y no se tocó ninguna.

El pooler de Neon reparte cada consulta entre conexiones que no comparten estado de sesión, así
que un `SET search_path` al conectar **no sobrevive**: funciona en la primera consulta y falla en
la tercera con `relation "solicitud" does not exist`, que es la peor forma de fallar porque
parece intermitente. La solución no es de aplicación, es del rol:

```sql
ALTER ROLE neondb_owner IN DATABASE neondb SET search_path TO vitalia_mvp, public;
```

Queda escrito en el catálogo y lo hereda cualquier conexión nueva, venga del pooler o no. Ya está
ejecutado en la base del curso; en una instancia limpia hay que correrlo **antes** del esquema.

### 4.1 · Orden de creación

```bash
cd fase2/codigo
psql "$DATABASE_URL" -f sql/01_esquema.sql        # 319 líneas · tablas, CHECKs, trigger, RULE
psql "$DATABASE_URL" -f sql/02_datos_semilla.sql  #  69 líneas · afiliados, procedimientos, CIE-10
psql "$DATABASE_URL" -f sql/02_bandeja.sql        #  35 líneas · vistas de la bandeja
```

Tres cosas del esquema que no son adorno, porque son los invariantes escritos como restricción y
no como código —un invariante regulatorio no puede depender de que alguien se acuerde—:

- `CHECK (tipo <> 'niega_necesidad_medica' OR firma_id IS NOT NULL)` → **R3**, la firma médica.
- Trigger `tg_cita_verificada` → **R2**, no hay carta con una cita que no se verificó.
- `RULE` sobre `evento_estado` que hace fallar el `DELETE` → la bitácora es **append-only**.
  Consecuencia práctica: para dejar la base en cero se usa `TRUNCATE … CASCADE`, no `DELETE`.
  Está en `demo/poblar.py::limpiar()`.

---

## 5. Qdrant: una colección por versión, y un alias

| Colección | Qué guarda | Puntos |
|---|---|---|
| `vitalia_politica_v2026_09` | El corpus normativo segmentado por cláusula, con `texto_literal` en el payload | **112** |
| *(la del caché)* | Preguntas del Carril 0 con su respuesta y sus citas, con TTL de 7 días | variable |
| **`politica_actual`** *(alias)* | Apunta a la colección de la versión vigente | — |

La aplicación **nunca** nombra `vitalia_politica_v2026_09`: lee por el alias. Publicar `v2026_10`
será crear la colección nueva, ingestar y mover el alias; el código no se toca. Es el **ADR-21**, y
la pantalla 5 lo dice en voz alta debajo de la tabla de versiones.

El caché lleva `VERSION_POLITICA` dentro de la clave, así que una versión nueva no «ensucia» el
caché viejo: lo deja inalcanzable. **El caché no puede tirar las citas.**

---

## 6. El entorno Python

```bash
cd fase2
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r codigo/requirements.txt
.venv/Scripts/python.exe -m spacy download es_core_news_md   # capa 5, Presidio
```

Python **3.12.5**. Las versiones que importan, porque hay una combinación que sí choca:

| Paquete | Versión | Nota |
|---|---|---|
| `fastapi` | 0.115.6 | |
| `starlette` | 0.41.3 | **fijada**: `mcp` 1.29 arrastra una más nueva que rompe a FastAPI 0.115 |
| `mcp` | 1.29.1 | servidor MCP propio |
| `uvicorn` | 0.34.0 | |
| `openai` | 1.59.6 | |
| `groq` | 0.15.0 | |
| `qdrant-client` | 1.12.2 | |
| `psycopg2-binary` | 2.9.10 | |
| `presidio-analyzer` / `presidio-anonymizer` | 2.2.355 | con `spacy` 3.8.16 |

Dos cosas de Windows que ahorran un rato:

- **`PYTHONIOENCODING=utf-8`** en cualquier ejecución cuya salida se redirija o se filtre; sin
  ella la consola cae a cp1252 y las tildes salen rotas —y las evidencias son en español.
- Presidio y spaCy escriben mucho `WARNING` al arrancar. No es un problema, es ruido; se filtra al
  leer los logs, no se silencia en el código.

---

## 7. Levantar el MVP y dejarlo listo para las capturas

Tres comandos, en este orden, desde `fase2/codigo`:

```bash
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python.exe -u -m demo.servidor   # :8088, y se queda vivo
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python.exe -u -m demo.poblar     # vacía y rellena la bandeja
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python.exe -u -m demo.capturar   # rehace las siete imágenes
```

| URL | Qué es |
|---|---|
| `http://127.0.0.1:8088/app/#/bandeja` | La interfaz de la mesa |
| `http://127.0.0.1:8088/docs` | OpenAPI del servicio |
| `http://127.0.0.1:8088/salud` | Estado de las dependencias |

Comprobación de que todo está en pie —y lo que debe responder:

```json
{"version_politica":"v2026_09","neon":{"ok":true},
 "qdrant":{"ok":true,"puntos":112},"ok":true}
```

**Si el puerto 8088 está ocupado.** En este equipo `com.docker.backend` escucha en
`0.0.0.0:8088`; uvicorn liga `127.0.0.1:8088` y gana para *localhost*, así que conviven. Lo que
**no** convive es un uvicorn viejo del mismo proyecto: sirve código anterior sin que nada lo
delate, y las capturas salen de una versión que ya no existe. Antes de levantar:

```bash
netstat -ano | grep :8088          # ¿qué PID hay?
taskkill //PID <pid> //F           # si es un python que no lanzaste tú
```

---

## 8. El servidor MCP

Se conecta a un cliente (Claude Desktop, Claude Code) con el fragmento de
`evidencias/E13_conexion_cliente_mcp.md` §1, que también está en `fase2/mcp.json`. Dos cosas de
configuración: `cwd` apunta a `codigo/` porque el servidor se lanza como módulo, y el bloque `env`
va **vacío** —`comun/config.py` ya carga `variables.sh`, y un archivo de configuración de
escritorio se sincroniza, se copia y se pega en sitios donde una clave no debería estar—.

La bandera `--solo-lectura` está puesta por defecto: es el gancho **G1**, que corta cualquier skill
marcada `escribe` antes de ejecutarla. La única marcada así es `preparar_subsanacion`, porque
gasta tokens y deja fila de costo atribuida a un expediente. *Modo solo lectura significa «no
gastes ni cambies», no solo «no cambies».*

---

## 9. Etapa B: la misma imagen en Cloud Run

El MVP no deja de correr en local por estar desplegado: **es la misma imagen**, y la única
diferencia es de dónde salen las credenciales. Eso es lo que hace que el despliegue sea evidencia
y no una segunda versión del sistema.

### 9.1 · La imagen

`codigo/Dockerfile` sirve **la API y la interfaz desde un solo contenedor** —`api/principal.py`
monta `app_mesa` como estáticos—, así que no hay un front separado que se pueda quedar
desalineado con el backend. Un solo trabajador de uvicorn, a propósito: el caché semántico y los
disyuntores del MCP viven en memoria del proceso, y con dos el panel contaría la mitad de los
aciertos.

Las credenciales **no viajan en la imagen**. `codigo/.dockerignore` excluye `variables.sh`,
`.env`, `*.json.key` y `.gcp/`, y la regla está escrita ahí con su motivo para que siga siendo
cierta si alguien mueve un archivo. El contexto de build pesa **593 KB**.

Lo que hace que esto funcione sin una sola bandera condicional es una línea de `comun/config.py`:
lee `variables.sh` **solo si existe** y con `os.environ.setdefault`. En local el archivo está y
manda; en Cloud Run no existe y manda lo que inyecta Secret Manager. *El código no sabe dónde está
corriendo, y no le hace falta.*

### 9.2 · Los cuatro comandos, en orden

```powershell
$env:CLOUDSDK_CONFIG = "F:\...\datapath_ai_solutions_architech_202608\.gcp"

# a · el repositorio de imágenes
gcloud artifacts repositories create vitalia-mvp --repository-format=docker --location=us-central1

# b · las claves, una por secreto (--data-file, nunca en la línea de comandos)
gcloud secrets create vitalia-database-url   --data-file=<archivo>
gcloud secrets create vitalia-qdrant-url     --data-file=<archivo>
gcloud secrets create vitalia-qdrant-api-key --data-file=<archivo>
gcloud secrets create vitalia-openai-api-key --data-file=<archivo>
gcloud secrets create vitalia-groq-api-key   --data-file=<archivo>

# c · construir (Cloud Build regional) y desplegar
gcloud builds submit --tag us-central1-docker.pkg.dev/datapath-labs-202608/vitalia-mvp/mesa:v1
gcloud run deploy vitalia-mesa --region us-central1 --no-allow-unauthenticated `
  --image us-central1-docker.pkg.dev/datapath-labs-202608/vitalia-mvp/mesa:v1 `
  --cpu 1 --memory 2Gi --concurrency 20 --max-instances 2 `
  --set-secrets DATABASE_URL=vitalia-database-url:latest,QDRANT_URL=vitalia-qdrant-url:latest,QDRANT_API_KEY=vitalia-qdrant-api-key:latest,OPENAI_API_KEY=vitalia-openai-api-key:latest,GROQ_API_KEY=vitalia-groq-api-key:latest

# d · el permiso mínimo para que la cuenta de ejecución pueda leerlos
gcloud secrets add-iam-policy-binding <secreto> `
  --member serviceAccount:465408735025-compute@developer.gserviceaccount.com `
  --role roles/secretmanager.secretAccessor
```

`--data-file` en lugar de `--data`: un valor pasado por la línea de comandos queda en el historial
del shell. Los archivos temporales se escriben en el directorio de trabajo temporal y se borran
en el mismo paso.

El permiso de (d) se da **secreto por secreto**, no en el proyecto: la cuenta de ejecución puede
leer estos cinco y ninguno más.

### 9.3 · Lo que quedó en pie

| | |
|---|---|
| Servicio | `vitalia-mesa` · `us-central1` · revisión `vitalia-mesa-00001-srk` |
| URL | `https://vitalia-mesa-465408735025.us-central1.run.app` |
| Imagen | `.../vitalia-mvp/mesa:v1` · digest `sha256:560c5a90…6bccbc` · build de 1 m 33 s |
| Recursos | cpu 1 · memoria 2 GiB · concurrencia 20 · de 0 a 2 instancias |
| Acceso | **cerrado**: `roles/run.invoker`, hace falta un token de identidad |

Comprobado desde el servicio remoto, no desde la máquina: `/salud` en **1,171 ms** con
`v2026_09` vigente, 112 puntos en Qdrant y Neon respondiendo; y una consulta N1 real resuelta en
**2,473 ms** con **dos citas verificadas y cero rechazadas**. Está en
`evidencias/E15_despliegue_cloud_run.json`, que lo regenera `demo.evidencia_despliegue`.

### 9.4 · Por qué la URL no es pública

«Público» en Cloud Run no es una casilla del servicio: es el permiso IAM
`allUsers → roles/run.invoker`. La opción elegida era dejarlo abierto durante la defensa y cerrarlo
después. **No se pudo:**

```
FAILED_PRECONDITION: One or more users named in the policy do not belong to a
permitted customer, perhaps due to an organization policy.
```

La organización **354203404684** aplica `constraints/iam.allowedPolicyMemberDomains` —*Domain
Restricted Sharing*— y solo admite miembros del cliente `C03etc3y2`; `allUsers` no lo es. La regla
se lee, no se supone (hay que habilitar antes `orgpolicy.googleapis.com` en el proyecto):

```powershell
gcloud org-policies describe constraints/iam.allowedPolicyMemberDomains --project=datapath-labs-202608 --effective
```
```yaml
name: projects/465408735025/policies/iam.allowedPolicyMemberDomains
spec:
  rules:
  - values:
      allowedValues:
      - C03etc3y2
```

Levantarla exige aplicar sobre el proyecto una excepción con el valor
`is:principalSet://goog/public:all`, y eso lo firma alguien con `roles/orgpolicy.policyAdmin` en la
organización. La
cuenta es `roles/owner` del proyecto pero **no tiene ningún permiso a nivel de organización**
(`gcloud organizations get-iam-policy` responde permiso denegado), así que la excepción no está en
sus manos: tendría que concederla un *Organization Policy Administrator*.

Mientras tanto el servicio se ve igual, sin abrir nada:

```powershell
gcloud run services proxy vitalia-mesa --region us-central1 --project datapath-labs-202608
# queda en http://localhost:8080 con el token puesto por el proxy
```

Y las siete capturas se pueden rehacer contra el servicio remoto sin tocar el código, porque
`demo.capturar` y `demo.poblar` leen el destino de `VITALIA_BASE` —eso es el veto **V2**: una
captura que no se puede rehacer no es evidencia.

---

## 10. Model Armor: el motor gestionado del guardrail

El guardrail de la sesión 09 es propio: ocho capas en `codigo/guardrails/entrada.py`. El curso
enseña también el camino gestionado —Model Armor—, así que se implementó y, sobre todo, **se
midió**: activarlo sin comparar sería marcar una casilla, no añadir un control.

### 10.1 La plantilla

Con `CLOUDSDK_CONFIG` apuntando a `.gcp/` como en §2:

```powershell
gcloud services enable modelarmor.googleapis.com --project datapath-labs-202608
```

La plantilla **no** se crea con `gcloud model-armor`: esa superficie apunta al endpoint global y
devuelve `PERMISSION_DENIED` aunque la cuenta sea `roles/owner`. Model Armor es regional, y hay
que hablarle a su región:

```powershell
$t = gcloud auth print-access-token
Invoke-RestMethod -Method POST -Headers @{Authorization="Bearer $t"} `
  -Uri "https://modelarmor.us-central1.rep.googleapis.com/v1/projects/datapath-labs-202608/locations/us-central1/templates?template_id=vitalia-preauth" `
  -ContentType "application/json" -InFile plantilla.json
```

| Filtro de `vitalia-preauth` | Umbral | Sustituye a |
|---|---|---|
| `rai` · dangerous, harassment, hate_speech, sexually_explicit | `MEDIUM_AND_ABOVE` | capa 3 (toxicidad) y parte de la 8 |
| `pi_and_jailbreak` | **`LOW_AND_ABOVE`** | capas 2 y 7 |
| `malicious_uris` | habilitado | capa 6 |
| `sdp` (básico) | habilitado | — solo inspecciona; la 5 sigue siendo Presidio |
| `csam` | siempre activo | parte de la 8 |

El umbral de `pi_and_jailbreak` es el más sensible **a propósito**: es la asimetría del error del
veto V1: rechazar una solicitud legítima que el prestador reenvía cuesta menos que dejar pasar
una inyección.

### 10.2 Los cuatro motores

`GUARDRAIL_ENGINE` decide qué corre. Las capas 1 (secretos), 4 (reglas del dominio) y 5 (PII)
**corren siempre**, con cualquier motor: son las que saben qué es un secreto nuestro, qué viola
R1/R3 y cómo anonimizar un DNI peruano. Ningún proveedor gestionado sabe nada de eso.

| Valor | Qué corre | Cuándo |
|---|---|---|
| `local` | capas 1–6 | desarrollo sin red |
| `groq` | las ocho | **por defecto en el MVP** |
| `model_armor` | 1, 4, 5 + Model Armor sustituyendo a 2, 3, 6, 7 y 8 | para comparar |
| `mixto` | las ocho **más** Model Armor | lo que recomienda la medición |

```bash
# en fase2/variables.sh
export MODEL_ARMOR_PROJECT_ID="datapath-labs-202608"
export MODEL_ARMOR_LOCATION="us-central1"
export MODEL_ARMOR_TEMPLATE_ID="vitalia-preauth"
export MODEL_ARMOR_TIMEOUT_SECONDS="3"
```

Si Model Armor no responde dentro del timeout, la capa se marca **`omitida`** y el orquestador
ejecuta las cinco capas locales que sustituía. No se hace fail-close como en las capas 7 y 8:
bloquear sería más caro sin ser más seguro, porque lo que hay debajo es exactamente lo que había
antes de Model Armor. Lo que **no** se hace es reportar como aprobada una capa que no se ejecutó.

### 10.3 El resultado, que es el motivo de todo esto

```bash
cd codigo && ../.venv/Scripts/python.exe -u -m pruebas.prueba_model_armor
```

| Motor | Ataques detectados | Falsos positivos | Mediana |
|---|---|---|---|
| propio (`groq`) | **16/16** | 0/4 | 1,362 ms |
| gestionado (`model_armor`) | **11/16** | 0/4 | 211 ms |
| `mixto` | **16/16** | 0/4 | 1,438 ms |

Los cinco que se le escapan al gestionado son R04 (*developer mode* en español), R05 (delimitador
falso), R13 (exfiltración a un dominio sin mala reputación), R14 (insulto en español peruano) y
R15 (fraude al seguro). Y las once detecciones que sí consigue salieron **todas** de
`pi_and_jailbreak`: `rai`, `malicious_uris` y `sdp` no marcaron ni un caso — ni siquiera el que
lleva DNI, correo y teléfono, que bloqueó `pi_and_jailbreak` y anonimizó Presidio.

La conclusión no es que Model Armor sea malo: es que **no es un reemplazo**. Aporta un
clasificador de inyección ajeno al nuestro por 211 ms; no aporta, ni puede, las reglas de Vitalia.
Detalle caso por caso en `evidencias/E16_model_armor_vs_capas_propias.json`.

Las credenciales: la capa usa las de aplicación por defecto y, si están caducadas —lo normal en
una máquina de laboratorio—, cae al token de la sesión de `gcloud`. Misma cuenta, mismo proyecto,
nada nuevo en disco.

---

## 11. Qué hay que tener antes de empezar, en una lista

1. Cuenta **Neon** con una base y el `ALTER ROLE … SET search_path` aplicado.
2. Clúster **Qdrant Cloud** (URL + API key).
3. Clave de **OpenAI** con acceso a `text-embedding-3-large`, `gpt-4o-mini` y `gpt-4o`.
4. Clave de **Groq** con acceso a `openai/gpt-oss-20b`, Prompt Guard y Llama Guard.
5. **Python 3.12** y **Google Chrome** (las capturas usan `--headless=new`).
6. `psql` en el `PATH` para cargar el esquema.
7. `fase2/variables.sh` con los valores de 1–4. **Ese archivo no se versiona y no se comparte.**
8. Para la etapa B, además: `gcloud` autenticado con `CLOUDSDK_CONFIG` apuntando a `.gcp/`, y
   las APIs `artifactregistry`, `cloudbuild`, `run` y `secretmanager` habilitadas en el proyecto.
9. Para el motor gestionado del guardrail: la API `modelarmor` habilitada, la plantilla
   `vitalia-preauth` creada en `us-central1` (§10) y las cuatro variables `MODEL_ARMOR_*`.

Cuando el curso termine, las claves de los puntos 2–4 se rotan o se borran. Hasta entonces siguen
vivas a propósito, porque el entorno se sigue usando.

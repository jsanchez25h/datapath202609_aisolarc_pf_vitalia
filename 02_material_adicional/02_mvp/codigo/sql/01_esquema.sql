-- ===========================================================================
-- Vitalia Salud EPS · MVP fase 2 · esquema del proceso de preautorización
-- Base: Neon Postgres (la misma instancia de los laboratorios del curso).
-- Todo vive en el esquema vitalia_mvp para no tocar public.history ni
-- public.dead_letter_documents, que son de las sesiones 06 y 04.
--
-- Fiel a `08_modelo_de_datos.md` §2. Los invariantes R2 y R3 se escriben como
-- restricciones de base, no como validación de aplicación: un invariante
-- regulatorio no puede depender de que el código lo respete.
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS vitalia_mvp;
SET search_path TO vitalia_mvp, public;

-- --------------------------------------------------------------------------
-- 1 · Catálogos y versionado de política
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS politica_version (
    version_id        TEXT PRIMARY KEY,              -- v2026_09
    sha256            TEXT        NOT NULL,
    vigencia_desde    DATE        NOT NULL,
    vigencia_hasta    DATE,
    aprobado_por      TEXT        NOT NULL,          -- el curador de política
    diff_vs_anterior  TEXT,
    coleccion_qdrant  TEXT        NOT NULL,
    fragmentos        INTEGER     NOT NULL DEFAULT 0,
    publicada_en      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (vigencia_hasta IS NULL OR vigencia_hasta >= vigencia_desde)
);

CREATE TABLE IF NOT EXISTS catalogo_procedimiento (
    codigo            TEXT PRIMARY KEY,
    descripcion       TEXT NOT NULL,
    requiere_preauth  BOOLEAN NOT NULL DEFAULT true,
    vigente_desde     DATE NOT NULL DEFAULT '2020-01-01',
    vigente_hasta     DATE
);

CREATE TABLE IF NOT EXISTS catalogo_cie10 (
    codigo            TEXT PRIMARY KEY,
    descripcion       TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- 2 · Espejo de solo lectura del core (R1 · el MVP NO es dueño de este dato)
--     En producción esto es una integración; aquí es un simulador declarado.
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core_afiliado (
    afiliado_ref      TEXT PRIMARY KEY,
    nombre            TEXT NOT NULL,
    plan_codigo       TEXT NOT NULL CHECK (plan_codigo IN ('VIT-INT','VIT-ESE','VIT-PRE')),
    afiliado_desde    DATE NOT NULL,
    estado            TEXT NOT NULL CHECK (estado IN ('activo','suspendido','baja')),
    deducible_anual   NUMERIC(10,2) NOT NULL DEFAULT 0,
    deducible_consumido NUMERIC(10,2) NOT NULL DEFAULT 0,
    preexistencias    TEXT[] NOT NULL DEFAULT '{}',
    fuente            TEXT NOT NULL DEFAULT 'core-simulado'
);

CREATE TABLE IF NOT EXISTS core_tarifario (
    procedimiento_codigo TEXT NOT NULL REFERENCES catalogo_procedimiento(codigo),
    plan_codigo          TEXT NOT NULL,
    tarifa_pen           NUMERIC(10,2) NOT NULL,
    coaseguro_pct        NUMERIC(5,2)  NOT NULL,
    copago_fijo_pen      NUMERIC(10,2) NOT NULL DEFAULT 0,
    tope_copago_pen      NUMERIC(10,2),
    PRIMARY KEY (procedimiento_codigo, plan_codigo)
);

-- --------------------------------------------------------------------------
-- 3 · La solicitud y su expediente
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS solicitud (
    solicitud_id      TEXT PRIMARY KEY,
    afiliado_ref      TEXT NOT NULL REFERENCES core_afiliado(afiliado_ref),
    prestador_id      TEXT NOT NULL,
    plan_codigo       TEXT NOT NULL,
    dx_cie10          TEXT NOT NULL REFERENCES catalogo_cie10(codigo),
    procedimiento_codigo TEXT NOT NULL REFERENCES catalogo_procedimiento(codigo),
    tipo              TEXT NOT NULL CHECK (tipo IN ('programado','urgente','extranjero')),
    canal             TEXT NOT NULL CHECK (canal IN ('N1','portal','mesa')),
    estado_actual     TEXT NOT NULL CHECK (estado_actual IN
                        ('recibida','E1','E2','E3','E4','auto','hitl','agente','emitida','rechazada_guardrail')),
    fecha_solicitud   DATE NOT NULL DEFAULT CURRENT_DATE,
    creada_en         TIMESTAMPTZ NOT NULL DEFAULT now(),
    hash_expediente   TEXT NOT NULL,
    idempotency_key   TEXT NOT NULL,
    sla_vence_en      TIMESTAMPTZ,
    version_politica_aplicada TEXT NOT NULL REFERENCES politica_version(version_id),
    UNIQUE (solicitud_id, idempotency_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_solicitud_idem ON solicitud(idempotency_key);

CREATE TABLE IF NOT EXISTS documento (
    doc_id            TEXT PRIMARY KEY,
    solicitud_id      TEXT NOT NULL REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    tipo              TEXT NOT NULL,
    gcs_uri           TEXT,
    sha256            TEXT NOT NULL,
    paginas           INTEGER,
    recibido_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS extraccion (
    extr_id           BIGSERIAL PRIMARY KEY,
    solicitud_id      TEXT NOT NULL REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    doc_id            TEXT REFERENCES documento(doc_id) ON DELETE CASCADE,
    campo             TEXT NOT NULL,
    valor             TEXT,
    confianza         NUMERIC(4,3) CHECK (confianza IS NULL OR (confianza >= 0 AND confianza <= 1)),
    validado_catalogo BOOLEAN NOT NULL DEFAULT false,
    modelo            TEXT,
    prompt_sha        TEXT,
    ts                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------------------
-- 4 · Máquina de estados append-only
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS transicion_valida (
    desde   TEXT NOT NULL,
    hacia   TEXT NOT NULL,
    PRIMARY KEY (desde, hacia)
);

CREATE TABLE IF NOT EXISTS evento_estado (
    ev_id       BIGSERIAL PRIMARY KEY,
    solicitud_id TEXT NOT NULL REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    desde       TEXT,
    hacia       TEXT NOT NULL,
    actor       TEXT NOT NULL,
    motivo      TEXT,
    trace_id    TEXT,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- evento_estado no se actualiza ni se borra: es la traza de una fiscalización.
CREATE OR REPLACE RULE evento_estado_no_update AS ON UPDATE TO evento_estado DO INSTEAD NOTHING;
CREATE OR REPLACE RULE evento_estado_no_delete AS ON DELETE TO evento_estado DO INSTEAD NOTHING;

-- --------------------------------------------------------------------------
-- 5 · Adjudicación, citas y firma
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS adjudicacion (
    adj_id          TEXT PRIMARY KEY,
    solicitud_id    TEXT NOT NULL REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    elegible        BOOLEAN NOT NULL,
    carencia_ok     BOOLEAN NOT NULL,
    carencia_dias_exigidos INTEGER,
    carencia_dias_afiliado INTEGER,
    cobertura       TEXT NOT NULL CHECK (cobertura IN ('cubierto','no_cubierto','requiere_juicio')),
    motivo          TEXT,                   -- por qué el motor concluyó esa cobertura
    copago_pen      NUMERIC(10,2),
    copago_desglose JSONB,
    confianza       NUMERIC(4,3),
    ruta            TEXT NOT NULL CHECK (ruta IN ('auto','hitl','agente','rechazo_guardrail')),
    motivo_ruta     TEXT,
    modelo          TEXT,
    modelo_version  TEXT,
    prompt_sha      TEXT,
    determinista    BOOLEAN NOT NULL DEFAULT true,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotente para una base creada antes de que `motivo` existiera.
ALTER TABLE adjudicacion ADD COLUMN IF NOT EXISTS motivo TEXT;

CREATE TABLE IF NOT EXISTS cita (
    cita_id             TEXT PRIMARY KEY,
    adj_id              TEXT REFERENCES adjudicacion(adj_id) ON DELETE CASCADE,
    solicitud_id        TEXT REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    chunk_id            TEXT NOT NULL,
    doc_id_corpus       TEXT NOT NULL,
    version_id          TEXT NOT NULL REFERENCES politica_version(version_id),
    articulo            TEXT NOT NULL,
    texto_literal       TEXT NOT NULL,
    offset_ini          INTEGER,
    offset_fin          INTEGER,
    score               NUMERIC(6,4),
    verificada_literal  BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS firma_medica (
    firma_id        TEXT PRIMARY KEY,
    adj_id          TEXT NOT NULL REFERENCES adjudicacion(adj_id),
    colegiatura_cmp TEXT NOT NULL,
    medico_id       TEXT NOT NULL,
    ip              TEXT,
    hash_doc        TEXT NOT NULL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS carta (
    carta_id        TEXT PRIMARY KEY,
    solicitud_id    TEXT NOT NULL REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL CHECK (tipo IN
                      ('autoriza','autoriza_parcial','observa','niega_administrativa','niega_necesidad_medica')),
    -- R2 · ninguna carta sin la versión de política que la selló
    version_politica TEXT NOT NULL REFERENCES politica_version(version_id),
    firma_id        TEXT REFERENCES firma_medica(firma_id),
    cuerpo          TEXT NOT NULL,
    copago_pen      NUMERIC(10,2),
    core_folio      TEXT,
    emitida_en      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- R3 · ninguna negación por necesidad médica sin firma de médico colegiado
    CONSTRAINT r3_firma_obligatoria
        CHECK (tipo <> 'niega_necesidad_medica' OR firma_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS carta_cita (
    carta_id  TEXT NOT NULL REFERENCES carta(carta_id) ON DELETE CASCADE,
    cita_id   TEXT NOT NULL REFERENCES cita(cita_id),
    PRIMARY KEY (carta_id, cita_id)
);

-- Ninguna cita sin verificación literal puede quedar referenciada por una carta.
CREATE OR REPLACE FUNCTION vitalia_mvp.f_cita_verificada() RETURNS TRIGGER AS $$
DECLARE ok BOOLEAN;
BEGIN
    SELECT verificada_literal INTO ok FROM vitalia_mvp.cita WHERE cita_id = NEW.cita_id;
    IF ok IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'O1: la cita % no está verificada literalmente y no puede citarse en una carta', NEW.cita_id;
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_cita_verificada ON carta_cita;
CREATE TRIGGER tg_cita_verificada BEFORE INSERT ON carta_cita
    FOR EACH ROW EXECUTE FUNCTION vitalia_mvp.f_cita_verificada();

-- --------------------------------------------------------------------------
-- 6 · Guardrails, agente, evaluación y FinOps
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS evaluacion_guardrail (
    eval_id     BIGSERIAL PRIMARY KEY,
    solicitud_id TEXT REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    sentido     TEXT NOT NULL CHECK (sentido IN ('entrada','salida')),
    capa        TEXT NOT NULL,
    categoria   TEXT,
    decision    TEXT NOT NULL CHECK (decision IN ('PERMITIR','TRANSFORMAR','CONFIRMAR','BLOQUEAR')),
    confianza   NUMERIC(4,3),
    posicion    INTEGER,
    latencia_ms INTEGER,
    detalle     TEXT,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS turno_agente (
    turno_id     BIGSERIAL PRIMARY KEY,
    solicitud_id TEXT NOT NULL REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    n_turno      INTEGER NOT NULL,
    tool_llamada TEXT,
    argumentos   JSONB,
    destinatario TEXT,
    resultado    TEXT,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (solicitud_id, n_turno)
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id  BIGSERIAL PRIMARY KEY,
    solicitud_id TEXT REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    usuario      TEXT,
    util         BOOLEAN NOT NULL,
    tipo_error   TEXT,
    comentario   TEXT,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluacion_ragas (
    eval_id       BIGSERIAL PRIMARY KEY,
    corrida       TEXT NOT NULL,
    pregunta      TEXT NOT NULL,
    respuesta     TEXT,
    contexto      TEXT[],
    faithfulness  NUMERIC(4,3),
    answer_relevancy NUMERIC(4,3),
    context_precision NUMERIC(4,3),
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Atribución de costo por span (sesiones 02 y 10)
CREATE TABLE IF NOT EXISTS metrica_costo (
    metrica_id    BIGSERIAL PRIMARY KEY,
    solicitud_id  TEXT REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    trace_id      TEXT,
    span          TEXT NOT NULL,          -- guardrail | recuperacion | extraccion | adjudicacion | emision
    proveedor     TEXT NOT NULL,          -- openai | groq | qdrant | ollama
    modelo        TEXT,
    tokens_in     INTEGER NOT NULL DEFAULT 0,
    tokens_out    INTEGER NOT NULL DEFAULT 0,
    costo_usd     NUMERIC(12,8) NOT NULL DEFAULT 0,
    latencia_ms   INTEGER,
    cache_hit     BOOLEAN NOT NULL DEFAULT false,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_costo_solicitud ON metrica_costo(solicitud_id);
CREATE INDEX IF NOT EXISTS ix_evento_solicitud ON evento_estado(solicitud_id);
CREATE INDEX IF NOT EXISTS ix_guardrail_solicitud ON evaluacion_guardrail(solicitud_id);

-- --------------------------------------------------------------------------
-- 7 · Transiciones permitidas (la máquina de estados no admite saltos)
-- --------------------------------------------------------------------------

INSERT INTO transicion_valida (desde, hacia) VALUES
    ('recibida','E1'), ('recibida','rechazada_guardrail'),
    ('E1','E2'), ('E2','E3'),
    ('E3','auto'), ('E3','hitl'), ('E3','agente'),
    ('auto','E4'), ('hitl','E4'), ('agente','E2'), ('agente','hitl'),
    ('E4','emitida')
ON CONFLICT DO NOTHING;

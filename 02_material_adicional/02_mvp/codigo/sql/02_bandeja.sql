-- Bandeja de la mesa · lo que una persona necesita para resolver un expediente
--
-- Un borrador NO es una carta. La tabla `carta` significa «emitida»: tiene el
-- folio del core, el sello de versión y la restricción `r3_firma_obligatoria`,
-- y cada fila suya es un documento que el afiliado puede oponer a Vitalia.
-- Guardar ahí un texto que todavía nadie firmó vaciaría de significado a la
-- tabla y a sus restricciones.
--
-- El borrador vive aparte, con su veredicto de guardrail al lado. Existe para
-- que el analista de la pantalla 4 lea lo que el sistema propuso —y por qué el
-- guardrail lo dejó pasar o no— sin que el expediente tenga que reprocesarse.
-- Sin esta tabla, el «ahorro de 19 minutos» del business case no tiene dónde
-- ocurrir: la persona tendría que redactar desde cero.

SET search_path TO vitalia_mvp, public;

CREATE TABLE IF NOT EXISTS borrador_carta (
    borrador_id     BIGSERIAL PRIMARY KEY,
    solicitud_id    TEXT NOT NULL REFERENCES solicitud(solicitud_id) ON DELETE CASCADE,
    adj_id          TEXT REFERENCES adjudicacion(adj_id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL,
    cuerpo          TEXT NOT NULL,
    aprobada_guardrail BOOLEAN NOT NULL,
    controles       JSONB NOT NULL DEFAULT '[]'::jsonb,
    version_politica TEXT NOT NULL REFERENCES politica_version(version_id),
    modelo          TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_borrador_solicitud ON borrador_carta (solicitud_id, creado_en DESC);

-- El expediente puede recibir más de un borrador: el que redactó el modelo y el
-- que la persona corrigió antes de emitir. Se conservan los dos —append-only,
-- igual que `evento_estado`— porque el veto V2 exige poder reconstruir qué se
-- propuso y qué se cambió, no solo qué se firmó.

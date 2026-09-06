-- ===========================================================================
-- Datos de demostración del MVP.
--
-- core_afiliado y core_tarifario simulan el core de Vitalia: el diseño declara
-- que la plataforma NO es dueña de ese dato (ADR-18) y aquí se respeta —se lee,
-- no se administra—. Las cifras salen del corpus normativo, no de la nada:
--   deducible anual .... VIT-ESE 1200 · VIT-INT 600 · VIT-PRE 0
--   coaseguro hospit. .. VIT-ESE 10% · VIT-INT 5% · VIT-PRE 0%
--   tope de bolsillo ... VIT-INT 8000 · VIT-PRE 4000 · VIT-ESE sin tope
--   copago de cesárea .. VIT-INT 1400 · VIT-PRE 0 · VIT-ESE no cubre maternidad
-- ===========================================================================

SET search_path TO vitalia_mvp, public;

-- --- CIE-10 ---------------------------------------------------------------
INSERT INTO catalogo_cie10 (codigo, descripcion) VALUES
 ('K80.2','Cálculo de la vesícula biliar sin colecistitis'),
 ('K80.1','Cálculo de la vesícula biliar con otra colecistitis'),
 ('M23.2','Trastorno de menisco debido a desgarro o lesión antigua'),
 ('M23.5','Inestabilidad crónica de la rodilla'),
 ('O82.0','Parto por cesárea electiva'),
 ('K40.9','Hernia inguinal sin obstrucción ni gangrena'),
 ('M17.1','Gonartrosis primaria unilateral'),
 ('D25.9','Leiomioma del útero, no especificado')
ON CONFLICT (codigo) DO NOTHING;

-- --- Procedimientos -------------------------------------------------------
INSERT INTO catalogo_procedimiento (codigo, descripcion, requiere_preauth) VALUES
 ('PRC-4712','Colecistectomía laparoscópica', true),
 ('PRC-2933','Artroscopia de rodilla', true),
 ('PRC-5901','Cesárea programada', true),
 ('PRC-1180','Hernioplastía inguinal con malla', true),
 ('PRC-8104','Artroplastía total de rodilla', true),
 ('PRC-6620','Histerectomía abdominal', true)
ON CONFLICT (codigo) DO NOTHING;

-- --- Tarifario (tarifa de la clínica y reglas de copago por plan) ----------
INSERT INTO core_tarifario
 (procedimiento_codigo, plan_codigo, tarifa_pen, coaseguro_pct, copago_fijo_pen, tope_copago_pen) VALUES
 ('PRC-4712','VIT-ESE', 12800.00, 10.00,    0.00, NULL),
 ('PRC-4712','VIT-INT', 12800.00,  5.00,    0.00, 8000.00),
 ('PRC-4712','VIT-PRE', 12800.00,  0.00,    0.00, 4000.00),
 ('PRC-2933','VIT-ESE',  9400.00, 10.00,    0.00, NULL),
 ('PRC-2933','VIT-INT',  9400.00,  5.00,    0.00, 8000.00),
 ('PRC-2933','VIT-PRE',  9400.00,  0.00,    0.00, 4000.00),
 ('PRC-5901','VIT-INT', 11200.00,  0.00, 1400.00, 8000.00),
 ('PRC-5901','VIT-PRE', 11200.00,  0.00,    0.00, 4000.00),
 ('PRC-1180','VIT-ESE',  7600.00, 10.00,    0.00, NULL),
 ('PRC-1180','VIT-INT',  7600.00,  5.00,    0.00, 8000.00),
 ('PRC-1180','VIT-PRE',  7600.00,  0.00,    0.00, 4000.00),
 ('PRC-8104','VIT-INT', 32500.00,  5.00,    0.00, 8000.00),
 ('PRC-8104','VIT-PRE', 32500.00,  0.00,    0.00, 4000.00),
 ('PRC-6620','VIT-ESE', 10900.00, 10.00,    0.00, NULL),
 ('PRC-6620','VIT-INT', 10900.00,  5.00,    0.00, 8000.00),
 ('PRC-6620','VIT-PRE', 10900.00,  0.00,    0.00, 4000.00)
ON CONFLICT (procedimiento_codigo, plan_codigo) DO NOTHING;

-- --- Afiliados de demostración -------------------------------------------
-- Las fechas de afiliación se fijan relativas a hoy para que los tres casos
-- de §2 del plan sigan demostrando lo mismo cualquier día que se corra la demo.
INSERT INTO core_afiliado
 (afiliado_ref, nombre, plan_codigo, afiliado_desde, estado, deducible_anual, deducible_consumido, preexistencias) VALUES
 ('AF-100234','Rosa Milagros Quispe Ayala','VIT-INT', CURRENT_DATE - INTERVAL '14 months', 'activo',  600.00,   0.00, '{}'),
 ('AF-100777','Carlos Alberto Ramos Tineo', 'VIT-ESE', CURRENT_DATE - INTERVAL '26 months', 'activo', 1200.00, 400.00, '{}'),
 ('AF-100512','Ana Lucía Cavero Bendezú',   'VIT-INT', CURRENT_DATE - INTERVAL '220 days',  'activo',  600.00,   0.00, '{}'),
 ('AF-100888','Jorge Enrique Salas Piedra', 'VIT-PRE', CURRENT_DATE - INTERVAL '3 years',   'activo',    0.00,   0.00, '{}'),
 ('AF-100999','Marina del Pilar Ochoa Ruiz','VIT-INT', CURRENT_DATE - INTERVAL '40 days',   'activo',  600.00,   0.00, '{}'),
 ('AF-101010','Víctor Hugo Paredes Lino',   'VIT-INT', CURRENT_DATE - INTERVAL '5 years',   'suspendido', 600.00, 0.00, '{}')
ON CONFLICT (afiliado_ref) DO NOTHING;

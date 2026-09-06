# Vitalia Salud EPS — proyecto final

**DataPath · AI Solutions Architect · cohorte 2026-08**
**Caso:** mesa de preautorización de procedimientos programados — Vitalia Salud EPS (Perú)
**Autor:** Jonatan Sánchez · **Fecha:** 2026-09-06

---

## Dos carpetas

```
01_presentacion_final/     ← lo que hay que abrir
   01_Vitalia_presentacion.pdf          20 págs · el diseño
   02_Vitalia_anexo_K.pdf                5 págs · el MVP funcionando
   03_Vitalia_anexo_K_capturas.pdf      29 págs · las 21 capturas, una por página
   INDICE_DE_ANEXOS.md                  los anexos A–K, cada uno a su documento

02_material_adicional/     ← el respaldo de todo lo anterior
   01_analisis_y_diseno/               fase 1 · los 11 documentos y los 14 planos
   02_mvp/                             fase 2 · configuración, evidencias y código
```

---

## Los tres PDF, en orden

| | Archivo | Qué es | Cuánto dura |
|---|---|---|---|
| 1 | `01_Vitalia_presentacion.pdf` | El diseño completo: 13 láminas de discurso y 7 planos a página completa | 15 min |
| 2 | `02_Vitalia_anexo_K.pdf` | El MVP: el mapa de las diez sesiones del curso, la interfaz y los invariantes | 5 min |
| 3 | `03_Vitalia_anexo_K_capturas.pdf` | El álbum de evidencia: 21 capturas a tamaño completo con qué mirar en cada una | a consultar |

Los dos primeros se proyectan. El tercero se lee: A4 vertical, una captura por página con la
explicación **encima** y no debajo, para quien lo abra después sin nadie que se lo cuente.

**Si solo se puede mirar una página de todo el paquete**, es la **pantalla 4a** —álbum, págs. 7 y 8—:
una carta de negación escrita, aprobada por los seis controles de salida y **sin emitir**, con el
expediente detenido en `hitl` esperando a una persona. Es el ADR-10 —*el sistema nunca niega solo*—
en una imagen, y no depende de que nadie se acuerde de aplicarlo: la máquina de estados no tiene
ninguna transición que saque de ahí un expediente sin firma.

---

## Qué hay en el material adicional

### `01_analisis_y_diseno/` — la fase 1

Los **once documentos** del proyecto, en el orden en que se leen, empezando por
`00_INDICE_del_proyecto.md`, que es el índice canónico y trae las cifras que no pueden variar entre
documentos. Dentro, `diagramas/` con los **catorce planos** en draw.io editable y en PDF, más
`presentacion_navegable/` con la presentación en HTML (`←` `→`, `F` pantalla completa).

### `02_mvp/` — la fase 2

| | |
|---|---|
| `09_ANEXO_K_evidencias.md` | **El anexo.** El mapa sesión por sesión, las 21 capturas, los invariantes, cómo se reproduce y qué **no** demuestra |
| `02_configuracion_entorno.md` | Las cuentas y cómo se configuró cada proveedor: GCP, Qdrant, Neon, OpenAI y Groq |
| `01_bitacora_de_ejecucion.md` | La ejecución real, con lo que falló y por qué |
| `00_PLAN_fase2.md` | Qué se iba a construir y con qué criterio se recortó |
| `evidencias/` | 15 archivos de corrida y hallazgos · `pantallas/` con las 7 capturas de la app · `consolas/` con las 14 de los proveedores |
| `codigo/` | 7,524 líneas de Python en 8 paquetes, más `Dockerfile`, `sql/` y el descriptor MCP |
| `presentacion_navegable/` | El anexo K y el álbum en HTML, con sus imágenes |

Los HTML son **autocontenidos**: sin CDN, sin dependencias y sin conexión. Solo necesitan la
carpeta `img/` que tienen al lado.

---

## Las tres cifras de costo que no deben mezclarse

- **Comprometido** (`05_caso_de_negocio.md`): run S/ 21,700/mes · neto S/ 74,900/mes · payback
  8.8 meses · VAN S/ 1.13 M · TIR ≈ 85%.
- **Bottom-up** (`05a_costeo_cloud.md` §9): run S/ 19,700 · neto S/ 76,900 · payback 8.6 meses.
  La diferencia de S/ 2,000/mes **no se descuenta del caso de negocio**: queda como contingencia
  hasta que tres meses de facturación etiquetada la confirmen.
- **Medido en el MVP** (tabla `metrica_costo`): **S/ 0.02 por solicitud**. **No es comparable** con
  los **S/ 0.86** del Anexo A: aquél cuesta la plataforma completa a 7,800 solicitudes/mes con
  infraestructura fija; éste suma los tokens de una demo.

---

## Lo que no está aquí, dicho antes de que nadie lo busque

- El MVP **no tiene integración con el core** de Vitalia, ni firma digital real, ni Identity
  Platform. La autenticación de la demo es de demostración, y así lo dice la propia pantalla.
- **La URL de Cloud Run no es pública.** La política de organización
  `constraints/iam.allowedPolicyMemberDomains` rechaza `allUsers`; el servicio se ve con token o
  levantando `gcloud run services proxy`. La política efectiva está copiada literal en
  `02_mvp/evidencias/E15_despliegue_cloud_run.json`.
- **El volumen es de demostración**, no de producción: los SLOs J1, J3 y J4 *bajo carga* siguen sin
  medirse.
- De las diez sesiones del curso, **siete están cerradas, tres parciales y una pendiente**. Dicho
  así, sesión por sesión, en `§K.1`.

La lista completa y sin adornos está en `02_mvp/09_ANEXO_K_evidencias.md` §K.6. Un revisor debe
poder señalar cada supuesto sin encontrar una defensa inventada.

---

## Las claves

Ninguna clave, token ni cadena de conexión viaja en este paquete. Las cinco del MVP viven en
**Secret Manager** y se montan en Cloud Run por referencia; las capturas de consola enseñan sus
**nombres y nunca sus valores**. El código lee todo del entorno y no contiene ninguna.

*La única cadena con aspecto de clave en todo el paquete es el señuelo `sk-proj-AAAA…` del corpus
de red team, en `02_mvp/codigo/pruebas/prueba_guardrail.py`: es un caso de prueba, y el guardrail
lo bloquea.*

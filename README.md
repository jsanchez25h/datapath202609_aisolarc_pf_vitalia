# Vitalia Salud EPS — mesa de preautorización de procedimientos programados

**Proyecto final · DataPath · AI Solutions Architect · cohorte 2026-08**
**Autor:** Jonatan Sánchez · **Fecha de entrega:** 2026-09-06

Este repositorio es el paquete de entrega completo: el diseño de la solución (fase 1) y el MVP
funcionando con su evidencia (fase 2, Anexo K).

## Por dónde empezar

| | Documento | Qué es |
|---|---|---|
| 1 | [01_Vitalia_presentacion.pdf](01_presentacion_final/01_Vitalia_presentacion.pdf) | 20 págs · el diseño: 13 láminas de discurso y 7 planos |
| 2 | [02_Vitalia_anexo_K.pdf](01_presentacion_final/02_Vitalia_anexo_K.pdf) | 5 págs · el MVP: mapa de las diez sesiones, interfaz e invariantes |
| 3 | [03_Vitalia_anexo_K_capturas.pdf](01_presentacion_final/03_Vitalia_anexo_K_capturas.pdf) | 29 págs · el álbum: las 21 capturas, una por página |
| | [INDICE_DE_ANEXOS.md](01_presentacion_final/INDICE_DE_ANEXOS.md) | Los anexos A–K, cada uno a su documento |

**Si solo se puede mirar una página**, es la **pantalla 4a** —álbum, págs. 7 y 8—: una carta de
negación aprobada por los seis controles de salida y **sin emitir**, con el expediente detenido en
`hitl` esperando a una persona.

El detalle completo del paquete —qué hay en cada carpeta, las tres cifras de costo que no deben
mezclarse y lo que este MVP **no** demuestra— está en **[LEEME.md](LEEME.md)**.

## Estructura

```
01_presentacion_final/     los tres PDF numerados + el índice de anexos
02_material_adicional/
   01_analisis_y_diseno/   fase 1 · 11 documentos, 14 planos (draw.io + PDF) y la presentación navegable
   02_mvp/                 fase 2 · configuración, bitácora, evidencias, código y el anexo en HTML
```

## Sobre las claves

Ninguna clave, token ni cadena de conexión viaja en este repositorio. Las cinco del MVP viven en
**Secret Manager** y se montan en Cloud Run por referencia; las capturas de consola enseñan sus
**nombres y nunca sus valores**. El código lee todo del entorno.

*La única cadena con aspecto de clave es el señuelo `sk-proj-AAAA…` del corpus de red team, en
`02_material_adicional/02_mvp/codigo/pruebas/prueba_guardrail.py`: es un caso de prueba, y el
guardrail lo bloquea.*

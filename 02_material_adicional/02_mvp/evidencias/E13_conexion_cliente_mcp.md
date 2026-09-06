# Cómo se conecta el servidor MCP a un cliente real

**Fecha:** 2026-09-05 · **Alcance:** `mcp_vitalia.servidor` sobre transporte stdio
**Evidencia asociada:** `E13_mcp_skills_y_ganchos.json`, `E13_hallazgos_del_mcp.md`

`prueba_mcp` ejerce las cuatro skills y los seis ganchos llamando a
`servidor.invocar()` directamente, y lo hace a propósito: el transporte lo pone
el SDK y no es lo que hay que demostrar. Lo que sí conviene dejar por escrito es
que el servidor **arranca y responde a un cliente que no es nuestro**, y con qué
configuración se le conecta. Esta hoja es eso.

---

## 1 · El fragmento de configuración

Va en el archivo de servidores MCP del cliente (`claude_desktop_config.json` en
Claude Desktop, `.mcp.json` en Claude Code, el equivalente en cualquier otro):

```json
{
  "mcpServers": {
    "vitalia": {
      "command": "F:\\Laboral\\xampp\\htdocs\\datapath_ai_solutions_architech_202608\\Modulo05\\Sesion10\\Proyecto\\fase2\\.venv\\Scripts\\python.exe",
      "args": ["-u", "-m", "mcp_vitalia.servidor", "--solo-lectura"],
      "cwd": "F:\\Laboral\\xampp\\htdocs\\datapath_ai_solutions_architech_202608\\Modulo05\\Sesion10\\Proyecto\\fase2\\codigo"
    }
  }
}
```

Tres cosas que no son casualidad:

**No hay ni una clave en el fragmento.** El bloque `env` está vacío porque no
hace falta: `comun.config` carga `variables.sh` al importarse y no pisa nada que
ya venga del entorno. Los secretos viven en un archivo que está en `.gitignore`,
no en un archivo de configuración de escritorio que se sincroniza, se copia y se
pega en un chat. Si en algún despliegue hiciera falta pasarlos por entorno, el
`setdefault` respeta lo que ya esté puesto y el archivo deja de mandar.

**`cwd` apunta a `codigo/`, no a la raíz.** El servidor se ejecuta como módulo
(`-m`), así que el paquete `mcp_vitalia` tiene que estar en el directorio de
trabajo. Si se lanzara el archivo directamente, `servidor.py` se añade el
directorio padre al `sys.path` para poder correr igual; el módulo es la forma
sana.

**`--solo-lectura` está puesto.** Es la bandera de la defensa. No es un permiso
de base de datos: es el gancho **G1**, que corta antes de ejecutar cualquier skill
marcada `escribe`. La única marcada así es `preparar_subsanacion`, y lo está
porque gasta tokens contra la cuenta y deja fila de costo atribuida a un
expediente. *Modo solo lectura significa «no gastes ni cambies», no solo «no
cambies»*: una llamada que gastó y fue bloqueada gastó igual.

Para una sesión donde sí se quiera redactar la subsanación, se quita la bandera
de `args` y nada más cambia.

---

## 2 · Lo que el cliente ve al conectarse

Transcripción real de un cliente JSON-RPC mínimo hablando por stdio con el
servidor arrancado con `--solo-lectura`:

```
initialize   -> vitalia-preautorizacion · protocolo 2024-11-05
tools/list   -> ['consultar_politica', 'simular_cobertura',
                 'estado_expediente', 'preparar_subsanacion']
resources    -> ['vitalia://skills', 'vitalia://trazas', 'vitalia://disyuntores']
simular      -> simular_cobertura@1.0.0 · determinista=True modelo=None
                copago S/ 1210.0 ruta «agente» faltan 2
subsanacion  -> G1 · el servidor está en modo solo lectura
```

Cuatro herramientas, tres recursos. **Lo que no aparece en `tools/list` importa
tanto como lo que aparece:** no hay una herramienta que emita una carta, ni una
que niegue, ni una que cambie el estado de un expediente. No están restringidas
por permisos —no están escritas—. Un agente conectado aquí puede leerlo todo,
calcular cualquier cosa y preparar el texto de una subsanación, y no tiene forma
de resolver una solicitud. Es el **ADR-10** —el sistema nunca niega solo— llevado
a la superficie de herramientas, donde no depende de que nadie recuerde
aplicarlo.

La llamada a `simular_cobertura` devuelve `determinista=true` y `modelo=null` en
el mismo objeto: **R1 se lee en el dato**, no en la documentación. El cálculo del
copago —S/ 1,210.00— no pasó por ningún modelo, y quien recibe la respuesta puede
comprobarlo sin creer en nadie.

La llamada a `preparar_subsanacion` no devolvió un error de protocolo: devolvió
un objeto con el motivo del corte. Un cliente que recibe una traza de Python no
puede hacer nada con ella; uno que recibe *«G1 · el servidor está en modo solo
lectura»* sabe qué pasó y puede decírselo a quien lo esté usando.

---

## 3 · Los tres recursos

Se leen sin invocar nada y sin gastar un token:

| Recurso | Qué trae |
|---|---|
| `vitalia://skills` | El catálogo: cuatro nombres, cinco versiones, cuál es `latest` y cuál escribe |
| `vitalia://trazas` | Las llamadas de la sesión: skill con versión, milisegundos, nivel de degradación, costo y desenlace |
| `vitalia://disyuntores` | El estado de los circuit breakers por dependencia externa |

La traza de la sesión de arriba, tal cual la devuelve el recurso:

```json
[
 {"skill": "simular_cobertura@1.0.0", "ms": 2650, "ok": true,
  "abortado": false, "motivo": "", "nivel": "N0",
  "costo_usd": 0.0, "ts": "2026-09-05T17:37:06"},
 {"skill": "preparar_subsanacion@1.0.0", "ms": 0, "ok": false,
  "abortado": true, "motivo": "G1 · el servidor está en modo solo lectura",
  "nivel": "N0", "costo_usd": 0.0, "ts": "2026-09-05T17:37:07"}
]
```

La llamada bloqueada **está en la traza**. El gancho G6 corre siempre, también
cuando la cadena previa abortó, y por eso el registro no tiene huecos: una
llamada que no se ejecutó es información, no ausencia de información. La versión
va pegada al nombre de la skill —`simular_cobertura@1.0.0`— porque el cliente
invoca un **nombre** y la versión se resuelve en cada llamada; sin ese sufijo,
una traza de la semana pasada no diría contra qué se corrió.

---

## 4 · Comprobarlo sin cliente gráfico

El servidor habla JSON-RPC por stdin/stdout, así que se verifica con cualquier
cosa que sepa escribir líneas. Lo mínimo:

```bash
cd fase2/codigo
../.venv/Scripts/python.exe -u -m mcp_vitalia.servidor --solo-lectura
```

y por la entrada estándar, una línea por mensaje:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"prueba","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

Un detalle práctico que costó un rato: si se le pasa el guion por redirección de
archivo, el proceso ve el fin de la entrada y termina **antes de escribir la
última respuesta**. Hay que sostener la tubería abierta —un cliente de verdad lo
hace— o leer cada respuesta antes de mandar la siguiente.

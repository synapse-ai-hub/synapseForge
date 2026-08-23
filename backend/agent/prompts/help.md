# Ayuda del sistema

Ésta es la documentación de referencia del sistema. Acá se explica cómo configurar agentes, tools, skills y las opciones disponibles. Si tenés dudas sobre cómo usar o configurar el sistema, preguntale directamente al agente. El agente tiene acceso a herramientas internas para leer archivos, buscar en la web, ejecutar comandos, etc. Para más detalles sobre las herramientas disponibles, indicar que se consulte la documentación del agente.

## Agentes

Los sub-agentes son agentes especializados que se definen externamente al código. Cada uno tiene su propio rol, herramientas y skills.

### Crear un agente

1. Crear un archivo `.md` en la carpeta de agentes de la configuración (`~/.config/synapseForge/agents/`).
2. El nombre del archivo (sin la extensión `.md`) es el identificador que se usa para invocarlo mediante `task`.
3. El archivo debe contener un bloque de frontmatter YAML al inicio, delimitado por `---`. Campos disponibles:

   - **`name`**: Nombre legible del agente.
   - **`description`**: Descripción breve que explica qué hace y cuándo debe ser usado.
   - **`permission`**: Define las tools y sub-agentes a los que tiene acceso. Si una tool no está listada, no estará disponible. Los valores posibles son `allow` (permitido) y `deny` (denegado).
     - Para tools planas: `read: allow`
     - Para `task` (delegación a sub-agentes): `task: { nombre_agente: allow }`
   - **`skill`**: Define qué skills puede cargar. Misma sintaxis que `permission`.
   - **`parameters`**: Configuración del modelo para este agente: `temperature`, `top_p`, `model`, `seed`.

4. Debajo del frontmatter va el cuerpo del prompt del agente: su rol, instrucciones específicas, reglas de comportamiento.

### Cómo se resuelven los permisos

Cuando el agente principal delega una tarea a un sub-agente mediante `task`, el sistema:
1. Lee el archivo `.md` del sub-agente.
2. Extrae el frontmatter.
3. Filtra las tools según `permission`: solo las marcadas como `allow` estarán disponibles.
4. Filtra las skills según `skill`.
5. Usa el cuerpo del markdown como system prompt del sub-agente.

Esto significa que un sub-agente solo puede usar lo que su archivo de definición le permite. No tiene acceso a tools no declaradas.

### AGENT.md — Comportamiento general

El archivo `AGENT.md` (si existe en `~/.config/synapseForge/agents/`) se inyecta como sección `## Behavior` en el system prompt de **todos** los agentes (el principal y los sub-agentes), **antes** de la sección `## MANDATORY:`. No reemplaza el prompt de nadie: sirve para definir el comportamiento general del proyecto (compatibilidad con opencode/claude code).


### Permisos del agente principal (`config.yaml`)

El agente principal no tiene tools ni skills directas por defecto — solo puede delegar mediante `task`. Si existe `~/.config/synapseForge/config.yaml`, sus permisos se toman de ahí:

```yaml
permissions:
  tool:
    read: allow
  skill:
    mi_skill: allow
  task:
    explorador: allow
```

- Si el archivo **no existe** → el agente principal queda solo con `task` (delegación siempre disponible).
- Si existe → usa **solo** los permisos explícitos del yaml.
- `task` está **siempre** disponible: si el yaml no lo lista, puede delegar a todos los sub-agentes; si lo lista, solo a los indicados.

---

## Tools externas

Además de las tools internas del sistema, se pueden crear herramientas personalizadas.

### Crear una tool externa

1. Crear un archivo `.py` en la carpeta `tools/` de la configuración (`~/.config/synapseForge/tools/`).
2. El nombre del archivo (sin `.py`) debe coincidir con el nombre de la herramienta y con el de la función que contiene.
3. La primera línea del docstring del módulo es la descripción que el LLM usará para decidir si invocar la tool.
4. La función debe ser `async` y debe devolver el contrato `{status, message, data, usage}`.
5. Una vez creada, se puede habilitar para cualquier agente agregándola en su `permission`.

---

## Tools nativas

Además de las tools externas, el sistema incluye **tools nativas** incorporadas en el core. También deben habilitarse explícitamente por agente (deny by default). Las disponibles son:

| Tool | Qué hace |
|------|----------|
| `read` | Lee un archivo o directorio del sistema de archivos local. |
| `write` | Escribe contenido a un archivo. |
| `edit` | Realiza reemplazos exactos de texto en un archivo. |
| `glob` | Búsqueda de archivos por patrón (ej: `**/*.py`). |
| `grep` | Búsqueda de contenido en archivos usando expresiones regulares. |
| `webfetch` | Descarga el contenido de una URL y lo convierte a markdown, texto o HTML. |
| `websearch` | Busca en la web. |
| `shell` | Ejecuta un comando en la terminal del sistema. |
| `task` | Delega una tarea a un sub-agente especializado. |
| `skill` | Carga el contenido de una skill por nombre. |
| `reference` | Carga un archivo de referencia específico de una skill. |
| `help` | Muestra esta documentación de ayuda. |
| `check_email` | Verifica correos no leídos en un buzón IMAP. |
| `send_email` | Envía un email vía SMTP. |
| `list_dir` | Lista el contenido de un directorio. |

---

## Skills

Las skills son conjuntos de instrucciones y material de referencia que se cargan bajo demanda.

### Crear una skill

1. Crear una carpeta en `~/.config/synapseForge/skills/`.
2. Dentro de esa carpeta, crear `SKILL.md` con frontmatter YAML:
   - `name`: nombre de la skill.
   - `description`: descripción breve.
3. El cuerpo de `SKILL.md` es el contenido que se inyecta como contexto cuando el agente carga la skill.
4. Opcionalmente, crear una subcarpeta `references/` con archivos adicionales (catálogos, manuales, guías) que pueden cargarse individualmente con la herramienta `reference`.

---

## Configuración del modelo

Al primer arranque aparece una pantalla inicial de configuración (se puede saltar) donde se cargan las API keys de los proveedores cloud. Sin ningún provider disponible, el chat y los creadores quedan bloqueados hasta configurar uno.

El modelo y proveedor se configuran desde el panel de Configuración en la interfaz:

1. **Proveedor**: seleccionar entre los disponibles (Groq, Google Gemini, OpenRouter para nube; Ollama para local, si está instalado).
2. **Modelo**: elegir entre los modelos disponibles para ese proveedor.
3. Los cambios persisten en la base de datos SQLite y se aplican al siguiente mensaje.

El modelo se elige explícitamente: seleccioná proveedor + modelo y pulsá **Aplicar**.

Soportados:
- **Groq**: modelos de API (Llama, Qwen, etc.).
- **Google Gemini**: modelos de la API de Google (Gemini).
- **OpenRouter**: acceso unificado a múltiples proveedores de modelos.
- **Ollama**: modelos locales (opcional — solo aparece si Ollama está corriendo).

### API keys de los providers

Las API keys de los providers cloud (Groq, Google, OpenRouter) se configuran en el panel de Configuración, sección **Providers**. Cada key es opcional: si no se carga una key para un provider, ese provider no aparece como disponible. Las keys se guardan cifradas en la base de datos SQLite interna y nunca se muestran nuevamente en la interfaz después de guardarlas. Al guardar una key se valida contra la API del proveedor: si es inválida se rechaza; si es válida, el provider queda disponible de inmediato.

---

## Creación de skills, tools y agentes

Las interfaces de creación (skills, tools y agentes) permiten elegir, en su pantalla inicial, con qué modelo cloud se genera el elemento:

1. Seleccionar proveedor (solo providers cloud con key configurada).
2. Seleccionar modelo.
3. Pulsar **Aplicar**.

La selección es efímera: vive mientras la pestaña está abierta y se usa para esa tarea de creación. Si no se aplica ninguna selección, el sistema usa automáticamente uno de los providers cloud disponibles.

---

## Ventana de contexto

Controla cuántos turnos de la conversación se recuerdan al responder:
- `-1`: todo el historial.
- `N`: los últimos N turnos.

Se configura desde el panel de Configuración.

---

## Modo verbose

Cuando está activado, las herramientas y sub-agentes se muestran en la interfaz durante la conversación. Se activa/desactiva desde el panel de Configuración.

---

## Archivos de contexto (Instrucciones y documentos)

Se pueden subir archivos desde el panel de Configuración en la sección **Instrucciones y documentos**. Los archivos subidos se inyectan automáticamente en el system prompt del agente como contexto adicional.

Formatos soportados: PDF, Word, TXT, MD, CSV, JSON, YAML, XML, PY.

Son útiles para proveer información de referencia permanente: manuales de empresa, reglas de negocio, documentación técnica, etc.

---

## MCP (Model Context Protocol)

Los servidores MCP se configuran en `~/.config/synapseForge/mcp.json` como un array JSON:

```json
[
  {
    "label": "nombre-servidor",
    "transport": "stdio",
    "command": ["node", "/ruta/al/servidor/index.js"]
  }
]
```

- `stdio` para servidores locales, `http` (con `server_url`) para remotos.
- Sus tools se descubren automáticamente al iniciar y se exponen como tools del agente.
- Cada servidor tiene un timeout propio: si falla o no responde, se aísla (se marca en rojo en la interfaz) y el resto del sistema sigue funcionando.
- El estado de cada servidor se ve en la pestaña **MCP** de la configuración: `connected` (verde) o `failed` (rojo).

---

## Telegram

El sistema incluye un **bot de Telegram** que actúa como puente hacia el agente. El bot hace long-polling contra la Telegram Bot API y publica cada mensaje en el event bus; el frontend lo recibe vía `/api/events` y corre el mismo flujo de chat que si hubieras escrito en la web. Cuando el backend termina, envía la respuesta final de vuelta a Telegram.

### Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot (de BotFather). Si no está seteado, el bot queda deshabilitado. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Lista de `chat_id` autorizados (separados por coma). Solo estos pueden usar el bot. |

### Comandos

| Comando | Descripción |
|---------|-------------|
| `/sesiones` | Lista las sesiones (títulos). |
| `/usar` | Cambia a una sesión por título (pregunta y espera respuesta). |
| `/cancelar` | Cancela cualquier comando en espera. |
| `/nueva` | Crea un chat nuevo. |
| `/actual` | Muestra la sesión actual (solo el título). |
| `/contexto` | Muestra el uso de la ventana de contexto. |
| `/borrar` | Borra un chat (pregunta y espera respuesta). |
| `/detener` | Detiene la tarea en curso. |
| `/proveedor` | Cambia el proveedor (entre los disponibles; pregunta y espera respuesta). |
| `/modelo` | Cambia el modelo (lista y espera respuesta). |
| `/skills` | Lista skills (solo dev). |
| `/tools` | Lista tools (solo dev). |
| `/agentes` | Lista agentes (solo dev). |
| `/crear` | Crea skill, tool o colección RAG (solo dev; pregunta qué crear y guía el flujo). |
| `/archivo` | Envía un archivo por path (pregunta y espera respuesta). |
| `/agenda` | Lista las tareas programadas. |
| `/agendar` | Agrega una tarea programada (pregunta la tarea y el horario). |
| `/horario` | Cambia el horario de una tarea programada (pregunta y espera respuesta). |
| `/eliminar_tarea` | Elimina una tarea programada (pregunta y espera respuesta). |
| `/ayuda` | Muestra la ayuda. |

Los comandos que necesitan un argumento (`/usar`, `/borrar`, `/proveedor`, `/modelo`, `/crear`, `/archivo`, `/agendar`, `/horario`, `/eliminar_tarea`) usan un sistema de **pregunta y respuesta**: el bot muestra la lista de opciones y espera que el usuario responda con el texto. `/cancelar` (o la palabra "cancelar") aborta la espera.

### Funcionalidades

- **Notas de voz**: se transcriben localmente con faster-whisper y se envían como mensaje.
- **Adjuntos**: los archivos enviados con el botón de adjuntar de Telegram se descargan y procesan igual que el backend (extracción de texto).
- **Toggle en el frontend**: el header tiene un toggle para activar/desactivar el bot (persistido en SQLite).
- **Descarte de mensajes en cola**: al reactivar el bot, se descartan los mensajes que llegaron mientras estaba apagado (solo se procesan los nuevos).
- **Notificaciones de tareas programadas**: cada vez que se ejecuta una tarea programada, el resultado (éxito o error, con fecha y hora) se envía a Telegram **siempre**, independientemente de si el bot está habilitado para trabajar.

---

## Tareas programadas (Agenda)

El agente puede ejecutar tareas en horarios definidos por el usuario. La zona horaria se toma directamente del sistema, sin configuración.

### Configurar desde la interfaz

El header tiene un botón **Agenda** que abre el panel de tareas programadas, donde se puede:

1. **Agregar una tarea**: descripción de lo que debe hacer el agente, hora (`HH:MM`) y días de la semana.
2. **Editar el horario** de una tarea existente (hora y días).
3. **Eliminar** tareas.
4. **Guardar**: valida todas las tareas antes de confirmar (descripción presente, horario válido, al menos un día).

Las tareas se persisten en la base de datos SQLite interna.

### Ejecución y notificaciones

- El backend revisa periódicamente si hay tareas que corresponde ejecutar y las corre usando el modelo y proveedor seleccionados, como si el usuario las hubiera pedido desde la interfaz.
- Cada ejecución queda registrada (tarea, estado, fecha y hora) y genera dos notificaciones:
  - En la **interfaz**, mediante la campanita del header: indica si la tarea terminó con éxito o falló, con fecha y hora.
  - En **Telegram**, con el mismo detalle, siempre (aunque el bot esté deshabilitado para trabajar).

---

## RAG (knowledge)

El sistema soporta **colecciones RAG** (bases de conocimiento vectoriales con ChromaDB) que se crean desde la interfaz de creación (pestaña **RAG**). Cada colección vive en `~/.config/synapseForge/knowledge/` y se construye subiendo archivos y URLs, que se procesan y almacenan como documentos vectoriales.

- Los embeddings se calculan en la nube vía OpenRouter (`liquid/lfm-2.5-embedding-350m:free`).
- **Requiere una API key de OpenRouter** cargada en **Providers**: sin ella, la sección de fuente de conocimiento queda deshabilitada (el resto de la app funciona normalmente).
- Las colecciones se listan y consultan desde la interfaz.
- Sirven para darle al agente acceso a conocimiento específico del dominio (documentos, manuales, bases de datos de texto) mediante búsqueda semántica.

---

**Ante cualquier duda, el usuario puede consultar la documentación del agente en la sección `docs`**.

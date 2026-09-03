<p align="center">
  <img src="../../src/logo_empresa.png" alt="Logo" width="150">
</p>

---

<h1 align="center">Módulo Agent</h1>

---

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0" />
  </a>
</p>

---

<h3 align="center">Agente LLM con loop iterativo, herramientas nativas y persistencia SQLite</h3>

---

## Descripción

El módulo **Agent** es el núcleo del asistente conversacional. Implementa un bucle `while(true)` que itera con el LLM usando detección nativa de tool calls, ejecuta las herramientas, persiste cada mensaje en SQLite y gestiona el contexto con compactación automática. Soporta proveedores cloud (Groq, Google Gemini, OpenRouter) y local (Ollama).

### ✨ Características Principales

- **Loop iterativo nativo**: Llama al LLM en un `while(true)` — si responde con `tool_calls`, las ejecuta y continúa; si responde con contenido, lo entrega y termina.
- **Persistencia SQLite**: Cada mensaje, tool call y resultado se guarda automáticamente en `agent_db/agent.db`.
- **Contexto compactable**: Gestión inteligente de tokens con estrategias configurables (ask, cod, original) y límite de turnos.
- **Soporte multi-proveedor**: Funciona con Groq, Google Gemini, OpenRouter (cloud) y Ollama (local) sin cambiar la lógica del loop.
- **Permisos y prompts**: Resolución dinámica de herramientas y skills desde archivos markdown de agente.
- **Configuración MCP**: `mcp.json` en `~/.config/synapseForge/` para servidores MCP (Model Context Protocol).

---

## ¿Qué resuelve?

- **Persistencia de conversaciones**: No pierde el historial entre sesiones — todo queda en SQLite.
- **Ejecución autónoma de herramientas**: El agente decide qué herramientas usar según la conversación, sin intervención manual.
- **Contexto ajustable**: Evita sobrecargar el LLM con historial innecesario mediante compactación automática.
- **Separación de responsabilidades**: Cada módulo (loop, sesión, contexto, configuración, permisos) tiene una función específica y desacoplada.
- **Configuración MCP persistente**: Servidores MCP se guardan en `mcp.json` y sobreviven a reinicios.
- **Modelo/Proveedor/Contexto persistidos en SQLite**: Selección de modelo, proveedor y ventana de contexto se guardan en la tabla `config_kv` y se restauran al arrancar.

---

## Estructura del producto

### 1. `loop.py` — Bucle principal del agente

Implementa el `while(true)` orquestador:
1. Crea o recupera la sesión en SQLite.
2. Carga el historial de la conversación.
3. Construye el system prompt (base + skills).
4. Resuelve las herramientas disponibles.
5. Itera: llama al LLM → si hay `tool_calls` las ejecuta → si hay contenido lo emite como SSE y termina.
6. Persiste cada mensaje en SQLite.

Expone el método `run(session_id, message)` que retorna un `AsyncGenerator` de eventos SSE (`chunk`, `tool_call`, `tool_result`, `session_title`, `done`).

### 2. `session.py` — Persistencia SQLite

Maneja toda la interacción con la base de datos SQLite:
- Creación y recuperación de sesiones.
- Guardado y carga de mensajes con tool calls y resultados.
- Almacenamiento de configuración clave/valor (`config_kv`): modelo seleccionado, proveedor, ventana de contexto.
- Path de la DB: `backend/agent/agent_db/agent.db` (relativo al project root).

### 3. `utils/config.py` — Configuración del entorno

Configuración del loop vía variables de entorno (`.env`):
- `COMPACTION_TRIGGER_TOKENS`, `COMPACTION_STRATEGY`, `COMPACTION_TAIL_TURNS`, etc.
- Dataclasses `CompactionConfig` y `SessionContext` para parámetros de compactación.

### 4. `agent.py` — Clase principal del agente

Centraliza la interacción con los proveedores LLM (Groq, Google Gemini, OpenRouter u Ollama local):
- Selección del proveedor según la configuración persistida en DB (nunca variables de entorno).
- Streaming de respuestas con detección nativa de tool calls.
- Gestión de la instancia de herramientas (`Tools`).
- Atributos runtime: `provider` (LOCAL/API), `_resolved_model` (modelo activo).

### 5. `tools.py` — Registro de herramientas

Define el catálogo completo de herramientas del agente:
- Métodos nativos (parser, websearch, webfetch, etc.).
- Carga dinámica de tools externas desde `~/.config/synapseForge/tools/`.
- Construcción del esquema function-calling para el LLM.
- Validación y ejecución de tool calls.
- Integración MCP: `execute_mcp_tool` expone herramientas de servidores MCP como tools nativas.

### 6. `permissions.py` — Permisos y prompts de agente

Resuelve en tiempo de ejecución:
- Herramientas permitidas para el agente (`get_tool_permissions`).
- Skills habilitadas (`get_skill_permissions`).
- Contenido del system prompt (`get_agent_prompt`).
- Filtrado de herramientas/skills según el agente activo.
- Permisos del agente principal (router) desde `config.yaml` (ver `loop.py`).

### 7. `utils/contract.py` — Contratos de respuesta

Define los formatos estándar de respuesta para todas las herramientas del agente:
- `make_success_response` / `make_error_response` para respuestas unificadas.
- Dataclasses `ContractResponse` y `UsageReport` para tipado estricto.
- Validación de estructura de respuesta.

### 8. `utils/` — Utilidades auxiliares

Contiene módulos de soporte genéricos para el funcionamiento del agente:
- `config.py` — Configuración del loop vía variables de entorno.
- `config_dir.py` — Gestión del directorio `~/.config/synapseForge/`.
- `contract.py` — Contratos de respuesta.
- `clean_memory.py` — Liberación de modelos de GPU/CPU.
- `model_resolver.py` — Resolución y validación del modelo activo.
- `model_catalog.py` — Catálogo de modelos sincronizado desde models.dev.
- `provider_keys.py` — Gestión de API keys (cifrado Fernet en SQLite).
- `skill_loader.py` — Carga y formateo de skills para el system prompt.
- `skills_helpers.py` — Helpers de evaluación y creación de skills.
- `email_parser.py` — Parseo de correos electrónicos (headers, body, adjuntos).
- `mcp_helper.py` — Integración con MCP (Model Context Protocol).
- `vector_db.py` — Wrapper de ChromaDB (RAG y memoria de largo plazo).
- `rag_helpers.py` — Helpers de RAG (indexación y consulta).
- `chunking.py` — División de documentos en chunks.
- `loop_helpers.py` — Helpers del loop (ejecución de tools, prompts).
- `scheduler_helpers.py` — Helpers de tareas programadas.
- `create_helpers.py` — Helpers de creación vía LLM (skills, tools, agentes).
- `tools_helpers.py` — Helpers de tools externas.
- `agent_helpers.py` — Helpers de los endpoints AgentInfo.
- `subagent_logger.py` — Logging de sub-agentes.
- `error_logger.py` — Registro de errores en `error_log`.

### 9. `prompts/` — Prompts del sistema

Almacena los prompts del agente en formato markdown:
- `system_prompt.md` — Prompt base del router.
- `mandatory.md` — Reglas `## MANDATORY:` inyectadas al final del system prompt de todos los agentes.
- `help.md` — Documentación interna para la tool `help`.
- `title.md` — Generación de títulos de sesión.
- `generar_skill.md`, `generar_tool.md`, `generar_agent.md` — Prompts de creación vía LLM.
- `iterar_skill.md`, `iterar_tool.md`, `iterar_agent.md` — Prompts de iteración.
- `evaluar_skills.md`, `explicar_skill.md` — Prompts auxiliares.

### 10. `agent_db/` — Base de datos SQLite

Directorio que contiene el archivo `agent.db` con las tablas:
- `sessions` — Metadatos de cada conversación.
- `messages` — Historial de mensajes con tool calls y resultados.
- `config_kv` — Configuración persistente (modelo, proveedor, turnos de contexto).
- `error_log` — Registro de excepciones del backend (session_id, turn_number, exception, source, created_at).

El esquema se crea de forma idempotente en `ddl_setup.py` (`CREATE TABLE IF NOT EXISTS`).

---

## Configuración del usuario

El agente utiliza **dos fuentes de configuración** separadas:

### 1. `mcp.json` — Servidores MCP

```
~/.config/synapseForge/mcp.json
```

En Windows: `%USERPROFILE%\.config\synapseForge\mcp.json`

Este archivo almacena **exclusivamente** la configuración de servidores MCP (Model Context Protocol) como un **array** directo. Se gestiona mediante `backend/agent/config_dir.py` (funciones `load_mcp_servers()` / `save_mcp_servers()`). La conexión se realiza con el SDK oficial `mcp` (`mcp_helper.py`), con timeout por servidor y health check: si un servidor falla, se aísla y el resto del sistema sigue funcionando.

#### Estructura de `mcp.json`

```json
[
  {
    "label": "nombre-servidor",
    "transport": "stdio",
    "command": ["node", "/ruta/al/servidor/index.js"],
    "environment": {
      "API_KEY": "valor"
    }
  }
]
```

#### Campos soportados por cada servidor

| Campo | Tipo | Descripción | Default |
|-------|------|-------------|---------|
| `label` | string | Identificador único del servidor | — |
| `transport` | string | `"stdio"` (local) o `"http"` (remoto) | `"stdio"` |
| `command` | string o list | Comando o lista de comandos para ejecutar | — |
| `args` | list | Argumentos adicionales (solo si command es string) | `[]` |
| `environment` | object | Variables de entorno para el subproceso | `{}` |
| `server_url` | string | URL del servidor HTTP/SSE | — |
| `headers` | object | Cabeceras HTTP para servidores remotos | `{}` |
| `disabled` | bool | `true` para deshabilitar sin borrar | `false` |

#### Ejemplos

**Servidor stdio local (como NotebookLM):**

```json
[
  {
    "label": "notebooklm-local",
    "transport": "stdio",
    "command": ["node", "D:/.mcp/notebooklm-mcp/dist/index.js"]
  }
]
```

**Servidor stdio con variables de entorno:**

```json
[
  {
    "label": "trello-server",
    "transport": "stdio",
    "command": ["D:/.mcp/Scripts/python.exe", "-m", "trello_mcp"],
    "environment": {
      "TRELLO_API_KEY": "tu-api-key",
      "TRELLO_TOKEN": "tu-token"
    }
  }
]
```

**Servidor HTTP/SSE remoto:**

```json
[
  {
    "label": "groq-mcp",
    "transport": "http",
    "server_url": "https://api.groq.com/mcp/server/id",
    "headers": {
      "Authorization": "Bearer tu-token"
    }
  }
]
```

> **Nota**: `model`, `provider`, `temperature`, `top_p`, `context_turns`, `ui_prefs` **NO** están en `mcp.json`. Se gestionan vía endpoints del frontend y se persisten en SQLite (`config_kv`).

---

### 1b. `AGENT.md` — Comportamiento general

`AGENT.md` (si existe en `~/.config/synapseForge/agents/`) se inyecta como sección `## Behavior` en el system prompt de **todos** los agentes (router y sub-agentes), **antes** de `## MANDATORY:`. No reemplaza el system prompt: `system_prompt.md` es siempre la base del router, y cada sub-agente usa su propio `.md`. Sirve para comportamiento general del proyecto (compatibilidad con opencode/claude code).

### 1c. `config.yaml` — Permisos del router

El agente principal (router) no tiene tools ni skills directas por defecto — solo `task`. Si existe `~/.config/synapseForge/config.yaml`, sus permisos se toman de ahí (misma lógica que el frontmatter de los agentes):

```yaml
permissions:
  tool:
    read: allow
  skill:
    mi_skill: allow
  task:
    explorador: allow
```

- Si el archivo **no existe** → el router queda solo con `task`.
- Si existe → usa **solo** los permisos explícitos del yaml.
- `task` está **siempre** disponible: si el yaml no lo lista, se permite para todos los sub-agentes; si lo lista, solo para los indicados.

---

### 2. Configuración runtime (SQLite `config_kv`)

Los siguientes parámetros se seleccionan desde el **frontend** y se guardan en la tabla `config_kv` de SQLite:

| Clave | Descripción | Endpoint |
|-------|-------------|----------|
| `selected_model` | Modelo activo (ej. `qwen/qwen3.6-27b`, `llama3.2:3b`) | `POST /config/models/select` |
| `selected_provider` | Proveedor activo: `LOCAL` (Ollama) o `API` (Groq, Google Gemini, OpenRouter) | `POST /config/models/select` |
| `context_window_turns` | Turnos de historial a mantener (`-1` = todos) | `POST /config/context-window` |

Se cargan automáticamente al inicio vía `load_persisted_config()` en `backend/routes/config.py` y se aplican al agente singleton.

> **Modelo por defecto**: no existe. El usuario elige proveedor + modelo y aplica (`POST /config/models/select`). Si hay un modelo persistido de una sesión anterior, se respeta.

#### Flujo de selección en el frontend

1. **Inicio app** → `GET /config/providers` → lista proveedores disponibles (Ollama si `ollama list` responde; cada provider cloud solo si tiene key válida guardada en la DB).
2. Usuario elige proveedor → `GET /config/models?provider=LOCAL|API` → lista modelos de ese proveedor.
3. Usuario elige modelo → `POST /config/models/select` con `{"model": "...", "provider": "LOCAL|API"}` (donde `API` cubre Groq, Google Gemini y OpenRouter).
4. Opcional: `POST /config/context-window` con `{"max_turns": 10}`.

---

## Skills (habilidades del agente)

Las skills se cargan desde el directorio de configuración del usuario:

```
~/.config/synapseForge/skills/
```

En Windows: `%APPDATA%\synapseForge\skills\`

### Estructura de una skill

Cada skill es una subcarpeta con un archivo `SKILL.md`:

```
skills/
├── plumbing-expert/
│   └── SKILL.md
├── electrical-expert/
│   └── SKILL.md
└── welding/
    └── SKILL.md
```

### Formato `SKILL.md`

```markdown
---
description: "Experto en instalaciones de plomería residencial y comercial. Cálculo de caudales, dimensionamiento de tuberías, selección de materiales."
triggers: "plomería, tuberías, caudal, presión, desagüe, agua, sanitarios"
---

# Plomería Experta

## Comportamiento
Cuando el usuario consulte sobre instalaciones de agua, desagües, sanitarios o calefacción por agua, actúa como plomero certificado...

## Reference Guide
### Tablas de referencia
- **Diámetros estándar**: 1/2", 3/4", 1", 1 1/4", 1 1/2", 2"
- **Materiales**: Cobre, PEX, PVC, CPVC, Polipropileno
...
```

### Carga automática

- Al iniciar el loop, `skill_loader.py` escanea `~/.config/synapseForge/skills/`.
- Lee el frontmatter YAML (`description`, `triggers`).
- Filtra según permisos del agente activo (`permissions.py`).
- Inyecta la sección formateada en el system prompt.

### Ejemplo de skill inyectada en el prompt

```
### plumbing-expert
- **Descripción**: Experto en instalaciones de plomería residencial y comercial. Cálculo de caudales, dimensionamiento de tuberías, selección de materiales.
- **Triggers**: plomería, tuberías, caudal, presión, desagüe, agua, sanitarios
```

---

## Tools (herramientas)

El agente distingue tres tipos de herramientas:

### 1. Tools nativas (en `tools.py`)

Definidas como métodos de la clase `Tools`. Incluyen:
- `read`, `write`, `edit`, `glob`, `grep`, `list_dir` — Operaciones de archivos.
- `websearch`, `webfetch` — Búsqueda y fetch web.
- `rag`, `search_memory` — Consulta de colecciones RAG y memoria de largo plazo.
- `check_email`, `send_email` — Correo electrónico (IMAP/SMTP).
- `shell` — Ejecución de comandos en la terminal.
- `skill`, `reference` — Carga de skills y archivos de referencia.
- `help` — Documentación interna de las tools.
- `task` — Delegación a sub-agentes.
- `execute_mcp_tool` — Ejecución de herramientas MCP.

### 2. Tools externas (en `~/.config/synapseForge/tools/`)

Archivos `.py` sueltos que el agente descubre al inicio:

```
tools/
├── mi_herramienta.py
└── otra_herramienta.py
```

Cada tool externa debe cumplir:
- La **primera línea del docstring del módulo** es la descripción que el LLM usa para decidir si invocarla.
- La función principal debe ser `async` y tener el **mismo nombre que el archivo** (sin `.py`).
- Debe devolver el contrato unificado `{status, message, data, usage}`.

**Ejemplo `tools/calculadora.py`:**
```python
"""Realiza operaciones matemáticas básicas."""

async def calculadora(expresion: str) -> dict:
    try:
        resultado = eval(expresion, {"__builtins__": {}}, {})
        return {"status": "success", "data": {"resultado": resultado}}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### 3. Tools MCP

Los servidores MCP configurados en `mcp.json` exponen sus herramientas automáticamente. `tools.py` las descubre vía `mcp_helper.py` (usando el SDK oficial `mcp`) y las registra como tools nativas con prefijo `mcp_<server>_<tool>`. El agente las invoca igual que cualquier otra tool. Cada servidor tiene un timeout propio: si falla, se aísla y el resto del sistema sigue funcionando.

### Carga y registro

- `tools.py` escanea `~/.config/synapseForge/tools/` al instanciar `Tools`.
- Valida que cada archivo tenga los 4 atributos requeridos.
- Construye el esquema function-calling para el LLM.
- Las tools externas aparecen junto a las nativas y MCP en la lista disponible.

### Ejecución de tools (igual para todos los proveedores)

**El flujo es idéntico para todos los proveedores:**

1. `agent.llm_streaming()` recibe `tools` (lista de esquemas JSON Schema).
2. **Groq / Google Gemini / OpenRouter**: `client.chat.completions.create(tools=..., tool_choice="auto", stream=True)`
3. **Ollama**: `ollama_client.chat(tools=..., stream=True)`
4. Todos los proveedores devuelven `tool_calls` en streaming.
5. `llm_streaming` **normaliza** los tool_calls de todos los formatos a:
   ```python
   {"id": "call_xxx", "name": "tool_name", "args": {"param": "value"}}
   ```
   Y yield `{'type': 'tool_calls_detected', 'content': [normalized_tool_calls]}`.
6. `loop.py` recibe el evento, itera cada `tc` y llama:
   ```python
   result_data = await execute_tool(agent, tc)
   ```
7. `execute_tool` (en `loop_helpers.py`) invoca:
   ```python
   await agent.tools._execute_tool(tc["name"], **tc["args"])
   ```
8. `_execute_tool` en `tools.py` despacha a nativa, externa o MCP — **solo recibe `name` y `**kwargs` (los args del tool_call)**.

> **Los parámetros LLM (`temperature`, `top_p`, `max_tokens`, `model`) se pasan SOLO a `llm_streaming()` — NUNCA a las tools.**

---

## Instalación

1. **Clonar el repositorio**

```bash
>>> git clone https://github.com/<owner>nombre_owner</owner>/<repo>nombre_repo</repo>.git
>>> cd <repo>nombre_repo</repo>
```

2. **Crear y activar un entorno virtual** (recomendado Python 3.11+)

```bash
>>> py -3.11 -m venv .<repo>nombre_repo</repo>
>>> .\.<repo>nombre_repo</repo>\Scripts\Activate.ps1
```

3. **Instalar dependencias**

```bash
>>> pip install -r requirements.txt
```

**Notas:**
- La base de datos SQLite se crea automáticamente en `backend/agent/agent_db/agent.db` al iniciar el agente.
- El directorio de configuración `~/.config/synapseForge/` (skills, tools, agents, mcp.json, config.yaml) se crea automáticamente al arrancar.
- Las variables de entorno se cargan desde `.env` en la raíz del proyecto.
- No requiere servicios externos — SQLite es parte de la stdlib de Python.

---

## Estructura del módulo

```plaintext
backend/agent/
│
├─ __init__.py              # Inicialización del paquete
├─ agent.py                 # Clase principal del agente (LLM provider)
├─ loop.py                  # Bucle while(true) del agente
├─ session.py               # Persistencia SQLite
├─ ddl_setup.py             # Creación idempotente de tablas SQLite
├─ permissions.py           # Resolución de permisos y prompts
├─ tools.py                 # Registro y ejecución de herramientas
├─ agent_db/                # Base de datos SQLite
│   └─ agent.db
├─ prompts/                 # Prompts del sistema
│   ├─ system_prompt.md     # Prompt base del router
│   ├─ help.md              # Documentación interna para tool help
│   ├─ title.md             # Prompt para generar títulos de sesión
│   ├─ mandatory.md         # Reglas ## MANDATORY: inyectadas a todos los agentes
│   ├─ generar_skill.md     # Prompt para crear skills con LLM
│   ├─ generar_tool.md      # Prompt para crear tools con LLM
│   ├─ generar_agent.md     # Prompt para crear agentes con LLM
│   ├─ iterar_skill.md      # Prompt para iterar skills
│   ├─ iterar_tool.md       # Prompt para iterar tools
│   ├─ iterar_agent.md      # Prompt para iterar agentes
│   ├─ evaluar_skills.md    # Prompt para evaluar skills existentes
│   └─ explicar_skill.md    # Prompt para explicar skills
├─ utils/                   # Utilidades auxiliares
│   ├─ agent_helpers.py     # Helpers de endpoints AgentInfo
│   ├─ chunking.py          # División de documentos en chunks
│   ├─ clean_memory.py      # Liberación de modelos
│   ├─ config.py            # Configuración vía entorno
│   ├─ config_dir.py        # Gestión del directorio ~/.config/synapseForge/
│   ├─ contract.py          # Contratos de respuesta
│   ├─ create_helpers.py    # Helpers de creación vía LLM
│   ├─ email_parser.py      # Parseo de correos electrónicos
│   ├─ error_logger.py      # Registro de errores
│   ├─ loop_helpers.py      # Helpers del loop
│   ├─ mcp_helper.py        # Integración MCP
│   ├─ model_catalog.py     # Catálogo de modelos (models.dev)
│   ├─ model_resolver.py    # Resolución del modelo activo
│   ├─ provider_keys.py     # Gestión de API keys
│   ├─ rag_helpers.py       # Helpers RAG
│   ├─ scheduler_helpers.py # Helpers de tareas programadas
│   ├─ skill_loader.py      # Carga de skills
│   ├─ skills_helpers.py    # Helpers de skills
│   ├─ subagent_logger.py   # Logging de sub-agentes
│   ├─ tools_helpers.py     # Helpers de tools externas
│   └─ vector_db.py         # Wrapper ChromaDB
└─ README.md
```

---

## Flujo principal

El agente sigue un ciclo iterativo:

1. **Inicio**: Se crea o recupera la sesión en SQLite.
2. **Carga**: Se carga el historial de mensajes desde la DB.
3. **Config runtime**: Se cargan `selected_model`, `selected_provider`, `context_window_turns` desde `config_kv`.
4. **Prompt**: Se construye el system prompt (base + skills del agente activo).
5. **Tool resolution**: Se resuelven las herramientas disponibles según permisos (nativas + externas + MCP).
6. **Loop** (`while True`):
   a. Se llama al LLM con `messages` + `tools` vía `agent.llm_streaming()`.
   b. `llm_streaming` normaliza tool_calls de todos los proveedores a `{"id", "name", "args"}` y yield `tool_calls_detected`.
   c. `loop.py` ejecuta cada tool vía `execute_tool(agent, tc)` → `agent.tools._execute_tool(name, **args)`.
   d. Resultados se agregan como `role: "tool"` y continúa el loop.
   e. Si el LLM devuelve contenido sin tool_calls → se emite como `chunk` SSE y se cierra el loop.
7. **Persistencia**: Cada mensaje se guarda en SQLite.
8. **Eventos SSE**: `chunk`, `tool_call`, `tool_result`, `subagent_call`, `subagent_result`, `session_title`, `done`.

---

## Stack Tecnológico

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003b57?logo=sqlite&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-API-f97316?logo=groq&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-API-4285F4?logo=google&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter-API-8b5cf6?logo=openrouter&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local-000000?logo=ollama&logoColor=white)

---

## Licencia

Este proyecto está licenciado bajo los términos especificados en el archivo [LICENSE](./LICENSE) ubicado en la raíz del repositorio.

---

Copyright (c) 2026 <legal>nombre_legal_empresa</legal>

---
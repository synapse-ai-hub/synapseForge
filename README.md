<p align="center">
  <img src="https://github.com/synapse-ai-hub/sources/raw/main/logo.png" alt="Logo" width="150">
</p>

---

<h1 align="center">synapseForge</h1>

---

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0" />
  </a>
  <a href="https://pypi.org/project/synapseforge/">
    <img src="https://img.shields.io/pypi/v/synapseforge" alt="PyPI" />
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white" alt="Python 3.12+" />
  </a>
</p>

---

<h3 align="center">CLI + Framework + Template para crear y distribuir proyectos de agentes IA full-stack</h3>

---

## Descripción

**synapseForge** es un paquete PyPI que provee un CLI para scaffoldear y distribuir proyectos de agentes IA desde cero. Incluye:

1. **CLI** (`synapseforge init`, `synapseforge launch`, `synapseforge colors`, `synapseforge run`) — scaffolding con GUI tkinter + build de distribución + editor de colores en vivo + servidor de desarrollo.
2. **Framework de agentes** (`backend/agent/`) — AgentLoop, Tools Registry (nativas + externas + MCP), Sessions (SQLite WAL), Permissions, Skills, RAG, MCP integration.
3. **Template de proyecto** embebido (`pipeline/template.zip`) — backend FastAPI + frontend React/Vite/TypeScript + estructura completa.
4. **Docker** — `Dockerfile` multi-stage + `docker-compose.yml` para despliegue en contenedor.

El usuario instala el paquete, ejecuta `synapseforge init`, completa los datos en la GUI, y obtiene un proyecto funcional con venv, dependencias, logo, `.ico`, colores, y placeholders reemplazados.

---

### ✨ Características Principales

- **`synapseforge init`**: Scaffolding completo desde template embebido con **GUI tkinter** (3 tabs: Proyecto, Logos, Colores) — estructura, venv, logo, .ico, placeholders, colores.
- **`synapseforge launch`**: Build de distribución autocontenido con PyInstaller + frontend compilado + Python embebido + launcher nativo → `.zip` listo para entregar.
- **`synapseforge colors`**: Editor GUI para modificar `frontend/public/colors.json` en caliente — recarga el navegador y ves los cambios sin rebuild.
- **`synapseforge run`**: Levanta `uvicorn --reload` (backend) + `npm run dev` (frontend) + abre el navegador. Ctrl+C mata ambos.
- **Pipeline de 11 pasos**: Input GUI → verificación de modelos Ollama (instala `qwen3.5:4b` si falta) → template → venv → pip install → npm install → logos → `.ico` → colores → config → placeholders XML en todo el proyecto.
- **Sistema de colores dual**: Build-time (placeholders XML en `config/replace.json`) + Runtime (`frontend/public/colors.json` cargado en `main.tsx`). 4 variables configurables, el resto fijas.
- **Framework de agentes completo**: AgentLoop (while True → LLM → tools → continue), Tools Registry (nativas + externas dinámicas + MCP), SessionManager (SQLite WAL), Permissions (allow/deny/ask + wildcards + `config.yaml` para el router), Skills (SKILL.md + references), MCP (SDK oficial `mcp`, stdio/HTTP + timeout + health check).
- **RAG (base de conocimiento)**: Colecciones vectoriales en ChromaDB con modelo de embeddings local (SentenceTransformer). Subida de archivos (PDF, Word, TXT, MD, CSV, XLSX, JSON, XML, YAML, PY) y páginas web (fetch + chunk + guardado de URL/HTML). Chunking con overlap inteligente y búsqueda por similitud coseno. Tool nativa `rag` con permisos por colección en el frontmatter del agente.
- **Creación de skills vía LLM**: Interfaz standalone (`skill.html`) y control remoto por Telegram. Entrevista iterativa + agente creador con tools → genera `SKILL.md` + referencias.
- **Archivos de contexto**: Subida de PDF, Word, TXT, MD, CSV, JSON, YAML, XML, PY → extracción de texto → inyección en system prompt del agente (instrucciones y documentos).
- **Métricas de uso**: Endpoints para sesiones, tools, errores y overview. Dashboard en frontend (`MetricsModal`).
- **Extracción de texto robusta**: Módulo compartido `file_text_extractor.py` soporta texto plano, Markdown, CSV, JSON, XML, YAML, Python, DOCX, DOC, XLSX, XLS, PDF. OCR **best-effort**: si falla por deps faltantes, devuelve lo que extrajo pdfminer.
- **Modo desktop app**: Heartbeat cada 10s desde frontend → watchdog en backend (3 min sin heartbeat = exit). Endpoint `/api/shutdown` para botón "Salir".
- **Configuración de usuario** (`~/.config/synapseForge/`): tools personalizadas, skills, agentes con permisos, `AGENT.md` (comportamiento general → `## Behavior`), `config.yaml` (permisos del router), servidores MCP (`mcp.json`), colecciones RAG (`knowledge/`).
- **Telegram como control remoto**: Bot que emite eventos al event bus; el frontend ejecuta el mismo flujo de chat. Comandos de sesión, modelo/proveedor, y creación de skills/RAG (abre la ventana correspondiente en el frontend).
- **Docker**: `Dockerfile` multi-stage (Node 20 build → Python 3.12 slim runtime) + `docker-compose.yml` con `VITE_MODE=prod`.

---

## ¿Qué resuelve?

- **Scaffolding repetitivo**: Un solo comando crea el proyecto completo con la estructura estándar de todos los proyectos SYNAPSE.
- **Configuración centralizada**: GUI interactiva que reemplaza todos los placeholders XML del proyecto (empresa, cliente, colores, logo, etc.).
- **Branding automatizado**: Copia de logos + generación de `.ico` (16×16 a 256×256) + extracción de paleta de colores desde la imagen.
- **Distribución sin dependencias**: Build autocontenido listo para entregar al cliente — incluye Python embebido, frontend estático, launcher nativo.

---

## Estructura del repositorio

```plaintext
synapseForge/
│
├─ synapseforge/                 # Paquete Python — CLI instalable via pip
│  ├─ __init__.py                #   __version__
│  ├─ __main__.py                #   python -m synapseforge
│  ├─ cli/
│  │  ├─ __init__.py
│  │  └─ main.py                 #   Parser CLI: init | launch | colors | run
│  └─ tk/                        #   GUIs tkinter
│     ├─ __init__.py
│     ├─ init_app.py             #   GUI 3 tabs para synapseforge init
│     ├─ colors_app.py           #   GUI editor colors.json para synapseforge colors
│     ├─ logo.ico
│     └─ logo.png
│
├─ pipeline/                     # Pipeline — código fuente de init y launch
│  ├─ __init__.py
│  ├─ template.zip               #   Template del proyecto comprimido (embebido)
│  ├─ init/                      #   Init: input, template, venv, config, logo, placeholders
│  │  ├─ __init__.py
│  │  ├─ __main__.py
│  │  ├─ main.py                 #   Orquestador (run(target_dir, config=None))
│  │  ├─ input_handler.py        #   GUI tkinter
│  │  ├─ template_handler.py     #   Descarga/extrae template.zip
│  │  ├─ venv_handler.py         #   Crea venv .{repo}/
│  │  ├─ config_handler.py       #   Guarda config/replace.json + frontend/public/colors.json
│  │  ├─ logo_handler.py         #   Copia logos + genera .ico con Pillow
│  │  └─ placeholder_handler.py  #   Reemplaza tags XML en todo el proyecto
│  └─ launch/                    #   Launch: PyInstaller, npm build, zip
│     ├─ __init__.py
│     ├─ forge.py                #   Orquestador 7 pasos
│     ├─ requirements.txt
│     ├─ .cache/                 #   Caché: Python embed + get-pip.py (descargados)
│     ├─ templates/
│     │  └─ launcher.py          #   Template launcher (abre browser, usa python embebido)
│     └─ README.md
│
├─ backend/                      # Fuente del template — backend FastAPI
│  ├─ __init__.py
│  ├─ main.py                    #   FastAPI app, CORS, lifespan, routers, health, shutdown, heartbeat, SPA static
│  ├─ instances.py               #   Singletons: agent, session_manager
│  ├─ event_bus.py               #   Event bus (SSE) para Telegram ↔ Frontend
│  ├─ routes/
│  │  ├─ __init__.py
│  │  ├─ chat.py                 #   POST /api/chat → SSE stream (AgentLoop)
│  │  ├─ create.py               #   POST /api/create/skill → SSE (creación de skills vía LLM)
│  │  ├─ config.py               #   Providers, models, context window, verbose, skills/tools/agents/mcp
│  │  ├─ sessions.py             #   CRUD sesiones, mensajes, títulos
│  │  ├─ context_files.py        #   CRUD archivos de contexto (instrucciones/documentos)
│  │  ├─ metrics.py              #   Métricas: overview, sessions, tools, errors
│  │  ├─ rag.py                  #   Colecciones RAG: create/list/delete, upload files, add URL
│  │  ├─ agent_items.py          #   Listar/eliminar skills, tools, agents, MCP, colecciones RAG
│  │  ├─ events.py               #   GET /api/events → SSE del event bus
│  │  ├─ telegram.py             #   Status/toggle del bot + active-session
│  │  ├─ file_text_extractor.py  #   Extracción texto: PDF, DOCX, XLSX, TXT + OCR fallback
│  │  └─ README.md
│  └─ agent/                     #   Framework de agentes
│     ├─ __init__.py
│     ├─ agent.py                #   Agent class (Groq/Ollama, streaming SSE, tool calling)
│     ├─ tools.py                #   Registry: nativas + externas (~/.config/synapseForge/tools/) + MCP
│     ├─ loop.py                 #   AgentLoop: while True → LLM → tool_calls → execute → continue
│     ├─ loop_helpers.py         #   build_system_prompt, fetch_context_window_turns, execute_tool
│     ├─ session.py              #   SessionManager (SQLite WAL, historial, config_kv, error_log)
│     ├─ permissions.py          #   Permisos por agente (tool/skill/task/rag allow/deny/ask + wildcards)
│     ├─ ddl_setup.py            #   Inicialización tablas SQLite
│     ├─ agent_db/               #   SQLite runtime (se crea al iniciar)
│     ├─ prompts/
│     │  ├─ system_prompt.md     #   Prompt base del router
│     │  ├─ help.md              #   Documentación interna para tool `help`
│     │  ├─ title.md             #   Prompt para generar títulos de sesión
│     │  ├─ generar_skill.md     #   Prompt para crear skills con LLM
│     │  ├─ evaluar_skills.md    #   Prompt para evaluar skills existentes
│     │  ├─ explicar_skill.md    #   Prompt para explicar una skill
│     │  ├─ iterar_skill.md      #   Prompt para la entrevista de creación de skills
│     │  └─ mandatory.md         #   Reglas `## MANDATORY:` inyectadas a todos los agentes
│     └─ utils/
│        ├─ __init__.py
│        ├─ agent_helpers.py     #   Listados de skills, tools, agents, MCP
│        ├─ chunking.py          #   Chunking con overlap inteligente (RAG)
│        ├─ clean_memory.py      #   Liberación modelos GPU/CPU
│        ├─ config.py            #   Config de runtime
│        ├─ config_dir.py        #   Descubrimiento ~/.config/synapseForge/
│        ├─ contract.py          #   ContractResponse, UsageReport, StreamingResponse
│        ├─ email_parser.py      #   Parseo emails (headers, body, adjuntos)
│        ├─ error_logger.py      #   Log de errores a SQLite (error_log table)
│        ├─ loop_helpers.py      #   Helpers del loop (system prompt, contexto, tools)
│        ├─ mcp_helper.py        #   MCP con SDK oficial (mcp), stdio/HTTP, timeout, health check
│        ├─ model_resolver.py    #   Resolución y validación modelo activo
│        ├─ skill_loader.py      #   Carga y formateo SKILL.md para system prompt
│        ├─ skill_creator/       #   Creación de skills vía LLM (evaluación + generación)
│        ├─ subagent_logger.py   #   Logger custom nivel SUBAGENT
│        └─ vector_db.py         #   Wrapper ChromaDB (colecciones, embeddings, query)
│
├─ frontend/                     # Fuente del template — frontend React/Vite/TS
│  ├─ public/
│  │  └─ docs.html               # Documentación del producto (usuario)
│  ├─ index.html                 # Entry SPA principal (App)
│  ├─ skill.html                 # Entry de la página de creación de skills (multi-page)
│  ├─ rag.html                   # Entry de la página de gestión de RAG (multi-page)
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ tsconfig.json
│  ├─ tsconfig.app.json
│  ├─ tsconfig.node.json
│  ├─ vite.config.ts
│  └─ src/
│     ├─ main.tsx                #   Entry: carga colors.json → setea CSS vars → render App
│     ├─ App.tsx                 #   Root + providers + manejo de eventos SSE (Telegram)
│     ├─ ragMain.tsx             #   Entry de rag.html → RagInterface
│     ├─ skillMain.tsx           #   Entry de skill.html → SkillInterface
│     ├─ index.css               #   @theme Tailwind v4: 4 vars configurables + fijas
│     ├─ skillColors.css         #   Colores de las páginas standalone
│     ├─ vite-env.d.ts
│     ├─ assets/
│     │  ├─ logo_cliente.png
│     │  └─ logo_empresa.png
│     ├─ services/
│     │  ├─ chatService.ts       #   SSE parsing: chunk, tool_call, done
│     │  ├─ configService.ts     #   Providers, models, MCP, skills/tools/agents, delete
│     │  ├─ sessionService.ts    #   Sesiones CRUD
│     │  ├─ contextFilesService.ts  #   CRUD archivos de contexto
│     │  ├─ metricsService.ts    #   Métricas: overview, sessions, tools, errors
│     │  ├─ telegramService.ts   #   Status/toggle/active-session de Telegram
│     │  └─ quoteHistoryService.ts
│     ├─ components/
│     │  ├─ ChatInterface.tsx    #   Chat SSE + gauge de contexto + toggle Telegram
│     │  ├─ Sidebar.tsx          #   Tabs: Conversaciones, Configuración, Agente, Crear
│     │  ├─ configTab.tsx        #   Proveedor, modelo, contexto, verbose, instrucciones/documentos
│     │  ├─ agentInfoTab.tsx     #   Panel: Tools, Skills, Agentes, MCP, RAG (con delete)
│     │  ├─ createTab.tsx        #   Accesos a las páginas de creación (skill, rag)
│     │  ├─ RagInterface.tsx     #   Gestión de colecciones RAG (archivos + URLs)
│     │  ├─ SkillInterface.tsx   #   Creación de skills vía LLM (entrevista + agente)
│     │  ├─ ContextGauge.tsx     #   Velocímetro de ventana de contexto
│     │  ├─ MetricsModal.tsx     #   Dashboard de métricas
│     │  ├─ HistoryModal.tsx
│     │  ├─ MessageBubble.tsx
│     │  ├─ chatBlocks.tsx       #   MessageRow, MarkdownRenderer, ToolCallBlock, FileChip
│     │  ├─ sessionsTab.tsx
│     │  ├─ Logo.tsx
│     │  └─ ui/                  #   shadcn/ui: avatar, button, dialog, input, separator, textarea, utils
│     └─ utils/
│        └─ mermaid.ts
│
├─ config/                       # Fuente del template — replace.json con placeholders XML
│  └─ replace.json
│
├─ store/                        # Store de tools y skills instalables
│  ├─ tools_store/
│  └─ skills_store/
│
├─ src/                          # Recursos adicionales
│  ├─ logo_empresa.png           #   Logo empresa para README (copiado por pipeline)
│  └─ template_readme.md         #   README.md para el proyecto generado
│
├─ on_boarding/                  # Onboarding para desarrolladores
│  ├─ ONBOARDING.md
│  ├─ CONTRIBUTING.md
│  └─ GIT_WORKFLOW.md
│
├─ cicd/                         # CI/CD
├─ client_db/                    # Base de datos cliente (template)
├─ tests/                        # Tests
│  └─ _test_gui.py
│
├─ .commands/                    # Comandos locales PowerShell
│  ├─ README.md
│  ├─ commands.json
│  ├─ init.ps1
│  └─ commands/
│     ├─ list_cmds.py
│     ├─ quick_push.py
│     ├─ quick_sync.py
│     └─ template.py
│
├─ .github/                      # Workflows y PR template
│
├─ docs/                         # Documentación (no trackeada)
├─ template/                     # Template de proyecto (no trackeado)
├─ dist/                         # Builds de distribución (no trackeado)
│
├─ Dockerfile                    # Multi-stage: Node 20 build → Python 3.12 slim runtime
├─ docker-compose.yml            # Servicio app: build ., puerto 8000, VITE_MODE=prod
├─ .dockerignore
├─ pyproject.toml                # Build config, entry point synapseforge, deps (colorthief, Pillow)
├─ requirements.txt              # Dependencias de desarrollo del repo synapseForge
├─ .env.example
├─ .gitignore
├─ LICENSE
├─ README.md                     # Este archivo (repo root)
├─ README_PYPI.md                # README para PyPI (package description)
├─ BUGS.md                       # Bugs conocidos
├─ refactor_agentes.md           # Notas de refactor de agentes
└─ tareas_pendientes.md          # Tracking interno
```

---

## Pipeline / Flujo principal

```mermaid
flowchart TD
    A["Usuario: pip install synapseforge"] --> B["CLI: synapseforge init"]
    B --> C["GUI tkinter 3 tabs (Proyecto, Logos, Colores)"]
    C --> D["Busca template.zip en paquete"]
    D --> E{"¿Está empaquetado?"}
    E -->|"Sí"| F["Extrae template.zip"]
    E -->|"No"| G["Descarga desde GitHub"]
    G --> F
    F --> H["Crea .venv con nombre del repo"]
    H --> I["pip install -r requirements.txt en venv"]
    I --> J["npm install en frontend/"]
    J --> K["Guarda config/replace.json"]
    K --> L["Copia logo empresa y logo cliente"]
    L --> M["Genera .ico con Pillow"]
    M --> N{"¿Usuario ingresó colores?"}
    N -->|"Sí"| O["Usa colores ingresados"]
    N -->|"No"| P["Extrae 4 colores con colorthief"]
    P --> Q["Mapeo directo a 4 variables"]
    O --> R["Reemplaza placeholders XML en todo el proyecto"]
    Q --> R
    R --> S["Proyecto listo en directorio destino"]

    T["CLI: synapseforge launch"] --> U["PyInstaller compila backend/main.py"]
    U --> V["npm run build (VITE_MODE=prod)"]
    V --> W["Descarga Python embebido 3.12.0 + pip + deps"]
    W --> X["Genera launcher.py personalizado"]
    X --> Y["PyInstaller --onefile → exe_name.exe"]
    Y --> Z["Empaqueta zip autocontenido"]
```

---

## CLI — Comandos

```bash
pip install synapseforge
```

| Comando | Descripción |
|---------|-------------|
| `synapseforge init [dir]` | Crea proyecto desde template con GUI interactiva |
| `synapseforge launch -p <path> -n <exe> [--skip-frontend] [--no-embed]` | Build de distribución autocontenida (zip) |
| `synapseforge colors [dir]` | Editor GUI para `frontend/public/colors.json` (cambios en vivo) |
| `synapseforge run [dir]` | Levanta uvicorn --reload + npm run dev + abre browser |
| `synapseforge --help` | Ayuda global |

### `synapseforge init` — Pipeline (GUI)

La GUI tiene 3 pestañas de entrada: **Proyecto** (empresa, owner, legal, repo, cliente, descripción, tarea), **Logos** (logo empresa obligatorio, logo cliente opcional) y **Colores** (4 colores hex con color picker + toggle de degradé). Al confirmar, el pipeline ejecuta 11 pasos:

1. **Input** — Recibe la configuración de la GUI.
2. **Modelos Ollama** — Ejecuta `ollama list` y verifica los modelos requeridos (`qwen3.5:4b`, `gemma4:e2b`, `phi4-mini-reasoning:3.8b`, `granite3.1-moe:3b`, `nemotron-3-nano:4b`). Si falta `qwen3.5:4b` lo instala con `ollama pull qwen3.5:4b`; los demás solo se verifican (avisa si faltan).
3. **Template** — Extrae `template.zip` empaquetado (o descarga desde GitHub).
4. **Venv** — Crea `./.{repo}/` con `python -m venv`.
5. **Deps Python** — `pip install -r requirements.txt` en el venv.
6. **npm install** — Instala dependencias del frontend.
7. **Logos** — Copia el logo de empresa y el de cliente.
8. **.ico** — Genera el favicon `.ico` desde el logo del cliente.
9. **Colores** — Si no se ingresaron, extrae la paleta con colorthief.
10. **Config** — Guarda el input como `config/replace.json` + genera `frontend/public/colors.json`.
11. **Placeholders** — Reemplaza los tags XML en todo el proyecto.

> **Comportamiento según directorio destino:**
> - Si **no existe** → lo crea y extrae el template.
> - Si **existe y está vacío** → extrae el template sin problemas.
> - Si **existe y tiene archivos** → extrae el template encima. Archivos del zip sobrescriben. Archivos previos no en el zip **se quedan** (restos).

### `synapseforge launch` — Build de distribución (7 pasos)

1. **Frontend** — `npm run build` con `VITE_MODE=prod` → `frontend/dist/`.
2. **Backend compile** — `python -m compileall -b backend/` → `.pyc` legacy.
3. **Backend limpio** — Copia compilado excluyendo: `.py` (solo `.pyc`), `__pycache__/`, `agent.db`, `.md/.txt` fuera de `agent/prompts/`.
4. **Python embebido** — Descarga Python 3.12.0 embed amd64, configura `_pth`, instala pip, instala `requirements.txt` deps en `Lib/site-packages/`.
5. **Launcher** — Genera `launcher.py` personalizado → PyInstaller `--onefile --noconsole` → `exe_name.exe`.
6. **Zip** — Empaqueta: `exe_name.exe`, `backend/`, `frontend/dist/`, `python/`, `.env`, `LICENSE`, `README.md`.
7. **Cleanup** — Mueve zip a raíz del repo, borra `__forge_build__/`, limpia `.pyc` del backend original.

Opciones: `--skip-frontend` (usa `frontend/dist/` existente) y `--no-embed` (usa el venv del proyecto en vez de descargar Python embebido).

### `synapseforge colors` — Editor de colores en vivo

- Abre GUI tkinter con los 4 campos de color + toggle de degradé + preview cuadrado + color picker nativo.
- Lee/escribe `frontend/public/colors.json`.
- **Cambios instantáneos**: recargá el navegador (F5) y ves los colores nuevos **sin rebuild**.

### `synapseforge run` — Servidor de desarrollo

- Requiere el **venv activado** (variable `VIRTUAL_ENV`).
- Levanta `uvicorn backend.main:app --reload --port 8000` (backend) y espera a que responda `/health`.
- Levanta `npm run dev` en `frontend/` (frontend, puerto 5173 por defecto Vite).
- Abre `http://localhost:5173` en el browser.
- **Ctrl+C** mata ambos procesos.

---

## Backend — Framework de Agentes

El template incluye un framework completo de agentes en `backend/agent/`:

| Módulo | Descripción |
|--------|-------------|
| `agent.py` | Agent class: conexión Groq/Ollama, streaming SSE, tool calling nativo |
| `loop.py` | AgentLoop: while True → LLM → tool_calls → execute → continue (max 25 iteraciones, max 3 profundidad sub-agentes) |
| `loop_helpers.py` | `build_system_prompt` (base + agentes + contexto + AGENT.md → `## Behavior` + `## MANDATORY:` + fecha), `fetch_context_window_turns`, `execute_tool` |
| `tools.py` | Tools Registry: nativas + externas dinámicas (`~/.config/synapseForge/tools/`) + MCP (`execute_mcp_tool`) |
| `session.py` | SessionManager: SQLite WAL, historial, config_kv (modelo, proveedor, context_window), error_log |
| `permissions.py` | Permisos por agente (tool/skill/task/rag allow/deny/ask + wildcards), filtrado en runtime |
| `config_dir.py` | Descubrimiento `~/.config/synapseForge/` (dev/prod) |
| `contract.py` | ContractResponse, UsageReport, StreamingResponse — tipado estricto |
| `instances.py` | Singletons: `agent`, `session_manager` |
| `ddl_setup.py` | Inicialización tablas SQLite (sessions, messages, config_kv, context_files, error_log, attachments) |
| `utils/clean_memory.py` | Liberación modelos GPU/CPU |
| `utils/model_resolver.py` | Resolución y validación modelo activo |
| `utils/skill_loader.py` | Carga y formateo SKILL.md para system prompt |
| `utils/skill_creator/` | Creación de skills vía LLM (evaluación + generación) |
| `utils/email_parser.py` | Parseo emails (headers, body, adjuntos) |
| `utils/mcp_helper.py` | MCP con SDK oficial (`mcp`), stdio/HTTP, timeout por servidor, tool discovery, health check |
| `utils/vector_db.py` | Wrapper ChromaDB: colecciones, embeddings, query por similitud coseno |
| `utils/chunking.py` | Chunking con overlap inteligente para RAG |
| `utils/subagent_logger.py` | Logger custom nivel SUBAGENT |
| `utils/error_logger.py` | Log de errores a SQLite (session_id, turn_number, exception, source) |

### Tools nativas

El registry expone las siguientes tools nativas (además de las externas y las MCP):

| Tool | Qué hace |
|------|----------|
| `read` | Lee un archivo o directorio del sistema de archivos local |
| `write` | Escribe contenido a un archivo (crea directorios padre) |
| `edit` | Reemplazos exactos de texto en un archivo |
| `glob` | Búsqueda de archivos por patrón |
| `grep` | Búsqueda de contenido en archivos con regex |
| `webfetch` | Descarga el contenido de una URL (markdown/text/html) |
| `websearch` | Busca en la web (DuckDuckGo) |
| `shell` | Ejecuta un comando en la terminal (async, con timeout y cancelación) |
| `list_dir` | Lista un directorio |
| `task` | Delega una tarea a un sub-agente especializado |
| `skill` | Carga el contenido de una skill por nombre |
| `reference` | Carga un archivo de referencia de una skill |
| `rag` | Consulta una colección RAG (solo las permitidas en `permission.rag`) |
| `check_email` | Verifica correos no leídos en un buzón IMAP |
| `send_email` | Envía un email |
| `help` | Documentación interna de las tools |

### Rutas API (`backend/routes/`)

| Archivo | Endpoints | Descripción |
|---------|-----------|-------------|
| `chat.py` | `POST /api/chat` | SSE stream: chunk, tool_call, tool_result, subagent_event, session_title, done, error. Adjuntos: máx 3 archivos, 25 MB total. Entrega la respuesta final a Telegram si corresponde. |
| `create.py` | `POST /api/create/skill` | Creación de skills vía LLM (SSE): entrevista iterativa + agente creador con tools. Eventos: chunk, reasoning, tool_call, tool_result, skill_action, skill_result, error, aborted. |
| `config.py` | `GET/POST /api/config/context-window`, `GET/POST /api/config/verbose-mode`, `GET /api/config/providers`, `GET /api/config/models`, `POST /api/config/models/select`, `GET /api/config/skills`, `GET /api/config/tools`, `GET /api/config/agents`, `GET /api/config/mcp` | Configuración de proveedores, modelos, ventana de contexto, modo verbose, y listados de skills/tools/agentes/MCP |
| `sessions.py` | `GET /api/sessions/titles`, `GET /api/sessions`, `GET /api/sessions/{id}`, `DELETE /api/sessions/{id}` | CRUD sesiones y mensajes (incluye contexto del gauge) |
| `context_files.py` | `GET/POST /api/context-files`, `DELETE /api/context-files/{id}` | CRUD archivos de contexto (instrucciones/documentos). Extracción texto → inyección en system prompt |
| `metrics.py` | `GET /api/metrics/overview`, `GET /api/metrics/sessions`, `GET /api/metrics/tools`, `GET /api/metrics/errors` | Métricas agregadas, por sesión, uso de tools, errores |
| `rag.py` | `POST/GET /api/rag/collections`, `DELETE /api/rag/collections/{name}`, `POST /api/rag/collections/{name}/files`, `POST /api/rag/collections/{name}/urls` | Gestión de colecciones RAG: crear/listar/eliminar, subir archivos, agregar páginas web |
| `agent_items.py` | `GET /api/agent/knowledge`, `DELETE /api/agent/skills/{name}`, `DELETE /api/agent/tools/{name}`, `DELETE /api/agent/agents/{name}`, `DELETE /api/agent/mcp/{label}`, `DELETE /api/agent/knowledge/{collection}` | Listar y eliminar skills, tools, agentes, servidores MCP y colecciones RAG |
| `events.py` | `GET /api/events` | SSE del event bus (Telegram → Frontend) |
| `telegram.py` | `GET /api/telegram/status`, `POST /api/telegram/toggle`, `GET/POST /api/telegram/active-session` | Estado/toggle del bot y sesión activa compartida |
| `file_text_extractor.py` | — | Módulo compartido extracción texto. Soporta: texto plano, Markdown, CSV, JSON, XML, YAML, Python, DOCX, DOC (LibreOffice), XLSX, XLS (LibreOffice), PDF (pdfminer + OCR opcional Tesseract). OCR **best-effort**: si falla por deps faltantes, devuelve lo que extrajo pdfminer. |

### RAG (base de conocimiento)

El sistema de RAG usa **ChromaDB** con persistencia en `~/.config/synapseForge/knowledge/` y un modelo de embeddings local (SentenceTransformer `all-MiniLM-L6-v2`, CPU). El modelo se precarga al iniciar la app y se comparte entre todos los consumidores.

- **Colecciones**: se crean desde la interfaz (`rag.html`) o por Telegram. El nombre debe estar en minúsculas, sin espacios, solo `[a-z0-9-]`, mínimo 3 caracteres.
- **Archivos**: se extrae el texto (módulo `file_text_extractor`), se chunkea y se guarda. Máx 20 archivos por request, 50 MB por archivo.
- **Páginas web**: se fetchea el contenido (con protección SSRF: bloqueo de IPs privadas y DNS pinning), se convierte a texto, se chunkea y se guarda. La URL se guarda en el metadata de cada chunk y el HTML crudo en el primer chunk.
- **Chunking**: `chunk_file_content` (500 caracteres base, 60 de overlap) con corte inteligente por delimitadores (`.`, `!`, `?`, espacio).
- **Búsqueda**: similitud coseno (`hnsw:space: cosine`). La tool `rag` devuelve los 5 chunks más similares.
- **Permisos**: la tool `rag` solo consulta las colecciones permitidas en el frontmatter del agente (`permission.rag`), igual que `task` restringe sub-agentes.

### Configuración de usuario (`~/.config/synapseForge/`)

```
~/.config/synapseForge/
├── skills/                 # Skills instaladas (carpeta por skill con SKILL.md + references/)
├── tools/                  # Tools instaladas (.py con TOOL_NAME, execute())
├── agents/                 # Agentes (.md con frontmatter YAML + permisos + prompt body) + AGENT.md (comportamiento general)
├── knowledge/              # Colecciones RAG (ChromaDB) — creadas desde la UI de creación
├── config.json             # Config principal (MCP, UI prefs, etc.)
├── mcp.json                # Servidores MCP (array JSON: label, transport, command, env)
└── config.yaml             # Permisos del router (tool/skill/task) — opcional
```

**Formato agente (`.md` en `agents/`):**
```markdown
---
name: "Mi Agente"
description: "Qué hace y cuándo usarlo"
permission:
  read: allow
  write: allow
  task:
    explorador: allow
  skill:
    mi_skill: allow
  rag:
    mi_coleccion: allow
parameters:
  temperature: 0.0
  top_p: 0.5
  model: null
---
# System prompt del agente (cuerpo del markdown)
```

### AGENT.md — Comportamiento general

`AGENT.md` (si existe en `~/.config/synapseForge/agents/`) se inyecta como sección `## Behavior` en el system prompt de **todos** los agentes (router y sub-agentes), **antes** de `## MANDATORY:`. No reemplaza el system prompt: `system_prompt.md` es siempre la base del router, y cada sub-agente usa su propio `.md`. Sirve para definir el comportamiento general del proyecto (compatibilidad con opencode/claude code).

### Reglas `## MANDATORY:`

Al final del system prompt de **todos** los agentes se inyecta la sección `## MANDATORY:` (desde `backend/agent/prompts/mandatory.md`) con las reglas obligatorias de fidelidad: extraer el objetivo fiel del usuario, no inventar ni agregar nada, formular preguntas si hay dudas, e iterar con tools/sub-agentes hasta cumplir el objetivo.

### Permisos del router (`config.yaml`)

El agente principal (router) no tiene tools ni skills directas por defecto — solo `task` (delegación). Si existe `~/.config/synapseForge/config.yaml`, sus permisos se toman de ahí:

```yaml
permissions:
  tool:
    read: allow
  skill:
    mi_skill: allow
  task:
    explorador: allow
```

- Si el archivo **no existe** → el router queda solo con `task` (delegación siempre disponible).
- Si existe → el router usa **solo** los permisos explícitos del yaml (misma lógica que el frontmatter de los agentes).
- `task` está **siempre** disponible: si el yaml no lo lista, se permite para todos los sub-agentes; si lo lista, solo para los sub-agentes indicados.

### Manejo de contexto

> **Estado actual**: El contexto se maneja mediante **ventana de contexto** (`context_window_turns`), que limita cuántos turnos del historial se pasan al LLM (`-1` = todo el historial). Además se detecta la **ventana de contexto en tokens** del modelo seleccionado (Ollama `/api/show` / Groq `/models`) y se persiste. El frontend muestra un **gauge** con el porcentaje de ventana usado. No hay compactación automática ni resumen de contexto implementado.

**Archivos de contexto (Instrucciones y documentos)**: Los archivos subidos vía `POST /api/context-files` se extraen y su contenido se concatena e inyecta en el system prompt del router y sub-agentes (ver `loop_helpers.py:load_context_text()` → `build_system_prompt()`). Sirven para proveer información de referencia permanente: manuales, reglas de negocio, documentación técnica.

### Modelo por defecto (LOCAL)

En la primera inicialización (cuando aún no hay modelo persistido), el proveedor **LOCAL** (Ollama) usa por defecto **`qwen3.5:4b`** si está instalado (acepta tools); si no, cae al primer modelo de `ollama list`. Una vez seleccionado, el modelo se guarda en SQLite (`config_kv`) y se usa desde ahí. El comando `init` verifica los modelos de Ollama e instala `qwen3.5:4b` si falta.

---

## Frontend — Chat SSE

SPA React/Vite/TypeScript con Tailwind v4 y shadcn/ui. Es **multi-page**: `index.html` (App principal), `skill.html` (creación de skills) y `rag.html` (gestión de RAG).

| Componente / Servicio | Descripción |
|----------------------|-------------|
| `chatService.ts` | Conexión SSE a `POST /api/chat`, parsea eventos: chunk, tool_call, tool_result, subagent_event, session_title, done, error |
| `configService.ts` | Providers, modelos, selección modelo, ventana de contexto, verbose, skills/tools/agentes/MCP, delete |
| `sessionService.ts` | CRUD sesiones y mensajes |
| `contextFilesService.ts` | CRUD archivos de contexto (list, upload, delete) |
| `metricsService.ts` | Overview, sessions, tools, errors |
| `telegramService.ts` | Status/toggle/active-session de Telegram |
| `Sidebar.tsx` | Tabs: Conversaciones + Configuración + Agente (dev) + Crear (dev) |
| `configTab.tsx` | Configuración: proveedor, modelo, ventana de contexto, toggle verbose, **Instrucciones y documentos** (drag-click upload, lista con delete) |
| `agentInfoTab.tsx` | Panel de agentes (dev): Tools, Skills, Agentes, MCP, RAG — con listado y delete |
| `createTab.tsx` | Accesos (dev) a las páginas de creación: Skill y RAG |
| `RagInterface.tsx` | Gestión de colecciones RAG: crear/eliminar colecciones, subir archivos, agregar URLs |
| `SkillInterface.tsx` | Creación de skills vía LLM: entrevista iterativa + agente creador, con streaming |
| `ContextGauge.tsx` | Velocímetro semicircular de ventana de contexto (verde → amarillo → rojo) |
| `MetricsModal.tsx` | Dashboard 4 tabs: Overview, Sessions, Tools, Errors |
| `chatBlocks.tsx` | Componentes compartidos: MessageRow, MarkdownRenderer, ToolCallBlock, ReasoningBlock, FileChip, FileWarningBanner |
| `main.tsx` | **Carga `colors.json` ANTES de renderizar React** → setea CSS custom properties en `document.documentElement.style` |

### Sistema de colores (Tailwind v4 `@theme`)

**Variables configurables (4 — build-time placeholders + runtime `colors.json`):**
```css
--color-app-primary            # primary
--color-app-primary-light      # secondary
--color-app-primary-text       # primary_text
--color-app-gradient-secondary # gradient_secondary
```

Además, `usar_gradiente` (toggle) no es una variable CSS: cuando está apagado, `gradient_secondary` se fuerza igual a `primary` para que los degradés se vean lisos.

- **Build-time**: `pipeline/init/placeholder_handler.py` reemplaza tags XML en `index.css` y todo el proyecto usando `config/replace.json`.
- **Runtime**: `main.tsx` hace `fetch("/colors.json")` y setea `--color-app-*` en `document.documentElement.style`. **Prioridad: runtime > build-time**.
- **`synapseforge colors`** edita `colors.json` en vivo → F5 en browser = colores nuevos sin rebuild.

---

## Telegram

El template incluye un **bot de Telegram** que actúa como control remoto del agente. El bot hace **long-polling** contra la Telegram Bot API, pero **no ejecuta el agent loop**: cuando llega un mensaje lo publica en el event bus, el frontend lo recibe vía `/api/events` y corre el mismo flujo de chat que si hubieras escrito en la web. Cuando el backend termina, envía la respuesta final de vuelta a Telegram.

### Arquitectura

- El bot **solo emite eventos** (`telegram_message`, `telegram_command`, `telegram_create`) al event bus.
- El frontend recibe esos eventos y ejecuta el flujo normal (`chatService.sendMessage` → `POST /api/chat`).
- Al terminar el request, el backend entrega la respuesta final a Telegram.
- Para la creación de skills/RAG, el bot emite `telegram_create` con `open`/`close` para abrir/cerrar la ventana correspondiente (`skill.html` / `rag.html`) en el frontend.

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
| `/cancelar` | Cancela cualquier comando en espera o sale del modo de creación. |
| `/nueva` | Crea un chat nuevo. |
| `/actual` | Muestra la sesión actual (solo el título). |
| `/contexto` | Muestra la ventana de contexto actual. |
| `/borrar` | Borra un chat (pregunta y espera respuesta). |
| `/detener` | Detiene la tarea en curso. |
| `/proveedor` | Cambia el proveedor (LOCAL/API, pregunta y espera respuesta). |
| `/modelo` | Cambia el modelo (lista y espera respuesta). |
| `/skills` | Lista skills (solo dev). |
| `/tools` | Lista tools (solo dev). |
| `/agentes` | Lista agentes (solo dev). |
| `/crear` | Crea skill o RAG (solo dev). Pregunta qué crear y guía el flujo. |
| `/ayuda` | Muestra la ayuda. |

Los comandos que necesitan un argumento (`/usar`, `/borrar`, `/proveedor`, `/modelo`, `/crear`) usan un sistema de **pregunta y respuesta**: el bot muestra la lista de opciones y espera que el usuario responda con el texto. `/cancelar` (o la palabra "cancelar") aborta la espera.

### Creación de skills y RAG por Telegram

El bot detecta la intención de crear una skill o un RAG (por ejemplo, "crear skill" o "crear rag") y entra en un **modo de creación**:

- **Skill**: abre `skill.html` en el frontend y guía la entrevista. Al crear la skill, la ventana se cierra.
- **RAG**: abre `rag.html` en el frontend. Tras cada acción (crear colección, subir archivo, agregar URL) pregunta en Telegram si querés terminar; respondé "sí" para cerrar la ventana o "no" para seguir. El comando `terminar` también cierra la ventana.

### Funcionalidades

- **Notas de voz**: se transcriben localmente con faster-whisper y se envían como mensaje.
- **Adjuntos**: los archivos enviados con el botón de adjuntar de Telegram se descargan y procesan igual que el backend (extracción de texto con `extract_text_from_bytes`).
- **Toggle en el frontend**: el header tiene un toggle para activar/desactivar el bot (persistido en SQLite).
- **Descarte de mensajes en cola**: al reactivar el bot, se descartan los mensajes que llegaron mientras estaba apagado (solo se procesan los nuevos). Al activar, el frontend muestra un contador de 3 segundos para que no envíes durante el descarte.

---

## Docker

### Dockerfile (multi-stage)

```dockerfile
# Stage 1: Build frontend (Node 20 Alpine)
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_MODE=prod
ARG VITE_URL_BASE=
ARG VITE_URL_PROD=
ENV VITE_MODE=$VITE_MODE VITE_URL_BASE=$VITE_URL_BASE VITE_URL_PROD=$VITE_URL_PROD
RUN npm run build

# Stage 2: Python runtime (3.12 slim)
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist/ ./frontend/dist/
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
services:
  app:
    build:
      context: .
      args:
        VITE_MODE: prod
    ports:
      - "8000:8000"
    restart: unless-stopped
```

**Uso:**
```bash
docker compose up --build -d
# App disponible en http://localhost:8000
```

- El backend sirve el frontend estático (`frontend/dist/`) automáticamente si existe.
- `VITE_MODE=prod` hace que los servicios frontend usen `VITE_URL_PROD` para llamadas a la API.
- Healthcheck en `/health` para orquestadores.

---

## Integración futura — Skills Vercel

Está planificada la integración con el ecosistema de [Vercel Skills](https://github.com/vercel-labs/skills) (`npx skills`), que permite buscar, instalar y gestionar skills desde repositorios públicos. El flujo planeado funciona en dos etapas:

1. **Búsqueda**: ejecutar `npx skills find <query>` para descubrir skills disponibles en el ecosistema.
2. **Evaluación/Instalación**: un LLM evalúa los resultados contra la necesidad del usuario, y si corresponde, instala la skill desde el source.

Esto permitiría ampliar el repositorio de skills sin tener que crearlas manualmente, aprovechando el ecosistema abierto de agent skills.

---

## Documentación

| Documento | Descripción |
|-----------|-------------|
| `on_boarding/` | Guía de onboarding, contribución y flujo Git |
| `docs/` | Documentación del proyecto (no trackeada) |

---

## Stack Tecnológico

![Python](https://img.shields.io/badge/Python-3.12+-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003b57?logo=sqlite&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector-000000?logo=chroma&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5-646cff?logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-4-06b6d4?logo=tailwindcss&logoColor=white)
![PyInstaller](https://img.shields.io/badge/PyInstaller-6-3776ab?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-API-f97316?logo=groq&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local-000000?logo=ollama&logoColor=white)

---

## Licencia

Apache 2.0 — Ver archivo [LICENSE](./LICENSE)

---

Copyright (c) 2026 SYNASPE AI SAS

---
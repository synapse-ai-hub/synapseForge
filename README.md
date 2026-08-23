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

1. **CLI** (`synapseforge init`, `launch`, `colors`, `run`) — scaffolding con GUI tkinter + build de distribución + editor de colores en vivo + servidor de desarrollo.
2. **Framework de agentes** (`backend/agent/`) — AgentLoop, Tools Registry (nativas + externas + MCP), Sessions (SQLite WAL), Permissions, Skills, RAG, MCP.
3. **Template de proyecto** embebido (`pipeline/template.zip`) — backend FastAPI + frontend React/Vite/TypeScript.
4. **Docker** — `Dockerfile` multi-stage + `docker-compose.yml`.

### ✨ Características Principales

- **Scaffolding completo**: `synapseforge init` crea el proyecto desde un template embebido con GUI interactiva — estructura, venv, logos, `.ico`, colores y reemplazo de placeholders.
- **Distribución autocontenida**: `synapseforge launch` genera un zip listo para entregar (PyInstaller + Python embebido + frontend compilado).
- **Multi-provider LLM**: LOCAL (Ollama, opcional), Groq, Google Gemini y OpenRouter. API keys cloud gestionadas desde el panel de configuración, validadas contra la API de cada proveedor y guardadas cifradas en SQLite. Pantalla inicial de configuración saltable: sin ningún provider configurado la app queda bloqueada hasta cargar una key.
- **Framework de agentes completo**: AgentLoop con tool calling nativo, tools registry (nativas + externas + MCP), permisos por agente (allow/deny/ask + wildcards), skills y sub-agentes con delegación por `task`.
- **RAG**: colecciones vectoriales en ChromaDB con embeddings en OpenRouter (`liquid/lfm-2.5-embedding-350m:free`). Subida de archivos y páginas web, chunking con overlap y búsqueda por similitud coseno. Requiere API key de OpenRouter (capa gratis).
- **Creación asistida por LLM**: interfaces standalone para crear skills, tools y agentes mediante entrevista iterativa + agente creador, con selección efímera de modelo cloud por tarea.
- **Telegram como control remoto**: el bot emite eventos al event bus y el frontend ejecuta el mismo flujo de chat. Comandos de sesión, modelo/proveedor, creación de skills/tools/RAG y gestión de la agenda.
- **Tareas programadas**: el usuario define tareas (descripción + hora + días) desde la Agenda del header o por Telegram; el backend las ejecuta con el modelo seleccionado y notifica el resultado en la campanita de la UI y por Telegram (siempre, aunque el bot esté deshabilitado).
- **Archivos de contexto**: subida de documentos (PDF, Word, TXT, MD, CSV, JSON, YAML, XML, PY) → extracción de texto → inyección en el system prompt del agente.
- **Métricas de uso**: sesiones, tools, errores y overview, con dashboard en el frontend.
- **Modo desktop app**: heartbeat watchdog + endpoint de shutdown para distribuir la app como producto.

---

## ¿Qué resuelve?

- **Scaffolding repetitivo**: Un solo comando crea el proyecto completo con la estructura estándar de todos los proyectos SYNAPSE.
- **Configuración centralizada**: GUI interactiva que reemplaza todos los placeholders XML del proyecto (empresa, cliente, colores, logo, etc.).
- **Branding automatizado**: Copia de logos + generación de `.ico` + extracción de paleta de colores desde la imagen.
- **Distribución sin dependencias**: Build autocontenido listo para entregar al cliente — incluye Python embebido, frontend estático, launcher nativo.

---

## Inicio rápido

```bash
pip install synapseforge

# Crear un proyecto (GUI interactiva)
synapseforge init mi-proyecto
cd mi-proyecto

# Levantar en desarrollo (requiere venv activado)
synapseforge run .
```

Al primer arranque aparece la pantalla de configuración: cargá una API key de algún proveedor cloud ([OpenRouter](https://openrouter.ai/settings/keys), [Google Gemini](https://aistudio.google.com/apikey) o [Groq](https://console.groq.com/keys) — todos con capa gratis) y aprieta **Aplicar**. Ollama es opcional (solo si querés modelos locales). La **fuente de conocimiento** necesita específicamente una key de OpenRouter.

---

## CLI — Comandos

| Comando | Descripción |
|---------|-------------|
| `synapseforge init [dir]` | Crea proyecto desde template con GUI interactiva |
| `synapseforge launch -p <path> -n <exe> [--skip-frontend] [--no-embed] [-c]` | Build de distribución autocontenida (zip). Con `-c` compila el backend a `.pyc`; por defecto empaqueta los `.py` |
| `synapseforge colors [dir]` | Editor GUI para `frontend/public/colors.json` (cambios en vivo sin rebuild) |
| `synapseforge run [dir]` | Levanta uvicorn --reload + npm run dev + abre browser |
| `synapseforge --help` | Ayuda global |

- **`init`**: pipeline de 10 pasos (input GUI → template → venv → deps → logos → `.ico` → colores → config → placeholders).
- **`launch`**: compila backend (PyInstaller), build del frontend, descarga Python embebido, genera launcher nativo y empaqueta todo en un zip.
- **`run`**: requiere el venv activado (`VIRTUAL_ENV`). Ctrl+C mata ambos servidores.

```mermaid
flowchart LR
    A["pip install synapseforge"] --> B["synapseforge init"]
    B --> C["GUI tkinter<br/>(Proyecto · Logos · Colores)"]
    C --> D["Extrae template + venv + deps<br/>+ branding + placeholders"]
    D --> E["Proyecto listo"]
    E --> F["synapseforge run<br/>(desarrollo)"]
    E --> G["synapseforge launch<br/>(zip distribuible)"]
```

---

## Estructura del proyecto

```plaintext
synapseForge/
│
├─ synapseforge/                 # Paquete Python — CLI instalable via pip
│  ├─ cli/main.py                #   Parser CLI: init | launch | colors | run
│  └─ tk/                        #   GUIs tkinter (init, colors)
│
├─ pipeline/                     # Código fuente de init y launch
│  ├─ template.zip               #   Template del proyecto (embebido)
│  ├─ init/                      #   Init: input, template, venv, config, logo, placeholders
│  └─ launch/                    #   Launch: PyInstaller, npm build, zip
│
├─ backend/                      # Fuente del template — backend FastAPI
│  ├─ main.py                    #   App FastAPI: CORS, lifespan, routers, health, SPA static
│  ├─ instances.py               #   Singletons: agent, session_manager
│  ├─ event_bus.py               #   Event bus (SSE) para Telegram ↔ Frontend
│  ├─ routes/                    #   Endpoints API (chat SSE, create, config, sessions, rag, metrics…)
│  └─ agent/                     #   Framework de agentes
│     ├─ agent.py                #   Agent class (multi-provider, streaming SSE, tool calling)
│     ├─ loop.py                 #   AgentLoop: LLM → tool_calls → execute → continue
│     ├─ tools.py                #   Registry: nativas + externas (~/.config/synapseForge/tools/) + MCP
│     ├─ session.py              #   SessionManager (SQLite WAL, historial, config_kv)
│     ├─ permissions.py          #   Permisos por agente (tool/skill/task/rag + wildcards)
│     ├─ ddl_setup.py            #   Inicialización tablas SQLite
│     ├─ prompts/                #   System prompt, mandatory, help, creación de skills
│     └─ utils/                  #   Helpers: MCP, RAG/vector_db, skill_loader, model_resolver…
│
├─ frontend/                     # Fuente del template — frontend React/Vite/TS
│  ├─ public/docs.html           #   Documentación del producto (usuario final)
│  └─ src/
│     ├─ components/             #   Chat, Sidebar, configTab, RagInterface, SkillInterface…
│     └─ services/               #   Clientes API (chatService SSE, configService, …)
│
├─ store/                        # Store de tools y skills instalables
├─ on_boarding/                  # Onboarding para desarrolladores
├─ cicd/                         # CI/CD
├─ tests/                        # Tests
├─ .commands/                    # Comandos locales PowerShell
├─ .github/                      # Workflows y PR template
│
├─ Dockerfile                    # Multi-stage: Node 20 build → Python 3.12 slim runtime
├─ docker-compose.yml            # Servicio app: puerto 8000, VITE_MODE=prod
├─ pyproject.toml                # Build config, entry point synapseforge
└─ requirements.txt              # Dependencias de desarrollo del repo
```

---

## Backend — Framework de Agentes

El template incluye un framework completo de agentes en `backend/agent/`: AgentLoop con streaming SSE y tool calling nativo, registro de tools (nativas, externas desde `~/.config/synapseForge/tools/` y servidores MCP vía SDK oficial), gestión de sesiones en SQLite (WAL), sistema de permisos por agente y skills cargadas como contexto.

**Tools nativas**: `read`, `write`, `edit`, `glob`, `grep`, `webfetch`, `websearch`, `shell`, `list_dir`, `task` (delegación a sub-agentes), `skill`, `reference`, `rag`, `check_email`, `send_email`, `help`.

### Configuración de usuario (`~/.config/synapseForge/`)

```
~/.config/synapseForge/
├── skills/                 # Skills instaladas (SKILL.md + references/)
├── tools/                  # Tools personalizadas (.py con TOOL_NAME, execute())
├── agents/                 # Agentes (.md con frontmatter YAML + permisos) + AGENT.md
├── knowledge/              # Colecciones RAG (ChromaDB)
├── mcp.json                # Servidores MCP
└── config.yaml             # Permisos del router (opcional)
```

**Formato agente (`.md` en `agents/`):**
```markdown
---
name: "Mi Agente"
description: "Qué hace y cuándo usarlo"
permission:
  read: allow
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

- **AGENT.md**: comportamiento general inyectado como sección `## Behavior` en el system prompt de todos los agentes (compatibilidad con opencode/claude code).
- **`## MANDATORY:`**: reglas de fidelidad inyectadas al final del system prompt de todos los agentes.
- **Permisos del router**: si existe `config.yaml` se usan solo sus permisos explícitos; si no, el router queda solo con `task` (delegación siempre disponible).

### Providers y modelos

Los proveedores soportados son **LOCAL** (Ollama, opcional), **GROQ**, **GOOGLE** (Gemini) y **OPENROUTER**. Las API keys cloud se gestionan desde el panel de Configuración (**Providers**): se validan contra la API de cada proveedor al guardarlas y se almacenan cifradas en la SQLite interna — las variables de entorno no se consultan. Al guardar una key válida, el provider queda disponible de inmediato en los selectores; un provider solo aparece si tiene key guardada — para LOCAL basta con que Ollama responda.

No hay modelo por defecto: al primer arranque (o si no hay ningún provider disponible) aparece la pantalla inicial de configuración, saltable. Sin ningún provider configurado el chat y los creadores quedan bloqueados hasta cargar una key válida.

La ventana de contexto en tokens del modelo seleccionado se detecta y persiste automáticamente, y el frontend muestra un gauge con el porcentaje usado.

En las pantallas de creación (skill, tool y agente) se puede elegir con qué modelo cloud se genera el elemento (proveedor + modelo + Aplicar). La selección es efímera: vale solo para esa tarea mientras la pestaña está abierta.

### Fuente de conocimiento (RAG)

Las colecciones RAG usan embeddings en la nube vía OpenRouter (`liquid/lfm-2.5-embedding-350m:free`, capa gratis) — no se instala ningún modelo local de embeddings. Para usar esta sección hace falta una API key de OpenRouter cargada en **Providers**: sin ella, la fuente de conocimiento queda deshabilitada (el resto de la app funciona normalmente).

---

## Frontend

SPA React/Vite/TypeScript con Tailwind v4 y shadcn/ui, **multi-page**: chat principal, creación de skills, gestión de RAG y documentación de usuario (`docs.html`). Incluye chat con streaming SSE y visualización de tool calls, sidebar con conversaciones/configuración/panel de agentes, gauge de ventana de contexto, Agenda de tareas programadas con campanita de notificaciones, dashboard de métricas y toggle de Telegram.

El sistema de colores es dual: build-time (placeholders XML reemplazados por el pipeline) + runtime (`frontend/public/colors.json` cargado antes de renderizar). `synapseforge colors` edita los colores en vivo sin rebuild.

---

## Telegram

Bot de Telegram como control remoto del agente: hace long-polling contra la Telegram Bot API pero **no ejecuta el agent loop** — publica los mensajes en el event bus, el frontend corre el flujo normal de chat y el backend devuelve la respuesta final a Telegram. Soporta comandos de sesión (`/sesiones`, `/usar`, `/nueva`, `/borrar`), modelo/proveedor (`/modelo`, `/proveedor`), control (`/detener`, `/contexto`, `/actual`), creación de skills/tools/RAG (`/crear`), envío de archivos (`/archivo`) y gestión de la agenda (`/agenda`, `/agendar`, `/horario`, `/eliminar_tarea`), además de notas de voz (transcripción local con faster-whisper) y adjuntos. Las ejecuciones de tareas programadas se notifican por Telegram siempre, independientemente de si el bot está habilitado para trabajar.

| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot (de BotFather). Si no está seteado, el bot queda deshabilitado. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Lista de `chat_id` autorizados (separados por coma). |

---

## Docker

`Dockerfile` multi-stage (Node 20 build del frontend → runtime Python 3.12 slim) + `docker-compose.yml`. El backend sirve el frontend estático automáticamente y expone healthcheck en `/health`.

```bash
docker compose up --build -d
# App disponible en http://localhost:8000
```

---

## Integración futura — Skills Vercel

Está planificada la integración con el ecosistema de [Vercel Skills](https://github.com/vercel-labs/skills) (`npx skills`), que permite buscar, instalar y gestionar skills desde repositorios públicos. El flujo planeado funciona en dos etapas:

1. **Búsqueda**: ejecutar `npx skills find <query>` para descubrir skills disponibles en el ecosistema.
2. **Evaluación/Instalación**: un LLM evalúa los resultados contra la necesidad del usuario, y si corresponde, instala la skill desde el source.

Esto permitiría ampliar el repositorio de skills sin tener que crearlas manualmente, aprovechando el ecosistema abierto de agent skills.

---

## Documentación

| Documento | Contenido |
|---|---|
| `frontend/public/docs.html` | Documentación del producto para el usuario final (servida por la app) |
| `on_boarding/` | Guía de onboarding, contribución y flujo Git |
| `docs/` | Documentación técnica del proyecto (no trackeada) |

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
![Google Gemini](https://img.shields.io/badge/Google_Gemini-API-4285F4?logo=google&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter-API-6467F2)
![Ollama](https://img.shields.io/badge/Ollama-Local-000000?logo=ollama&logoColor=white)

---

## Licencia

Este proyecto está licenciado bajo los términos especificados en el archivo [LICENSE](./LICENSE) ubicado en la raíz del repositorio.

---

Copyright (c) 2026 SYNASPE AI SAS

---

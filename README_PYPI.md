<p align="center">
  <img src="https://github.com/synapse-ai-hub/sources/raw/main/logo.png" alt="Logo" width="150">
</p>

---

<h1 align="center">synapseForge</h1>

---

<p align="center">
  <a href="https://pypi.org/project/synapseforge/">
    <img src="https://img.shields.io/pypi/v/synapseforge" alt="PyPI" />
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white" alt="Python 3.12+" />
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0" />
  </a>
</p>

---

<h3 align="center">CLI + Template to scaffold and ship AI agent projects (FastAPI + React/Vite/TS)</h3>

---

## Description

**synapseForge** is a PyPI package that provides a CLI to scaffold full-stack AI agent projects from scratch — backend (FastAPI), frontend (React/Vite/TypeScript), branding (logo, .ico, color palette), dependencies, and a self-contained distribution build.

The generated project includes:

- **Agent Framework** (`backend/agent/`): AgentLoop, Tools Registry (native + external + MCP), Sessions (SQLite WAL), Permissions, Skills, RAG, MCP integration
- **RAG (knowledge base)**: ChromaDB vector collections with a local embedding model (SentenceTransformer). Upload files (PDF, Word, TXT, MD, CSV, XLSX, JSON, XML, YAML, PY) and web pages (fetch + chunk + keep URL/HTML). Intelligent-overlap chunking and cosine-similarity search. Native `rag` tool with per-collection permissions in the agent frontmatter
- **Skill creation via LLM**: standalone interface (`skill.html`) and Telegram remote control. Iterative interview + agent creator with tools → generates `SKILL.md` + references
- **Context Files**: Upload PDF, Word, TXT, MD, CSV, JSON, YAML, XML, PY — text extraction with automatic injection into system prompt
- **Metrics**: Aggregated usage stats, per-session breakdown, tool usage, errors
- **File Extraction**: Shared module supporting plain text, Markdown, CSV, JSON, XML, YAML, Python, DOCX, DOC (via LibreOffice), XLSX, XLS (via LibreOffice), PDF (pdfminer + optional Tesseract OCR)
- **Frontend** (React/Vite/TS): Chat SSE streaming, config panel (provider/model/context), sessions sidebar, context files management, tool calls visualization, metrics dashboard, context-window gauge
- **Telegram Bot**: Long-polling remote control that forwards messages to the agent through the web UI, with commands (sessions, model/provider, stop), voice transcription, file attachments, and skill/RAG creation
- **User Config** (`~/.config/synapseForge/`): Custom tools, skills, agent definitions with permissions, MCP server config, RAG collections
- **Docker**: Multi-stage Dockerfile + docker-compose.yml for single-container deployment
- **Desktop App Mode**: Heartbeat watchdog (3min timeout → auto-exit), shutdown endpoint, `synapseforge run` for dev

---

## Installation

```bash
pip install synapseforge
```

**Package dependencies** (only these two — everything else is project-level):

- `colorthief>=0.2.0` — Automatic color palette extraction from the logo
- `Pillow>=10.0.0` — .ico favicon generation

---

## Quick Start

### Create a new project

```bash
synapseforge init my-project
```

Interactive GUI pipeline (3 tabs):

1. **Project** — Company logo (for README), client logo (for app, optional), company name, owner, legal name, repo name, client name, description, task (all required).
2. **Logos** — File pickers for both logos, optional width/height for company logo.
3. **Colors** — 4 hex fields with color picker (primary, secondary, primary_text, gradient_secondary) + a gradient toggle. Leave empty to auto-extract from client logo.

During init, the pipeline also runs `ollama list` to verify the required models and installs `qwen3.5:4b` with `ollama pull` if it's missing (the other required models are only checked).

```bash
cd my-project
# Ready to develop
```

> **Target directory behavior:**
> - If it **does not exist** → creates it and extracts template.
> - If it **exists and is empty** → extracts template cleanly.
> - If it **exists with files** → extracts on top. Zip files overwrite. Pre-existing files not in zip **remain** (orphaned).

### Build a distributable

```bash
synapseforge launch -p ./my-project -n "MyApp"
```

1. **Frontend** — `npm run build` with `VITE_MODE=prod` → `frontend/dist/`
2. **Backend** — Compile to `.pyc`, clean copy (exclude `.py`, `__pycache__`, `agent.db`, docs outside `agent/prompts/`)
3. **Embedded Python** — Downloads Python 3.12.0 embed amd64, configures `_pth`, installs pip, installs `requirements.txt` deps
4. **Launcher** — Generates customized `launcher.py` → PyInstaller `--onefile --noconsole` → `MyApp.exe`
5. **Package** — Bundles `MyApp.exe`, `backend/`, `frontend/dist/`, `python/`, `.env`, `LICENSE`, `README.md` into a timestamped zip
6. **Cleanup** — Moves zip to project root, removes build artifacts, cleans `.pyc` from original backend

Options: `--skip-frontend` (use existing `frontend/dist/`) and `--no-embed` (use the project venv instead of downloading embedded Python).

### Edit colors at runtime (no rebuild)

```bash
synapseforge colors ./my-project
```

Opens tkinter GUI with 4 color fields + a gradient toggle + live preview squares + native color picker. Saves to `frontend/public/colors.json`. **Refresh browser (F5) to see changes instantly.**

For the **LOCAL** provider (Ollama), the default model on first initialization is **`qwen3.5:4b`** when installed; otherwise it falls back to the first model of `ollama list`. Once selected, the model is persisted in SQLite (`config_kv`).

### Run development servers

```bash
synapseforge run ./my-project
```

Requires the project **venv to be activated** (`VIRTUAL_ENV`). Starts `uvicorn backend.main:app --reload --port 8000` (waits for `/health`) + `npm run dev` in `frontend/`, then opens `http://localhost:5173`. **Ctrl+C stops both.**

### Telegram

The generated project includes a **Telegram bot** that bridges messages to the agent through the web UI. Configure it in `.env`:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather. If empty, the bot is disabled. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Comma-separated list of authorized `chat_id`s. |

The bot supports commands (`/sesiones`, `/usar`, `/nueva`, `/actual`, `/contexto`, `/borrar`, `/detener`, `/proveedor`, `/modelo`, `/skills`, `/tools`, `/agentes`, `/crear`, `/ayuda`, `/cancelar`), voice transcription (faster-whisper), file attachments, and skill/RAG creation. Enable/disable it from the frontend header toggle.

---

## Requirements

| Tool | Version | Needed for |
|------|---------|------------|
| Python | 3.12+ | `init`, `launch`, `run`, `colors` |
| Node.js | 20+ | `launch` (frontend build), `run` (dev server) |
| Docker | 20+ | Optional: containerized deployment |

---

## Generated project structure

The structure created by `synapseforge init` (the template embedded in `pipeline/template.zip`):

```
my-project/
├── backend/
│   ├── __init__.py
│   ├── main.py                # FastAPI app (CORS, lifespan, routers, health, shutdown, heartbeat, SPA static)
│   ├── instances.py           # Singletons: agent, session_manager
│   ├── event_bus.py           # Event bus (SSE) for Telegram ↔ Frontend
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py            # POST /api/chat → SSE stream (AgentLoop)
│   │   ├── create.py          # POST /api/create/skill → SSE (LLM skill creation)
│   │   ├── config.py          # Providers, models, context window, verbose, skills/tools/agents/mcp
│   │   ├── sessions.py        # CRUD sessions, messages, titles
│   │   ├── context_files.py   # CRUD context files (instructions/documents)
│   │   ├── metrics.py         # Metrics: overview, sessions, tools, errors
│   │   ├── rag.py             # RAG collections: create/list/delete, upload files, add URL
│   │   ├── agent_items.py     # List/delete skills, tools, agents, MCP, RAG collections
│   │   ├── events.py          # GET /api/events → SSE event bus
│   │   ├── telegram.py        # Bot status/toggle + active-session
│   │   ├── file_text_extractor.py  # Text extraction: PDF, DOCX, XLSX, TXT + OCR fallback
│   │   └── README.md
│   └── agent/                 # Agent framework (Loop, Tools, MCP, Skills, Sessions, Permissions, RAG)
│       ├── __init__.py
│       ├── agent.py           # Agent class (Groq/Ollama, streaming SSE, tool calling)
│       ├── tools.py           # Registry: native + external + MCP
│       ├── loop.py            # AgentLoop: while True → LLM → tool_calls → execute → continue
│       ├── loop_helpers.py    # build_system_prompt (injects context_files), fetch_context_window, execute_tool
│       ├── session.py         # SessionManager (SQLite WAL, history, config_kv, error_log)
│       ├── permissions.py     # Permissions per agent (tool/skill/task/rag allow/deny/ask + wildcards)
│       ├── config_dir.py      # ~/.config/synapseForge/ discovery
│       ├── contract.py        # ContractResponse, UsageReport, StreamingResponse
│       ├── ddl_setup.py       # SQLite table initialization
│       ├── agent_db/          # SQLite runtime (created on start)
│       ├── prompts/
│       │   ├── system_prompt.md  # Router base prompt
│       │   ├── mandatory.md   # ## MANDATORY: fidelity rules injected into all agents
│       │   ├── help.md        # Internal documentation for `help` tool
│       │   ├── title.md       # Prompt for session title generation
│       │   ├── generar_skill.md / evaluar_skills.md / explicar_skill.md / iterar_skill.md  # Skill creation prompts
│       └── utils/
│           ├── __init__.py
│           ├── agent_helpers.py    # Skills/tools/agents/MCP listings
│           ├── chunking.py         # Intelligent-overlap chunking (RAG)
│           ├── clean_memory.py     # GPU/CPU model release
│           ├── config.py           # Runtime config
│           ├── config_dir.py       # ~/.config/synapseForge/ discovery
│           ├── contract.py         # Unified response contract
│           ├── email_parser.py     # Email parsing (headers, body, attachments)
│           ├── error_logger.py     # Error logging to SQLite (error_log table)
│           ├── loop_helpers.py     # Loop helpers (system prompt, context, tools)
│           ├── mcp_helper.py       # MCP stdio/HTTP, tool discovery, health check
│           ├── model_resolver.py   # Active model resolution and validation
│           ├── skill_loader.py     # SKILL.md loading and formatting for system prompt
│           ├── skill_creator/      # LLM-based skill creation (evaluation + generation)
│           ├── subagent_logger.py  # Custom SUBAGENT log level
│           └── vector_db.py        # ChromaDB wrapper (collections, embeddings, query)
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── skill.html             # Skill creation page (multi-page)
│   ├── rag.html               # RAG management page (multi-page)
│   ├── public/
│   │   └── docs.html          # Product documentation (user)
│   └── src/
│       ├── main.tsx           # Entry: loads colors.json → sets CSS vars → render App
│       ├── App.tsx            # Root + providers + SSE event handling (Telegram)
│       ├── ragMain.tsx        # Entry of rag.html → RagInterface
│       ├── skillMain.tsx      # Entry of skill.html → SkillInterface
│       ├── index.css          # @theme Tailwind v4: 4 configurable vars + fixed
│       ├── skillColors.css    # Colors of the standalone pages
│       ├── vite-env.d.ts
│       ├── assets/
│       │   ├── logo_cliente.png
│       │   └── logo_empresa.png
│       ├── services/
│       │   ├── chatService.ts          # SSE parsing: chunk, tool_call, done
│       │   ├── configService.ts        # Providers, models, MCP, skills/tools/agents, delete
│       │   ├── sessionService.ts       # Sessions CRUD
│       │   ├── contextFilesService.ts  # CRUD context files
│       │   ├── metricsService.ts       # Metrics: overview, sessions, tools, errors
│       │   ├── telegramService.ts      # Telegram status/toggle/active-session
│       │   └── quoteHistoryService.ts
│       ├── components/
│       │   ├── ChatInterface.tsx       # Chat SSE + context gauge + Telegram toggle
│       │   ├── Sidebar.tsx             # Tabs: Conversations, Config, Agent, Create
│       │   ├── configTab.tsx           # Provider, model, context, verbose, instructions/documents
│       │   ├── agentInfoTab.tsx        # Panel: Tools, Skills, Agents, MCP, RAG (with delete)
│       │   ├── createTab.tsx           # Access to creation pages (skill, rag)
│       │   ├── RagInterface.tsx        # RAG collection management (files + URLs)
│       │   ├── SkillInterface.tsx      # LLM skill creation (interview + agent)
│       │   ├── ContextGauge.tsx        # Context-window gauge
│       │   ├── MetricsModal.tsx        # Metrics dashboard
│       │   ├── HistoryModal.tsx
│       │   ├── MessageBubble.tsx
│       │   ├── chatBlocks.tsx          # MessageRow, MarkdownRenderer, ToolCallBlock, FileChip
│       │   ├── sessionsTab.tsx
│       │   ├── Logo.tsx
│       │   └── ui/                     # shadcn/ui: avatar, button, dialog, input, separator, textarea, utils
│       └── utils/
│           └── mermaid.ts
├── config/
│   └── replace.json           # Project placeholders (build-time)
├── store/                     # Store of installable tools and skills
│   ├── tools_store/
│   └── skills_store/
├── src/
│   └── logo_empresa.png       # Company logo (for README, copied by pipeline)
├── on_boarding/               # Developer onboarding
│   ├── ONBOARDING.md
│   ├── CONTRIBUTING.md
│   └── GIT_WORKFLOW.md
├── cicd/                      # CI/CD
├── client_db/                 # Client database (template)
├── tests/                     # Tests
├── .commands/                 # Local PowerShell commands
│   ├── README.md
│   ├── commands.json
│   ├── init.ps1
│   └── commands/
│       ├── list_cmds.py
│       ├── quick_push.py
│       ├── quick_sync.py
│       └── template.py
├── .github/                   # Workflows and PR template
│   └── PULL_REQUEST_TEMPLATE/
│       ├── feature.md
│       ├── fix.md
│       └── general.md
├── Dockerfile                 # Multi-stage: Node build → Python runtime
├── docker-compose.yml         # Single service, port 8000, VITE_MODE=prod
├── .dockerignore
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## User configuration (`~/.config/synapseForge/`)

```
~/.config/synapseForge/
├── skills/                 # Installed skills (SKILL.md per skill + references/)
├── tools/                  # Custom tools (.py files with TOOL_NAME, execute())
├── agents/                 # Agent definitions (.md with YAML frontmatter + permissions + prompt) + AGENT.md (general behavior → ## Behavior)
├── knowledge/              # RAG collections (ChromaDB) — created from the create UI
├── config.json             # Main config (UI prefs, etc.)
├── mcp.json                # MCP servers (JSON array: label, transport, command, env)
└── config.yaml             # Router permissions (tool/skill/task) — optional
```

### Agent definition (`.md` in `agents/`)

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

**Permissions**: `allow` / `deny` / `ask` (default: deny). Supports wildcards (`*`). Nested for `task` (sub-agent names), `skill` (skill names) and `rag` (collection names).

**AGENT.md** (`~/.config/synapseForge/agents/AGENT.md`): general behavior injected as a `## Behavior` section in the system prompt of **all** agents (router and sub-agents), before `## MANDATORY:`. It never replaces the system prompt — `system_prompt.md` is always the router's base.

**Router permissions (`config.yaml`)**: the router has no direct tools/skills by default — only `task` (delegation). If `~/.config/synapseForge/config.yaml` exists with a `permissions` section (same structure as agent frontmatter: `tool`, `skill`, `task`), the router uses only those explicit permissions. `task` is always available: if the yaml doesn't list it, delegation to all sub-agents is allowed; if it does, only to the listed ones.

**`## MANDATORY:`**: injected at the end of every agent's system prompt (from `backend/agent/prompts/mandatory.md`): extract the user's faithful objective, don't add or invent anything, ask useful questions when in doubt, and iterate with tools/sub-agents until the objective is met.

### Context handling

> **Current state**: Context is managed via **context window** (`context_window_turns`), which limits how many conversation turns are passed to the LLM (`-1` = all history). The selected model's **token context window** is also detected and persisted, and the frontend shows a gauge with the used percentage. Automatic compaction/summarization is not implemented.

**Context Files (Instructions & Documents)**: Files uploaded via Config panel → `POST /api/context-files` → text extracted → concatenated and injected into system prompt for router and sub-agents. Useful for permanent reference: company manuals, business rules, technical docs.

### RAG (knowledge base)

RAG uses **ChromaDB** persisted at `~/.config/synapseForge/knowledge/` with a local embedding model (SentenceTransformer `all-MiniLM-L6-v2`, CPU), pre-loaded at startup. Collections are created from the UI (`rag.html`) or Telegram. Files are text-extracted, chunked (500 chars base, 60 overlap, intelligent cut) and stored; web pages are fetched (with SSRF protection), converted to text, chunked and stored (URL in metadata, raw HTML in the first chunk). Search uses **cosine similarity**; the native `rag` tool returns the 5 most similar chunks and only queries collections allowed in the agent's `permission.rag`.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `synapseforge init [dir]` | Scaffold a project from bundled template (GUI) |
| `synapseforge launch -p <path> -n <exe> [--skip-frontend] [--no-embed]` | Build self-contained distribution zip |
| `synapseforge colors [dir]` | Edit `frontend/public/colors.json` via GUI (live reload) |
| `synapseforge run [dir]` | Start uvicorn + npm dev servers, open browser (venv must be active) |
| `synapseforge --help` | Show global help |

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.12+-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5-646cff?logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-4-06b6d4?logo=tailwindcss&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector-000000?logo=chroma&logoColor=white)
![PyInstaller](https://img.shields.io/badge/PyInstaller-6-3776ab?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-API-f97316?logo=groq&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local-000000?logo=ollama&logoColor=white)

---

## License

Apache 2.0

---

Copyright (c) 2026 SYNASPE AI SAS

---
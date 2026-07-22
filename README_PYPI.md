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

---

## Installation

```bash
pip install synapseForge
```

**Package dependencies** (only these two — everything else is project-level):

- `colorthief>=1.0.0` — Automatic color palette extraction from the logo
- `Pillow>=10.0.0` — .ico favicon generation

---

## Quick Start

### Create a new project

```bash
synapseForge init my-project
```

Interactive pipeline:

1. **Input** — Provide logo (absolute path), company name, owner, legal name, repo name, client name, and optional hex colors.
2. **Template** — Extracts the bundled `template.zip` (or downloads from GitHub if not available locally).
3. **Venv** — Creates `./.{repo}/` virtual environment.
4. **Deps** — Runs `pip install -r requirements.txt` inside the venv.
5. **Config** — Saves all input as `config/replace.json`.
6. **Logo** — Copies the logo to `frontend/src/assets/logo_empresa.png`.
7. **.ico** — Generates `logo_empresa.ico` via Pillow (16×16 to 256×256).
8. **Colors** — If no colors were entered, extracts up to 3 dominant colors from the logo using colorthief.
9. **Placeholders** — Replaces all XML tags (`<empresa>`, `<cliente>`, `<color_primario>`, etc.) across every project file.

```bash
cd my-project
# Ready to develop
```

> **Target directory behavior:**
> - If it **does not exist** → the command errors out and does nothing.
> - If it **exists and is empty** → the template is extracted cleanly.
> - If it **exists with files** → the template is extracted on top. Zip files overwrite existing ones. Files already in the directory that are not in the zip **remain** (orphaned).

### Build a distributable

```bash
synapseForge launch ./my-project "MyApp"
```

1. **PyInstaller** — Compiles the backend into a standalone `.exe`.
2. **Frontend** — Runs `npm run build` → generates `frontend/dist/`.
3. **Package** — Bundles backend.exe, frontend/dist/, venv, launcher, .env, LICENSE, README, docs/ into a zip.

---

## Requirements

| Tool | Version | Needed for |
|------|---------|------------|
| Python | 3.12+ | `init` and `launch` |
| Node.js | 20+ | `launch` (frontend build) |

---

## Generated project structure

```
my-project/
├── backend/
│   ├── main.py                # FastAPI app (CORS, lifespan, routers)
│   ├── routes/                # Chat SSE, Config, Sessions
│   ├── agent/                 # Agent framework (Loop, Tools, MCP, Skills, Sessions, Permissions)
│   └── requirements.txt
├── frontend/
│   ├── src/                   # React/Vite/TS — Chat, Sidebar, Config
│   └── package.json
├── config/
│   └── replace.json           # Project placeholders
├── docs/
│   ├── tools/                 # Tool creation guide
│   └── agents/                # Agent creation guide
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## User configuration (`~/.config/synapseForge/`)

```
~/.config/synapseForge/
├── skills/                 # Installed skills (SKILL.md per skill)
├── tools/                  # Custom tools (.py files)
├── agents/                 # Agent definitions with permissions (.md)
└── config.json             # MCP server configuration
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `synapseForge init [dir]` | Scaffold a project from the bundled template |
| `synapseForge launch <path> <exe>` | Build a self-contained distribution |
| `synapseForge --help` | Show global help |

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.12+-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5-646cff?logo=vite&logoColor=white)
![PyInstaller](https://img.shields.io/badge/PyInstaller-6-3776ab?logo=python&logoColor=white)

---

## License

Apache 2.0

---

Copyright (c) 2026 SYNASPE AI SAS

---

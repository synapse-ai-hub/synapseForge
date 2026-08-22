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

<h3 align="center">CLI to scaffold and ship full-stack AI agent projects (FastAPI + React/Vite/TS)</h3>

---

## Description

**synapseForge** is a PyPI package that provides a CLI to scaffold full-stack AI agent projects from scratch — backend (FastAPI), frontend (React/Vite/TypeScript), branding (logo, .ico, color palette), dependencies, and a self-contained distribution build.

The generated project includes:

- **Agent Framework**: AgentLoop with native tool calling, tools registry (native + external + MCP), sessions (SQLite WAL), per-agent permissions, skills and sub-agent delegation
- **Multi-provider LLM**: LOCAL (Ollama), Groq, Google Gemini and OpenRouter — cloud API keys managed from the config panel, validated against each provider's API and stored encrypted in SQLite
- **RAG knowledge base**: ChromaDB vector collections with local embeddings; upload files and web pages, cosine-similarity search
- **LLM-assisted creation**: standalone interfaces to generate skills, tools and agents through an iterative interview, with ephemeral cloud model selection per task
- **Telegram bot**: remote control that bridges messages to the agent through the web UI (commands, voice transcription, attachments)
- **Frontend**: chat with SSE streaming, config panel, sessions sidebar, context-window gauge, metrics dashboard
- **Docker** support and **desktop app mode** (heartbeat watchdog + shutdown endpoint)

---

## Installation

```bash
pip install synapseforge
```

Package dependencies: `colorthief` (color palette extraction) and `Pillow` (.ico generation) — everything else is project-level.

## Requirements

| Tool | Version | Needed for |
|------|---------|------------|
| Python | 3.12+ | `init`, `launch`, `run`, `colors` |
| Node.js | 20+ | `launch` (frontend build), `run` (dev server) |
| Docker | 20+ | Optional: containerized deployment |

**LLM provider (required):** at least one cloud API key is needed to use the app — [OpenRouter](https://openrouter.ai/settings/keys), [Google Gemini](https://aistudio.google.com/apikey) or [Groq](https://console.groq.com/keys) all offer free tiers. Keys are loaded from the in-app config panel (**Providers**) on first launch; nothing else has to be installed.

> The **knowledge base** feature specifically requires an **OpenRouter** key (free tier works). Without it, that section stays disabled — everything else runs normally.

**Ollama (optional):** local models are supported but not required. Install Ollama only if you want to run models locally.

---

## Quick Start

### Create a new project

```bash
synapseforge init my-project
cd my-project
```

Interactive GUI pipeline (project data, logos, colors).

### Run in development

```bash
synapseforge run ./my-project
```

Requires the project venv to be activated (`VIRTUAL_ENV`). Starts backend + frontend dev servers and opens the browser. Ctrl+C stops both.

### Build a distributable

```bash
synapseforge launch -p ./my-project -n "MyApp"
```

Builds the frontend, bundles embedded Python and packages everything into a self-contained zip ready to deliver. By default the backend ships as `.py` sources; pass `-c` / `--compile` to compile it to `.pyc`. Other options: `--skip-frontend`, `--no-embed`.

### Edit colors at runtime (no rebuild)

```bash
synapseforge colors ./my-project
```

GUI editor for `frontend/public/colors.json`. Refresh the browser (F5) to see changes instantly.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `synapseforge init [dir]` | Scaffold a project from bundled template (GUI) |
| `synapseforge launch -p <path> -n <exe> [--skip-frontend] [--no-embed] [-c]` | Build self-contained distribution zip (`-c` compiles backend to `.pyc`, default ships `.py`) |
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
![Google Gemini](https://img.shields.io/badge/Google_Gemini-API-4285F4?logo=google&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter-API-6467F2)
![Ollama](https://img.shields.io/badge/Ollama-Local-000000?logo=ollama&logoColor=white)

---

## License

Apache 2.0

---

Copyright (c) 2026 SYNASPE AI SAS

---

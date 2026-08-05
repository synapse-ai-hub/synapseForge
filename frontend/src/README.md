<p align="center">
  <img src="../../src/logo_empresa.png" alt="Logo" width="150">
</p>

---

<h1 align="center">[Frontend — <descripcion>Nombre del proyecto</descripcion>]</h1>

---

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0" />
  </a>
</p>

---

<h3 align="center">[Interfaz de usuario React + TypeScript + Vite para el <descripcion>Nombre del proyecto</descripcion>]</h3>

---

## Descripción

Frontend del **<descripcion>Nombre del proyecto</descripcion>**. Aplicación React 19 + TypeScript + Vite que provee la interfaz de chat streaming (SSE), panel de configuración de modelo/proveedor/contexto, gestión de sesiones y visualización de tool calls en tiempo real.

### ✨ Características Principales

- **Chat streaming SSE**: Conversación en tiempo real con Server-Sent Events.
- **Configuración dinámica**: Selección de proveedor (Ollama/Groq), modelo y ventana de contexto desde la UI.
- **Gestión de sesiones**: Sidebar con historial, títulos, preview y eliminación.
- **Tool calls visibles**: Colapsables por tool con input/output formateado.
- **Adjuntos**: Arrastrar y soltar archivos; extracción de texto automática.
- **Tema oscuro/claro**: Persistido en localStorage.

---

## Stack Tecnológico

- **React 19** + **TypeScript 5**
- **Vite 6** (dev server + build)
- **Tailwind CSS 4** (utilidad-first styling)
- **Lucide React** (iconos)
- **Marked** (renderizado markdown en mensajes)
- **DOMPurify** (sanitización XSS del markdown)

---

## Estructura del proyecto

```plaintext
frontend/
├─ public/                     # Assets estáticos (docs.html, colors.json, skill.html)
├─ src/
│  ├─ assets/                  # Logo, imágenes
│  │  ├─ logo_empresa.png      # Logo de la empresa
│  │  └─ logo_cliente.png      # Logo del cliente
│  ├─ components/              # Componentes React
│  │  ├─ ChatInterface.tsx     # Chat principal (streaming SSE, adjuntos, autoscroll)
│  │  ├─ SkillInterface.tsx    # Página de creación de skills (setup + chat + overlay)
│  │  ├─ chatBlocks.tsx        # Componentes compartidos (MessageRow, MarkdownRenderer, ToolCallBlock, ReasoningBlock, FileChip, etc.)
│  │  ├─ Sidebar.tsx           # Barra lateral con tabs (sessions, config, agent, create)
│  │  ├─ sessionsTab.tsx       # Lista de sesiones de chat
│  │  ├─ configTab.tsx         # Configuración (proveedor, modelo, contexto, verbose, archivos de contexto)
│  │  ├─ agentInfoTab.tsx      # Panel de agentes (tools, skills, agents, mcp, rag)
│  │  ├─ createTab.tsx         # Creación de skills/tools/agentes/RAG
│  │  ├─ HistoryModal.tsx      # Historial de cotizaciones
│  │  ├─ MetricsModal.tsx      # Dashboard de métricas
│  │  ├─ MessageBubble.tsx     # Burbuja de mensaje (legacy)
│  │  ├─ Logo.tsx              # Logo
│  │  └─ ui/                   # shadcn/ui: avatar, button, dialog, input, separator, textarea, utils
│  ├─ services/                # Capa de comunicación con API
│  │  ├─ chatService.ts        # Streaming SSE a /api/chat
│  │  ├─ configService.ts      # Providers, models, MCP, verbose
│  │  ├─ sessionService.ts     # Sesiones CRUD
│  │  ├─ contextFilesService.ts# Archivos de contexto CRUD
│  │  ├─ metricsService.ts     # Métricas
│  │  └─ quoteHistoryService.ts# Historial de cotizaciones
│  ├─ App.tsx                  # Componente raíz + estado global
│  ├─ main.tsx                 # Entry: carga colors.json → setea CSS vars → render App
│  ├─ skillMain.tsx            # Entry de la skill page (multi-page)
│  ├─ index.css                # Estilos globales + @theme (colores)
│  ├─ skillColors.css          # Overrides de colores para la skill page
│  └─ vite-env.d.ts            # Tipos de Vite
├─ index.html
├─ skill.html                  # Entry HTML de la skill page (multi-page)
├─ package.json
├─ tsconfig.json
├─ tsconfig.app.json
├─ tsconfig.node.json
├─ vite.config.ts
└─ README.md
```

---

## Instalación

1. **Clonar el repositorio**

```bash
>>> git clone https://github.com/<owner>nombre_owner</owner>/<repo>nombre_repo</repo>.git
>>> cd <repo>nombre_repo</repo>/frontend
```

2. **Instalar dependencias**

```bash
>>> npm install
```

3. **Desarrollo**

```bash
>>> npm run dev
```

Abre `http://localhost:5173` (proxy a `http://localhost:8000/api` configurado en `vite.config.ts`).

4. **Build producción**

```bash
>>> npm run build
```

Output en `dist/`.

---

## Variables de entorno

Crea `.env` en la raíz del proyecto (el `envDir` de Vite apunta a `../`):

```env
VITE_MODE=dev            # "dev" o "prod"
VITE_URL_DEV=http://localhost:8000
VITE_URL_PROD=http://localhost:8000
VITE_URL_BASE=http://localhost:8000
```

Los servicios usan `VITE_MODE` para elegir entre `VITE_URL_DEV` y `VITE_URL_PROD`; `VITE_URL_BASE` se usa como base de la API en varios servicios.

---

## Flujo principal

1. **Carga inicial** → `main.tsx` hace `fetch("/colors.json")` y setea las CSS vars → renderiza `App`.
2. **Proveedores** → `configService` llama `GET /config/providers` → muestra proveedores disponibles.
3. **Selección modelo** → `GET /config/models?provider=X` → lista modelos; `POST /config/models/select` → persiste en backend (SQLite `config_kv`).
4. **Chat** → `ChatInterface` envía `POST /api/chat` (SSE) → `chatService` parsea eventos → `MessageRow`/`chatBlocks` renderizan bloques (texto, razonamiento, tools, sub-agentes).
5. **Sesiones** → `sessionService` `GET /api/sessions` → `sessionsTab` en sidebar.
6. **Contexto** → `POST /config/context-window` → ajusta `max_turns`.
7. **Archivos de contexto** → `contextFilesService` `GET/POST/DELETE /api/context-files` → `configTab` gestiona subida/eliminación → se inyectan en el system prompt.

---

## Componentes clave

### `ChatInterface.tsx`
Chat principal. Mantiene el estado de mensajes, streaming SSE a `/api/chat`, autoscroll, adjuntos de archivos, detener generación, heartbeat y shutdown. Renderiza cada mensaje con `MessageRow`.

### `chatBlocks.tsx`
Componentes compartidos entre `ChatInterface` y `SkillInterface`:
- `MessageRow` — Fila de mensaje (asistente con avatar + bloques intercalados, usuario con burbuja).
- `MarkdownRenderer` — Renderiza markdown a HTML con sanitización DOMPurify.
- `ToolCallBlock` — Tarjeta de tool call con estados y sub-pasos de sub-agentes.
- `ReasoningBlock`, `FileChip`, `FileWarningBanner`, `TypingIndicator`.

### `SkillInterface.tsx`
Página de creación de skills (multi-page `skill.html`). Flujo en dos fases: setup (nombre + descripción) y chat de entrevista con streaming SSE a `/api/create/skill`. Al finalizar muestra un overlay de resultado.

### `Sidebar.tsx`
Barra lateral con tabs: Conversaciones (`sessionsTab`), Configuración (`configTab`), Agente (`agentInfoTab`) y Crear (`createTab`).

### `configTab.tsx`
Configuración: selector de proveedor/modelo, ventana de contexto, toggle verbose y gestión de archivos de contexto.

### `agentInfoTab.tsx`
Panel de agentes con 5 sub-paneles: Tools, Skills, Agentes, MCP y RAG.

### `MetricsModal.tsx`
Dashboard de métricas con tabs: Overview, Sessions, Tools, Errors.

### Servicios (`services/`)
Capa fina sobre `fetch`. `chatService` (SSE), `configService` (providers/models/MCP/verbose), `sessionService` (sesiones), `contextFilesService` (archivos de contexto), `metricsService` (métricas), `quoteHistoryService` (historial de cotizaciones).

---

## Estilos y tema

Las variables de color se declaran en `src/index.css` dentro de `@theme {}`. El pipeline `synapseForge init` reemplaza automáticamente los placeholders `<tag>default</tag>` con los valores ingresados o extraídos del logo.

### Variables configurables (definidas por el pipeline)

| Variable | Key de `colors.json` | Uso |
|----------|----------------------|-----|
| `--color-app-primary` | `primary` | Color principal: botón de enviar, barra de actividad, opción seleccionada del menú, enlaces de las respuestas |
| `--color-app-primary-light` | `secondary` | Detalles suaves: anillo de foco de los campos, anillo de la conversación seleccionada, bordes de las tarjetas |
| `--color-app-primary-text` | `primary_text` | Texto e íconos sobre el color principal (flecha de enviar, texto de botones, ícono del avatar) |
| `--color-app-gradient-secondary` | `gradient_secondary` | Color final del degradé de los botones y el avatar |

Además, `usar_gradiente` (toggle) no es una variable CSS: cuando está apagado, `gradient_secondary` se fuerza igual a `primary` para que los degradés se vean lisos.

### Variables fijas (no se modifican en el pipeline)

| Variable | Valor | Uso |
|----------|-------|-----|
| `--color-app-bg` | `#FFFFFF` | Fondo general de la app |
| `--color-app-bg-secondary` | `#F5F5F5` | Fondo secundario |
| `--color-app-bg-tertiary` | `#EBEBEB` | Paneles, tool calls, fondos terciarios |
| `--color-app-text` | `#151515` | Texto principal |
| `--color-app-text-secondary` | `#5C5C5C` | Texto secundario |
| `--color-app-border` | `#D4D4D4` | Bordes generales |
| `--color-app-success` | `#2B7D5B` | Estados de éxito |
| `--color-app-warning` | `#C4903A` | Estados de advertencia |
| `--color-app-error` | `#C2413D` | Estados de error |

**Para cambiar colores manualmente**: editar `src/index.css` → `@theme {}` → recargar, o usar `synapseforge colors` que edita `frontend/public/colors.json` en vivo.

> **Nota**: los placeholders se reemplazan automáticamente al ejecutar `synapseForge init`. Para regenerar los colores desde el logo, ejecutar nuevamente el pipeline.

---

## Scripts disponibles

| Comando | Descripción |
|---------|-------------|
| `npm run dev` | Servidor de desarrollo (HMR) |
| `npm run build` | Build producción en `dist/` |
| `npm run preview` | Preview del build local |
| `npm run lint` | ESLint + TypeScript check |

---

## Licencia

Este proyecto está licenciado bajo los términos especificados en el archivo [LICENSE](./LICENSE) ubicado en la raíz del repositorio.

---

Copyright (c) 2026 <legal>nombre_legal_empresa</legal>

---
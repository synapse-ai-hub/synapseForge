<p align="center">
  <img src="<logo>url_logo</logo>" alt="Logo" width="<width>ancho_logo</width>">
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

Frontend del **<descripcion>Nombre del proyecto</descripcion>**. Aplicación React 18 + TypeScript + Vite que provee la interfaz de chat streaming (SSE), panel de configuración de modelo/proveedor/contexto, gestión de sesiones y visualización de tool calls en tiempo real.

### ✨ Características Principales

- **Chat streaming SSE**: Conversación en tiempo real con Server-Sent Events.
- **Configuración dinámica**: Selección de proveedor (Ollama/Groq), modelo y ventana de contexto desde la UI.
- **Gestión de sesiones**: Sidebar con historial, títulos, preview y eliminación.
- **Tool calls visibles**: Colapsables por tool con input/output formateado.
- **Adjuntos**: Arrastrar y soltar archivos; extracción de texto automática.
- **Tema oscuro/claro**: Persistido en localStorage.

---

## Stack Tecnológico

- **React 18** + **TypeScript 5**
- **Vite 5** (dev server + build)
- **Tailwind CSS 3** (utilidad-first styling)
- **Lucide React** (iconos)
- **Marked** (renderizado markdown en mensajes)
- **date-fns** (formateo de fechas)

---

## Estructura del proyecto

```plaintext
frontend/
├─ public/                     # Assets estáticos
├─ src/
│  ├─ assets/                  # Logo, imágenes
│  │  └─  logo_cliente.png      # Logo de la empresa
│  │  └─  logo_cliente.ico      # Favicon generado
│  ├─ components/              # Componentes React
│  │  ├─ Chat/                 # Área de chat principal
│  │  │  ├─ ChatArea.tsx       # Contenedor de mensajes
│  │  │  ├─ Message.tsx        # Burbuja de mensaje individual
│  │  │  ├─ ToolCallCollapsible.tsx  # Colapsable para tool calls
│  │  │  └─ InputArea.tsx      # Input de usuario + adjuntos
│  │  ├─ Sidebar/              # Panel lateral
│  │  │  ├─ Sidebar.tsx        # Contenedor sidebar
│  │  │  ├─ SessionList.tsx    # Lista de sesiones
│  │  │  └─ ConfigPanel.tsx    # Panel de configuración
│  │  ├─ Config/               # Configuración de modelo/proveedor
│  │  │  ├─ ProviderSelector.tsx
│  │  │  ├─ ModelSelector.tsx
│  │  │  └─ ContextWindowInput.tsx
│  │  └─ UI/                   # Componentes base reutilizables
│  │     ├─ Button.tsx
│  │     ├─ Input.tsx
│  │     ├─ Select.tsx
│  │     └─ Collapsible.tsx
│  ├─ services/                # Capa de comunicación con API
│  │  ├─ api.ts                # Cliente fetch base + helpers
│  │  ├─ chat.ts               # chatStream, deleteConversation
│  │  ├─ sessions.ts           # listSessions, getSession, deleteSession
│  │  └─ config.ts             # providers, models, selectModel, contextWindow, mcp
│  ├─ hooks/                   # Custom hooks
│  │  ├─ useChat.ts            # Lógica de chat streaming
│  │  ├─ useSessions.ts        # Carga y gestión de sesiones
│  │  └─ useConfig.ts          # Estado de configuración (provider, model, context)
│  ├─ types/                   # Tipos TypeScript compartidos
│  │  ├─ chat.ts               # Message, ToolCall, SSE events
│  │  ├─ session.ts            # Session, SessionPreview
│  │  └─ config.ts             # Provider, Model, ConfigState
│  ├─ utils/                   # Utilidades
│  │  ├─ format.ts             # Formateo de fechas, markdown
│  │  └─ sse.ts                # Parser de Server-Sent Events
│  ├─ App.tsx                  # Componente raíz + providers
│  ├─ main.tsx                 # Entry point
│  ├─ index.css                # Estilos globales + @theme (colores)
│  └─ vite-env.d.ts            # Tipos de Vite
├─ index.html
├─ package.json
├─ tsconfig.json
├─ vite.config.ts
├─ tailwind.config.js
├─ postcss.config.js
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

Crea `.env` en `frontend/`:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## Flujo principal

1. **Carga inicial** → `useConfig` llama `GET /config/providers` → muestra proveedores disponibles.
2. **Selección proveedor** → `GET /config/models?provider=X` → lista modelos.
3. **Selección modelo** → `POST /config/models/select` → persiste en backend (SQLite `config_kv`).
4. **Chat** → `POST /api/chat` (SSE) → `useChat` parsea eventos → renderiza `Message` + `ToolCallCollapsible`.
5. **Sesiones** → `GET /api/sessions` → `SessionList` en sidebar.
6. **Contexto** → `POST /config/context-window` → ajusta `max_turns`.

---

## Componentes clave

### `ChatArea.tsx`
Orquesta el flujo de mensajes. Mantiene array `messages: Message[]`. Suscribe a `useChat` para streaming.

### `Message.tsx`
Renderiza una burbuja. Soporta `role: "user" | "assistant" | "tool"`. Para `assistant` con `toolCalls`, renderiza `ToolCallCollapsible` por cada tool.

### `ToolCallCollapsible.tsx`
Colapsable por tool call. Muestra:
- **Header**: nombre del tool + timestamp.
- **Body**: JSON formateado de `args` (input) y `result` (output).

### `ConfigPanel.tsx`
Agrupa `ProviderSelector`, `ModelSelector`, `ContextWindowInput`. Usa `useConfig` para estado reactivo.

### `useChat.ts`
Maneja la conexión SSE:
- `sendMessage(message, files?)` → POST FormData a `/api/chat`.
- Parsea eventos: `chunk`, `tool_calls_detected`, `tool_result`, `session_title`, `done`, `error`.
- Actualiza estado local de mensajes en tiempo real.

### `api.ts` + `chat.ts` / `sessions.ts` / `config.ts`
Capa fina sobre `fetch`. Manejan errores, timeouts y tipado de respuestas.

---

## Estilos y tema

Colores definidos en `src/index.css` dentro de `@theme {}`:

| Variable | Default | Uso |
|----------|---------|-----|
| `--color-app-primary` | `#D76F10` | Botones primary, enlaces, acentos |
| `--color-app-primary-light` | `#F0A347` | Focus rings, hover bordes, typing dots |
| `--color-app-bg` | `#FFFFFF` | Fondo principal |
| `--color-app-bg-secondary` | `#F5F5F5` | Hover, filas tabla |
| `--color-app-bg-tertiary` | `#EBEBEB` | Paneles, código, tool calls |
| `--color-app-text` | `#151515` | Texto principal |
| `--color-app-text-secondary` | `#5C5C5C` | Texto secundario |
| `--color-app-border` | `#D4D4D4` | Bordes |
| `--color-app-success` | `#2B7D5B` | Estados éxito |
| `--color-app-warning` | `#C4903A` | Estados warning |
| `--color-app-error` | `#C2413D` | Estados error |

**Cambiar colores**: editar `src/index.css` → `@theme {}` → `Ctrl+F5` (hard refresh).

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
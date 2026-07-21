"""FastAPI application entry point for the <descripcion>Nombre del proyecto</descripcion> API.

This module initializes the FastAPI application, configures CORS middleware,
mounts route handlers, and provides a health check endpoint.
"""

import json
import logging
import os
import sys
import time
import urllib.request
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict



import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of where uvicorn is invoked from.
# ---------------------------------------------------------------------------
_project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.config_dir import ensure_config_dir
from backend.instances import agent, session_manager, context_manager
from backend.routes import config as config_module
from backend.agent.utils.error_logger import log_error

# ---------------------------------------------------------------------------
# Router imports (wrapped in try/except so the app can start even if the
# route modules have not been created yet).
# ---------------------------------------------------------------------------
try:
    from backend.routes.chat import router as chat_router
except ImportError as e:
    log_error(str(e), source="main.py:chat_import")
    chat_router = None
    logging.warning("backend.routes.chat could not be imported.")

try:
    from backend.routes.sessions import router as sessions_router
except ImportError as e:
    log_error(str(e), source="main.py:sessions_import")
    sessions_router = None
    logging.warning("backend.routes.sessions could not be imported.")

try:
    from backend.routes.config import router as config_router
except ImportError as e:
    log_error(str(e), source="main.py:config_import")
    config_router = None
    logging.warning("backend.routes.config could not be imported.")

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heartbeat watchdog (desktop app: exit if no frontend heartbeat for 3 min)
# ---------------------------------------------------------------------------
_last_heartbeat: float = 0.0
_HEARTBEAT_TIMEOUT: float = 180.0  # 3 minutes


async def _heartbeat_watchdog() -> None:
    """Background task: exit process if no heartbeat received within timeout."""
    global _last_heartbeat
    while True:
        await asyncio.sleep(30)
        if _last_heartbeat and (time.time() - _last_heartbeat) > _HEARTBEAT_TIMEOUT:
            logger.info("Sin heartbeat %.0fs -> suicidio", _HEARTBEAT_TIMEOUT)
            os._exit(0)

# ---------------------------------------------------------------------------
# Model resolution at startup (via the config endpoint, not a helper)
# ---------------------------------------------------------------------------
async def _resolve_model_at_startup() -> None:
    """Resolve the default model, preferring any persisted selection.

    Runs as a background task after the server is listening. If a model was
    already resolved via persisted config (loaded in lifespan), we return early.
    Otherwise we call the config endpoint (``GET /api/config/models``) to
    perform the normal resolution and persist the resulting default so it
    survives the next restart.
    """
    await asyncio.sleep(2)

    # If a model was already resolved (persisted), we are done.
    if agent is not None and agent._resolved_model is not None:
        logger.info("Modelo ya resuelto (persistido): %s", agent._resolved_model)
        return

    # Otherwise resolve via the config endpoint and persist the default.
    host = os.getenv("HOST", "127.0.0.1")
    port = os.getenv("PORT", "8000")
    url = f"http://{host}:{port}/api/config/models"
    try:
        def _get() -> dict:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode())

        data = await asyncio.to_thread(_get)
        logger.info("Model resolved at startup via endpoint: %s", data.get("model"))

        if session_manager is not None and data.get("model"):
            session_manager.set_config("selected_model", data.get("model"))
    except Exception as exc:
        log_error(str(exc), source="main.py:_resolve_model_at_startup(model)")
        logger.warning("Failed to resolve model at startup via %s: %s", url, exc)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    logger.info("Starting <descripcion>Nombre del proyecto</descripcion> API ...")

    # Ensure config directory exists (~/.config/synapseAgent/)
    try:
        ensure_config_dir()
        logger.info("Config directory initialized.")
    except Exception as exc:
        log_error(str(exc), source="main.py:lifespan(config_dir)")
        logger.warning("Failed to initialize config directory: %s", exc)

    # Load persisted config (model, provider, context window) from SQLite BEFORE serving requests
    try:
        await asyncio.to_thread(config_module.load_persisted_config)
        logger.info("Persisted config loaded from SQLite.")
    except Exception as exc:
        log_error(str(exc), source="main.py:lifespan(load_persisted_config)")
        logger.warning("Failed to load persisted config: %s", exc)

    # Resolve the model via the config endpoint once the server is up (fallback if no persisted model)
    asyncio.create_task(_resolve_model_at_startup())

    # Start heartbeat watchdog (desktop app: exit if frontend closes)
    asyncio.create_task(_heartbeat_watchdog())

    logger.info("<descripcion>Nombre del proyecto</descripcion> API started successfully.")
    yield
    logger.info("<descripcion>Nombre del proyecto</descripcion> API shutting down.")


app = FastAPI(
    title="<descripcion>Nombre del proyecto</descripcion> API",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
if chat_router is not None:
    app.include_router(chat_router, prefix="/api")

if sessions_router is not None:
    app.include_router(sessions_router, prefix="/api")

if config_router is not None:
    app.include_router(config_router, prefix="/api")


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check() -> Dict[str, object]:
    """Return the current health status of the API.

    Returns:
        A dictionary with status, version, and current timestamp.
    """
    return {
        "status": "ok",
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Shutdown endpoint (for desktop app exit button)
# ---------------------------------------------------------------------------
@app.post("/api/shutdown")
async def shutdown() -> Dict[str, str]:
    """Shutdown the server gracefully. Only works when running as a desktop app."""
    import os
    import signal
    import sys

    logger.info("Shutdown requested via /api/shutdown")

    # Give the response time to be sent before killing the process
    async def _delayed_shutdown():
        await asyncio.sleep(0.5)
        if sys.platform == "win32":
            os.kill(os.getpid(), signal.CTRL_BREAK_EVENT)
        else:
            os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_delayed_shutdown())
    return {"status": "shutting down"}


# ---------------------------------------------------------------------------
# Heartbeat endpoint (frontend pings every 10s; watchdog exits if >3min silent)
# ---------------------------------------------------------------------------
@app.post("/api/heartbeat")
async def heartbeat() -> Dict[str, str]:
    """Receive heartbeat from frontend. Updates last-seen timestamp."""
    global _last_heartbeat
    _last_heartbeat = time.time()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend SPA (static files)
# Solo se activa si existe frontend/dist/. Si no, el backend funciona solo API.
# ---------------------------------------------------------------------------
_frontend_dist: str = os.path.join(_project_root, "frontend", "dist")
if os.path.isdir(_frontend_dist):
    logger.info("Sirviendo frontend desde %s", _frontend_dist)

    # Assets compilados (JS, CSS, imágenes)
    _assets_dir: str = os.path.join(_frontend_dist, "assets")
    if os.path.isdir(_assets_dir):
        app.mount(
            "/assets",
            StaticFiles(directory=_assets_dir),
            name="assets",
        )

    @app.get("/")
    async def serve_index() -> FileResponse:
        """Serve the SPA entry point (index.html)."""
        return FileResponse(os.path.join(_frontend_dist, "index.html"))

    @app.api_route("/{path:path}", methods=["GET"])
    async def serve_spa(path: str) -> FileResponse:
        """Catch-all: any non-API GET path serves index.html (SPA routing)."""
        if path.startswith("api/") or path in (
            "health",
            "openapi.json",
            "docs",
            "redoc",
        ):
            return JSONResponse(
                {"detail": "Not Found"}, status_code=404
            )
        return FileResponse(os.path.join(_frontend_dist, "index.html"))
else:
    logger.info(
        "Frontend dist no encontrado en %s. Modo solo API.", _frontend_dist
    )

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting <descripcion>Nombre del proyecto</descripcion> API on http://0.0.0.0:8000")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

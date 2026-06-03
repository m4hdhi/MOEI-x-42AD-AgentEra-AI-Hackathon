from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .core.config import get_settings
from .core.correlation import CorrelationIdMiddleware
from .core.errors import unhandled_handler, validation_handler
from .routes import (
    activity,
    admin_auth,
    analytics,
    auth,
    chat,
    copilot,
    crm,
    exec_dashboard,
    feedback,
    health,
    mock_uaepass,
    notifications,
    recordings,
    search,
    voice,
    whatsapp,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Hassan API starting — env={settings.app_env}, primary={settings.primary_llm}")
    # Start the proactive-notifications dispatcher
    from .core.dispatcher import start_dispatcher_background, stop_dispatcher_background
    start_dispatcher_background()
    try:
        yield
    finally:
        stop_dispatcher_background()
        logger.info("Hassan API shutting down")


app = FastAPI(
    title="Hassan — Channel Gateway",
    description="Single ingress for web / voice / WhatsApp / mobile. Normalizes payloads, "
    "extracts user_id + language, dispatches to the LangGraph supervisor.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://han-ringleted-dubitatively.ngrok-free.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-Id"],
)

app.add_exception_handler(RequestValidationError, validation_handler)
app.add_exception_handler(Exception, unhandled_handler)

# Static assets for the mock UAE PASS login page (logo etc.)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin_auth.router)
app.include_router(mock_uaepass.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(whatsapp.router)
app.include_router(copilot.router)
app.include_router(exec_dashboard.router)
# v2 endpoints for omnichannel CRM + proactive engagement + analytics + live activity
app.include_router(crm.router)
app.include_router(notifications.router)
app.include_router(recordings.router)
app.include_router(feedback.router)
app.include_router(analytics.router)
app.include_router(activity.router)
app.include_router(search.router)

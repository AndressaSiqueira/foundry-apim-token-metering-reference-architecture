from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.chat import router as chat_router
from app.telemetry.otel import setup_telemetry

# Initialise settings once at startup
settings = get_settings()

# Initialise OpenTelemetry before any request handlers are attached
setup_telemetry(settings)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Foundry Agent App",
    description="Sample agent that calls Azure AI Foundry via the APIM AI Gateway with OTel instrumentation.",
    version=settings.otel_service_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": settings.otel_service_name, "version": settings.otel_service_version}

# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Stage 1 – builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install only the packages needed to compile wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 – runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="foundry-agent-app"
LABEL org.opencontainers.image.description="Reference Python FastAPI agent app for APIM AI Gateway token metering"
LABEL org.opencontainers.image.licenses="MIT"

# Create a non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Install pre-built wheels (no network required)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels

# Copy application source
COPY app/ ./app/

# Drop privileges
USER appuser

EXPOSE 8000

# Health check so container orchestrators can validate readiness
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

ENTRYPOINT ["python", "-m", "uvicorn", "app.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

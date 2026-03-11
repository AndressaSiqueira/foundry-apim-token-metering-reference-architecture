# Agent App — Foundry APIM Token Metering reference

A lightweight **Python 3.12 / FastAPI** service that demonstrates how to route AI requests through  
[Azure API Management AI Gateway](https://learn.microsoft.com/azure/api-management/ai-gateway-overview) 
with end-to-end OpenTelemetry observability.

---

## Directory layout

```
src/agent-app/
├── app/
│   ├── main.py               # FastAPI entry-point, OTel init, CORS, /healthz
│   ├── config.py             # pydantic-settings Settings class
│   ├── models.py             # Pydantic request / response models
│   ├── routes/
│   │   └── chat.py           # POST /chat endpoint
│   ├── services/
│   │   └── foundry_client.py # httpx async client → APIM gateway
│   └── telemetry/
│       └── otel.py           # TracerProvider, MeterProvider, LoggerProvider
├── tests/
│   ├── test_chat.py          # FastAPI route integration tests
│   └── test_foundry_client.py# FoundryGatewayClient unit tests
├── load_test/
│   └── locustfile.py         # Locust load-test scenarios
├── Dockerfile                # Multi-stage, non-root, Python 3.12-slim
└── requirements.txt          # Pinned production + dev dependencies
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APIM_GATEWAY_URL` | ✅ | — | Full URL of the APIM gateway, e.g. `https://<name>.azure-api.net` |
| `APIM_SUBSCRIPTION_KEY` | ✅ | — | APIM product subscription key (`Ocp-Apim-Subscription-Key`) |
| `APP_TENANT_ID` | — | `default-tenant` | Logical tenant identifier sent as a custom APIM dimension |
| `APP_CONSUMER_NAME` | — | `agent-app` | Service / consumer identifier |
| `MODEL_DEPLOYMENT` | — | `gpt-4o` | Foundry model deployment name |
| `MODEL_API_VERSION` | — | `2024-08-01-preview` | Azure OpenAI REST API version |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | — | `""` | App Insights connection string (omit to disable cloud export) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | `""` | OTLP collector endpoint for local trace export |
| `LOG_CONTENT_HASH_ENABLED` | — | `true` | SHA-256 hash prompt content on spans instead of storing plaintext |
| `LOG_CONTENT_REDACT_ENABLED` | — | `false` | Replace prompt content with `[REDACTED]` on spans |

Copy `.env.example` from the repo root and fill in the required values.

---

## Local development

### Prerequisites

- Python 3.12+
- An APIM gateway deployed (or use the Bicep modules in `infra/bicep/`) + a Foundry endpoint

### Quick start

```bash
# 1 – create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate        # macOS / Linux

# 2 – install all dependencies
pip install -r requirements.txt

# 3 – configure environment
cp ../../.env.example .env
# edit .env with your APIM_GATEWAY_URL and APIM_SUBSCRIPTION_KEY

# 4 – run the app
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Test manually:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello, explain APIM token metering."}]}'
```

---

## Running tests

```bash
# From src/agent-app/
pytest tests/ -v --cov=app --cov-report=term-missing
```

All tests mock the httpx backend and OTel setup — no live Azure services are required.

---

## Running with Docker

```bash
# Build
docker build -t foundry-agent-app:local .

# Run (pass env vars directly or via --env-file)
docker run --rm -p 8000:8000 \
  --env-file .env \
  foundry-agent-app:local
```

---

## Load testing with Locust

```bash
# Install Locust (already in requirements.txt)
pip install locust

# Headless run — 10 users, 2 users/sec ramp, 60 s duration
locust -f load_test/locustfile.py --headless \
  -u 10 -r 2 --run-time 60s \
  --host http://localhost:8000

# Web UI run (navigate to http://localhost:8089)
locust -f load_test/locustfile.py --host http://localhost:8000
```

---

## OpenTelemetry signal overview

| Signal | Exporter | When |
|---|---|---|
| Traces | Azure Monitor (OTLP-compatible) | `APPLICATIONINSIGHTS_CONNECTION_STRING` set |
| Traces | OTLP gRPC | `OTEL_EXPORTER_OTLP_ENDPOINT` set |
| Metrics | Azure Monitor | `APPLICATIONINSIGHTS_CONNECTION_STRING` set |
| Logs | Azure Monitor | `APPLICATIONINSIGHTS_CONNECTION_STRING` set |

Traces use **W3C Trace Context** (`traceparent`) propagated downstream to APIM and Foundry, enabling end-to-end correlation in Application Insights.

---

## Privacy controls

| Flag | Behaviour |
|---|---|
| `LOG_CONTENT_HASH_ENABLED=true` | SHA-256 of the full messages array stored on span as `gen_ai.request.body_hash` |
| `LOG_CONTENT_REDACT_ENABLED=true` | `gen_ai.request.messages` span attribute set to `[REDACTED]` |
| Both `false` | No prompt content ever written to spans or logs |

See [docs/privacy.md](../../docs/privacy.md) for the full privacy model.

# foundry-apim-token-metering-reference-architecture

> **Production-grade reference architecture** for multi-tenant token metering, showback/chargeback, and monetization using **Azure API Management AI Gateway** + **Microsoft Azure AI Foundry**.

[![CI](https://github.com/AndressaSiqueira/foundry-apim-token-metering-reference-architecture/actions/workflows/ci.yml/badge.svg)](https://github.com/AndressaSiqueira/foundry-apim-token-metering-reference-architecture/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Folder Structure

```
foundry-apim-token-metering-reference-architecture/
├── .github/
│   └── workflows/
│       └── ci.yml                       # GitHub Actions CI pipeline
├── analytics/
│   ├── kql/
│   │   ├── tokens-per-tenant-day.kql    # Token usage aggregated per tenant/day
│   │   ├── estimated-cost.kql           # Cost estimation from token counts
│   │   ├── anomaly-detection.kql        # Anomaly detection on token usage
│   │   └── quota-vs-cost.kql            # Quota consumption versus estimated cost
│   └── pricing/
│       ├── pricing.json                 # Current model pricing table (USD per 1K tokens)
│       └── update_pricing.py            # Placeholder pricing updater script
├── docs/
│   ├── reference-architecture.md        # Component deep-dive and data flows
│   ├── observability.md                 # OTel, GenAI spans, dashboards
│   ├── token-metering.md                # Token counting, cost model, chargeback
│   ├── privacy.md                       # Redaction, hashing, data residency
│   └── security.md                      # Auth, Managed Identity, threat model
├── infra/
│   └── bicep/
│       ├── main.bicep                   # Orchestrator template
│       ├── main.bicepparam              # Parameter file
│       ├── modules/
│       │   ├── apim.bicep               # API Management with AI Gateway settings
│       │   ├── app-insights.bicep       # Application Insights workspace-based
│       │   ├── log-analytics.bicep      # Log Analytics workspace
│       │   ├── monitor-workbook.bicep   # Azure Monitor Workbook (token dashboard)
│       │   ├── identities.bicep         # Managed identities + RBAC assignments
│       │   └── diagnostic-settings.bicep# Diagnostic settings (APIM → Log Analytics)
│       └── README.md
├── policies/
│   ├── README.md
│   ├── global-policy.xml                # APIM global policy (correlation, error handling)
│   ├── product-ai-policy.xml            # Product policy (auth, token quotas per tier)
│   └── operation-chat-policy.xml        # Operation policy (token metrics, safe logging)
├── src/
│   └── agent-app/                       # Python FastAPI sample agent
│       ├── app/
│       │   ├── main.py                  # FastAPI application entry point
│       │   ├── config.py                # Settings (pydantic-settings, env-based)
│       │   ├── models.py                # Pydantic request/response models
│       │   ├── routes/
│       │   │   └── chat.py              # POST /chat endpoint
│       │   ├── services/
│       │   │   └── foundry_client.py    # APIM gateway client (httpx + Azure Identity)
│       │   └── telemetry/
│       │       └── otel.py              # OpenTelemetry setup (GenAI semantic conventions)
│       ├── tests/
│       │   ├── test_chat.py             # Chat endpoint integration tests
│       │   └── test_foundry_client.py   # Foundry client unit tests
│       ├── load_test/
│       │   └── locustfile.py            # Locust load test definition
│       ├── Dockerfile
│       ├── requirements.txt
│       └── README.md
├── .env.example                         # Environment variable template (no secrets)
├── .gitignore
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE                              # MIT
├── README.md
└── SECURITY.md
```

---

## Architecture Overview

```
                        ┌──────────────────────────────────────────────────────────────────┐
                        │                        Azure Subscription                         │
                        │                                                                    │
  ┌──────────────┐      │  ┌─────────────────────────────────────────────────────────────┐ │
  │   Tenant A   │      │  │             Azure API Management  (AI Gateway)               │ │
  │  app / agent │──────┼─▶│                                                               │ │
  └──────────────┘      │  │  Inbound policies                                             │ │
                        │  │  ┌───────────────────────────────────────────────────────┐   │ │
  ┌──────────────┐      │  │  │ • Validate Entra / subscription-key auth              │   │ │
  │   Tenant B   │      │  │  │ • Token-limit (TPM / TPD) per Product                 │   │ │
  │  app / agent │──────┼─▶│  │ • Correlation-ID injection                            │   │ │
  └──────────────┘      │  │  │ • Emit-token-metric (prompt / completion / total      │   │ │
                        │  │  │   tokens + custom dimensions: tenant, app, model,     │   │ │
  ┌──────────────┐      │  │  │   product, operationId, correlationId)                │   │ │
  │   Tenant C   │      │  │  │ • Safe logging (no prompt/response body by default)   │   │ │
  │  app / agent │──────┼─▶│  └───────────────────────────────────────────────────────┘   │ │
  └──────────────┘      │  │                         │                                     │ │
                        │  │                         ▼                                     │ │
                        │  │        ┌─────────────────────────────┐                       │ │
                        │  │        │   Azure AI Foundry           │                       │ │
                        │  │        │   Model Deployments          │                       │ │
                        │  │        │   - gpt-4o                   │                       │ │
                        │  │        │   - gpt-4o-mini              │                       │ │
                        │  │        │   - text-embedding-3-large   │                       │ │
                        │  │        └─────────────────────────────┘                       │ │
                        │  └─────────────────────────────────────────────────────────────┘ │
                        │                         │                                         │
                        │      ┌──────────────────┼──────────────────┐                    │
                        │      ▼                  ▼                  ▼                    │
                        │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐          │
                        │  │  Azure   │  │ Application  │  │  Azure Monitor   │          │
                        │  │  Monitor │  │  Insights    │  │  Workbook        │          │
                        │  │ (Metrics)│  │ (OTel traces)│  │ (Token dashboard)│          │
                        │  └──────────┘  └──────────────┘  └──────────────────┘          │
                        │      ▲                  ▲                                        │
                        │      │                  │                                        │
                        │  APIM diagnostics   OTel SDK (FastAPI app)                      │
                        └──────────────────────────────────────────────────────────────────┘
```

---

## Key Capabilities

| Capability | Implementation |
|---|---|
| **Token metering** | APIM `azure-openai-emit-token-metric` policy emits prompt/completion/total tokens as Azure Monitor custom metrics |
| **Multi-tenant isolation** | APIM Products + per-product subscriptions; each tenant gets a unique subscription key mapped to a product tier |
| **Token quotas (TPM / TPD)** | APIM `azure-openai-token-limit` policy enforces tokens-per-minute and tokens-per-day per product/tenant |
| **Showback / chargeback** | KQL queries multiply tokens × pricing rates per model per tenant per day |
| **Monetization tiers** | APIM Products (Free 40K TPD / Standard 400K TPD / Premium 4M TPD) with matching Azure Monitor alert rules |
| **OTel GenAI traces** | FastAPI emits spans following [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) |
| **Managed Identity auth** | APIM system-assigned MI calls Foundry; no API keys anywhere in code or config |
| **Privacy-first logging** | Prompts/responses suppressed by default; configurable SHA-256 hashing for audit trail |
| **Correlation** | `x-correlation-id` injected at APIM, propagated in OTel `traceparent`, surfaced in all logs/metrics |
| **IaC** | Bicep modules for APIM, App Insights, Log Analytics, workbook, identities, RBAC, diagnostics |
| **CI** | GitHub Actions: ruff lint, mypy, pytest with coverage, Bicep build validation |

---

## Quick Start

### Prerequisites

| Tool | Minimum version |
|---|---|
| Azure CLI | 2.60 |
| Bicep CLI | `az bicep install` |
| Python | 3.12 |
| Docker | 24.x (optional) |

### 1 – Clone and configure

```bash
git clone https://github.com/AndressaSiqueira/foundry-apim-token-metering-reference-architecture.git
cd foundry-apim-token-metering-reference-architecture
cp .env.example .env
# Edit .env with your values (never commit .env)
```

### 2 – Deploy infrastructure

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID>"
az group create --name rg-token-metering --location eastus2

az deployment group create \
  --resource-group rg-token-metering \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/main.bicepparam \
  --parameters environmentName=dev
```

> See [infra/bicep/README.md](infra/bicep/README.md) for full parameter reference and required RBAC roles.

### 3 – Apply APIM policies

After deployment, apply policies via the Azure Portal or Azure CLI:

```bash
# Global policy
az apim policy set --service-name <apim-name> \
  --resource-group rg-token-metering \
  --xml-policy @policies/global-policy.xml
```

> Per-product and per-operation policies are documented in [policies/README.md](policies/README.md).

### 4 – Run the sample agent app

```bash
cd src/agent-app
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Test /chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello, explain token metering briefly."}]}'
```

### 5 – Run tests

```bash
cd src/agent-app
pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
```

### 6 – Load test

```bash
cd src/agent-app
pip install locust
locust -f load_test/locustfile.py --headless -u 10 -r 2 --run-time 60s \
  --host http://localhost:8000
```

### 7 – Explore KQL analytics

Open [Log Analytics](https://portal.azure.com) → your workspace → **Logs**, then paste queries from `analytics/kql/`.

---

## Documentation

| File | Description |
|---|---|
| [docs/reference-architecture.md](docs/reference-architecture.md) | Component deep-dive, data flows, deployment options |
| [docs/observability.md](docs/observability.md) | OTel SDK setup, GenAI spans, metrics, App Insights, workbook |
| [docs/token-metering.md](docs/token-metering.md) | Token counting, Foundry cost model, showback/chargeback, tiers |
| [docs/privacy.md](docs/privacy.md) | Privacy design, redaction, hashing, data residency guidance |
| [docs/security.md](docs/security.md) | Auth flows, Managed Identity, network isolation, threat model |
| [infra/bicep/README.md](infra/bicep/README.md) | IaC parameter reference, RBAC requirements, deployment guide |
| [policies/README.md](policies/README.md) | APIM policy catalog and configuration guide |
| [src/agent-app/README.md](src/agent-app/README.md) | Sample app environment variables, running, Docker, testing |

---

## References

- [Azure API Management – AI Gateway overview](https://learn.microsoft.com/azure/api-management/ai-gateway-overview)
- [Azure API Management – Emit token metric policy](https://learn.microsoft.com/azure/api-management/azure-openai-emit-token-metric-policy)
- [Azure API Management – Token limit policy](https://learn.microsoft.com/azure/api-management/azure-openai-token-limit-policy)
- [Azure API Management – Semantic caching policy](https://learn.microsoft.com/azure/api-management/azure-openai-semantic-caching-lookup-policy)
- [Azure API Management – Authentication with Managed Identity](https://learn.microsoft.com/azure/api-management/authentication-managed-identity-policy)
- [Azure AI Foundry – Model deployments overview](https://learn.microsoft.com/azure/ai-studio/concepts/deployments-overview)
- [Azure AI Foundry – Quota and limits](https://learn.microsoft.com/azure/ai-services/openai/quotas-limits)
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Azure Monitor – Custom metrics overview](https://learn.microsoft.com/azure/azure-monitor/essentials/metrics-custom-overview)
- [Azure Monitor – Workbooks overview](https://learn.microsoft.com/azure/azure-monitor/visualize/workbooks-overview)
- [Bicep documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview)
- [Managed identities for Azure resources](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/overview)
- [Azure RBAC built-in roles](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before submitting.

## Security

Report vulnerabilities via [SECURITY.md](SECURITY.md). Architecture security details in [docs/security.md](docs/security.md).

## License

[MIT](LICENSE) © Andressa Siqueira and contributors.

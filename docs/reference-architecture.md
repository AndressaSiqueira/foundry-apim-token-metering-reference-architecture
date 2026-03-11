# Reference Architecture: Foundry + APIM Token Metering

## Overview

This document provides a deep-dive into every component of the reference
architecture, explains the data flows, and discusses deployment topology
options.

---

## Components

### 1. Clients / Tenants

Each tenant is an application or AI agent that calls the APIM AI Gateway
endpoint. Tenants are identified by their **APIM subscription key**, which
maps to an APIM **Product** (tier). The subscription key is sent as the
`Ocp-Apim-Subscription-Key` HTTP header.

The sample `agent-app` in `src/agent-app/` demonstrates a Python FastAPI
application acting as Tenant A.

| Tenant attribute | How captured |
|---|---|
| Tenant ID | Custom header `x-tenant-id` → APIM policy variable |
| Consumer name | Custom header `x-consumer-name` → metric dimension |
| Product tier | Derived from APIM subscription → product → emit-token-metric dimension |
| Correlation ID | `x-correlation-id` header injected/propagated by APIM |

---

### 2. Azure API Management – AI Gateway

APIM acts as the **single ingress point** for all AI requests. No client ever
calls Azure AI Foundry directly.

#### APIs modeled in APIM

| APIM API | Backend URL | Notes |
|---|---|---|
| `foundry-chat` | `https://<foundry>.cognitiveservices.azure.com/openai/deployments/{deployment}/chat/completions` | Chat completions |
| `foundry-embeddings` | `https://<foundry>.cognitiveservices.azure.com/openai/deployments/{deployment}/embeddings` | Embeddings |

#### Products and quotas

| Product | TPM limit | TPD limit | Use case |
|---|---|---|---|
| `ai-free` | 40,000 | 40,000 | Dev / sandbox tenants |
| `ai-standard` | 400,000 | 400,000 | Production tenants |
| `ai-premium` | 4,000,000 | 4,000,000 | High-volume / VIP tenants |

#### Policy pipeline per request

```
Inbound:
  1. validate-jwt  OR  check-header (Ocp-Apim-Subscription-Key)
  2. set-variable: tenantId, consumerName from headers
  3. set-header: x-correlation-id (generate if absent)
  4. azure-openai-token-limit (TPM + TPD, per product)
  5. authentication-managed-identity (acquire Foundry token)
  6. set-header: Authorization Bearer {mi-token}

Backend:
  → Azure AI Foundry model deployment

Outbound:
  7. azure-openai-emit-token-metric (custom dimensions)
  8. set-header: remove Authorization (strip upstream token from response headers)
  9. log-to-eventhub OR set-body redaction (privacy gate)

On-Error:
  10. return-response with structured error + correlation ID
```

---

### 3. Azure AI Foundry (Model Deployments)

Foundry hosts the model deployments. APIM authenticates to Foundry using
the **system-assigned Managed Identity** of the APIM instance, which is
assigned the **Cognitive Services OpenAI User** role on the Foundry resource.

Supported deployment types:

| Deployment | Endpoint suffix | Notes |
|---|---|---|
| `gpt-4o` | `/chat/completions` | Default chat model |
| `gpt-4o-mini` | `/chat/completions` | Low-cost alternative |
| `text-embedding-3-large` | `/embeddings` | Vector embeddings |

Token usage is returned in the `usage` field of every response and is parsed
by the APIM `azure-openai-emit-token-metric` policy.

---

### 4. Azure Monitor Custom Metrics

The `azure-openai-emit-token-metric` policy emits three Azure Monitor custom
metrics per request:

| Metric name | Unit | Description |
|---|---|---|
| `PromptTokens` | Count | Tokens in the user prompt |
| `CompletionTokens` | Count | Tokens in the model response |
| `TotalTokens` | Count | Prompt + completion |

Each metric carries the following **custom dimensions**:

```
ApiId            – APIM API identifier
OperationId      – APIM operation identifier
ProductId        – APIM product (tier)
SubscriptionId   – APIM subscription (per-tenant)
UserId           – APIM user (optional)
tenant-id        – extracted from x-tenant-id header
consumer-name    – extracted from x-consumer-name header
model-deployment – e.g. "gpt-4o"
correlation-id   – end-to-end correlation GUID
```

These dimensions enable fine-grained slicing in KQL and workbooks.

---

### 5. Log Analytics Workspace

All diagnostic data lands in a single Log Analytics workspace:

- **APIM gateway logs**: `ApiManagementGatewayLogs` table
  (request duration, response code, subscription, headers)
- **APIM metrics**: forwarded via diagnostic settings
- **App Insights traces / spans**: via OTel exporter
- **Azure Monitor Metrics**: queryable via `customMetrics` table

Retention: configurable (default 90 days). For cost control, archive data
beyond 30 days to Azure Storage using workspace data export rules.

---

### 6. Application Insights

Workspace-based Application Insights instance. The `agent-app` sends OTel
spans and metrics here via the Azure Monitor OTel exporter.

Key tables:

| Table | Content |
|---|---|
| `requests` | Incoming HTTP requests to the agent app |
| `dependencies` | Outbound calls from agent to APIM (HTTP dependency spans) |
| `traces` | Log messages |
| `customMetrics` | Custom metrics emitted by the APIM policy |
| `customEvents` | GenAI inference events |

---

### 7. Azure Monitor Workbook

A pre-built workbook (`infra/bicep/modules/monitor-workbook.bicep`) provides:

- Token usage per tenant per day (bar chart)
- Estimated cost per tenant per day (line chart)
- Top models by total tokens (pie chart)
- TPD quota vs. consumption per product tier
- P95 request latency from APIM gateway logs
- Anomaly detection band on daily token spend

---

## Data Flows

### Chat request (happy path)

```
client
  │  POST /chat   {messages: [...]}  Ocp-Apim-Subscription-Key: <key>
  │  x-tenant-id: tenant-a
  │  x-consumer-name: order-bot
  ▼
APIM (inbound)
  │  1. Validate subscription key
  │  2. Extract tenantId, consumerName into policy variables
  │  3. Set / propagate x-correlation-id
  │  4. Enforce token quota (TPM/TPD bucket decrement)
  │  5. Acquire Foundry bearer token via Managed Identity
  ▼
Azure AI Foundry
  │  POST /openai/deployments/gpt-4o/chat/completions
  │  Authorization: Bearer <mi-token>
  ▼
APIM (outbound)
  │  6. Parse usage.prompt_tokens, usage.completion_tokens
  │  7. Emit custom metrics to Azure Monitor
  │  8. Strip internal headers
  │  9. Privacy gate: redact / hash body if configured
  ▼
client
  │  200 OK  {choices: [...]}  x-correlation-id: <guid>
```

### Token quota exceeded path

```
client
  │  POST /chat (over TPM/TPD limit)
  ▼
APIM (inbound)
  │  4. azure-openai-token-limit → 429 Too Many Requests
  │     Retry-After: <seconds>
  │     x-correlation-id: <guid>
  ▼
client
  │  429 Too Many Requests
```

---

## Deployment Topology Options

### Option A – Single region (default)

```
Resource Group: rg-token-metering
├── APIM (Developer / Standard v2)
├── Azure AI Foundry (Cognitive Services account)
├── Log Analytics Workspace
├── Application Insights
└── Managed Identity
```

### Option B – Multi-region with APIM premium

- Deploy APIM Premium with multiple gateway units in different regions.
- Use Azure Front Door or Traffic Manager for global load balancing.
- Each region has its own Foundry deployment with PTU or PAYG capacity.
- Metrics aggregate to a single Log Analytics workspace.

### Option C – Network-isolated (private endpoints)

- APIM deployed in internal mode inside a VNet.
- Private endpoints for Foundry and Log Analytics.
- Azure Firewall or Application Gateway as the public-facing ingress.
- Recommended for regulated workloads (HIPAA, PCI-DSS).

---

## Identity and Authorization Summary

| From | To | Auth mechanism |
|---|---|---|
| Client | APIM | APIM subscription key (or Entra JWT) |
| APIM | Azure AI Foundry | System-assigned Managed Identity + `Cognitive Services OpenAI User` role |
| APIM | Log Analytics | Diagnostic settings (Azure-managed) |
| Agent app | APIM | APIM subscription key in header |
| Agent app | Azure Monitor (OTel) | `DefaultAzureCredential` (Managed Identity on Azure, developer credential locally) |

---

## Scalability Considerations

- **APIM throughput**: APIM Standard v2 supports up to 3,000 RPS per unit.
  Premium supports auto-scale. Token-quota policy overhead is sub-millisecond.
- **Foundry capacity**: Use Provisioned Throughput Units (PTU) for predictable
  latency; PAYG for bursty/dev workloads.
- **Metrics ingestion**: Azure Monitor custom metrics ingest at up to
  1 MB/min per region; recommended to batch or sample at very high volumes.
- **Log Analytics**: Use commitment tier pricing for high-volume environments.
  Consider data export to cold storage after 30 days.

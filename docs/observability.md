# Observability Guide

This document covers the full observability stack: OpenTelemetry instrumentation
in the agent app, APIM diagnostic logs/metrics, Application Insights, and the
Azure Monitor Workbook.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Agent App                                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  OTel SDK                                                 │  │
│  │  • TracerProvider → Azure Monitor OTel exporter           │  │
│  │  • MeterProvider  → Azure Monitor OTel exporter           │  │
│  │  • OTLP exporter (optional, for local Jaeger / ADOT)      │  │
│  │                                                           │  │
│  │  Spans emitted:                                           │  │
│  │    chat.request        (gen_ai.system=az.ai.inference)    │  │
│  │    gen_ai.chat         (GenAI semantic conventions)       │  │
│  │    http.client         (outbound APIM call)               │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
           │ OTLP / Azure Monitor exporter
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Application Insights (workspace-based)                          │
│  ← requests, dependencies, traces, customEvents, customMetrics  │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Log Analytics Workspace                                         │
│  ← ApiManagementGatewayLogs (APIM diagnostics)                  │
│  ← customMetrics (token metric dimensions)                       │
│  ← AppDependencies, AppRequests, AppTraces                       │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Azure Monitor Workbook                                          │
│  (token usage, cost estimation, quota vs. consumption, anomaly) │
└─────────────────────────────────────────────────────────────────┘
```

---

## OpenTelemetry SDK Setup

The agent app initializes OTel in `app/telemetry/otel.py`. Key choices:

| Concern | Decision |
|---|---|
| Exporter | `AzureMonitorTraceExporter` + `AzureMonitorMetricExporter` |
| Credential | `DefaultAzureCredential` (MI on Azure, AZ CLI / VS Code locally) |
| Propagation | W3C TraceContext (`traceparent`) + Baggage |
| Sampler | `ParentBased(root=TraceIdRatioBased(1.0))` (100% in dev; lower in prod) |
| SDK version | opentelemetry-sdk ≥ 1.24 |

```python
# app/telemetry/otel.py (excerpt)
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

exporter = AzureMonitorTraceExporter(
    connection_string=settings.applicationinsights_connection_string
)
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
```

---

## GenAI Semantic Conventions

The agent app follows the
[OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
for trace attributes:

| OTel attribute | Example value | Notes |
|---|---|---|
| `gen_ai.system` | `az.ai.inference` | Identifies the AI system |
| `gen_ai.request.model` | `gpt-4o` | Model deployment name |
| `gen_ai.request.max_tokens` | `2048` | From request parameters |
| `gen_ai.request.temperature` | `0.7` | From request parameters |
| `gen_ai.response.model` | `gpt-4o` | Echoed from response |
| `gen_ai.response.finish_reasons` | `["stop"]` | Array of finish reasons |
| `gen_ai.usage.prompt_tokens` | `142` | From response usage field |
| `gen_ai.usage.completion_tokens` | `89` | From response usage field |
| `server.address` | `<apim>.azure-api.net` | APIM gateway hostname |
| `server.port` | `443` | |

Additionally, the app sets W3C `traceparent` on outbound APIM requests so
trace context flows end-to-end into APIM gateway logs.

---

## APIM Diagnostics

APIM is configured to emit logs to Log Analytics via `diagnostics` settings.
The `ApiManagementGatewayLogs` table captures:

```kql
ApiManagementGatewayLogs
| project TimeGenerated, CorrelationId, ApimSubscriptionId,
          ApiId, OperationId, ResponseCode, DurationMs,
          RequestHeaders, BackendResponseCode
| limit 100
```

Note: request/response bodies are **not** logged by default (privacy-first).
Enable body logging only in non-production environments and only if
required for debugging.

---

## Token Custom Metrics

The APIM `azure-openai-emit-token-metric` policy emits metrics to the
Azure Monitor namespace `azure-apim-token-metrics`:

```xml
<azure-openai-emit-token-metric>
  <dimension name="ApiId" />
  <dimension name="OperationId" />
  <dimension name="ProductId" />
  <dimension name="SubscriptionId" />
  <dimension name="tenant-id" value="@(context.Variables.GetValueOrDefault<string>("tenantId", "unknown"))" />
  <dimension name="consumer-name" value="@(context.Variables.GetValueOrDefault<string>("consumerName", "unknown"))" />
  <dimension name="model-deployment" value="@(context.Variables.GetValueOrDefault<string>("modelDeployment", "unknown"))" />
  <dimension name="correlation-id" value="@(context.Request.Headers.GetValueOrDefault("x-correlation-id", "none"))" />
</azure-openai-emit-token-metric>
```

Query token metrics:

```kql
AzureMetrics
| where ResourceProvider == "MICROSOFT.APIMANAGEMENT"
| where MetricName in ("PromptTokens", "CompletionTokens", "TotalTokens")
| extend tenantId = tostring(parse_json(Properties)["tenant-id"])
| summarize TotalTokens=sum(Total)
    by tenantId, MetricName, bin(TimeGenerated, 1h)
| order by TimeGenerated desc
```

---

## Correlation: App Traces ↔ APIM Logs

Every request has an `x-correlation-id` that flows:

1. Generated by APIM inbound policy if not present in request.
2. Added to outbound `x-correlation-id` response header.
3. Returned to the client in the response.
4. The agent app reads it from the response and sets it as a span attribute
   (`custom.correlation_id`).
5. APIM logs capture it in `CorrelationId`.

To correlate app trace with APIM log:

```kql
let correlationId = "<guid>";
union AppDependencies, ApiManagementGatewayLogs
| where CorrelationId == correlationId
    or Properties has correlationId
| project TimeGenerated, Type, Name, DurationMs, ResultCode
| order by TimeGenerated asc
```

---

## Azure Monitor Workbook

The workbook (`infra/bicep/modules/monitor-workbook.bicep`) contains these tabs:

| Tab | Key visuals |
|---|---|
| **Overview** | Total tokens today, total estimated cost, active tenants |
| **Token Usage** | Tokens per tenant per day (stacked bar), top models |
| **Cost Estimation** | Estimated cost per tenant (line chart), cost breakdown by model |
| **Quotas** | TPD consumption vs quota per product tier (gauge) |
| **Latency** | P50/P95/P99 latency from APIM logs |
| **Anomalies** | Anomaly detection on daily token spend per tenant |

To import manually:

1. Open [Azure Monitor Workbooks](https://portal.azure.com/#blade/Microsoft_Azure_Monitor_Workbooks/WorkbooksGalleryBlade).
2. Click **+ New** → **Advanced Editor** (</> icon).
3. Paste the JSON from the Bicep module output or from `analytics/` directory.

---

## Local Development with Jaeger

For local tracing without an Azure subscription:

```bash
# Start Jaeger all-in-one
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest

# Set env variable
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Run app
uvicorn app.main:app --reload
```

Open http://localhost:16686 to view traces.

---

## Alerting

Recommended Azure Monitor alert rules (deploy via Bicep or Portal):

| Alert | Signal | Threshold |
|---|---|---|
| High token spike | `TotalTokens` custom metric | > 2× 7-day average in 5 min |
| Quota nearing limit | `TotalTokens` per tenant | > 80% of TPD quota |
| High error rate | `ApiManagementGatewayLogs` 5xx | > 5% of requests over 5 min |
| Latency P95 | `DurationMs` from APIM logs | > 5000 ms |

# Token Metering, Cost Model, and Showback / Chargeback

This document explains how tokens are counted, how APIM enforces quotas, how
token usage is converted to estimated cost, and how showback and chargeback
are implemented.

---

## How Azure AI Foundry Counts Tokens

Azure AI Foundry models use the **tiktoken** BPE (Byte-Pair Encoding)
tokenizer. Token count depends on:

- The model family (GPT-4o uses `cl100k_base` tokenizer).
- The content of the messages, system prompt, and function tool definitions.
- Structured output schema definitions add tokens.

### Rules of thumb

| Content | Approximate tokens |
|---|---|
| 1 English word | ~1.3 tokens (avg) |
| 100 English words | ~75–100 tokens |
| 1 code line | ~5–15 tokens |
| 1 image (gpt-4o vision, 512×512) | ~170 tokens |
| 1 image (high-res tile) | 170 + tiles × 85 tokens |

The exact count for a request is always returned in the response
`usage` object:

```json
{
  "usage": {
    "prompt_tokens": 142,
    "completion_tokens": 89,
    "total_tokens": 231
  }
}
```

APIM's `azure-openai-emit-token-metric` policy reads this field and emits
Azure Monitor custom metrics.

---

## Foundry Token-Based Cost Model

Azure AI Foundry charges differently for **input (prompt) tokens** and
**output (completion) tokens**. Pricing varies by model and changes over time.
Always consult the [official Azure pricing page](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/).

The `analytics/pricing/pricing.json` file stores the current rates used in
KQL cost-estimation queries:

```json
{
  "models": {
    "gpt-4o": {
      "input_per_1k_tokens": 0.0025,
      "output_per_1k_tokens": 0.01,
      "currency": "USD",
      "updated": "2026-03-01"
    },
    "gpt-4o-mini": {
      "input_per_1k_tokens": 0.00015,
      "output_per_1k_tokens": 0.0006,
      "currency": "USD",
      "updated": "2026-03-01"
    },
    "text-embedding-3-large": {
      "input_per_1k_tokens": 0.00013,
      "output_per_1k_tokens": 0.0,
      "currency": "USD",
      "updated": "2026-03-01"
    }
  }
}
```

### Cost formula

```
EstimatedCost = (PromptTokens / 1000 × InputRate)
              + (CompletionTokens / 1000 × OutputRate)
```

Example for gpt-4o, 142 prompt + 89 completion tokens:

```
Cost = (142 / 1000 × 0.0025) + (89 / 1000 × 0.01)
     = 0.000355 + 0.00089
     = $0.001245
```

---

## APIM Token Quotas

### Token limit policy (`azure-openai-token-limit`)

Limits are enforced **before** the request reaches Foundry. The policy
estimates prompt tokens using tiktoken-compatible counting and subtracts
from the bucket. If the limit is reached, APIM returns `429 Too Many
Requests` with a `Retry-After` header.

```xml
<azure-openai-token-limit
  tokens-per-minute="10000"
  counter-key="@(context.Product.Id)"
  estimate-prompt-tokens="true"
  remaining-tokens-header-name="x-ratelimit-remaining-tokens"
  tokens-consumed-header-name="x-ratelimit-consumed-tokens" />
```

**Key parameters:**

| Parameter | Description |
|---|---|
| `tokens-per-minute` | Sliding-window TPM limit |
| `counter-key` | Isolation scope: `Product.Id`, `Subscription.Id`, or custom |
| `estimate-prompt-tokens` | `true` = count before sending (no Foundry call on over-limit) |
| `remaining-tokens-header-name` | Sets response header with remaining allowance |

### Additional per-day quota

For daily limits, use an additional `quota` policy keyed by subscription:

```xml
<quota-by-key calls="1000000" renewal-period="86400"
  counter-key="@(context.Subscription.Id)" />
```

Or use a rate-limit-by-key for tokens-per-day tracking via an external
cache (Redis) if you need exact TPD enforcement across APIM units.

---

## Showback Model

Showback surfaces token consumption and estimated cost to internal teams
(platform, finance) without direct billing integration.

### Data pipeline

```
APIM emit-token-metric
  → Azure Monitor Custom Metrics
    → Log Analytics (AzureMetrics / customMetrics table)
      → KQL queries (analytics/kql/)
        → Azure Monitor Workbook (dashboard)
          → CSV export or scheduled email
```

### Monthly showback report query

See `analytics/kql/estimated-cost.kql` for the full query. Summary:

```kql
customMetrics
| where name in ("PromptTokens", "CompletionTokens")
| extend tenantId = tostring(customDimensions["tenant-id"])
| extend modelDeployment = tostring(customDimensions["model-deployment"])
| summarize
    PromptTokens = sumif(value, name == "PromptTokens"),
    CompletionTokens = sumif(value, name == "CompletionTokens")
    by tenantId, modelDeployment, bin(timestamp, 1d)
// Join with pricing lookup to compute estimated cost
```

---

## Chargeback Model

Chargeback integrates estimated cost into actual billing or invoice systems.

### Integration patterns

| Pattern | Description |
|---|---|
| **Azure Cost Management tags** | Tag the Foundry resource with `tenant-id` and use cost analysis. Limitation: does not split per-tenant at inference level without APIM metering. |
| **Custom billing database** | Export daily KQL results (token × rate) to an Azure SQL or Cosmos DB table. Finance team queries it for invoicing. |
| **Azure Marketplace metering** | For ISVs: use [Azure Marketplace metered billing](https://learn.microsoft.com/azure/marketplace/marketplace-metering-service-apis) to emit usage events per tenant subscription. |
| **Power BI / Fabric** | Connect Log Analytics to Power BI or Microsoft Fabric for self-service chargeback reports. |

### Recommended chargeback pipeline

```
Scheduled export (daily, 02:00 UTC)
  → analytics/pricing/update_pricing.py updates pricing.json
  → KQL query: estimated_cost_per_tenant_per_day
  → Export to Azure SQL table: dbo.TokenCostAllocation
  → Finance ERP imports table
  → Monthly invoice generation per tenant
```

---

## Monetization Tiers

For external monetization (SaaS), map APIM Products to paid tiers:

| Tier | APIM Product | TPM | TPD | Monthly price |
|---|---|---|---|---|
| Free | `ai-free` | 40,000 | 40,000 | $0 |
| Standard | `ai-standard` | 400,000 | 400,000 | Usage-based |
| Premium | `ai-premium` | 4,000,000 | 4,000,000 | Negotiated |

Monetization flow:

1. Tenant subscribes to a Product in the APIM Developer Portal.
2. APIM subscription key is issued and sent to the tenant's app.
3. Token limits enforced per product tier.
4. Azure Marketplace metered billing emits usage events per tenant.
5. Azure invoices the tenant's subscription monthly.

---

## Updating Pricing

Run `analytics/pricing/update_pricing.py` to update `pricing.json`:

```bash
cd analytics/pricing
pip install requests
python update_pricing.py --output pricing.json
```

The script is a placeholder that fetches pricing data. Wire it to the
Azure Retail Prices API or maintain the JSON manually. Re-run KQL queries
after updating pricing to reflect new rates in cost reports.

---

## Token Metering Flow Diagram

```
  Client Request
       │
       ▼
  APIM (inbound)
  ├── Token limit check (estimate prompt tokens)
  │   ├── Within limit → continue
  │   └── Over limit   → 429, Retry-After
       │
       ▼
  Azure AI Foundry
  └── Returns: choices[] + usage{prompt_tokens, completion_tokens}
       │
       ▼
  APIM (outbound)
  ├── Read usage from response body
  ├── Emit PromptTokens metric    (+ custom dimensions)
  ├── Emit CompletionTokens metric(+ custom dimensions)
  └── Emit TotalTokens metric     (+ custom dimensions)
       │
       ▼
  Azure Monitor Custom Metrics → Log Analytics
       │
       ▼
  KQL cost queries → Workbook → Showback / Chargeback
```

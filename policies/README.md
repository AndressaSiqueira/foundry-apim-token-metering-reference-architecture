# APIM Policies

This directory contains the Azure API Management policy XML files for the
token metering reference architecture.

---

## Policy Hierarchy

```
Global (global-policy.xml)
  └── Product (product-ai-policy.xml)           applied to ai-free / ai-standard / ai-premium
        └── API > Operation (operation-chat-policy.xml)  applied to POST /chat/completions
```

Policies are evaluated in order from outermost to innermost on inbound;
reverse order on outbound.

---

## Files

| File | Scope | Key responsibilities |
|---|---|---|
| `global-policy.xml` | All APIs in APIM | Correlation ID injection, global error handler, CORS |
| `product-ai-policy.xml` | Product (tier) | Managed Identity auth, token quota, client header extraction |
| `operation-chat-policy.xml` | API operation | Emit token metrics, model routing, safe body handling |

---

## Required APIM Named Values

Before applying policies, create these Named Values in APIM:

| Named value key | Description | Secret? |
|---|---|---|
| `foundry-endpoint` | Base URL of the Foundry Cognitive Services account | No |

---

## Applying Policies

### Via Azure CLI

```bash
APIM=apim-tm-dev
RG=rg-token-metering

# Global policy
az apim policy set \
  --service-name $APIM \
  --resource-group $RG \
  --xml-policy @policies/global-policy.xml

# Product policy (repeat for each product: ai-free, ai-standard, ai-premium)
az apim product policy set \
  --service-name $APIM \
  --resource-group $RG \
  --product-id ai-standard \
  --xml-policy @policies/product-ai-policy.xml

# Operation policy
az apim api operation policy set \
  --service-name $APIM \
  --resource-group $RG \
  --api-id foundry-chat \
  --operation-id chat-completions \
  --xml-policy @policies/operation-chat-policy.xml
```

### Via Azure Portal

1. Navigate to **API Management → APIs**.
2. Select the API and operation.
3. Click **Policies** → **Code editor** (`</>`).
4. Paste the XML content.

---

## Token Quota Tiers

The `product-ai-policy.xml` uses APIM `context.Product.Id` to determine which
quota applies. Adjust `tokens-per-minute` values to match your capacity:

| Product | `tokens-per-minute` | `tokens-per-day` |
|---|---|---|
| `ai-free` | 2,000 | 40,000 |
| `ai-standard` | 20,000 | 400,000 |
| `ai-premium` | 200,000 | 4,000,000 |

---

## Custom Dimensions Reference

All three token metric names (`PromptTokens`, `CompletionTokens`, `TotalTokens`)
are emitted with the following dimensions:

| Dimension key | Value source |
|---|---|
| `ApiId` | `context.Api.Id` |
| `OperationId` | `context.Operation.Id` |
| `ProductId` | `context.Product.Id` |
| `SubscriptionId` | `context.Subscription.Id` |
| `tenant-id` | `x-tenant-id` request header |
| `consumer-name` | `x-consumer-name` request header |
| `model-deployment` | Path parameter `/deployments/{deployment-id}` |
| `correlation-id` | `x-correlation-id` header (injected or propagated) |

---

## Privacy Notes

- Body logging is **disabled** globally. Policies do not log request or
  response bodies.
- APIM subscription keys are **never** forwarded to the Foundry backend.
- The `Authorization` header sent to Foundry (MI bearer token) is
  stripped before returning the response to the client.

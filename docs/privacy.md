# Privacy Design

This document describes the privacy controls built into the reference
architecture. The default posture is **privacy-first**: no prompt or response
content is stored in plaintext anywhere in the observability stack.

---

## Threat Model (Privacy)

| Threat | Mitigation |
|---|---|
| Prompt content leaking into logs | Body logging disabled by default in APIM diagnostics |
| Response content stored in plaintext | Redaction gate in APIM outbound policy |
| User PII in telemetry spans | OTel span bodies never include raw content; only token counts |
| Subscription keys in logs | APIM correlation headers used; keys never logged |
| Tenant cross-contamination | Separate APIM subscriptions; dimensions isolated per tenant |

---

## APIM Privacy Gate

### Default: no body logging

The APIM diagnostic settings are configured with `logClientIp: false` and
`verbosity: headers` (not `body`). The `ApiManagementGatewayLogs` table
will capture headers and metadata but **not** request or response bodies.

```xml
<!-- global-policy.xml: strip sensitive headers before logging -->
<inbound>
  <set-variable name="sanitizedRequest" value="" />
  <!-- do NOT log body: diagnostic settings use verbosity=headers -->
</inbound>
```

### Optional: hashed body for audit

Set `LOG_CONTENT_HASH_ENABLED=true` in the agent app environment. This
causes the app to compute a SHA-256 hash of the serialized messages array
and attach it as a span attribute `gen_ai.request.body_hash`. The hash
can be used to detect duplicate requests or verify content integrity
without storing plaintext.

```python
import hashlib
import json

def hash_messages(messages: list[dict]) -> str:
    """Returns SHA-256 hex digest of serialized messages."""
    payload = json.dumps(messages, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

### Optional: full redaction

Set `LOG_CONTENT_REDACT_ENABLED=true` to completely suppress the messages
payload from being forwarded. In this mode the agent app sends only a
stub to the observability layer:

```json
{"messages": "[REDACTED]"}
```

This is suitable for highly regulated environments where even hashed
content must not be retained.

---

## Agent App Privacy Controls

Priority order (highest wins):

```
LOG_CONTENT_REDACT_ENABLED=true  ->  messages replaced with "[REDACTED]"
LOG_CONTENT_HASH_ENABLED=true    ->  messages replaced with SHA-256 hash
(default: neither flag set)      ->  no content in OTel spans
```

Token counts (`gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`)
are **always** recorded because they contain no PII.

---

## OpenTelemetry Span Privacy

The following GenAI span attributes are **intentionally excluded** from
the span to prevent PII leakage:

| Excluded attribute | Reason |
|---|---|
| `gen_ai.prompt` | Contains raw user input |
| `gen_ai.completion` | Contains model output |
| `http.request.body` | Contains full JSON payload |
| `http.response.body` | Contains model response |

Only token count attributes and safe metadata are recorded:

```
gen_ai.system
gen_ai.request.model
gen_ai.request.max_tokens
gen_ai.request.temperature
gen_ai.response.finish_reasons
gen_ai.usage.prompt_tokens
gen_ai.usage.completion_tokens
custom.correlation_id
custom.tenant_id
custom.consumer_name
```

---

## Data Residency

| Data type | Storage location | Retention |
|---|---|---|
| APIM gateway logs | Log Analytics workspace (same region) | 90 days (configurable) |
| OTel traces | Application Insights (same region) | 90 days (configurable) |
| Custom metrics | Azure Monitor (same region) | 93 days |
| Model input/output | **Not stored** (transient in Foundry) | N/A |

To comply with data residency requirements:

1. Deploy all resources in the required Azure region.
2. Do not enable cross-region geo-replication on Log Analytics unless required.
3. Set workspace `retentionInDays` to the minimum required by your policy.
4. Enable [Log Analytics workspace data purge](https://learn.microsoft.com/azure/azure-monitor/logs/personal-data-mgmt)
   for GDPR right-to-erasure requests.

---

## GDPR / Compliance Considerations

| Requirement | Implementation |
|---|---|
| **Data minimization** | Token counts + metadata only; no PII in logs by default |
| **Right to erasure** | Log Analytics workspace data purge API |
| **Purpose limitation** | Metrics used for billing/monitoring only; documented in privacy notice |
| **Consent** | End-user consent managed by the application layer (out of scope for this repo) |
| **Data Processor agreement** | Microsoft Online Services DPA covers Azure services |

---

## Audit Trail

For regulated industries, an audit trail can be built without storing PII:

1. **Correlation ID** links every APIM log entry to an OTel trace span.
2. **SHA-256 body hash** allows verifying whether two requests had identical
   content without storing the content.
3. **Token counts** enable billing audit without content.
4. **Timestamp** from APIM logs provides request timing.

```kql
// Audit trail: all requests by tenant in a time window
ApiManagementGatewayLogs
| where TimeGenerated between (ago(30d) .. now())
| where ApimSubscriptionId startswith "tenant-a-"
| project TimeGenerated, CorrelationId, OperationId,
          ResponseCode, DurationMs
| order by TimeGenerated desc
```

---

## Recommendations for Production

1. Enable `LOG_CONTENT_HASH_ENABLED=true` as the default for all workloads.
2. Set `LOG_CONTENT_REDACT_ENABLED=true` for healthcare, legal, or financial
   workloads where hashes are still too much.
3. Review Log Analytics workspace access permissions: restrict to the
   `Log Analytics Reader` or a custom role.
4. Enable diagnostic setting `logClientIp: false` (already the default in
   the Bicep module).
5. Rotate APIM subscription keys every 90 days. Use Azure Key Vault for
   storing keys at rest.
6. Document your data-processing flows in a DPIA if required.

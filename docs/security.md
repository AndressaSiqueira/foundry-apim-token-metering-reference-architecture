# Security Architecture

This document covers the security design of the reference implementation:
authentication, authorization, network isolation, secret management, and
a threat model.

---

## Principles

1. **Zero standing secrets** – No API keys in code, config, or environment
   variables in production. Managed Identity everywhere.
2. **Least privilege** – Each component has only the RBAC roles it needs.
3. **Defense in depth** – Multiple layers: network, identity, policy,
   application code.
4. **Privacy by default** – No PII in logs unless explicitly configured.
   (See [privacy.md](privacy.md).)
5. **Audit everything** – All APIM calls logged with correlation IDs.

---

## Authentication Flows

### Client → APIM

Two supported patterns:

**Pattern A: APIM Subscription Key (default for this sample)**

```
Client app sends:
  Ocp-Apim-Subscription-Key: <key>
  x-tenant-id: tenant-a
  x-consumer-name: order-bot

APIM validates:
  - Key exists and is active
  - Associated product is not over quota
  - Proceed with request
```

**Pattern B: Entra ID JWT (recommended for production)**

```
Client app acquires Entra ID token:
  audience: api://<apim-backend-app-id>
  scope: .default

APIM validates JWT:
  <validate-jwt
    header-name="Authorization"
    failed-validation-httpcode="401"
    require-expiration-time="true"
    require-scheme="Bearer" >
    <openid-config url="https://login.microsoftonline.com/<tenant-id>/.well-known/openid-configuration" />
    <audiences>
      <audience>api://<apim-backend-app-id></audience>
    </audiences>
  </validate-jwt>
```

### APIM → Azure AI Foundry

APIM uses its **system-assigned Managed Identity** to acquire a bearer
token for Azure Cognitive Services:

```xml
<authentication-managed-identity
  resource="https://cognitiveservices.azure.com/"
  output-token-variable-name="foundryToken" />
<set-header name="Authorization" exists-action="override">
  <value>@("Bearer " + (string)context.Variables["foundryToken"])</value>
</set-header>
```

The APIM Managed Identity is assigned the
`Cognitive Services OpenAI User` role on the Foundry resource.
No API keys are used or stored.

### Agent App → Azure Monitor (OTel)

The agent app uses `DefaultAzureCredential`:

- **On Azure (AKS, Container Apps, App Service)**: Workload Identity or
  system-assigned MI on the compute resource.
- **Locally**: Azure CLI credential or VS Code credential.

Required role: `Monitoring Metrics Publisher` on the Application Insights
component resource.

---

## RBAC Assignments

All assignments are provisioned by `infra/bicep/modules/identities.bicep`:

| Principal | Role | Scope |
|---|---|---|
| APIM system-assigned MI | `Cognitive Services OpenAI User` | Foundry resource |
| APIM system-assigned MI | `Monitoring Metrics Publisher` | Azure Monitor |
| Agent app MI | `Monitoring Metrics Publisher` | Application Insights |
| CI/CD service principal | `Contributor` | Resource group (infra deploy only) |
| Ops team (AAD group) | `Log Analytics Reader` | Log Analytics workspace |

---

## Network Isolation

### Default (no VNet)

All traffic flows over the Azure backbone (Microsoft global network).
Suitable for dev/test and most production scenarios.

### Recommended for regulated workloads

1. **APIM in Internal mode** inside an Azure Virtual Network.
2. **Private endpoint for Azure AI Foundry** (`privatelink.cognitiveservices.azure.com`).
3. **Private endpoint for Log Analytics** (`privatelink.ods.opinsights.azure.com`).
4. **Private endpoint for Application Insights** (OTLP ingestion endpoint).
5. **Azure Firewall or NSGs** to restrict outbound from APIM subnet to
   Foundry private endpoint only.
6. **Application Gateway** (WAF v2) as the public ingress in front of APIM.

```
Internet
  │
  ▼
Azure Application Gateway (WAF v2)   <-- public IP
  │
  ▼
APIM (internal mode, VNet subnet)
  │  private endpoint
  ▼
Azure AI Foundry  (no public endpoint)
```

---

## Secret Management

| Secret type | Storage | Rotation |
|---|---|---|
| APIM subscription keys | APIM (Azure-managed) | Manual or automated via Key Vault event |
| Foundry access | Managed Identity (no secret) | N/A (automatic token rotation) |
| OTel connection string | Azure Key Vault secret (Key Vault reference in App Settings) | Annual or on compromise |
| CI/CD credentials | GitHub Environments + OIDC federation | N/A (no long-lived secret) |

**Never** store secrets in:
- Source code
- `.env` files committed to git
- Docker image layers
- Application logs or telemetry

---

## APIM Threat Mitigations

| Threat | APIM Control |
|---|---|
| Prompt injection attacks | Input validation policy; body size limit |
| Abuse / cost overrun | Token limit policy (TPM/TPD) per subscription |
| DDoS | APIM rate-limit-by-key policy; Azure DDoS Protection |
| Credential theft | No API keys to steal; Managed Identity used throughout |
| Data exfiltration via response | Body logging disabled; network egress policy |
| SSRF | APIM backend URL is fixed; no user-controlled URL |
| Replay attacks | Entra ID JWT with `jti` claim + short expiry (Pattern B) |

---

## CI/CD Security

The GitHub Actions workflow (`ci.yml`) uses **OIDC federation** to
authenticate to Azure without storing long-lived secrets:

1. GitHub Actions OIDC provider is registered in Entra ID as a federated
   credential on the CI service principal.
2. The workflow requests a short-lived token from GitHub's OIDC endpoint.
3. Azure validates the token and issues an access token for the
   resource group.
4. No `AZURE_CLIENT_SECRET` is stored in GitHub Secrets.

> For the Bicep-validation-only CI job in this template, a `read-only`
> role on the subscription is sufficient.

---

## Threat Model Summary

| STRIDE category | Example threat | Mitigated by |
|---|---|---|
| **Spoofing** | Attacker impersonates a tenant | APIM subscription key or Entra JWT auth |
| **Tampering** | Request body modified in transit | TLS 1.2+ enforced; end-to-end HTTPS |
| **Repudiation** | Tenant denies making a request | APIM gateway logs with correlation ID |
| **Information disclosure** | Prompts leaked in logs | Body logging disabled; OTel span attributed token counts only |
| **Denial of service** | Tenant exhausts Foundry capacity | Token limit policy (TPM/TPD) |
| **Elevation of privilege** | App accesses another tenant's data | Separate APIM subscriptions per tenant; RBAC |

---

## Security Checklist for Production

- [ ] Replace APIM subscription key auth with Entra ID JWT validation.
- [ ] Enable APIM with VNet integration and private endpoint for Foundry.
- [ ] Enable Azure DDoS Standard on the VNet.
- [ ] Store OTel connection string in Key Vault; use Key Vault reference.
- [ ] Enable APIM `validate-content` policy to limit request body size.
- [ ] Set APIM TLS minimum version to 1.2.
- [ ] Enable Microsoft Defender for APIs on the APIM instance.
- [ ] Review and tighten NSG rules on the APIM subnet.
- [ ] Configure Azure Monitor alert for 401/403 rate spikes.
- [ ] Run `az apim validate` and review the APIM security baseline.

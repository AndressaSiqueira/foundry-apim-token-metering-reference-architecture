# Infrastructure (Bicep)

This directory contains the Bicep Infrastructure-as-Code for the token metering
reference architecture.

---

## Module Map

```
infra/bicep/
├── main.bicep               ← Orchestrator (deploy this)
├── main.bicepparam          ← Parameter values
└── modules/
    ├── log-analytics.bicep  ← Log Analytics Workspace
    ├── app-insights.bicep   ← Application Insights (workspace-based)
    ├── apim.bicep           ← API Management + Products + Logger
    ├── identities.bicep     ← User-Assigned MI + RBAC role assignments
    ├── diagnostic-settings.bicep  ← APIM diag → Log Analytics
    └── monitor-workbook.bicep     ← Token dashboard workbook
```

---

## Required Azure Roles

The deploying principal needs:

| Role | Scope | Reason |
|---|---|---|
| `Contributor` | Resource group | Create/update all resources |
| `User Access Administrator` | Resource group | Create RBAC assignments |

For the Foundry account in a separate resource group:

| Role | Scope | Reason |
|---|---|---|
| `Contributor` or `Cognitive Services Contributor` | Foundry resource group | Read Foundry resource for role assignment |
| `User Access Administrator` | Foundry resource | Assign `Cognitive Services OpenAI User` to APIM MI |

---

## Parameters Reference

| Parameter | Required | Default | Description |
|---|---|---|---|
| `environmentName` | No | `dev` | Environment prefix (2–10 chars) |
| `location` | No | RG location | Azure region |
| `foundryAccountName` | **Yes** | — | Foundry (Cognitive Services) account name |
| `foundryResourceGroupName` | No | same RG | RG containing the Foundry account |
| `apimPublisherEmail` | **Yes** | — | APIM publisher contact email |
| `apimPublisherName` | No | `Platform Team` | APIM publisher display name |
| `apimSku` | No | `Developer` | `Developer`, `StandardV2`, or `Premium` |
| `apimSkuCapacity` | No | `1` | Number of APIM units |
| `logRetentionDays` | No | `90` | Log Analytics retention (30–730) |
| `tags` | No | `{...}` | Resource tags |

---

## Deployment Commands

### Validate

```bash
az bicep build --file infra/bicep/main.bicep
az deployment group validate \
  --resource-group rg-token-metering \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/main.bicepparam
```

### What-if (dry run)

```bash
az deployment group what-if \
  --resource-group rg-token-metering \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/main.bicepparam
```

### Deploy

```bash
az deployment group create \
  --resource-group rg-token-metering \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/main.bicepparam \
  --name deploy-$(date +%Y%m%d%H%M%S)
```

### Retrieve outputs

```bash
az deployment group show \
  --resource-group rg-token-metering \
  --name <deployment-name> \
  --query properties.outputs
```

---

## Resource Naming Convention

All resources use the prefix `tm-<environmentName>-`:

| Resource | Name pattern |
|---|---|
| Log Analytics | `law-tm-<env>` |
| Application Insights | `appi-tm-<env>` |
| API Management | `apim-tm-<env>` |
| User-assigned MI | `id-agent-app-tm-<env>` |

---

## Post-Deployment Steps

1. **Update the Foundry endpoint** named value in APIM:
   ```bash
   az apim nv update \
     --service-name apim-tm-dev \
     --resource-group rg-token-metering \
     --named-value-id foundry-endpoint \
     --value "https://<your-foundry>.cognitiveservices.azure.com"
   ```

2. **Apply APIM policies** (see [../../policies/README.md](../../policies/README.md)).

3. **Create APIM API** pointing to the Foundry endpoint.

4. **Create APIM subscriptions** for each tenant and store keys securely.

5. **Configure the agent app** with the APIM gateway URL and subscription key.

---

## Tear Down

```bash
az group delete --name rg-token-metering --yes --no-wait
```

> Warning: this deletes ALL resources including the Foundry account
> if it was deployed in the same resource group. Use a separate RG for
> the Foundry account if you want to preserve it.

// =============================================================================
// main.bicepparam – Parameter file for main.bicep
//
// Usage:
//   az deployment group create \
//     --resource-group rg-token-metering \
//     --template-file infra/bicep/main.bicep \
//     --parameters infra/bicep/main.bicepparam
// =============================================================================

using './main.bicep'

param environmentName = 'dev'
param location = 'eastus2'

// Replace with the name of your Azure AI Foundry (Cognitive Services) account
param foundryAccountName = 'YOUR_FOUNDRY_ACCOUNT_NAME'

// Leave empty to use the same resource group as the deployment
param foundryResourceGroupName = ''

// APIM publisher details
param apimPublisherEmail = 'platform@contoso.com'
param apimPublisherName = 'Platform Team'

// Developer SKU is suitable for dev/test.
// Use 'StandardV2' or 'Premium' for production.
param apimSku = 'Developer'
param apimSkuCapacity = 1

param logRetentionDays = 90

param tags = {
  environment: 'dev'
  project: 'token-metering-reference'
  managedBy: 'bicep'
  costCenter: 'platform'
}

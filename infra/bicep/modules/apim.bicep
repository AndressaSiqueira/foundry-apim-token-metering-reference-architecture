// =============================================================================
// modules/apim.bicep
// Deploys Azure API Management with AI Gateway configuration.
// =============================================================================

param name string
param location string
param publisherEmail string
param publisherName string
param sku string = 'Developer'
param skuCapacity int = 1
param logAnalyticsWorkspaceId string
param tags object = {}

// ---------------------------------------------------------------------------
// API Management service
// ---------------------------------------------------------------------------

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
    capacity: skuCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    // Disable public network access for internal-mode deployments;
    // set to 'Enabled' for the default public topology
    publicNetworkAccess: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// APIM Logger (sends gateway logs to Log Analytics)
// ---------------------------------------------------------------------------

resource apimLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = {
  parent: apimService
  name: 'azuremonitor'
  properties: {
    loggerType: 'azureMonitor'
    isBuffered: true
    description: 'Azure Monitor logger for APIM gateway logs'
    resourceId: logAnalyticsWorkspaceId
  }
}

// ---------------------------------------------------------------------------
// APIM Products (tier definitions)
// ---------------------------------------------------------------------------

resource productFree 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apimService
  name: 'ai-free'
  properties: {
    displayName: 'AI Free'
    description: 'Free tier: 40,000 TPD. For development and sandbox tenants.'
    state: 'published'
    subscriptionRequired: true
    approvalRequired: false
    subscriptionsLimit: 100
  }
}

resource productStandard 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apimService
  name: 'ai-standard'
  properties: {
    displayName: 'AI Standard'
    description: 'Standard tier: 400,000 TPD. For production tenants.'
    state: 'published'
    subscriptionRequired: true
    approvalRequired: true
    subscriptionsLimit: 500
  }
}

resource productPremium 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apimService
  name: 'ai-premium'
  properties: {
    displayName: 'AI Premium'
    description: 'Premium tier: 4,000,000 TPD. For high-volume and VIP tenants.'
    state: 'published'
    subscriptionRequired: true
    approvalRequired: true
    subscriptionsLimit: 50
  }
}

// ---------------------------------------------------------------------------
// Named values (APIM safe configuration references)
// ---------------------------------------------------------------------------

resource nvFoundryEndpoint 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apimService
  name: 'foundry-endpoint'
  properties: {
    displayName: 'foundry-endpoint'
    // Placeholder – set to your Foundry endpoint after deployment
    value: 'https://YOUR_FOUNDRY_ACCOUNT.cognitiveservices.azure.com'
    secret: false
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output apimName string = apimService.name
output resourceId string = apimService.id
output gatewayUrl string = apimService.properties.gatewayUrl
output principalId string = apimService.identity.principalId
output loggerId string = apimLogger.id

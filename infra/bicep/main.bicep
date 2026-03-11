// =============================================================================
// main.bicep – Orchestrator template for the Token Metering Reference Architecture
//
// Deploys:
//   - Log Analytics Workspace
//   - Application Insights (workspace-based)
//   - API Management (AI Gateway)
//   - Managed Identity + RBAC assignments
//   - Diagnostic settings (APIM → Log Analytics)
//   - Azure Monitor Workbook (token dashboard)
// =============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Environment name prefix used in all resource names (e.g. dev, prod).')
@minLength(2)
@maxLength(10)
param environmentName string = 'dev'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Name of the Azure AI Foundry (Cognitive Services) account this APIM will proxy.')
param foundryAccountName string

@description('Resource group that contains the Foundry account (defaults to the same RG).')
param foundryResourceGroupName string = resourceGroup().name

@description('APIM publisher email.')
param apimPublisherEmail string

@description('APIM publisher display name.')
param apimPublisherName string = 'Platform Team'

@description('APIM SKU. Use Developer for dev/test, StandardV2 or Premium for production.')
@allowed(['Developer', 'StandardV2', 'Premium'])
param apimSku string = 'Developer'

@description('APIM SKU capacity (units). Developer=1 only.')
param apimSkuCapacity int = 1

@description('Log Analytics data retention in days.')
@minValue(30)
@maxValue(730)
param logRetentionDays int = 90

@description('Resource tags applied to all resources.')
param tags object = {
  environment: environmentName
  project: 'token-metering-reference'
  managedBy: 'bicep'
}

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

var prefix = 'tm-${environmentName}'

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'deploy-log-analytics'
  params: {
    name: 'law-${prefix}'
    location: location
    retentionInDays: logRetentionDays
    tags: tags
  }
}

module appInsights 'modules/app-insights.bicep' = {
  name: 'deploy-app-insights'
  params: {
    name: 'appi-${prefix}'
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

module identities 'modules/identities.bicep' = {
  name: 'deploy-identities'
  params: {
    location: location
    prefix: prefix
    foundryAccountName: foundryAccountName
    foundryResourceGroupName: foundryResourceGroupName
    appInsightsResourceId: appInsights.outputs.resourceId
    tags: tags
  }
}

module apim 'modules/apim.bicep' = {
  name: 'deploy-apim'
  params: {
    name: 'apim-${prefix}'
    location: location
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    sku: apimSku
    skuCapacity: apimSkuCapacity
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

module diagnostics 'modules/diagnostic-settings.bicep' = {
  name: 'deploy-diagnostics'
  params: {
    apimName: apim.outputs.apimName
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
  }
  dependsOn: [apim, logAnalytics]
}

module workbook 'modules/monitor-workbook.bicep' = {
  name: 'deploy-workbook'
  params: {
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    appInsightsResourceId: appInsights.outputs.resourceId
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// RBAC: grant APIM MI the Cognitive Services OpenAI User role on Foundry
// ---------------------------------------------------------------------------

module foundryRbac 'modules/identities.bicep' = {
  name: 'assign-apim-foundry-rbac'
  scope: resourceGroup(foundryResourceGroupName)
  params: {
    location: location
    prefix: prefix
    foundryAccountName: foundryAccountName
    foundryResourceGroupName: foundryResourceGroupName
    appInsightsResourceId: appInsights.outputs.resourceId
    apimPrincipalId: apim.outputs.principalId
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output apimGatewayUrl string = apim.outputs.gatewayUrl
output apimName string = apim.outputs.apimName
output logAnalyticsWorkspaceId string = logAnalytics.outputs.workspaceId
output appInsightsConnectionString string = appInsights.outputs.connectionString
output appInsightsInstrumentationKey string = appInsights.outputs.instrumentationKey

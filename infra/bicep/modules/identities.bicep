// =============================================================================
// modules/identities.bicep
// Provisions RBAC role assignments for Managed Identities.
//
// Role assignments:
//   1. APIM system-assigned MI → Cognitive Services OpenAI User (on Foundry)
//   2. Agent app user-assigned MI → Monitoring Metrics Publisher (on App Insights)
// =============================================================================

param location string
param prefix string
param foundryAccountName string
param foundryResourceGroupName string
param appInsightsResourceId string
param tags object = {}

// Optional: APIM principal ID when this module is called as a scope-scoped module
param apimPrincipalId string = ''

// ---------------------------------------------------------------------------
// Built-in role definition IDs
// ---------------------------------------------------------------------------

var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var monitoringMetricsPublisherRoleId = '3913510d-42f4-4e42-8a64-420c390055eb'

// ---------------------------------------------------------------------------
// User-assigned Managed Identity for the agent app
// ---------------------------------------------------------------------------

resource agentAppIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-agent-app-${prefix}'
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------
// Existing Foundry resource reference (for role assignment scope)
// ---------------------------------------------------------------------------

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' existing = {
  name: foundryAccountName
  scope: resourceGroup(foundryResourceGroupName)
}

// ---------------------------------------------------------------------------
// Role assignment: APIM MI → Cognitive Services OpenAI User on Foundry
// (Only created if apimPrincipalId is provided)
// ---------------------------------------------------------------------------

resource apimFoundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(apimPrincipalId)) {
  name: guid(foundryAccount.id, apimPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: apimPrincipalId
    principalType: 'ServicePrincipal'
    description: 'APIM MI: Cognitive Services OpenAI User on Foundry account'
  }
}

// ---------------------------------------------------------------------------
// Role assignment: Agent app MI → Monitoring Metrics Publisher on App Insights
// ---------------------------------------------------------------------------

resource agentAppMetricsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsightsResourceId, agentAppIdentity.id, monitoringMetricsPublisherRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', monitoringMetricsPublisherRoleId)
    principalId: agentAppIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Agent app MI: Monitoring Metrics Publisher on App Insights'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output agentAppIdentityId string = agentAppIdentity.id
output agentAppIdentityClientId string = agentAppIdentity.properties.clientId
output agentAppIdentityPrincipalId string = agentAppIdentity.properties.principalId

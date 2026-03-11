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
param appInsightsResourceId string
param tags object = {}

// ---------------------------------------------------------------------------
// Built-in role definition IDs
// ---------------------------------------------------------------------------

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
// Role assignment: Agent app MI → Monitoring Metrics Publisher on App Insights
// ---------------------------------------------------------------------------

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: last(split(appInsightsResourceId, '/'))
}

resource agentAppMetricsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsightsResourceId, agentAppIdentity.id, monitoringMetricsPublisherRoleId)
  scope: appInsights
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

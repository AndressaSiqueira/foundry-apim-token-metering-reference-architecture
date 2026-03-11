// =============================================================================
// modules/foundry-rbac.bicep
// Assigns APIM managed identity access to Azure AI Foundry account.
// Deploy this module at the Foundry resource group scope.
// =============================================================================

targetScope = 'resourceGroup'

param foundryAccountName string
param apimPrincipalId string

var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' existing = {
  name: foundryAccountName
}

resource apimFoundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, apimPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: apimPrincipalId
    principalType: 'ServicePrincipal'
    description: 'APIM MI: Cognitive Services OpenAI User on Foundry account'
  }
}

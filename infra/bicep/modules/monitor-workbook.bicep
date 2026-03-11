// =============================================================================
// modules/monitor-workbook.bicep
// Deploys an Azure Monitor Workbook as the token usage dashboard.
// =============================================================================

param location string
param logAnalyticsWorkspaceId string
param tags object = {}

// Unique ID for the workbook
var workbookId = guid(resourceGroup().id, 'token-metering-workbook')

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: workbookId
  location: location
  kind: 'shared'
  tags: union(tags, {
    'hidden-title': 'Token Metering Dashboard'
  })
  properties: {
    displayName: 'Token Metering Dashboard'
    description: 'End-to-end token usage, estimated cost, quota consumption, and latency for Foundry + APIM AI Gateway'
    category: 'workbook'
    sourceId: logAnalyticsWorkspaceId
    // Workbook JSON definition (serialized ARM workbook format)
    serializedData: string(loadJsonContent('../workbook-template.json'))
  }
}

output workbookId string = workbook.id
output workbookName string = workbook.name

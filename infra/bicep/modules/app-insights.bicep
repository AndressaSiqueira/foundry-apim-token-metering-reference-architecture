// =============================================================================
// modules/app-insights.bicep
// Deploys a workspace-based Application Insights component.
// =============================================================================

param name string
param location string
param logAnalyticsWorkspaceId string
param tags object = {}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    // Disable classic ingestion; all data goes to Log Analytics workspace
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: 90
    // Disable sampling by default; agent app controls sampling via OTel SDK
    SamplingPercentage: null
  }
}

output resourceId string = appInsights.id
output instrumentationKey string = appInsights.properties.InstrumentationKey
output connectionString string = appInsights.properties.ConnectionString
output appId string = appInsights.properties.AppId

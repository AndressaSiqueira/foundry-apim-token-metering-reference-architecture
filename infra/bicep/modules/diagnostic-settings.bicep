// =============================================================================
// modules/diagnostic-settings.bicep
// Configures APIM diagnostic settings to send logs and metrics to Log Analytics.
// =============================================================================

param apimName string
param logAnalyticsWorkspaceId string

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimName
}

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${apimName}'
  scope: apimService
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        // Gateway request/response logs (headers only; no body for privacy)
        category: 'GatewayLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'WebSocketConnectionLogs'
        enabled: false
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        // Includes Capacity, Duration, Requests, EventHubDroppedEvents metrics
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    // logClientIp is set at the diagnostics/service level, not here
    // Body logging: disabled by default (privacy-first)
    // Set verbosity to 'information' for headers only
  }
}

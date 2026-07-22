targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short lowercase prefix used in resource names.')
@minLength(3)
@maxLength(18)
param namePrefix string

@description('Developer and other trusted public IPv4 addresses allowed to reach Foundry. Portal NAT egress is added automatically.')
param allowedPublicIps array

@description('Container image for the KM portal. azd replaces this during deployment.')
param kmPortalImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Resource-group budget notification recipients. Leave empty to skip budget deployment.')
param budgetContactEmails array = []

@description('Budget start date. Defaults to the first day of the deployment month.')
param budgetStartDate string = utcNow('yyyy-MM-01')

@description('Microsoft Entra tenant ID for single-tenant portal authentication.')
param entraTenantId string

@description('Application (client) ID of the Entra portal API registration.')
param entraPortalClientId string

@description('Expected audience in Entra access tokens presented to the portal API.')
param entraApiAudience string

@secure()
@description('Confidential-client secret used only for delegated Microsoft Graph OBO token exchange.')
param portalEntraClientSecret string

@secure()
@description('Random value used to hash artifact owners in Blob metadata.')
param artifactOwnerHashSalt string

@description('Container Apps VNet address prefix.')
param vnetAddressPrefix string = '10.20.0.0/16'

@description('Container Apps infrastructure subnet prefix. Must be /23 or larger.')
param infrastructureSubnetPrefix string = '10.20.0.0/23'

var tags = {
  workload: 'km-agents-foundry-scenario'
  dataClassification: 'synthetic-only'
}

var foundryAccountName = '${namePrefix}-foundry'
var foundryProjectName = '${namePrefix}-project'
var logAnalyticsName = '${namePrefix}-logs'
var appInsightsName = '${namePrefix}-appi'
var vnetName = '${namePrefix}-vnet'
var subnetName = 'container-apps-infrastructure'
var natGatewayName = '${namePrefix}-nat'
var portalPublicIpName = '${namePrefix}-portal-egress-pip'
var containerEnvName = '${namePrefix}-cae'
var portalAppName = '${namePrefix}-km-portal'
var portalIdentityName = '${namePrefix}-portal-id'
var portalArtifactsStorageName = toLower(take('${replace(namePrefix, '-', '')}${uniqueString(resourceGroup().id)}artifacts', 24))
var keyVaultName = toLower(take('${replace(namePrefix, '-', '')}${uniqueString(resourceGroup().id)}kv', 24))

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    DisableIpMasking: false
  }
}

resource portalIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: portalIdentityName
  location: location
  tags: tags
}

resource portalKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 90
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'None'
      defaultAction: 'Deny'
      ipRules: [
        {
          value: portalPublicIp.properties.ipAddress
        }
      ]
    }
  }
}

resource portalEntraSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: portalKeyVault
  name: 'entra-client-secret'
  properties: {
    value: portalEntraClientSecret
  }
}

resource artifactOwnerHashSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: portalKeyVault
  name: 'artifact-owner-hash-salt'
  properties: {
    value: artifactOwnerHashSalt
  }
}

resource artifactStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: portalArtifactsStorageName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'None'
      defaultAction: 'Deny'
      ipRules: [
        {
          action: 'Allow'
          value: portalPublicIp.properties.ipAddress
        }
      ]
    }
  }
}

resource artifactBlobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: artifactStorage
  name: 'default'
}

resource artifactContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: artifactBlobService
  name: 'case-study-artifacts'
  properties: {
    publicAccess: 'None'
  }
}

resource artifactLifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: artifactStorage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          enabled: true
          name: 'delete-expired-artifacts'
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'case-studies/'
              ]
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: 1
                }
              }
            }
          }
        }
      ]
    }
  }
}

resource portalPublicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: portalPublicIpName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
  }
}

resource natGateway 'Microsoft.Network/natGateways@2024-05-01' = {
  name: natGatewayName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 10
    publicIpAddresses: [
      {
        id: portalPublicIp.id
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
  }
}

resource infrastructureSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: subnetName
  properties: {
    addressPrefix: infrastructureSubnetPrefix
    delegations: [
      {
        name: 'Microsoft.App-environments'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
    natGateway: {
      id: natGateway.id
    }
  }
}

var configuredIpRules = [for ip in allowedPublicIps: {
  value: ip
}]

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: concat(configuredIpRules, [
        {
          value: portalPublicIp.properties.ipAddress
        }
      ])
      virtualNetworkRules: []
    }
    disableLocalAuth: true
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: foundryProjectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'KM Agents'
    description: 'Prompt and hosted case-study generation agent graphs.'
  }
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvName
  location: location
  tags: tags
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: infrastructureSubnet.id
      internal: false
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource portalApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: portalAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${portalIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: cae.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        {
          name: 'entra-client-secret'
          keyVaultUrl: portalEntraSecret.properties.secretUriWithVersion
          identity: portalIdentity.id
        }
        {
          name: 'artifact-owner-hash-salt'
          keyVaultUrl: artifactOwnerHashSecret.properties.secretUriWithVersion
          identity: portalIdentity.id
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'km-portal'
          image: kmPortalImage
          env: [
            {
              name: 'FOUNDRY_PROJECT_ENDPOINT'
              value: 'https://${foundry.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
            {
              name: 'TEMPLATE_POLICY_PATH'
              value: '/app/assets/templates/contoso-template-policy.json'
            }
            {
              name: 'MAX_REPAIR_ATTEMPTS'
              value: '2'
            }
            {
              name: 'KM_AGENTS_ENVIRONMENT'
              value: 'production'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: portalIdentity.properties.clientId
            }
            {
              name: 'AZURE_STORAGE_BLOB_ENDPOINT'
              value: artifactStorage.properties.primaryEndpoints.blob
            }
            {
              name: 'ARTIFACT_CONTAINER_NAME'
              value: artifactContainer.name
            }
            {
              name: 'ARTIFACT_STORAGE_MODE'
              value: 'blob'
            }
            {
              name: 'ENTRA_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'ENTRA_PORTAL_CLIENT_ID'
              value: entraPortalClientId
            }
            {
              name: 'ENTRA_API_AUDIENCE'
              value: entraApiAudience
            }
            {
              name: 'ENTRA_CLIENT_SECRET'
              secretRef: 'entra-client-secret'
            }
            {
              name: 'ARTIFACT_OWNER_HASH_SALT'
              secretRef: 'artifact-owner-hash-salt'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'startup'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 0
              periodSeconds: 10
              failureThreshold: 30
            }
            {
              type: 'liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'readiness'
              httpGet: {
                path: '/readyz'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource portalFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, portalIdentity.id, cognitiveServicesUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: cognitiveServicesUserRoleId
    principalId: portalIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource portalBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(artifactStorage.id, portalIdentity.id, storageBlobDataContributorRoleId)
  scope: artifactStorage
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleId
    principalId: portalIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource portalKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(portalKeyVault.id, portalIdentity.id, keyVaultSecretsUserRoleId)
  scope: portalKeyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: portalIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource portalNetworkBudget 'Microsoft.Consumption/budgets@2023-11-01' = if (length(budgetContactEmails) > 0) {
  name: '${namePrefix}-portal-network-monthly'
  properties: {
    category: 'Cost'
    amount: 50
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
      endDate: '2035-12-31'
    }
    notifications: {
      Actual_GreaterThan_80_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: budgetContactEmails
      }
      Actual_GreaterThan_100_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: budgetContactEmails
      }
    }
  }
}

output foundryAccountName string = foundry.name
output foundryProjectName string = foundryProject.name
output foundryProjectEndpoint string = 'https://${foundry.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
output kmPortalUrl string = 'https://${portalApp.properties.configuration.ingress.fqdn}'
output portalManagedIdentityClientId string = portalIdentity.properties.clientId
output portalStaticEgressIp string = portalPublicIp.properties.ipAddress
output artifactStorageBlobEndpoint string = artifactStorage.properties.primaryEndpoints.blob
output portalKeyVaultUri string = portalKeyVault.properties.vaultUri
output configuredDeveloperAllowedPublicIps array = allowedPublicIps

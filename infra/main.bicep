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

@description('Object ID of the Entra group whose members may invoke Foundry with user OBO credentials.')
param foundryUserGroupObjectId string

@secure()
@description('Confidential-client secret used only for Foundry OBO token exchange.')
param portalEntraClientSecret string

@secure()
@description('Random value used to hash artifact owners in Blob metadata.')
param artifactOwnerHashSalt string

@description('Container Apps VNet address prefix.')
param vnetAddressPrefix string = '10.20.0.0/16'

@description('Container Apps infrastructure subnet prefix. Must be /23 or larger.')
param infrastructureSubnetPrefix string = '10.20.0.0/23'

@description('Subnet prefix for private endpoints (Key Vault, Storage) required because a tenant policy forces those resources to publicNetworkAccess Disabled.')
param privateEndpointSubnetPrefix string = '10.20.2.0/24'

@description('Chat model deployment name. Must match AZURE_AI_MODEL_DEPLOYMENT_NAME / azure.yaml.')
param modelDeploymentName string = 'gpt-5.4-mini'

@description('Chat model version to deploy.')
param modelDeploymentVersion string = '2026-03-17'

@description('GlobalStandard SKU capacity (thousands of tokens per minute) for the chat model deployment.')
param modelDeploymentCapacity int = 20

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
var foundryCustomSubdomainName = toLower('${replace(namePrefix, '-', '')}-${uniqueString(subscription().id, resourceGroup().id, foundryAccountName)}')
var containerRegistryName = toLower(take('${replace(namePrefix, '-', '')}${uniqueString(resourceGroup().id)}acr', 50))

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

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: containerRegistryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
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
    // A tenant-wide Azure Policy (modify effect: keyvaultpublicnetworkmodify) forces this to
    // Disabled regardless of what is declared here, so it is declared explicitly to match the
    // enforced reality. Access is via the private endpoint below plus RBAC; network ACLs are
    // vestigial once public access is disabled but are left in place for defense in depth if the
    // policy is ever relaxed.
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      bypass: 'None'
      defaultAction: 'Deny'
      ipRules: concat(configuredIpRules, [
        {
          value: portalPublicIp.properties.ipAddress
        }
      ])
      virtualNetworkRules: [
        {
          id: infrastructureSubnet.id
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

resource artifactStorage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
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
    // A tenant-wide Azure Policy (modify effect: storageaccountpublicnetworkmodify) forces this
    // to Disabled regardless of what is declared here, so it is declared explicitly. Access is
    // via the private endpoint below plus RBAC.
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      bypass: 'None'
      defaultAction: 'Deny'
      ipRules: [for ip in allowedPublicIps: {
        action: 'Allow'
        value: ip
      }]
      virtualNetworkRules: [
        {
          action: 'Allow'
          id: infrastructureSubnet.id
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
    serviceEndpoints: [
      {
        service: 'Microsoft.KeyVault'
      }
      {
        service: 'Microsoft.Storage.Global'
      }
    ]
  }
}

// A tenant-wide Azure Policy (modify effect) forces Key Vault and Storage account
// publicNetworkAccess to Disabled regardless of what this template requests, so both need
// private endpoints reachable from the portal's Container Apps environment. Private endpoints
// cannot share the Microsoft.App/environments-delegated subnet, hence a dedicated subnet.
resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: 'private-endpoints'
  properties: {
    addressPrefix: privateEndpointSubnetPrefix
    privateEndpointNetworkPolicies: 'Disabled'
  }
  dependsOn: [
    infrastructureSubnet
  ]
}

resource keyVaultPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
  tags: tags
}

resource keyVaultPrivateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: keyVaultPrivateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource storagePrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.blob.${environment().suffixes.storage}'
  location: 'global'
  tags: tags
}

resource storagePrivateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: storagePrivateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource keyVaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${keyVaultName}-pe'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: '${keyVaultName}-plsc'
        properties: {
          privateLinkServiceId: portalKeyVault.id
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

resource keyVaultPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: keyVaultPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-vaultcore-azure-net'
        properties: {
          privateDnsZoneId: keyVaultPrivateDnsZone.id
        }
      }
    ]
  }
}

resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${portalArtifactsStorageName}-pe'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: '${portalArtifactsStorageName}-plsc'
        properties: {
          privateLinkServiceId: artifactStorage.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource storagePrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: storagePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob-storage'
        properties: {
          privateDnsZoneId: storagePrivateDnsZone.id
        }
      }
    ]
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
    // Required before the Foundry account can host project resources.
    allowProjectManagement: true
    // Projects require a globally unique custom subdomain on AIServices accounts.
    customSubDomainName: foundryCustomSubdomainName
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

// Chat model deployment consumed by the Prompt and Hosted agents (referenced by
// AZURE_AI_MODEL_DEPLOYMENT_NAME). azure.yaml declares this same deployment under the
// `ai-project` service, but this custom Bicep template doesn't use azd's pre-provision
// hooks, so the deployment must be created explicitly here as well.
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: modelDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: modelDeploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelDeploymentName
      version: modelDeploymentVersion
    }
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
  tags: union(tags, {
    'azd-service-name': 'km-portal'
  })
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
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: portalIdentity.id
        }
      ]
      // NOTE: Azure Container Apps' keyVaultUrl secret references are resolved by the platform
      // control plane at deployment time from OUTSIDE the customer VNet -- they never traverse a
      // private endpoint, even when one exists and DNS/RBAC are correctly configured. A tenant
      // policy in this subscription forces Key Vault publicNetworkAccess to Disabled, so
      // keyVaultUrl-based secrets can never resolve here. The values are passed directly as
      // native Container App secrets instead (still `@secure()` params, never logged). The
      // values are also written to Key Vault above for audit/rotation tooling, but the Container
      // App does not depend on Key Vault being reachable to start.
      secrets: [
        {
          name: 'entra-client-secret'
          value: portalEntraClientSecret
        }
        {
          name: 'artifact-owner-hash-salt'
          value: artifactOwnerHashSalt
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
              value: 'https://${foundryCustomSubdomainName}.services.ai.azure.com/api/projects/${foundryProject.name}'
            }
            {
              name: 'PROMPT_ORCHESTRATOR_AGENT_NAME'
              value: 'km-prompt-orchestrator'
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

var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource foundryUserGroup 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, foundryUserGroupObjectId, cognitiveServicesUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: cognitiveServicesUserRoleId
    principalId: foundryUserGroupObjectId
    principalType: 'Group'
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

resource portalAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, portalIdentity.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRoleId
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
output foundryProjectEndpoint string = 'https://${foundryCustomSubdomainName}.services.ai.azure.com/api/projects/${foundryProject.name}'
output kmPortalUrl string = 'https://${portalApp.properties.configuration.ingress.fqdn}'
output portalManagedIdentityClientId string = portalIdentity.properties.clientId
output portalStaticEgressIp string = portalPublicIp.properties.ipAddress
output artifactStorageBlobEndpoint string = artifactStorage.properties.primaryEndpoints.blob
output portalKeyVaultUri string = portalKeyVault.properties.vaultUri
output configuredDeveloperAllowedPublicIps array = allowedPublicIps
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer

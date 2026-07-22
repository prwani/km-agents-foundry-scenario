# KM-Agents Deployment Plan

## Status

Blocked

## Scope

Deploy the existing Python Microsoft Foundry case-study scenario to Sweden
Central. The secure portal path, production artifact infrastructure, and
Microsoft 365 Copilot packaging are prepared; provisioning begins only after
this plan is approved and validation succeeds.

## Azure Context

- **Subscription**: ME-M365CPI88726844-prafullawani-1
  (`6f52fedd-df2c-47f7-a01f-e48682864606`)
- **Tenant**: `a3321a7a-958c-4f4a-ad4f-f4d9c193c977`
- **Location**: Sweden Central (`swedencentral`)
- **AZD environment**: `km-agents-swc`
- **Resource group**: `rg-km-agents-swc`

Microsoft Foundry and Azure Container Apps providers are registered and both
support Sweden Central. Existing Azure Policy assignments concern Defender
coverage for database services and do not impose conflicting requirements.

## Current architecture

- Azure Container Apps hosts the authenticated KM portal with VNet integration
  solely for NAT Gateway static egress.
- Microsoft Foundry remains publicly reachable with `defaultAction: Deny` and
  an explicit IPv4 allow-list because Work IQ does not support VNet-restricted
  Foundry endpoints.
- The system has isolated Prompt and Hosted three-agent graphs. The Hosted
  generator uses Agent Framework Harness and the repository-owned PPTX skill.
- Work IQ runs in delegated user context. The portal will use OBO for Microsoft
  Graph source retrieval.
- Case-study artifacts are validated fail-closed against the canonical
  Contoso template and sensitivity policy. Portal downloads are authenticated,
  single-use, and expire after 15 minutes.

## Remaining preparation work

1. Create the single-tenant `km-agents-portal` Entra application registration,
   expose an `access_as_user` scope, add delegated Microsoft Graph `Files.Read`,
   and create an expiring confidential-client secret. The secret value is used
   only as a secure deployment parameter and is stored in the deployment Key
   Vault.
2. Create the `km-agents-swc` azd environment, bind it to the confirmed
   subscription and Sweden Central, and check that the target resource group
   has no resource or Container Apps environment conflict.
3. Obtain the developer workstation's public IPv4 address and use it, plus the
   provisioned NAT static IP, as the Foundry selected-IP allow-list.
4. Supply the required tenant-owned Work IQ connection and A2A connection IDs,
   template URL, and optional budget notification recipients. Provision
   specialists before their orchestrators.
5. Implement the Hosted Foundry session file-transfer adapter only after the
   installed SDK exposes supported create-session, upload, download, and
   cleanup APIs. Hosted portal requests remain fail-closed until then.
6. Run all source, Bicep, azd preview, policy, RBAC, and runtime validation.
   Record results in this plan before the deployment workflow.

## Execution sequence

1. Provision the secure foundation: Foundry account/project and model,
   Container Apps environment with NAT static egress, Key Vault, private Blob
   storage, managed identity, observability, and the protected portal.
2. Deploy the Hosted specialist agents and configure their A2A connections.
3. Create immutable Prompt specialist versions, configure Prompt A2A
   connections, then create the Prompt orchestrator.
4. Validate both stacks and publish the separate Microsoft 365 Copilot
   packages only after tenant administrator approval.

## Current blocker

On 2026-07-22, Azure CLI successfully obtained an ARM/Graph token for tenant
`a3321a7a-958c-4f4a-ad4f-f4d9c193c977`, but Microsoft Graph control-plane calls
used by `az ad app` and `az rest` were rejected with Conditional Access error
`TokenCreatedWithOutdatedPolicies`. No Entra application, azd environment, or
Azure resource was created. Resume only after a full interactive
`az logout` followed by `az login --tenant a3321a7a-958c-4f4a-ad4f-f4d9c193c977`
and target-subscription selection completes successfully.

## Security decisions

- No credentials, tokens, Microsoft 365 content, or non-synthetic customer
  artifacts are stored in source control.
- The deployment creates a Key Vault for the confidential OBO client secret and artifact-owner
  hash salt. Both values are secure deployment inputs and are injected into Container Apps by
  Key Vault reference; they are never stored in azd files.
- OBO access is scoped to each signed-in user; application-only Graph access
  is not used for source retrieval.
- Each generated PPTX must pass deterministic validation before delivery.
- Production artifact delivery uses a private, firewall-restricted Blob container with
  managed-identity access, 15-minute owner-bound single-use application enforcement, and a
  one-day cleanup lifecycle policy for unconsumed blobs.

## Deployment boundary

The Hosted portal path cannot be exposed as functional until supported Foundry
hosted-session file APIs are available. Work IQ and A2A connection IDs require
tenant/operator configuration and must never be guessed or replaced with
placeholders. After those values are provided, the next mandatory workflow is
`azure-validate` followed by `azure-deploy`.

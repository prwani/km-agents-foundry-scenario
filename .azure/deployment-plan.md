# KM-Agents Deployment Plan

## Status

Planning

## Scope

Prepare the existing Python Microsoft Foundry case-study scenario for a later
Azure deployment. The secure portal path, production artifact infrastructure,
and Microsoft 365 Copilot packaging are prepared; this plan does not authorize
provisioning or deployment.

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

1. Implement the Hosted Foundry session file-transfer adapter only after the
   installed SDK exposes the supported create-session, upload, download, and
   cleanup APIs. The portal deliberately fails closed for Hosted requests until
   then; it must not call undocumented REST endpoints.
2. Collect results for the completed evaluation runner and produce the synthetic
   comparison report.
3. Finalize actual deployment values and connection setup for Foundry A2A,
   Work IQ, Container Apps NAT egress, selected-IP access, and Entra OAuth.
4. Validate source, Bicep, contracts, generated assets, and deployment
   configuration before any deployment request.

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

Deployment is intentionally deferred. Before deployment, confirm the Azure
subscription, region, selected public IPs, budget notification recipient,
tenant administrator consent, Work IQ connection IDs, and Microsoft 365
Copilot publication settings. Then validate with `azure-validate` before
using `azure-deploy`.

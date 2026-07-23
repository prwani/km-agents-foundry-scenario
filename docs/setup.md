# Setup and deployment

## Prerequisites

- Azure CLI and Azure Developer CLI installed.
- An Azure subscription with permissions to deploy resource groups, Cognitive Services/Foundry resources, Container Apps, managed identities, role assignments, Log Analytics, and Application Insights.
- azd extensions for Foundry agents/projects installed where needed.
- A single-tenant Entra application registration for the KM portal API.
- An Entra group containing portal users, assigned the Cognitive Services User role on the Foundry account. The portal does not receive a Foundry data-plane role; it calls Foundry with each user's OBO credential.
- A list of public IPv4 addresses allowed to call Foundry:
  - Developer workstation public IPs.
  - KM portal/container app outbound egress IPs.
  - Any additional trusted runtime caller IPs.

## Configuration

Set these values in the azd environment or deployment parameters:

| Value | Purpose |
| --- | --- |
| `AZURE_LOCATION` | Azure region |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Foundry model deployment used by agents |
| `ALLOWED_PUBLIC_IPS` | Comma-separated public IPv4 allow-list |
| `PROMPT_GENERATOR_A2A_CONNECTION_ID` | Project connection ID for the prompt generator A2A endpoint |
| `PROMPT_VALIDATOR_A2A_CONNECTION_ID` | Project connection ID for the prompt validator A2A endpoint |
| `ENTRA_TENANT_ID` | Tenant ID used for bearer-token validation and OBO |
| `ENTRA_PORTAL_CLIENT_ID` | Client ID of the portal's confidential Entra application |
| `ENTRA_API_AUDIENCE` | API audience accepted by the portal, such as `api://<app-id>` |
| `ENTRA_CLIENT_SECRET` | Confidential-client secret for OBO; deployment input only, stored in Key Vault |
| `ARTIFACT_OWNER_HASH_SALT` | Random secret used to protect artifact ownership metadata; deployment input only, stored in Key Vault |
| `AZURE_STORAGE_BLOB_ENDPOINT` | Production artifact Blob endpoint; supplied by Bicep |
| `ARTIFACT_CONTAINER_NAME` | Production artifact Blob container; supplied by Bicep |

Create a dedicated single-tenant app registration, expose the portal API with the configured audience, and grant the portal client the delegated Azure AI authorization required for OBO. The incoming token must be issued for the configured API audience. Do not grant unrelated delegated data-access scopes for this scenario.

Generate distinct high-entropy values for `ENTRA_CLIENT_SECRET` and `ARTIFACT_OWNER_HASH_SALT` in the operator's secret-management workflow. Do not add either value to `.env.example`, azd environment files, Bicep parameter files, source control, or logs. The Bicep deployment accepts them as secure deployment parameters, stores them in the deployment-created Key Vault, and injects them into Container Apps as Key Vault references.

## Deployment flow

1. Supply the required Azure, Entra, Prompt A2A, budget, and secret values through the approved operator deployment channel.
2. Update `.azure/deployment-plan.md` with the approved target context and mark it ready for validation.
3. Run the approved Azure validation workflow, then use the approved deployment workflow. Do not deploy this scenario with ad-hoc `azd provision` or `azd deploy` commands.
4. Create the Prompt generator with `python scripts\provision_prompt_agents.py --agent case-study-generator`. Provisioning uploads and attaches the canonical template to its Code Interpreter container.
5. Create the Prompt validator, expose both Prompt specialists through Foundry-supported A2A, and create project connections to those endpoints.
6. Set the two `PROMPT_*_A2A_CONNECTION_ID` values and create the Prompt orchestrator with `python scripts\provision_prompt_agents.py --agent orchestrator`.
7. Deploy the single Hosted case-study agent. It generates, deterministically validates, and performs no more than two repairs in-process.
8. Deploy the KM portal after the Prompt orchestrator endpoint is available.

Prompt provisioning creates immutable agent versions through `azure-ai-projects`. Run `python scripts\provision_prompt_agents.py --dry-run` first to validate definitions and list required non-secret environment variables without making Azure calls.

## Network ACL behavior

The Foundry account keeps public network access enabled but denies all traffic except `allowedPublicIps`. If a caller receives `403 Forbidden`, verify that the caller's public egress IP is present in the allow-list.

Do not add undocumented Microsoft service IP ranges to this allow-list to diagnose Hosted-agent deployment failures. The current Hosted deployment failure occurs before a version is created and must be investigated through Foundry diagnostics or Microsoft support using the recorded request IDs.

## Artifact delivery

Production deployment creates a Standard LRS StorageV2 account and a private `case-study-artifacts` Blob container. The portal's user-assigned managed identity receives only `Storage Blob Data Contributor` on that storage account. The storage firewall permits the Container Apps infrastructure subnet through a service endpoint, Blob public access and shared-key access are disabled, and lifecycle management removes unconsumed case-study artifacts after one day. The application itself enforces the stricter 15-minute authenticated, owner-bound, single-use download window.

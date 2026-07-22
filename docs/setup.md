# Setup and deployment

## Prerequisites

- Azure CLI and Azure Developer CLI installed.
- An Azure subscription with permissions to deploy resource groups, Cognitive Services/Foundry resources, Container Apps, managed identities, role assignments, Log Analytics, and Application Insights.
- azd extensions for Foundry agents/projects installed where needed.
- A Microsoft 365 tenant with Microsoft 365 Copilot licensing for calling users.
- Work IQ prerequisites completed from `docs/work-iq.md`.
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
| `WORK_IQ_PROJECT_CONNECTION_ID` | Fully qualified operator-created Work IQ project connection ID |
| `PROMPT_GENERATOR_A2A_CONNECTION_ID` | Project connection ID for the prompt generator A2A endpoint |
| `PROMPT_VALIDATOR_A2A_CONNECTION_ID` | Project connection ID for the prompt validator A2A endpoint |
| `HOSTED_GENERATOR_A2A_CONNECTION_ID` | Project connection ID for the hosted generator A2A endpoint |
| `HOSTED_VALIDATOR_A2A_CONNECTION_ID` | Project connection ID for the hosted validator A2A endpoint |
| `CASE_STUDY_TEMPLATE_URL` | SharePoint/OneDrive template reference |

Do not store credentials, access tokens, Microsoft 365 file contents, or generated decks in source control.

## Deployment flow

1. Run local validation: `python -m unittest discover -s tests`.
2. Preview infrastructure: `azd provision --preview`.
3. Provision infrastructure: `azd provision`.
4. Deploy the three hosted agents with `azd deploy`.
5. Create the prompt generator and validator with `python scripts\provision_prompt_agents.py --agent case-study-generator` and `--agent validator`.
6. Expose the two prompt specialists through Foundry-supported A2A and create project connections to those endpoints.
7. Set the two `PROMPT_*_A2A_CONNECTION_ID` values and create the prompt orchestrator with `python scripts\provision_prompt_agents.py --agent orchestrator`.
8. Record hosted-agent A2A endpoints from azd output and update the hosted orchestrator configuration.
9. Deploy the KM portal after all orchestrator endpoints are available.
10. Publish Microsoft 365 Copilot assets by following `docs/m365-copilot.md`.

Prompt provisioning creates immutable agent versions through `azure-ai-projects`. Run `python scripts\provision_prompt_agents.py --dry-run` first to validate definitions and list required non-secret environment variables without making Azure calls.

## Network ACL behavior

The Foundry account keeps public network access enabled but denies all traffic except `allowedPublicIps`. If a caller receives `403 Forbidden`, verify that the caller's public egress IP is present in the allow-list. Do not switch this scenario to private endpoint-only access because Work IQ requires the public Foundry endpoint path.

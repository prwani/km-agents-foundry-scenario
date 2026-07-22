# Microsoft 365 Copilot publication

The `m365-copilot/` folder contains two separately publishable declarative-agent
packages:

| Package | Fixed implementation |
| --- | --- |
| `m365-copilot/prompt/` | Prompt Agents with Code Interpreter |
| `m365-copilot/hosted/` | Hosted Agents with Agent Framework Harness |

The legacy root templates describe the shared API contract. Package and publish each
variant separately during evaluation; do not let an agent select the implementation
at runtime.

## Operator steps

1. Deploy the KM portal and confirm its HTTPS endpoint.
2. In each selected package, replace `<km-portal-fqdn>`, `<tenant-id>`, and
   `<portal-api-app-client-id>` in `openapi.yaml`.
3. Configure OAuth authorization-code authentication for the portal API's
   `access_as_user` delegated scope. The token audience must equal
   `ENTRA_API_AUDIENCE`; do not use a Graph token as the portal token.
4. Package the selected declarative agent and OpenAPI action using the Microsoft 365 tooling approved by your tenant.
5. Submit `KM Case Study (Prompt)` and `KM Case Study (Hosted)` separately for
   admin review and tenant publication.

## Behavioral requirements

The Copilot-facing agent calls only the KM portal API. It must not request raw Microsoft 365
file contents, credentials, access tokens, or customer-sensitive information from the user.
It accepts only explicit SharePoint/OneDrive links; it does not perform broad tenant search.
Validation failures from the Foundry validator must be surfaced as failures, not silently
overridden. An approved response exposes only the opaque portal artifact ID, which is valid
for a 15-minute, authenticated, owner-bound single-use download; it never exposes a Foundry
file ID or an unrestricted URL.

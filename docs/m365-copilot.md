# Microsoft 365 Copilot publication

The `m365-copilot/` folder contains templates for publishing the KM orchestrator through Microsoft 365 Copilot.

## Operator steps

1. Deploy the KM portal and confirm its HTTPS endpoint.
2. Replace `<km-portal-fqdn>` in `m365-copilot/openapi.template.yaml`.
3. Configure authentication according to tenant policy. Do not place secrets in the manifest.
4. Package the declarative agent and OpenAPI action using the Microsoft 365 tooling approved by your tenant.
5. Submit for admin review and tenant publication.

## Behavioral requirements

The Copilot-facing agent should call only the KM portal orchestrator API. It should not request raw Microsoft 365 file contents, credentials, access tokens, or customer-sensitive information from the user. Validation failures from the Foundry validator must be surfaced as failures, not silently overridden.

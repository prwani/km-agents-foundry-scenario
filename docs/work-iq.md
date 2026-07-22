# Work IQ and OBO prerequisites

Work IQ gives the case-study creation agent access to Microsoft 365 context in the signed-in user's permissions boundary. Configure it as a Foundry **Work IQ** project connection and reference its fully qualified resource ID from the agent tool.

## Required operator steps

1. Pre-provision the Work IQ service principal in the tenant.
2. Create a bring-your-own Entra app for OAuth2.
3. Add the Work IQ delegated scope `api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask`.
4. Add `offline_access`.
5. Have a Global Administrator grant tenant-wide admin consent for `WorkIQAgent.Ask`.
6. Ensure each calling end user has a Microsoft 365 Copilot license.
7. In Foundry, create a **Work IQ** project connection with the BYO Entra application.
8. Configure the tenant-specific authorization, token, and refresh URLs.
9. Configure scopes `api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask,offline_access`.
10. Store the client secret in the Foundry connection only, never in source control or azd output.
11. Write only the fully qualified connection resource ID to `WORK_IQ_PROJECT_CONNECTION_ID`.

## Runtime requirements

Every Work IQ call runs as the signed-in user and honors Microsoft 365 permissions and sensitivity labels. The case-study agent must fail if Work IQ cannot confirm access or returns data that cannot be safely summarized.

## Source-control restrictions

Do not commit:

- Client secrets or certificates.
- Access or refresh tokens.
- Microsoft 365 document contents.
- Generated decks.
- Customer-sensitive summaries.

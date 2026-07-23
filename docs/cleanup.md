# Cleanup

Use `azd down` only after confirming that required generated artifacts have been downloaded or deleted.

Expected cleanup:

- Foundry account and project.
- Hosted agents and model deployments.
- Container Apps environment and KM portal app.
- Log Analytics and Application Insights resources.
- Managed identities and role assignments.

Operator-owned tenant artifacts such as the Entra portal application, its secret, and Cognitive Services User group assignment may require separate cleanup by tenant administrators.

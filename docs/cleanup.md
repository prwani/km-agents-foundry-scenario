# Cleanup

Use `azd down` only after confirming that all generated artifacts in Microsoft 365 are either retained according to policy or deleted by the owning user.

Expected cleanup:

- Foundry account and project.
- Hosted agents and model deployments.
- Container Apps environment and KM portal app.
- Log Analytics and Application Insights resources.
- Managed identities and role assignments.

Operator-owned tenant artifacts such as Entra applications, admin consent grants, Work IQ service principal setup, and Microsoft 365 Copilot publication entries may require separate cleanup by tenant administrators.

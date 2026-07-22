# Validation

Run:

```powershell
python -m unittest discover -s tests
```

The tests verify:

- Required project files exist.
- `azure.yaml` contains three direct-code Foundry hosted-agent services.
- Foundry network ACLs are configured for selected public IPv4 addresses.
- Runtime allow-list parsing rejects private, loopback, and malformed IP addresses.
- Validator logic fails explicitly when template or deck extraction evidence is missing.
- Microsoft 365 content and secrets are excluded from committed examples.

If Azure CLI with Bicep support is installed, the infrastructure test also compiles `infra/main.bicep`. Without Azure CLI, the static infrastructure checks still run.

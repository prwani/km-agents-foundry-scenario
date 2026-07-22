# KM-Agents Foundry Scenario

KM-Agents is a synthetic Microsoft Foundry case study that implements the same workflow using two isolated agent graphs:

| Stack | Orchestrator | Generator | Validator |
| --- | --- | --- | --- |
| Prompt | Foundry Prompt Agent | Prompt Agent + Code Interpreter | Prompt Agent + Code Interpreter |
| Hosted | Python hosted agent | Python hosted agent + Agent Framework Harness + in-house PPTX skill | Python hosted agent |

The authenticated KM portal lets users explicitly select either stack. Both use the same Contoso Limited template, content contract, validation policy, model settings where supported, and synthetic evaluation corpus.

## Security and network posture

- Foundry keeps public access enabled because Work IQ does not support VNet-restricted Foundry endpoints.
- Foundry denies traffic by default and allows only configured developer IPv4 addresses plus the KM portal NAT Gateway static public IPv4.
- The KM portal runs on Azure Container Apps Consumption in a workload-profiles environment with VNet integration and NAT Gateway.
- The signed-in user is preserved through OBO. Explicit SharePoint/OneDrive URLs are resolved by the portal with delegated Graph access.
- Files move through Foundry-managed temporary file/session storage and are deleted after retrieval.
- Phase 1 downloads are authenticated, single-use, and expire after 15 minutes.

## Repository layout

| Path | Purpose |
| --- | --- |
| `agents/prompt/` | Prompt-agent definitions and instructions |
| `src/km_agents/agents/hosted/` | Hosted-agent entrypoints |
| `skills/pptx/` | Repository-owned PowerPoint skill |
| `src/km_agents/pptx_skill/` | Template generation, deck generation, and deterministic validation |
| `assets/templates/` | Canonical Contoso template and versioned validation policy |
| `assets/brand/` | Contoso logo and brand tokens |
| `evaluation/corpus/v1/` | Reproducible synthetic DOCX/PPTX/PDF/XLSX evidence and 12-case manifest |
| `src/km_portal/` | Authenticated portal API |
| `infra/` | Foundry, Container Apps, NAT/static IP, identity, observability, and budget Bicep |
| `tests/` | Offline contract, template, security, and infrastructure tests |

## Local validation

```powershell
python -m pip install -e ".[assets]"
python -m km_agents.pptx_skill.template
python .\scripts\generate_synthetic_assets.py
python .\scripts\provision_prompt_agents.py --dry-run
python -m unittest discover -s tests
az bicep build --file .\infra\main.bicep
```

## Deployment prerequisites

Review `docs/setup.md` and `docs/work-iq.md` before provisioning. Tenant-owned Work IQ/Entra consent steps and Microsoft 365 Copilot publication remain explicit operator actions. Never commit credentials, access tokens, Microsoft 365 content, or generated customer decks.

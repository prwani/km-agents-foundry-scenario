# KM-Agents Foundry Scenario

KM-Agents is a synthetic Microsoft Foundry case study that implements the same workflow using a Prompt-agent graph and a single Hosted Harness agent:

| Stack | Composition |
| --- | --- |
| Prompt | Orchestrator, generator, and validator Prompt Agents |
| Hosted | One Python Hosted Agent using Agent Framework Harness, the in-house PPTX skill, and deterministic in-process validation |

The Entra-authenticated KM portal accepts up to ten validated DOCX, PDF, PPTX, or XLSX uploads. It uses the signed-in user assertion to invoke Foundry through OBO, then offers an approved deck through an owner-bound, single-use download.

## Current live status

- Foundry account, project, model, Prompt generator v3, and Prompt validator v5 are deployed.
- Hosted source packaging and local protocol invocation pass, but this Foundry project returns
  `500 server_error` before creating any Hosted version. The failure persists after assigning the
  deploying user Foundry Project Manager and enabling unrestricted public networking; Microsoft's
  unmodified featured sample also fails at the same API boundary, so Hosted sessions are unavailable.
- The Prompt orchestrator still requires its two A2A project connections.
- KM Portal deployment remains halted because the Hosted prerequisite is unmet; the earlier
  Sweden Central Container Apps environment allocation also returned `AKSCapacityHeavyUsage`.
- All 12 synthetic cases have been attempted. The complete paired 72-run evaluation is not yet
  valid because Hosted is unavailable and Prompt Code Interpreter calls are frequently throttled.

## Security and network posture

- Foundry temporarily allows traffic from all public networks while deployment testing is in progress. Restore the configured developer and KM portal NAT Gateway IPv4 allow-list after testing.
- The KM portal runs on Azure Container Apps Consumption in a workload-profiles environment with VNet integration and NAT Gateway.
- Uploaded evidence is validated at the portal boundary, transferred only to Foundry-managed temporary storage, and deleted after use.
- The canonical Contoso template is bundled with the Hosted case-study agent and is uploaded once to the Prompt generator's Code Interpreter container during provisioning.
- The portal uses a managed identity for private Blob artifact storage and Key Vault references. Storage and Key Vault firewalls allow only trusted developer IPs and the Container Apps infrastructure subnet through service endpoints. OBO ensures Foundry evaluates the request as the signed-in user.
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
| `scripts/report_evaluation.py` | Fail-closed 72-run synthetic evaluation report generator |
| `src/km_portal/` | Entra-authenticated upload portal API |
| `infra/` | Foundry, Container Apps, NAT/static IP, identity, observability, and budget Bicep |
| `tests/` | Offline contract, template, security, and infrastructure tests |

See [docs/agent-testing.md](docs/agent-testing.md) for Foundry Playground and
PowerShell testing instructions.

## VS Code Hosted-agent control deployment

Use this procedure to test whether the Microsoft Foundry Toolkit can create a
minimal Hosted agent in the existing project. Create the control in an empty
folder so the wizard does not modify this repository.

1. Install **Microsoft Foundry Toolkit** in VS Code and switch it to the
   prerelease version.
2. Sign in to Azure in VS Code with the `admin` identity.
3. Open an empty local folder.
4. Run **Foundry Toolkit: Create new Hosted Agent** from the Command Palette.
5. Select **Python**, **Agent Framework**, **Responses API**, and the **Basic**
   sample.
6. Select **Set up with Microsoft Foundry**, then choose:
   - Account: `kmagents-foundry`
   - Project: `kmagents-project`
   - Model deployment: `gpt-5.4-mini`
7. Name the control agent `km-hosted-vscode-control` and create the project.
8. In the generated folder, prepare and start the local agent:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python main.py
   ```

9. Confirm local readiness at `http://localhost:8088/`.
10. Run **Foundry Toolkit: Deploy Hosted Agent** from the Command Palette.
11. Select **Code** as the deployment method and **Remote** as the package
    mode, target the existing `kmagents-project`, review, and deploy.
12. If deployment succeeds, verify that the version is active under
    **Hosted Agents** and send a simple prompt from the Playground.
13. If deployment fails, retain the complete error and request ID. An HTTP 500
    from `POST /agents` is the same service-side failure seen through azd, the
    Python SDK, and the direct REST API.

### Relevance of the official troubleshooting checklist

The currently documented checks have already been covered:

- The deploying identity has **Foundry Project Manager** at project scope.
- Azure authentication reaches the project API; the response is HTTP 500, not
  an authentication or authorization error.
- The project endpoint and `gpt-5.4-mini` deployment exist and are usable.
- `main.py` and `requirements.txt` are at the deployment ZIP root.
- Local Hosted readiness and a real local model invocation pass.
- azd and its Foundry extensions meet the documented minimum versions.
- Unrestricted public networking does not change the failure.

The VS Code-specific Toolkit installation check remains relevant for the
control deployment. If it also returns HTTP 500, the documented action for a
persistent 5xx failure is to contact Microsoft support with the request IDs.

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

Review `docs/setup.md` before provisioning. Never commit credentials, access tokens, uploaded content, or generated customer decks.

# KM-Agents Deployment Plan

## Status

Ready for Validation

## Azure context

- **Subscription**: ME-M365CPI88726844-prafullawani-1 (`6f52fedd-df2c-47f7-a01f-e48682864606`)
- **Tenant**: `a3321a7a-958c-4f4a-ad4f-f4d9c193c977`
- **Location**: East US 2 (`eastus2`)
- **AZD environment**: `km-agents-eus2-probe`
- **Resource group**: `rg-km-agents-eus2-probe`

Microsoft Foundry and Azure Container Apps providers are registered and both support East US 2. This
resource group already hosts the proven Foundry account, project, active Hosted agent, and portal
deployment. The earlier Sweden Central deployment remains historical and is not a deployment target.

## Current architecture

- Azure Container Apps hosts the authenticated KM portal with VNet integration solely for NAT Gateway static egress.
- Microsoft Foundry remains publicly reachable with `defaultAction: Deny` and an explicit IPv4 allow-list containing developer and portal NAT egress addresses.
- The system has a three-agent Prompt graph and a single Hosted Harness agent. The Hosted agent uses the repository-owned PPTX skill, deterministic validation, and a bounded repair loop in-process.
- Portal users upload bounded, signature-validated DOCX, PDF, PPTX, and XLSX evidence directly to the portal. The canonical PPTX template is part of each generator's deployed definition.
- The portal uses OBO to call Foundry as the signed-in user. An Entra group assigned Cognitive Services User to Foundry must contain authorized portal users. The portal managed identity intentionally has no Foundry user role.
- Case-study artifacts are validated fail-closed against the canonical Contoso template and sensitivity policy. Portal downloads are authenticated, single-use, and expire after 15 minutes.

## Remaining deployment work

1. Revalidate the current source and Bicep against the active East US 2 environment before deployment.
2. Create new Prompt generator and validator versions with the canonical template and the bundled
   brand-guidelines reference. Provision the Prompt orchestrator only when its two A2A connection
   IDs are configured.
3. Deploy the current Hosted Harness package, including deterministic visual QA and the
   brand-guidelines reference, then invoke it from Foundry.
4. Deploy the portal revision only after the Hosted deployment succeeds and the Container Apps
   registry role check is confirmed.

## Validation checklist

- [ ] Azure CLI and Azure Developer CLI availability
- [ ] `azure.yaml` schema validation
- [ ] azd authentication and East US 2 subscription selection
- [ ] Bicep compilation and static role verification
- [ ] Provision preview against `km-agents-eus2-probe`
- [ ] Python test suite, local Hosted harness E2E, and Prompt-agent provisioning dry run
- [ ] Container image package validation

## Validation proof

The earlier Sweden Central validation record below is retained as historical evidence only. Fresh
validation is required for the current source and East US 2 deployment target.

| Check | Command | Result |
| --- | --- | --- |
| Tooling and account | `az --version`; `azd version`; `az account show`; `azd auth login --check-status` | Azure CLI 2.88.0 and azd 1.28.0 authenticated to `ME-M365CPI88726844-prafullawani-1` in Sweden Central. |
| Policy review | `az policy assignment list` | Only Defender database policy assignments were present; none conflict with this topology. |
| Model SKU and quota | `az cognitiveservices model list`; `az cognitiveservices usage list` | `gpt-4o-mini` version `2024-07-18` supports `GlobalStandard`; 2,000 capacity is available and the scenario requests 20. |
| Bicep | `az bicep build --file .\infra\main.bicep` | Passed. |
| Static RBAC | Bicep review | Authorized-user group receives Cognitive Services User on Foundry; portal identity receives Storage Blob Data Contributor on artifact storage and Key Vault Secrets User on Key Vault. |
| Application tests | `python -m unittest discover -s tests`; targeted infrastructure and agent tests | Passed. |
| Prompt definitions | `python .\scripts\provision_prompt_agents.py --dry-run` | Passed; generator and validator use Code Interpreter and the orchestrator requires the two A2A connection IDs. |
| Manifest and packaging | `validate_azure_yaml`; `azd package --no-prompt` | Passed; all hosted code packages and the remote portal build configuration validate. |
| Infrastructure preview | `azd provision --preview --no-prompt` | Passed; creates Foundry, project, Container Apps environment and portal, NAT/VNet, Key Vault, Storage, Log Analytics, and Application Insights in `rg-km-agents-swc`. |

The Foundry hosted-agent doctor still requests legacy `agent.yaml` files for each service even though the current multi-agent `azure.yaml` schema validates and `azd package` completes. This is a non-blocking extension diagnostic limitation; no deployment action depends on the legacy manifests.

## First provisioning attempt

The first `azd provision --no-prompt` attempt on 2026-07-22 partially created the VNet, NAT public IP, Log Analytics, Application Insights, Foundry account, Storage, and Key Vault. It stopped for two independent reasons:

1. The Foundry account was created with `allowProjectManagement: false`, so the project resource was rejected. The Bicep template now explicitly enables it.
2. Azure returned `AKSCapacityHeavyUsage` while allocating the Sweden Central Container Apps environment. This is a regional capacity condition, not a template or quota failure. One retry is appropriate before requesting approval to change regions.

The halted retry established that project management was enabled, but Azure then required a `customSubDomainName` on the AIServices account before it would create a project. The template now supplies a deterministic, globally unique subdomain derived from the subscription and resource group.

## Validation refresh

Validation refreshed on 2026-07-22 after consolidating the Hosted stack and correcting the Foundry project prerequisite.

| Check | Command | Result |
| --- | --- | --- |
| Hosted-agent consolidation | `python -m unittest discover -s tests` | Passed: 43 tests. The Hosted workflow is one Harness agent with an in-process deterministic validation tool and a fixed two-repair policy. |
| Bicep | `az bicep build --file .\infra\main.bicep` | Passed. The AIServices account has both `allowProjectManagement: true` and a deterministic globally unique `customSubDomainName`. |
| Package validation | `azd package --no-prompt` | Passed for `ai-project`, `hosted-case-study-agent`, and `km-portal`. |
| Infrastructure preview | `azd provision --preview --no-prompt` | Passed. The preview creates the Foundry project and applies the required AIServices custom subdomain. |
| Model revalidation | `az cognitiveservices model list`; `az cognitiveservices usage list` | The previously selected `gpt-4o-mini` `2024-07-18` version became deprecating and cannot accept new deployments. `gpt-5.4-mini` `2026-03-17` is Generally Available in Sweden Central with Global Standard support and 2,740 capacity available; the scenario requests 20. |

## Foundry agent validation

- The Foundry account (`kmagents-foundry`), project (`kmagents-project`), and `gpt-5.4-mini` model deployment succeeded.
- On 2026-07-23, the operator changed the live account to public network access with `defaultAction: Allow` to isolate the Hosted-agent failure from selected-IP rules. This is an operational test change only; the Bicep source remains the secure selected-IP configuration.
- Prompt generator version 1 generated an eight-slide PPTX from synthetic evidence. Local deterministic validation approved it with zero findings.
- Prompt validator version 2 inspected the generated deck and reported only informational template and identity findings, but incorrectly returned `approved: false`. Validator version 3 corrects the instruction so informational findings cannot reject a deck.
- The corrected validator version is active, but current file-backed Code Interpreter invocations are throttled by the 20-capacity model deployment (`429 rate_limit_exceeded`, request ID `04b960d7b7bccc41c87797e58a4fe8ab`). Do not increase model capacity without approval; retry after quota is available.
- Retrying `azd deploy hosted-case-study-agent --no-prompt` with unrestricted public access still failed before a Hosted version was created. Foundry returned `500 server_error` from `POST /agents` with request ID `d5732e098d9e260f5fae37814d13aadb`; this confirms the selected-IP firewall was not the cause.
- The local diagnostic confirms the project endpoint is reachable and the developer role is sufficient. It has no Hosted session logs to query because no version exists. Its `agent.yaml` warning is a stale extension check: this direct-code agent is defined by the valid `azure.yaml` service block and packages successfully.

## Hosted contract correction and control deployment

Validation refreshed on 2026-07-23 against the current official direct-code contract.

- The Hosted service now packages from `project: src` with `main.py` and
  `requirements.txt` at the ZIP root. The ZIP contains the required `km_agents` modules,
  canonical template, policy, and PPTX skill, while excluding portal code, environment files,
  repository metadata, and evaluation documents.
- The Harness now supplies an `InMemoryHistoryProvider(load_messages=False)` because
  `ResponsesHostServer` owns conversation history. Local readiness returned HTTP 200 and a real
  local model invocation returned `READY`.
- Deploying the corrected service still failed before version creation through the beta azd
  extension (`c8c27b4df453b10717d9c44de7b62c83`).
- Microsoft's unmodified featured Python Responses sample failed against the same project at the
  same boundary (`f0a7b4482ffb2a46d1d27f4b8e640845`).
- The current `azure-ai-projects` 2.3.0 `create_version_from_code` API also failed before version
  creation (`c8483434978e1268fb4a4b507897e466`).
- Sweden Central is listed as supported for Hosted agents, the project provisioning state and
  agent identity are valid, and public network access is enabled. These controls isolate the
  remaining failure to the Foundry service/project. Escalate the retained request IDs to
  Microsoft support; do not perform more package rewrites or deploy retries without new evidence.
- On 2026-07-23, the operator assigned the deploying CLI identity Foundry Project Manager at
  project scope and re-enabled unrestricted public networking for the remainder of testing.
  The role assignment was verified, and the live account reports `publicNetworkAccess: Enabled`
  with `defaultAction: Allow`. A new direct-code retry still failed at `POST /agents` with
  `500 server_error` and request ID `a83a25dc432e0d662a51e72bc17a05de`.
- A direct REST `multipart/form-data` source-code deployment using the documented `v1` API,
  ZIP SHA-256 header, metadata part, and code part failed at the same `POST /agents` endpoint
  with `500 server_error` and request ID `5bdb949aa5b0c2b68b277c5fc486c8d0`.
  This rules out azd and Python SDK serialization as the cause.
- Checked Azure Resource Health for `kmagents-foundry`. It briefly reported
  `availabilityState: Unavailable` (transient, unplanned, auto-recovering) and then flipped to
  `Available` (`reasonChronicity: Persistent`, "no known Azure platform problems"). A deployment
  retry taken immediately after the `Available` reading still failed identically at `POST /agents`
  with `500 server_error` and request ID `1dd1cbb34e493a902b2a1b117f3bbf0f`. This shows Resource
  Health's coarse control-plane signal for the classic Cognitive Services resource does not cover
  the Foundry Agent Service `POST /agents` data-plane operation, so it is not reliable evidence for
  this incident either way. The blocker remains isolated to the Foundry hosted-agent creation
  service; escalate to Microsoft support with all retained request IDs
  (`c8c27b4df453b10717d9c44de7b62c83`, `f0a7b4482ffb2a46d1d27f4b8e640845`,
  `c8483434978e1268fb4a4b507897e466`, `a83a25dc432e0d662a51e72bc17a05de`,
  `5bdb949aa5b0c2b68b277c5fc486c8d0`, `1dd1cbb34e493a902b2a1b117f3bbf0f`).
- Keep unrestricted networking during testing as requested. Restore `defaultAction: Deny` and
  the selected-IP posture only after the operator confirms testing is complete.
- No KM Portal deployment was attempted because the operator required Hosted success first.
- East US 2 proxy diagnostic (2026-07-23): to check whether the Sweden Central ACA
  `AKSCapacityHeavyUsage` failure reflected a broader subscription/platform issue, a throwaway
  resource group `rg-km-agents-eus2-probe` and a plain Container Apps environment
  `cae-km-probe-eus2` (Consumption workload profile, auto-created Log Analytics workspace) were
  provisioned in East US 2 with no other resources. Provisioning succeeded cleanly
  (`provisioningState: Succeeded`, `publicNetworkAccess: Enabled`), with no capacity error of any
  kind. This indicates the earlier Sweden Central ACA failure was regional capacity contention
  specific to that region, not a subscription-wide or platform-wide Container Apps outage. It does
  not directly explain the Hosted-agent `POST /agents` 500s, which are a distinct Foundry Agent
  Service data-plane API and may or may not share the same backend compute pool. Sweden Central
  resources (`rg-km-agents-swc`, `kmagents-foundry`, `kmagents-project`) were not touched. The
  probe resource group should be deleted once the operator confirms no further use, or kept if a
  full East US 2 Foundry/Hosted-agent control test is approved next.
- **Hosted-agent control deployment SUCCEEDED in East US 2 (2026-07-23).** In the same
  `rg-km-agents-eus2-probe` resource group: created Foundry account `kmagents-foundry-eus2`
  (`allowProjectManagement: true` by default, no PATCH needed), project `kmagents-project-eus2`,
  assigned the deploying identity (`df390249-9cf9-461e-a7d0-bb3a3f6c9584`) the built-in
  `Foundry Project Manager` role at project scope, and deployed `gpt-5.4-mini` version
  `2026-03-17` as `GlobalStandard` capacity 20 (same version already used in Sweden Central; the
  model is Global Standard-eligible in `eastus2` per the Foundry Models region-availability table).
  Created a new azd environment `km-agents-eus2-probe` pointing at this project and ran
  `azd deploy hosted-case-study-agent` unmodified (same `src/` package that failed 9 times in
  Sweden Central). **It succeeded in ~2 minutes** — agent `km-hosted-case-study-agent` version 1
  reached `Status: active` (Agent GUID `fbb3c580-5e3e-42eb-bc66-8ceb66a5692e`), confirmed via
  `azd ai agent show`. Endpoint:
  `https://kmagents-foundry-eus2.services.ai.azure.com/api/projects/kmagents-project-eus2/agents/km-hosted-case-study-agent/endpoint/protocols/openai/responses?api-version=v1`.
  **Conclusion: the Hosted-agent `500 server_error` at `POST /agents` was specific to the Sweden
  Central Foundry backend/region, not to this repository's package, RBAC, networking, azd
  configuration, or account settings** (all of which are identical between the two attempts except
  region). Sweden Central resources were not touched or modified by this test.

## Twelve-case live Prompt pass

- Prompt generator v3 adds a final package scrub for unapproved customer names and forces sparse,
  non-sensitive evidence to produce an eight-slide deck with explicit uncertainty placeholders.
- Prompt validator v5 computes approval from error-level findings and forbids
  `approved: false` with an empty findings array.
- A targeted clean-case run passed generator, deterministic validation, and validator end to end.
- All 12 corpus cases were attempted once. In the final pass, generator v3 returned PPTX artifacts
  for ten cases; nine passed local deterministic template/sensitivity validation. The seeded
  sensitive case correctly failed closed. The contradictory-evidence case still exposed an
  unapproved customer name, while the XLSX-only generator call was throttled.
- Validator calls were predominantly blocked by the existing model deployment's `429` limit; one
  returned a transient 400. Cases 5 and 12 returned error-level validator rejection. Therefore the
  corpus does not pass, and the planned three repetitions across both implementations (72 runs)
  must not be reported as complete.

## Role assignment verification

- **Foundry users:** the authorized Entra group receives `Cognitive Services User`, scoped only to the Foundry account, for OBO user invocation.
- **Portal identity:** the user-assigned portal identity receives `Storage Blob Data Contributor` on the artifact account and `Key Vault Secrets User` on the Key Vault.
- **Least privilege:** no portal managed identity role grants Foundry data-plane access; Foundry calls continue to use the signed-in user's OBO credential.

## Execution sequence

1. Provision the secure foundation: Foundry account/project and model, Container Apps environment with NAT static egress, Key Vault, private Blob storage, managed identity, observability, and the protected portal.
2. Deploy the single Hosted case-study agent.
3. Create immutable Prompt specialist versions, configure Prompt A2A connections, then create the Prompt orchestrator.
4. Validate both stacks with the synthetic corpus after the Hosted file-transfer adapter is available.

## Security decisions

- No credentials, tokens, uploaded content, or non-synthetic customer artifacts are stored in source control.
- The deployment creates a Key Vault for the confidential OBO client secret and artifact-owner hash salt. Both values are secure deployment inputs and are injected into Container Apps by Key Vault reference; they are never stored in azd files.
- OBO access is scoped to each signed-in user. The portal uses its managed identity only for Key Vault and artifact Blob storage.
- Each generated PPTX must pass deterministic validation before delivery.
- Production artifact delivery uses a private, firewall-restricted Blob container with managed-identity access through the Container Apps infrastructure subnet service endpoint, 15-minute owner-bound single-use application enforcement, and a one-day cleanup lifecycle policy for unconsumed blobs.

## Deployment boundary

The Hosted portal path cannot be exposed as functional until supported Foundry hosted-session file APIs are available. Prompt A2A connection IDs and Entra application values require tenant/operator configuration and must never be guessed or replaced with placeholders. After those values are provided and the implementation is marked `Ready for Validation`, the next mandatory workflow is `azure-validate` followed by `azure-deploy`.

## East US 2 deployment target and diagnostic history (2026-07-23)

Sweden Central's Hosted-agent creation kept failing with Foundry `500 server_error` (9/9 attempts) and its Container Apps environment kept failing with `AKSCapacityHeavyUsage`. Per explicit operator instruction, a throwaway resource group `rg-km-agents-eus2-probe` (East US 2, azd environment `km-agents-eus2-probe`) was stood up to isolate whether these were regional/backend issues or caused by this repo's code, RBAC, or config. **Sweden Central (`rg-km-agents-swc`) was left completely untouched throughout this entire diagnostic.**

### Findings

1. **A bare Container Apps environment provisioned cleanly in East US 2** with no `AKSCapacityHeavyUsage` — the Sweden Central ACA failure is regional capacity contention, not subscription-wide.
2. **The exact unmodified `src/` Hosted-agent package that failed 9/9 times in Sweden Central deployed successfully in East US 2 in ~2 minutes** (first against a manually created Foundry account/project, later against the repo's Bicep-managed one) — the Sweden Central `500 server_error` is a region/backend-specific Foundry issue, not caused by this repo's code, azd config, RBAC, or account settings.
3. **A tenant-wide Azure Policy (`Azure_Security_Baseline`, assigned at the tenant root management group) silently forces `publicNetworkAccess: Disabled`** on Key Vault and Storage accounts via `modify`-effect policy definitions (`keyvaultpublicnetworkmodify`, `storageaccountpublicnetworkmodify`), regardless of what any ARM/Bicep template declares. Foundry (Cognitive Services) accounts are *not* subject to this policy and keep working with the selected-IP-allowlist design. **This same policy will very likely block Sweden Central's KM Portal deployment too, independent of the ACA capacity issue**, since it is tenant-wide, not region-specific.
4. **A genuine, previously-undiscovered Azure Container Apps platform limitation**: ACA's `keyVaultUrl` secret references are resolved by the platform control plane from *outside* the customer VNet at deployment time and never traverse a private endpoint, even with correct DNS/RBAC. Combined with (3), Key-Vault-referenced ACA secrets can never resolve in this subscription. **Fix applied**: the portal's `entra-client-secret` and `artifact-owner-hash-salt` are now passed as native Container App secrets (`value:` from the secure Bicep parameters) instead of `keyVaultUrl` references. They are still also written to Key Vault for audit/rotation tooling, but the Container App no longer depends on Key Vault being reachable to start. Private endpoints + private DNS zones for Key Vault and Storage were still added for defense in depth / other tooling.
5. **Fixed a real endpoint-construction bug in `infra/main.bicep`**: the Foundry project endpoint (Bicep output `foundryProjectEndpoint` and the portal's `FOUNDRY_PROJECT_ENDPOINT` env var) used `${foundry.name}.services.ai.azure.com`, but the actual hostname is based on the account's `customSubDomainName` (includes a `uniqueString` suffix, can differ from the resource name) — fixed to use the `foundryCustomSubdomainName` variable everywhere. This previously worked only by coincidence when a manually created account's subdomain happened to equal its name.
6. **The repo never provisioned an Azure Container Registry** for the KM Portal's `remoteBuild: true` service — `azd deploy km-portal` failed identically in both regions with "could not determine container registry endpoint". Added a `Microsoft.ContainerRegistry/registries` resource (Basic SKU, RBAC-only, no admin user) to `infra/main.bicep`, wired the Container App's `configuration.registries` to pull via the portal's managed identity (granted `AcrPull`), and added the `AZURE_CONTAINER_REGISTRY_ENDPOINT` output azd needs. **Operator action required for any environment**: the human running `azd deploy km-portal` also needs `AcrPush` on the registry (assigned via `az role assignment create ... --role AcrPush`), since the remote build runs under the operator's own credentials, not the portal's managed identity.
7. **The portal Container App was missing the `azd-service-name: km-portal` tag** azd needs to resolve the deploy target — added via `tags: union(tags, { 'azd-service-name': 'km-portal' })`.
8. **Fixed a real `Dockerfile` bug**: `CMD` ran `uvicorn km_portal.main:app` with `WORKDIR /app`, but the `km_portal` package lives at `src/km_portal/` — this crash-looped every container start with `ModuleNotFoundError: No module named 'km_portal'` (would hit Sweden Central identically once deployed). Fixed with `uvicorn km_portal.main:app --app-dir src ...`.
9. The developer's public IP is dynamic (ISP-assigned) and changed between sessions; `ALLOWED_PUBLIC_IP` needed updating before Foundry's firewall would admit the deploying machine again. Re-check this before resuming any Sweden Central work.

### Result

Full stack (VNet/NAT, Key Vault + private endpoint, Storage + private endpoint, Container Registry, Foundry account + project, Log Analytics, App Insights, Container Apps Environment, Container App) provisions cleanly via `azd provision`. `azd deploy ai-project`, `azd deploy hosted-case-study-agent`, and `azd deploy km-portal` all succeed. The Hosted agent `km-hosted-case-study-agent` is `active`. The portal's `/healthz` returns `200 {"status":"ok"}` publicly at `https://kmagents-km-portal.happyrock-f2ee803e.eastus2.azurecontainerapps.io/`.

### Open decision for the operator

East US 2 is the active deployment target for the current source revision. Sweden Central resources
remain historical and untouched. Before the next deployment, re-run validation and record fresh
proof for `km-agents-eus2-probe`.

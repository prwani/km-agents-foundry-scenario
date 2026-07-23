# Testing Foundry agents

Use this guide to exercise the case-study agents from Microsoft Foundry
Playground or PowerShell. Use only the repository's synthetic corpus or other
non-sensitive test material. Do not commit downloaded decks, tokens, session
IDs, or customer uploads.

## Current availability

| Agent | Name | Current test path |
| --- | --- | --- |
| Prompt generator | `km-prompt-case-study-generator` | Ready for Playground and command-line tests. |
| Prompt validator | `km-prompt-validator` | Ready for Playground and command-line tests. Its current version is 3. |
| Prompt orchestrator | `km-prompt-orchestrator` | Requires the generator and validator A2A project connections before it can be provisioned. |
| Hosted case-study agent | `km-hosted-case-study-agent` | Requires a successful `azd deploy hosted-case-study-agent --no-prompt` before it can be invoked. |

The synthetic source `evaluation\corpus\v1\sources\fabrikam-clean-brief.docx`
is the recommended first input. It represents a case where the customer name
is not approved for external use, so a compliant deck must use `Customer`.

## One-time command-line setup

Run the commands from the repository root after authenticating with an
identity that has access to the Foundry project:

```powershell
az login
azd auth login

$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
$env:FOUNDRY_PROJECT_ENDPOINT = azd env get-value FOUNDRY_PROJECT_ENDPOINT
if ([string]::IsNullOrWhiteSpace($env:FOUNDRY_PROJECT_ENDPOINT)) {
    $env:FOUNDRY_PROJECT_ENDPOINT = azd env get-value AZURE_AI_PROJECT_ENDPOINT
}
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME = azd env get-value AZURE_AI_MODEL_DEPLOYMENT_NAME

if ([string]::IsNullOrWhiteSpace($env:FOUNDRY_PROJECT_ENDPOINT)) {
    throw "The Foundry project endpoint is not configured in the active azd environment."
}
if ([string]::IsNullOrWhiteSpace($env:AZURE_AI_MODEL_DEPLOYMENT_NAME)) {
    throw "The model deployment name is not configured in the active azd environment."
}

azd ai project show --output json
```

For local SDK-based commands, install the project dependencies once:

```powershell
python -m pip install -e ".[assets]"
```

## Prompt agents in Foundry Playground

1. Open [Microsoft Foundry](https://ai.azure.com), select the
   `kmagents-foundry` resource and `kmagents-project` project, then open
   **Build > Agents**.
2. Select the intended agent and its active version.
3. Keep uploads synthetic. The generator already has the canonical template
   attached; do not upload or replace it.

### Prompt generator

Select `km-prompt-case-study-generator`, upload
`fabrikam-clean-brief.docx`, and send:

```text
Create a case-study PPTX from the attached synthetic evidence.
Customer name: Fabrikam
Customer name approved for external use: false
Audience: enterprise sales leadership
Preserve the canonical template and use Customer as the display name.
Do not invent metrics or quotations. Save the result as case-study.pptx.
```

Download the returned PowerPoint artifact from the Code Interpreter citation.
Expected result: an eight-slide deck with all protected template elements
preserved and `Customer` rather than `Fabrikam`.

### Prompt validator

Select `km-prompt-validator`, upload the generated PPTX, and send:

```text
Validate the attached candidate PPTX against the attached canonical template
and validation policy. The display name must be Customer because external
customer-name use is not approved. Inspect completely and return exactly JSON
with approved, findings, and policy_version.
```

Expected result: `approved` is `true` when inspection completes with no
error-level finding. Informational findings alone do not reject a deck.

### Prompt orchestrator

Do not test `km-prompt-orchestrator` until its two A2A project connections
are configured and the agent is provisioned. Once available, upload the same
synthetic source and send the request payload required by the portal contract.
The orchestrator must return one `CaseStudyResponse` JSON object and must not
return an artifact URL or Foundry file identifier.

## Prompt agents from PowerShell

The following commands use the Foundry Responses API through the installed
Azure AI Projects SDK. They upload files with `purpose="assistants"` because
the agents use Code Interpreter, download artifacts from the container-file
citation, and delete temporary remote files afterward.

### Generate a synthetic deck

```powershell
$env:CASE_STUDY_SOURCE = (Resolve-Path ".\evaluation\corpus\v1\sources\fabrikam-clean-brief.docx").Path
$env:CASE_STUDY_OUTPUT = Join-Path $env:TEMP "km-agents-synthetic-case-study.pptx"

@'
import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

source = Path(os.environ["CASE_STUDY_SOURCE"])
output = Path(os.environ["CASE_STUDY_OUTPUT"])
project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
client = project.get_openai_client()
uploaded = client.files.create(
    file=(source.name, source.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    purpose="assistants",
)
container_file = None
try:
    response = client.responses.create(
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "Create a case-study PPTX from the attached synthetic evidence. "
                        "Customer name: Fabrikam. Customer name approved for external use: false. "
                        "Audience: enterprise sales leadership. Preserve the canonical template, "
                        "use Customer as the display name, do not invent metrics or quotations, "
                        "and save the result as case-study.pptx."
                    ),
                },
                {"type": "input_file", "file_id": uploaded.id},
            ],
        }],
        extra_body={
            "agent_reference": {
                "name": "km-prompt-case-study-generator",
                "type": "agent_reference",
            }
        },
    )
    print(response.output_text)

    def citations(value):
        if isinstance(value, dict):
            if value.get("type") == "container_file_citation":
                yield value
            for nested in value.values():
                yield from citations(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from citations(nested)

    container_file = next(
        item
        for item in citations(response.model_dump(mode="json"))
        if str(item.get("filename", "")).lower().endswith(".pptx")
    )
    content = client.containers.files.content.retrieve(
        container_file["file_id"],
        container_id=container_file["container_id"],
    ).read()
    if not content.startswith(b"PK\x03\x04"):
        raise RuntimeError("Foundry returned an invalid PowerPoint artifact.")
    output.write_bytes(content)
    print(f"Saved synthetic deck to {output}")
finally:
    client.files.delete(uploaded.id)
    if container_file is not None:
        client.containers.files.delete(
            container_file["file_id"],
            container_id=container_file["container_id"],
        )
    project.close()
'@ | python -
```

### Validate the generated deck

```powershell
@'
import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

candidate = Path(os.environ["CASE_STUDY_OUTPUT"])
if not candidate.is_file():
    raise FileNotFoundError(f"Generated deck not found: {candidate}")

project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
client = project.get_openai_client()
uploaded = client.files.create(
    file=(
        candidate.name,
        candidate.read_bytes(),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    purpose="assistants",
)
try:
    response = client.responses.create(
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "Validate the attached candidate PPTX against the attached canonical "
                        "template and validation policy. The display name must be Customer "
                        "because external customer-name use is not approved. Inspect completely "
                        "and return exactly JSON with approved, findings, and policy_version."
                    ),
                },
                {"type": "input_file", "file_id": uploaded.id},
            ],
        }],
        extra_body={
            "agent_reference": {
                "name": "km-prompt-validator",
                "type": "agent_reference",
            }
        },
    )
    print(response.output_text)
finally:
    client.files.delete(uploaded.id)
    project.close()
'@ | python -
```

Delete the temporary local deck after the test:

```powershell
Remove-Item $env:CASE_STUDY_OUTPUT
```

## Hosted agent from PowerShell

The Hosted agent is intentionally separate from the Prompt graph. It performs
generation, deterministic validation, and up to two repairs in one session.
Its session filesystem expects evidence under `input/` and produces an
approved deck under `output/`.

### Deploy and verify

Run this only after the Foundry project and model deployment are available:

```powershell
azd deploy hosted-case-study-agent --no-prompt
azd ai agent show hosted-case-study-agent --output json
```

Continue only when `azd ai agent show` reports an active version and has
written the `AGENT_HOSTED_CASE_STUDY_AGENT_*` values to the active azd
environment.

### Upload, invoke, download, and clean up

```powershell
$source = (Resolve-Path ".\evaluation\corpus\v1\sources\fabrikam-clean-brief.docx").Path

azd ai agent sessions create hosted-case-study-agent
azd ai agent files upload hosted-case-study-agent $source `
    --target-path "input/fabrikam-clean-brief.docx"

azd ai agent invoke hosted-case-study-agent @'
Create a case-study deck using input/fabrikam-clean-brief.docx.
Use Customer as the display name because external customer-name use is not
approved. Preserve the canonical template, use only supported evidence, and
write the approved deck to output/case-study.pptx only when deterministic
validation approves it.
'@

azd ai agent files list output
azd ai agent files download "output/case-study.pptx" `
    --target-path (Join-Path $env:TEMP "km-agents-hosted-case-study.pptx")
```

After confirming the output is present, remove the remote session and the
local temporary deck. Replace `<session-id>` with the value returned by
`azd ai agent sessions create`.

```powershell
azd ai agent sessions delete <session-id> --agent-name hosted-case-study-agent
Remove-Item (Join-Path $env:TEMP "km-agents-hosted-case-study.pptx")
```

If the Hosted agent is not yet deployed, `azd ai agent show` and the session
commands fail by design. Do not work around this by exposing a development
server or by accepting a deck that has not passed deterministic validation.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `429 rate_limit_exceeded` from a Prompt test | Wait for the model deployment rate window to recover, then run one test again. Do not raise model capacity without approval. |
| `403 Forbidden` from Foundry | Confirm the selected azd environment, authenticated identity, and Foundry network-access configuration. |
| Prompt generator returns no PPTX citation | Treat the test as failed; do not approve or deliver an artifact. |
| Hosted agent cannot be resolved | Deploy `hosted-case-study-agent` first, then verify it with `azd ai agent show hosted-case-study-agent --output json`. |
| Hosted agent returns an inconclusive validation result | Treat it as a rejection. Download no artifact and delete the Hosted session. |

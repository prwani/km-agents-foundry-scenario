"""Deploy the hosted case-study agent directly via the Azure AI Projects SDK.

Why this exists: `azd deploy hosted-case-study-agent` (and the underlying
`azure.ai.agents` azd extension, as of 1.0.0-beta.6) always computes the
code-package size from a fully dependency-bundled build, even when
`codeConfiguration.dependency_resolution: remote_build` is set in
`azure.yaml`. That pushes the package past the 250 MB cap for this project's
dependency set (agent-framework-foundry, azure-identity, python-pptx, etc.)
even though remote_build only needs to upload source, not dependencies.

This script bypasses azd's packaging step and calls the same
`create_version_from_code` SDK API directly with a minimal, dependency-free
zip (source files only), matching the `codeConfiguration` and
`environmentVariables` declared for the `hosted-case-study-agent` service in
`azure.yaml`. It should be retired once azd's remote_build packaging bug is
fixed upstream -- re-check with `azd deploy hosted-case-study-agent` first.

Usage:
    python scripts/deploy_hosted_sdk.py --environment km-agents-eus2-probe

Requires an active `az login` / `azd auth login` identity with the
"Foundry Project Manager" (or equivalent) role on the target project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    CodeConfiguration,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
AGENT_NAME = "km-hosted-case-study-agent"

# Source files/directories to include in the deployment zip. Kept in sync
# with the entry point + environment variable paths declared for the
# hosted-case-study-agent service in azure.yaml.
INCLUDE_PATHS = [
    "main.py",
    "km_agents",
    "assets/templates/contoso-case-study-template.pptx",
    "assets/templates/contoso-brand-guidelines.md",
    "assets/templates/contoso-template-policy.json",
    "skills/pptx",
    "requirements.txt",
]

ENVIRONMENT_VARIABLES = {
    "CASE_STUDY_TEMPLATE_PATH": "assets/templates/contoso-case-study-template.pptx",
    "CASE_STUDY_BRAND_GUIDELINES_PATH": "assets/templates/contoso-brand-guidelines.md",
    "PPTX_SKILL_PATH": "skills/pptx",
    "HARNESS_MAX_ITERATIONS": "3",
    "HARNESS_DISABLE_WEB_SEARCH": "true",
    "HARNESS_DISABLE_SHELL": "true",
    "MAX_REPAIR_ATTEMPTS": "2",
    "TEMPLATE_POLICY_PATH": "assets/templates/contoso-template-policy.json",
}


def _azd_env_values(environment: str) -> dict[str, str]:
    proc = subprocess.run(
        ["azd", "env", "get-values", "-e", environment],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    values: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        values[key.strip()] = raw_value.strip().strip('"')
    return values


def _build_zip() -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="km-hosted-deploy-"))
    zip_path = tmp_dir / "hosted-case-study-agent.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in INCLUDE_PATHS:
            src = SRC_ROOT / rel
            if src.is_dir():
                for file_path in src.rglob("*"):
                    if file_path.is_file() and "__pycache__" not in file_path.parts:
                        zf.write(file_path, file_path.relative_to(SRC_ROOT))
            elif src.is_file():
                zf.write(src, src.relative_to(SRC_ROOT))
            else:
                raise FileNotFoundError(f"Expected deployment input not found: {src}")
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Built deployment zip: {zip_path} ({size_mb:.2f} MB)", flush=True)
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True, help="azd environment name")
    args = parser.parse_args()

    env_values = _azd_env_values(args.environment)
    endpoint = env_values.get("FOUNDRY_PROJECT_ENDPOINT") or env_values.get(
        "foundryProjectEndpoint"
    )
    model_deployment = env_values.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    if not endpoint or not model_deployment:
        raise SystemExit(
            "Missing FOUNDRY_PROJECT_ENDPOINT / AZURE_AI_MODEL_DEPLOYMENT_NAME "
            f"in azd environment '{args.environment}'. Run `azd env get-values` "
            "to inspect available values."
        )

    zip_path = _build_zip()
    code = zip_path.read_bytes()

    env_vars = dict(ENVIRONMENT_VARIABLES)
    env_vars["AZURE_AI_MODEL_DEPLOYMENT_NAME"] = model_deployment

    credential = DefaultAzureCredential(exclude_managed_identity_credential=True)
    with AIProjectClient(endpoint=endpoint, credential=credential) as project:
        created = project.agents.create_version_from_code(
            agent_name=AGENT_NAME,
            description=(
                "Uses Agent Framework Harness to generate, deterministically validate, "
                "and repair case-study decks in one fail-closed workflow."
            ),
            definition=HostedAgentDefinition(
                cpu="0.5",
                memory="1Gi",
                code_configuration=CodeConfiguration(
                    runtime="python_3_13",
                    entry_point=["python", "main.py"],
                    dependency_resolution="remote_build",
                ),
                protocol_versions=[
                    ProtocolVersionRecord(protocol="responses", version="2.0.0")
                ],
                environment_variables=env_vars,
            ),
            code=(zip_path.name, code, "application/zip"),
            code_zip_sha256=hashlib.sha256(code).hexdigest(),
        )
        print(f"CREATED_VERSION={created.version}", flush=True)

        for _ in range(120):
            version = project.agents.get_version(
                agent_name=AGENT_NAME,
                agent_version=created.version,
            )
            status = str(version["status"])
            print(f"STATUS={status}", flush=True)
            if status == "active":
                print(json.dumps(dict(version), default=str, indent=2))
                return
            if status == "failed":
                raise RuntimeError(f"Hosted agent provisioning failed: {dict(version)}")
            time.sleep(5)

        raise TimeoutError("Hosted agent version did not become active within 10 minutes")


if __name__ == "__main__":
    main()

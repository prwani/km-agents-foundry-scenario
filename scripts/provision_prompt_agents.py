from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    A2APreviewTool,
    AutoCodeInterpreterToolParam,
    CodeInterpreterTool,
    PromptAgentDefinition,
)
from azure.identity import DefaultAzureCredential


ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = ROOT / "agents" / "prompt"
CANONICAL_TEMPLATE = ROOT / "assets" / "templates" / "contoso-case-study-template.pptx"
BRAND_GUIDELINES_TEMPLATE = (
    ROOT / "assets" / "templates" / "contoso-case-study-template-with-brand-guidelines.pptx"
)
VALIDATION_POLICY = ROOT / "assets" / "templates" / "contoso-template-policy.json"
ENV_PATTERN = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")
DEPLOYMENT_ORDER = ("case-study-generator", "validator", "orchestrator")


@dataclass(frozen=True)
class PromptAgentSpec:
    source: Path
    name: str
    model: str
    instructions: str
    temperature: float
    tools: tuple[dict[str, Any], ...]


def resolve_environment(value: str) -> str:
    match = ENV_PATTERN.fullmatch(value)
    if not match:
        return value
    name = match.group(1)
    resolved = os.getenv(name)
    if not resolved:
        raise ValueError(f"Required environment variable {name} is not set")
    return resolved


def referenced_environment(value: object) -> set[str]:
    if isinstance(value, str):
        match = ENV_PATTERN.fullmatch(value)
        return {match.group(1)} if match else set()
    if isinstance(value, dict):
        return set().union(*(referenced_environment(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(referenced_environment(item) for item in value))
    return set()


def load_spec(folder: str, resolve: bool = True) -> PromptAgentSpec:
    source = PROMPT_ROOT / folder / "agent.yaml"
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if payload.get("kind") != "prompt":
        raise ValueError(f"{source} must declare kind: prompt")
    instructions_file = source.parent / payload["instructions_file"]
    instructions = instructions_file.read_text(encoding="utf-8").strip()
    if not instructions:
        raise ValueError(f"{instructions_file} must not be empty")
    model = resolve_environment(payload["model"]) if resolve else payload["model"]
    return PromptAgentSpec(
        source=source,
        name=payload["name"],
        model=model,
        instructions=instructions,
        temperature=float(payload.get("temperature", 0.2)),
        tools=tuple(payload.get("tools", [])),
    )


def build_tools(
    spec: PromptAgentSpec, code_interpreter_file_ids: tuple[str, ...] = ()
) -> list[object]:
    tools: list[object] = []
    for tool in spec.tools:
        tool_type = tool["type"]
        if tool_type == "code_interpreter":
            container = (
                AutoCodeInterpreterToolParam(file_ids=list(code_interpreter_file_ids))
                if code_interpreter_file_ids
                else None
            )
            tools.append(CodeInterpreterTool(container=container))
        elif tool_type == "a2a_preview":
            tools.append(
                A2APreviewTool(
                    project_connection_id=resolve_environment(tool["project_connection_id"])
                )
            )
        else:
            raise ValueError(f"Unsupported tool type {tool_type!r} in {spec.source}")
    return tools


def dry_run(folders: tuple[str, ...]) -> None:
    result = []
    for folder in folders:
        spec = load_spec(folder, resolve=False)
        raw = yaml.safe_load(spec.source.read_text(encoding="utf-8"))
        result.append(
            {
                "name": spec.name,
                "source": spec.source.relative_to(ROOT).as_posix(),
                "tools": [tool["type"] for tool in spec.tools],
                "required_environment": sorted(referenced_environment(raw)),
            }
        )
    print(json.dumps(result, indent=2))


def provision(folders: tuple[str, ...]) -> None:
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not endpoint:
        raise ValueError("FOUNDRY_PROJECT_ENDPOINT or AZURE_AI_PROJECT_ENDPOINT is required")
    credential = DefaultAzureCredential()
    with AIProjectClient(endpoint=endpoint, credential=credential) as project:
        for folder in folders:
            spec = load_spec(folder)
            attached_file_ids: list[str] = []
            version_created = False
            try:
                if folder == "case-study-generator":
                    for source in (CANONICAL_TEMPLATE, BRAND_GUIDELINES_TEMPLATE):
                        if not source.is_file():
                            raise FileNotFoundError(f"Prompt generator artifact is missing: {source}")
                        attached_file_ids.append(
                            project.get_openai_client()
                            .files.create(
                                file=(
                                    source.name,
                                    source.read_bytes(),
                                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                ),
                                purpose="assistants",
                            )
                            .id
                        )
                elif folder == "validator":
                    for source, content_type in (
                        (
                            CANONICAL_TEMPLATE,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        ),
                        (
                            BRAND_GUIDELINES_TEMPLATE,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        ),
                        (VALIDATION_POLICY, "application/json"),
                    ):
                        if not source.is_file():
                            raise FileNotFoundError(f"Validator artifact is missing: {source}")
                        attached_file_ids.append(
                            project.get_openai_client()
                            .files.create(
                                file=(source.name, source.read_bytes(), content_type),
                                purpose="assistants",
                            )
                            .id
                        )
                agent = project.agents.create_version(
                    agent_name=spec.name,
                    definition=PromptAgentDefinition(
                        model=spec.model,
                        instructions=spec.instructions,
                        temperature=spec.temperature,
                        tools=build_tools(spec, tuple(attached_file_ids)),
                    ),
                )
                version_created = True
            finally:
                if not version_created:
                    for file_id in attached_file_ids:
                        project.get_openai_client().files.delete(file_id)
            print(json.dumps({"name": agent.name, "version": agent.version}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create immutable versions of the KM prompt agents.")
    parser.add_argument(
        "--agent",
        choices=("all", *DEPLOYMENT_ORDER),
        default="all",
        help="Agent definition to create; specialists are ordered before the orchestrator.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate definitions and print required non-secret configuration without Azure calls.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    folders = DEPLOYMENT_ORDER if args.agent == "all" else (args.agent,)
    if args.dry_run:
        dry_run(folders)
    else:
        provision(folders)


if __name__ == "__main__":
    main()

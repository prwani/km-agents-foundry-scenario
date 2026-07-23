from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os


class ConfigurationError(ValueError):
    """Raised when required scenario configuration is missing or unsafe."""


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(f"Required environment variable is missing: {name}")
    return value


def validate_public_ipv4(address: str) -> str:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid IPv4 address in allow-list: {address}") from exc
    if ip.version != 4 or ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        raise ConfigurationError(f"Allow-list entry must be a public IPv4 address: {address}")
    return str(ip)


def parse_allowed_public_ips(raw_value: str | None) -> list[str]:
    values = split_csv(raw_value)
    if not values:
        raise ConfigurationError("At least one public IPv4 address is required in ALLOWED_PUBLIC_IPS")
    return [validate_public_ipv4(value) for value in values]


@dataclass(frozen=True)
class RuntimeSettings:
    foundry_project_endpoint: str
    model_deployment_name: str
    allowed_public_ips: tuple[str, ...]
    prompt_orchestrator_agent_name: str | None = None
    hosted_orchestrator_agent_name: str | None = None
    template_policy_path: str = "assets/templates/contoso-template-policy.json"
    max_repair_attempts: int = 2

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        return cls(
            foundry_project_endpoint=require_env("FOUNDRY_PROJECT_ENDPOINT"),
            model_deployment_name=require_env("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
            allowed_public_ips=tuple(parse_allowed_public_ips(os.getenv("ALLOWED_PUBLIC_IPS"))),
            prompt_orchestrator_agent_name=os.getenv("PROMPT_ORCHESTRATOR_AGENT_NAME"),
            hosted_orchestrator_agent_name=os.getenv("HOSTED_ORCHESTRATOR_AGENT_NAME"),
            template_policy_path=os.getenv(
                "TEMPLATE_POLICY_PATH",
                "assets/templates/contoso-template-policy.json",
            ),
            max_repair_attempts=int(os.getenv("MAX_REPAIR_ATTEMPTS", "2")),
        )

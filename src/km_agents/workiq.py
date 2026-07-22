from __future__ import annotations

from dataclasses import dataclass

from .config import ConfigurationError


WORKIQ_SCOPE = "api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask"


@dataclass(frozen=True)
class WorkIqConnection:
    project_connection_id: str

    def toolbox_shape(self) -> dict[str, str]:
        if not self.project_connection_id.startswith("/subscriptions/"):
            raise ConfigurationError(
                "Work IQ project connection ID must be a fully qualified Azure resource ID"
            )
        return {
            "type": "work_iq_preview",
            "project_connection_id": self.project_connection_id,
        }


def build_sharepoint_retrieval_prompt(customer_name: str, artifact_urls: tuple[str, ...]) -> str:
    if not artifact_urls:
        raise ConfigurationError("At least one SharePoint/OneDrive artifact reference is required")
    joined = "\n".join(f"- {url}" for url in artifact_urls)
    return (
        "Retrieve only user-authorized Microsoft 365 context needed for a case study. "
        "Respect sensitivity labels and do not return raw confidential content.\n"
        f"Customer: {customer_name}\nArtifacts:\n{joined}"
    )

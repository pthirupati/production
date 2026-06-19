"""In-memory DevOps toolchain state (CI, Helm, pipelines)."""

from __future__ import annotations


class DevOpsState:
    def __init__(self, scenario_slug: str = "") -> None:
        self.scenario_slug = scenario_slug.lower()
        self.pipeline_status = "success"
        self.helm_release_status = "deployed"
        self.helm_revision = 3
        self.kubeconfig_valid = True
        self.image_tag = "v1.2.0"
        self._apply_scenario()

    def _apply_scenario(self) -> None:
        s = self.scenario_slug
        if "ci-pipeline" in s or "pipeline-failure" in s:
            self.pipeline_status = "failed"
            self.kubeconfig_valid = False
            self.image_tag = "broken"
        elif "helm" in s:
            self.helm_release_status = "pending-upgrade"
            self.helm_revision = 4

    def gitlab_pipeline(self) -> str:
        if self.pipeline_status == "failed":
            return (
                "Pipeline #4821 — FAILED\n"
                "  deploy | failed | Error: unauthorized: KUBECONFIG not set\n"
                "  build  | success\n"
            )
        return "Pipeline #4821 — passed\n  deploy | success\n  build  | success\n"

    def helm_history(self, release: str = "webapp") -> str:
        if self.helm_release_status == "pending-upgrade":
            return (
                f"REVISION  STATUS          CHART\n"
                f"4         pending-upgrade webapp-1.2.0\n"
                f"3         deployed        webapp-1.1.0\n"
            )
        return f"REVISION  STATUS    CHART\n3         deployed  webapp-1.1.0\n"

    def helm_rollback(self, release: str, rev: int = 3) -> str:
        self.helm_release_status = "deployed"
        self.helm_revision = rev
        return f"Rollback was a success! Happy Helming!"

    def fix_pipeline(self) -> str:
        self.pipeline_status = "success"
        self.kubeconfig_valid = True
        self.image_tag = "v1.2.0"
        return "Pipeline variables updated — redeploy scheduled"

    def is_healthy(self) -> bool:
        return self.pipeline_status == "success" and self.helm_release_status == "deployed"

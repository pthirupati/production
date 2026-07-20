"""Topic-aware fault injection — plant REAL broken state from scenario keywords.

Academy generators often recycle nginx/rsyslog breaks for unrelated titles.
This module maps slug keywords onto genuine Lab Server state so the terminal
and GUI reflect the scenario narrative before the learner starts fixing.
"""

from __future__ import annotations

from typing import Any


def apply_topic_fault(slug: str, state: Any) -> bool:
    """Apply a topic fault if the slug matches. Returns True when something changed."""
    low = (slug or "").lower()
    if not low:
        return False

    # Disk pressure (exact families — avoid inode/deleted-open hijacks)
    if low in ("disk-full", "sim-disk-full", "sim-rhel-disk-full") or (
        low.endswith("-disk-full") and "inode" not in low and "deleted" not in low
    ):
        from .scenario_presets import _preset_disk_full
        _preset_disk_full(state)
        return True

    # Git / devops CI topics — plant a broken CI config + inactive runner, not nginx
    if any(k in low for k in ("git-flow", "git-merge", "learn-git", "ci-pipeline", "cicd", "gitlab-ci", "jenkins")):
        return _fault_ci_git(state, low)

    # GitOps / Argo / Flux — OutOfSync app + missing FIXED path for marker labs
    if any(k in low for k in ("gitops", "argocd", "flux", "outofsync", "kustomize")):
        return _fault_gitops(state, low)

    # Permissions / ACL
    if any(k in low for k in ("permissions", "acl", "chmod", "chown", "sudoers")):
        return _fault_permissions(state, low)

    # Networking basics
    if any(k in low for k in ("dns", "resolv", "ntp", "chrony", "firewall", "selinux")):
        return _fault_network_security(state, low)

    # AWS academy fail-open closure — plant broken config so is-failed check fails
    if low.startswith("academy-aws") or (low.startswith("aws-") and "terraform" not in low):
        return _fault_aws_academy(state, low)

    # Azure / GCP academy — plant cloud CLI config fault + sentinel
    if low.startswith(("academy-azure", "azure-")):
        return _fault_cloud_cli(state, low, "azure")
    if low.startswith(("academy-gcp", "gcp-")):
        return _fault_cloud_cli(state, low, "gcp")

    return False


def _fault_ci_git(state: Any, slug: str) -> bool:
    from .rhel_os import SimService, SimProcess

    state._mkdir("/opt/ci")
    state._mkdir("/root/app")
    state._write_file(
        "/opt/ci/.gitlab-ci.yml",
        "stages: [build]\nbuild:\n  script:\n    - echo BROKEN_PIPELINE\n    - exit 1\n",
    )
    state._write_file(
        "/opt/ci/Jenkinsfile",
        "pipeline { agent any; stages { stage('Build') { steps { sh 'exit 1' } } } }\n",
    )
    state._write_file(
        "/root/app/.git/config",
        "[core]\n\trepositoryformatversion = 0\n[branch \"main\"]\n\tremote = origin\n",
    )
    state.services["gitlab-runner"] = SimService(
        "gitlab-runner", active="failed", enabled="enabled",
        description="GitLab Runner", loaded="loaded", sub_state="failed",
    )
    # Keep a broken-config sentinel so FIXED-OK / is-failed validators stay fail-closed
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_gitops(state: Any, slug: str) -> bool:
    state._mkdir("/opt/gitops")
    state._mkdir("/root/.kube")
    state._write_file(
        "/opt/gitops/application.yaml",
        "apiVersion: argoproj.io/v1alpha1\nkind: Application\nmetadata:\n  name: webapp\n"
        "spec:\n  source:\n    repoURL: https://github.com/example/gitops.git\n"
        "    path: overlays/prod\n  syncPolicy: {}\n"
        "status:\n  sync:\n    status: OutOfSync\n  health:\n    status: Degraded\n",
    )
    state._write_file(
        "/opt/gitops/flux-kustomization.yaml",
        "apiVersion: kustomize.toolkit.fluxcd.io/v1\nkind: Kustomization\n"
        "metadata:\n  name: apps\nspec:\n  path: ./apps\n  prune: true\n"
        "status:\n  conditions:\n  - type: Ready\n    status: \"False\"\n"
        "    message: reconciliation failed\n",
    )
    state._write_file("/root/.kube/config", "apiVersion: v1\nkind: Config\nclusters: []\n")
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_permissions(state: Any, slug: str) -> bool:
    state._mkdir("/opt/app")
    state._mkdir("/etc/sudoers.d")
    state._write_file("/opt/app/secret.env", "SECRET=changeme\n", mode="777")
    state._write_file(
        "/etc/sudoers.d/app",
        "appuser ALL=(ALL) NOPASSWD: ALL\n# insecure — needs lockdown\n",
        mode="644",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_network_security(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    if "dns" in slug or "resolv" in slug:
        state._write_file("/etc/resolv.conf", "nameserver 127.0.0.1\n# broken — no upstream\n")
    if "ntp" in slug or "chrony" in slug:
        state.services["chronyd"] = SimService(
            "chronyd", active="failed", enabled="enabled", description="NTP client/server",
        )
    if "firewall" in slug:
        state.services["firewalld"] = SimService(
            "firewalld", active="failed", enabled="enabled", description="firewalld",
        )
    if "selinux" in slug:
        state.selinux_mode = "Permissive"
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_aws_academy(state: Any, slug: str) -> bool:
    """Close fail-open: academy-aws check.sh is `systemctl is-failed` with no prior break."""
    state._mkdir("/opt/aws")
    state._write_file(
        "/opt/aws/lab-state.json",
        '{"ec2":"misconfigured","sg":"too-open","status":"broken"}\n',
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_cloud_cli(state: Any, slug: str, cloud: str) -> bool:
    state._mkdir(f"/opt/{cloud}")
    state._write_file(
        f"/opt/{cloud}/config",
        f"# broken {cloud} CLI profile — subscription/project not set\n",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True

"""Topic-aware fault injection — plant REAL broken state from scenario keywords.

Academy generators often recycle nginx/rsyslog breaks for unrelated titles.
This module maps slug keywords onto genuine Lab Server state so the terminal
and GUI reflect the scenario narrative before the learner starts fixing.
"""

from __future__ import annotations

from typing import Any

# Shared with scripts/upgrade_academy_labs.py — keep keyword lists in sync.
CI_KEYWORDS = (
    "git-flow", "git-merge", "learn-git", "ci-pipeline", "cicd", "gitlab-ci",
    "jenkins", "artifacts", "cd-release", "change-management", "incident-response",
)
GITOPS_KEYWORDS = ("gitops", "argocd", "flux", "outofsync", "kustomize", "drift", "sync")
PERM_KEYWORDS = ("permissions", "acl", "chmod", "chown", "sudoers")
NETSEC_KEYWORDS = ("dns", "resolv", "ntp", "chrony", "firewall", "selinux", "vlan", "bonding", "mtu", "nat")
K8S_KEYWORDS = ("kubernetes", "k8s", "pod-", "crashloop", "kubelet", "helm-")
TF_KEYWORDS = ("terraform", "tfstate", "iac-")
DOCKER_KEYWORDS = ("docker-compose", "compose", "containerd", "dockerfile")
DB_KEYWORDS = ("postgres", "mysql", "mariadb", "redis", "mongodb", "pgbouncer")
JAVA_KEYWORDS = ("spring-boot", "jvm", "tomcat", "heap-", "gc-pause", "springboot")
SEC_KEYWORDS = ("secrets", "vault", "tls-", "cert-", "rbac", "owasp")
OPENSTACK_KEYWORDS = ("openstack", "nova", "neutron", "keystone", "glance", "cinder", "horizon")
MEMCACHE_KEYWORDS = ("memcached", "memcache")
MQ_KEYWORDS = ("rabbitmq", "amqp")


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

    # Cloud academies FIRST — slug keywords like "firewall"/"dns" must not steal
    # GCP firewall-rules / Azure NSG labs into host firewalld/named breaks.
    if low.startswith("academy-aws") or (low.startswith("aws-") and "terraform" not in low):
        return _fault_aws_academy(state, low)
    if low.startswith(("academy-azure", "azure-")):
        return _fault_cloud_cli(state, low, "azure")
    if low.startswith(("academy-gcp", "gcp-")):
        return _fault_cloud_cli(state, low, "gcp")
    if low.startswith(("academy-openstack", "openstack-")) or any(
        k in low for k in OPENSTACK_KEYWORDS
    ):
        return _fault_openstack(state, low)

    # Git / devops CI topics — plant a broken CI config + inactive runner, not nginx
    if any(k in low for k in CI_KEYWORDS):
        return _fault_ci_git(state, low)

    # GitOps / Argo / Flux — OutOfSync app + missing FIXED path for marker labs
    if any(k in low for k in GITOPS_KEYWORDS):
        return _fault_gitops(state, low)

    # Permissions / ACL
    if any(k in low for k in PERM_KEYWORDS):
        return _fault_permissions(state, low)

    # Networking / host security basics
    if any(k in low for k in NETSEC_KEYWORDS):
        return _fault_network_security(state, low)

    # Kubernetes / workloads
    if any(k in low for k in K8S_KEYWORDS):
        return _fault_kubernetes(state, low)

    # Terraform / IaC
    if any(k in low for k in TF_KEYWORDS):
        return _fault_terraform(state, low)

    # Docker / compose
    if any(k in low for k in DOCKER_KEYWORDS):
        return _fault_docker(state, low)

    # Databases
    if any(k in low for k in DB_KEYWORDS):
        return _fault_database(state, low)

    # Memcached / message queues
    if any(k in low for k in MEMCACHE_KEYWORDS):
        return _fault_service_unit(state, low, "memcached", "Memcached")
    if any(k in low for k in MQ_KEYWORDS):
        return _fault_service_unit(state, low, "rabbitmq-server", "RabbitMQ broker")

    # Java / JVM apps — do not match "javascript"
    if "javascript" not in low and any(k in low for k in JAVA_KEYWORDS):
        return _fault_java(state, low)

    # Security / secrets / TLS
    if any(k in low for k in SEC_KEYWORDS):
        return _fault_security(state, low)

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
    # Graded via `systemctl is-active gitlab-runner` — no FIXED-OK sentinel.
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
        state.services["named"] = SimService(
            "named", active="failed", enabled="enabled", description="DNS server",
        )
    if "ntp" in slug or "chrony" in slug:
        state.services["chronyd"] = SimService(
            "chronyd", active="failed", enabled="enabled", description="NTP client/server",
        )
    if "firewall" in slug:
        state.services["firewalld"] = SimService(
            "firewalld", active="failed", enabled="enabled", description="firewalld",
        )
        # Academy list-ports labs grade via is_port_open(80). Default FirewallState
        # includes the "http" service, which auto-passes without learner work —
        # strip http/ports so the unfixed world fail-closes (grader-integrity).
        from .scenario_presets import _preset_firewalld_blocked
        _preset_firewalld_blocked(state)
        # Keep firewalld failed after the nginx/firewall preset (preset may leave
        # other services active; firewalld itself must stay down until started).
        state.services["firewalld"] = SimService(
            "firewalld", active="failed", enabled="enabled", description="firewalld",
        )
    if "selinux" in slug:
        state.selinux_mode = "Permissive"
    if "vlan" in slug or "bonding" in slug or "mtu" in slug or "nat" in slug:
        state._write_file(
            "/etc/sysconfig/network-scripts/ifcfg-eth0",
            "DEVICE=eth0\nBOOTPROTO=none\nONBOOT=no\n# broken NIC config\n",
        )
        from .scenario_presets import _plant_broken_config_sentinel
        _plant_broken_config_sentinel(slug, state)
    elif "selinux" in slug:
        from .scenario_presets import _plant_broken_config_sentinel
        _plant_broken_config_sentinel(slug, state)
    # firewall/dns/chrony are graded via systemctl is-active <unit> — no sentinel.
    return True


def _fault_kubernetes(state: Any, slug: str) -> bool:
    state._mkdir("/root/.kube")
    state._mkdir("/opt/k8s")
    state._write_file("/root/.kube/config", "apiVersion: v1\nkind: Config\nclusters: []\n")
    state._write_file(
        "/opt/k8s/deployment.yaml",
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: webapp\n"
        "spec:\n  replicas: 1\n  template:\n    spec:\n      containers:\n"
        "      - name: app\n        image: broken:missing\n",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_terraform(state: Any, slug: str) -> bool:
    state._mkdir("/opt/terraform")
    state._write_file(
        "/opt/terraform/main.tf",
        'resource "null_resource" "broken" {\n  triggers = { status = "BROKEN" }\n}\n',
    )
    state._write_file("/opt/terraform/terraform.tfstate", '{"version":4,"resources":[]}\n')
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_docker(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/app")
    state._write_file(
        "/opt/app/docker-compose.yml",
        "services:\n  web:\n    image: nginx:broken\n    ports: [\"80:80\"]\n",
    )
    state.services["docker"] = SimService(
        "docker", active="failed", enabled="enabled",
        description="Docker Application Container Engine",
        loaded="loaded", sub_state="failed",
    )
    return True


def _fault_database(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    unit = "postgresql"
    if any(k in slug for k in ("mysql", "mariadb")):
        unit = "mysqld"
    elif "redis" in slug:
        unit = "redis"
    elif "mongo" in slug:
        unit = "mongod"
    state.services[unit] = SimService(
        unit, active="failed", enabled="enabled",
        description=f"{unit} database", loaded="loaded", sub_state="failed",
    )
    return True


def _fault_java(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/app")
    state._write_file("/opt/app/application.properties", "server.port=0\n# broken bind\n")
    state.services["spring-boot"] = SimService(
        "spring-boot", active="failed", enabled="enabled",
        description="Spring Boot Application Service",
        loaded="loaded", sub_state="failed",
    )
    return True


def _fault_security(state: Any, slug: str) -> bool:
    state._mkdir("/opt/app")
    state._mkdir("/etc/pki/tls")
    if "secret" in slug or "vault" in slug:
        state._write_file("/opt/app/secrets.env", "API_KEY=plaintext-in-repo\n", mode="666")
    if "tls" in slug or "cert" in slug:
        state._write_file("/etc/pki/tls/certs/lab.crt", "# EXPIRED CERT\nBROKEN\n")
    if "rbac" in slug or "owasp" in slug:
        state._write_file(
            "/opt/app/rbac.yaml",
            "rules:\n- apiGroups: [\"*\"]\n  resources: [\"*\"]\n  verbs: [\"*\"]\n",
        )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_service_unit(state: Any, slug: str, unit: str, desc: str) -> bool:
    from .rhel_os import SimService

    state.services[unit] = SimService(
        unit, active="failed", enabled="enabled",
        description=desc, loaded="loaded", sub_state="failed",
    )
    return True


def _fault_openstack(state: Any, slug: str) -> bool:
    state._mkdir("/opt/openstack")
    state._write_file(
        "/opt/openstack/clouds.yaml",
        "clouds:\n  lab:\n    auth:\n      auth_url: http://127.0.0.1:5000/v3\n"
        "      project_name: broken\n      username: broken\n      password: wrong\n"
        "    region_name: RegionOne\n",
    )
    state._write_file(
        "/opt/openstack/lab-state.json",
        '{"nova":"down","neutron":"misconfigured","status":"broken"}\n',
    )
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

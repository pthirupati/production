"""
AI Infra Engineering — surface map + wiki-informed scenario notes.

Scenarios under technology slug ``ai-infra`` reuse existing Lab surfaces
(Bare Metal/MAAS, Datacenter twin, AWX, GPU terminal) instead of parallel UIs.

Internal ops references used for realism (DigitalOcean Confluence/Jira):
- GPU Bare Metal Escalation Process (GM1)
- ESC Troubleshooting Runbook — Images/Kernels / dcgm-exporter (IAAS)
- PSINFRA Team — MAAS commissioning / repave
- DCOPS thermal violation tickets (e.g. DCOPS-17409 H100 GPU4 fail)
- PSINFRA-1816 Dell XE9680 H100 SXM tray donors
- AMD Support One-Pager / INCI-2333 rocm hang
"""

from __future__ import annotations

# topic substring → (simulation_type, consoles, extra YAML flags)
AI_INFRA_TOPIC_SURFACES: dict[str, dict] = {
    "maas": {
        "simulation_type": "baremetal",
        "consoles": ["baremetal", "terminal"],
        "hosted_as": "baremetal",
    },
    "lxd": {
        "simulation_type": "baremetal",
        "consoles": ["baremetal", "terminal"],
        "hosted_as": "baremetal",
    },
    "pxe": {
        "simulation_type": "baremetal",
        "consoles": ["baremetal", "terminal"],
        "hosted_as": "baremetal",
    },
    "bmc": {
        "simulation_type": "baremetal",
        "consoles": ["baremetal", "terminal", "bmc"],
        "hosted_as": "baremetal",
    },
    "awx": {
        "simulation_type": "ansible-awx",
        "consoles": ["awx", "terminal"],
    },
    "thermal": {
        "simulation_type": "datacenter",
        "consoles": ["datacenter", "terminal"],
        "datacenter_link": True,
        "hosted_as": "datacenter",
    },
    "chassis": {
        "simulation_type": "datacenter",
        "consoles": ["datacenter", "terminal"],
        "datacenter_link": True,
        "hosted_as": "datacenter",
    },
    "dcgm": {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    },
    "nvidia-smi": {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    },
    "rocm": {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    },
    "packer": {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    },
    "nccl": {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    },
    "nvlink": {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    },
    "missing-gpu": {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    },
    "vyos": {
        # VyOS UI not shipped yet — Lab Terminal + DC twin for uplink context.
        "simulation_type": "datacenter",
        "consoles": ["datacenter", "terminal"],
        "datacenter_link": True,
        "hosted_as": "datacenter",
    },
}


def surface_for_topic(topic: str) -> dict:
    key = (topic or "").lower().replace("_", "-")
    for needle, cfg in AI_INFRA_TOPIC_SURFACES.items():
        if needle in key:
            return dict(cfg)
    return {
        "simulation_type": "gpu",
        "consoles": ["terminal"],
        "hosted_as": "baremetal",
    }


def apply_ai_infra_surfaces(spec: dict, topic: str) -> dict:
    """Mutate academy/hero spec so LabRunner opens the right existing surface."""
    cfg = surface_for_topic(topic)
    spec["simulation_type"] = cfg["simulation_type"]
    spec["consoles"] = list(cfg.get("consoles") or ["terminal"])
    if cfg.get("datacenter_link"):
        spec["datacenter_link"] = True
    if cfg.get("hosted_as"):
        spec["hosted_as"] = cfg["hosted_as"]
    # Curriculum stamp only — do NOT set cross_technology True (clears consolesKind).
    spec["lab_servers"] = [
        {
            "id": "gpu-node-01",
            "role": "primary",
            "hostname": "gpu-node-01",
            "persona": "linux" if cfg["simulation_type"] == "gpu" else (
                "baremetal" if cfg["simulation_type"] == "baremetal" else "baremetal"
            ),
            "appears_in": list(spec["consoles"]),
        }
    ]
    return spec

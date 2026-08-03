"""Environment-resolver lint rules for scenario.yaml."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "lint_scenarios",
    ROOT / "scripts" / "lint_scenarios.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
_env_resolver_errors = _mod._env_resolver_errors


def test_vmware_link_rejects_datacenter_hosted():
    errs = _env_resolver_errors(
        {
            "slug": "add-second-nic",
            "vmware_link": True,
            "hosted_as": "datacenter",
            "simulation_type": "vmware",
        },
        Path("scenarios/vmware/add-second-nic/scenario.yaml"),
    )
    assert any("hosted_as=datacenter" in e or "expected vmware" in e for e in errs)


def test_aws_consoles_must_include_aws():
    errs = _env_resolver_errors(
        {
            "slug": "academy-aws-001-learn-ec2",
            "simulation_type": "aws",
            "consoles": ["terminal"],
        },
        Path("scenarios/aws/academy-aws-001-learn-ec2/scenario.yaml"),
    )
    assert any("omit `aws`" in e for e in errs)


def test_ok_when_aligned():
    errs = _env_resolver_errors(
        {
            "slug": "academy-aws-001-learn-ec2",
            "simulation_type": "aws",
            "hosted_as": "aws",
            "consoles": ["aws", "terminal"],
        },
        Path("scenarios/aws/academy-aws-001-learn-ec2/scenario.yaml"),
    )
    assert errs == []

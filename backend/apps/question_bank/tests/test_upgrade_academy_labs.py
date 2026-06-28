"""Tests for academy lab upgrade helpers."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

from upgrade_academy_labs import (  # noqa: E402
    assign_service_unit,
    check_script_for_mode,
    classify_mode,
)


def test_classify_mode_service_for_generic_linux():
    assert classify_mode("linux", "generic", "academy-linux-004-troubleshoot-journald-logs") == "service"


def test_classify_mode_dedicated_nmap():
    assert classify_mode("nmap", "nmap", "academy-nmap-001-learn-tcp-scan") == "dedicated"


def test_classify_mode_k8s():
    assert classify_mode("kubernetes", "kubernetes", "academy-kubernetes-001-learn-pods") == "k8s"


def test_check_script_service_has_no_marker():
    body = check_script_for_mode("service", "nginx")
    assert "FIXED-OK" not in body
    assert "systemctl is-active nginx" in body


def test_assign_service_unit_deterministic():
    u1 = assign_service_unit("linux", "academy-linux-001-learn-users-groups")
    u2 = assign_service_unit("linux", "academy-linux-001-learn-users-groups")
    assert u1 == u2
    assert u1 in ("nginx", "crond", "rsyslog", "chronyd")


def test_no_academy_check_sh_uses_fixed_ok_marker():
    """Regression: all academy labs must use real validation, not FIXED-OK grep."""
    root = Path(__file__).resolve().parents[4]
    marker = re.compile(r"FIXED-OK")
    offenders = []
    for path in (root / "scenarios").glob("*/academy-*/check.sh"):
        if marker.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"marker checks remain: {offenders[:5]}"

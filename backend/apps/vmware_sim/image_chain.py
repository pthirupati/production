"""§X3 / §G2 — grade the Packer → AMI → EC2 → guest provenance chain.

A marker file cannot prove a golden-image lab. The learner must have:

1. a published Packer content manifest containing the required packages,
2. an AMI registered from that manifest (matching digest) in the expected region,
3. a running instance launched from *that* AMI ID, and
4. an in-guest OS state that reflects the AMI (kernel / packages / user).

Fail closed at every step — absence of any link is a grade failure, never a pass.
"""

from __future__ import annotations

from typing import Any


def _guest_state_for_session(session_id: str | None):
    if not session_id:
        return None
    try:
        from apps.labs.provisioner.simulation.shell import get_sim_session
        entry = get_sim_session(str(session_id))
    except Exception:
        return None
    if not entry:
        return None
    engine = (entry.get("state") or {}).get("engine")
    return getattr(getattr(engine, "shell", None), "state", None)


def _factory_manifest(aws_state: dict) -> dict | None:
    try:
        from apps.vmware_sim import packer_factory as pf
        res = pf.get_manifest(aws_state)
    except Exception:
        return None
    if not res.get("ok"):
        return None
    man = res.get("manifest")
    return man if isinstance(man, dict) else None


def validate_image_chain(
    aws_state: dict,
    *,
    session_id: str | None = None,
    guest_state: Any = None,
    require: dict | None = None,
) -> tuple[bool, str]:
    """Assert the full artifact provenance chain. Returns (ok, reason)."""
    if not isinstance(aws_state, dict):
        return False, "No AWS state"
    req = require if isinstance(require, dict) else {}
    require_packages = [str(p) for p in (req.get("packages") or []) if str(p).strip()]
    require_region = str(req.get("region") or aws_state.get("region") or "").strip() or None
    require_guest = bool(req.get("require_guest", True))
    require_gpu = bool(req.get("require_gpu_stack", False))

    factory_man = _factory_manifest(aws_state)

    amis = [
        a for a in (aws_state.get("amis") or [])
        if isinstance(a, dict) and (a.get("manifest") or a.get("digest"))
    ]
    if not amis:
        return False, "No imported AMI registered — import the Packer artifact first"

    ami = None
    if factory_man and factory_man.get("digest"):
        digest = factory_man["digest"]
        ami = next((a for a in amis if a.get("digest") == digest), None)
        if ami is None:
            return False, "Imported AMI digest does not match the published Packer artifact"
    else:
        # Most recently registered imported AMI (created timestamps are ISO).
        ami = sorted(amis, key=lambda a: a.get("created") or "", reverse=True)[0]

    if require_region and ami.get("region") and ami.get("region") != require_region:
        return False, f"AMI {ami.get('id')} is registered in {ami.get('region')}, expected {require_region}"

    manifest = ami.get("manifest") if isinstance(ami.get("manifest"), dict) else None
    if not manifest:
        manifest = factory_man
    if not isinstance(manifest, dict) or not manifest:
        return False, "AMI has no content manifest — refuse to grade without provenance"

    for pkg in require_packages:
        if pkg not in (manifest.get("packages") or []):
            return False, f"Artifact manifest missing required package: {pkg}"

    if require_gpu and not manifest.get("gpu_stack"):
        return False, "Artifact manifest does not include the GPU driver stack"

    ami_id = ami.get("id")
    running = [
        i for i in (aws_state.get("instances") or [])
        if isinstance(i, dict)
        and i.get("state") == "running"
        and (i.get("amiId") == ami_id or i.get("ami_id") == ami_id)
    ]
    if not running:
        return False, f"No running instance launched from AMI {ami_id}"

    inst = running[0]
    want_digest = ami.get("digest") or manifest.get("digest")
    got_digest = inst.get("amiDigest") or inst.get("ami_digest")
    if want_digest and got_digest and got_digest != want_digest:
        return False, "Instance AMI digest does not match the registered image"

    # Guest OS must reflect the AMI the learner built (§X3).
    gst = guest_state if guest_state is not None else _guest_state_for_session(session_id)
    if require_guest:
        if gst is None:
            return False, "Guest OS state not available to verify AMI seed"
        kernel = str(manifest.get("kernel") or "").strip()
        if kernel and getattr(gst, "kernel", None) != kernel:
            return False, f"Guest kernel is {getattr(gst, 'kernel', '?')}, expected {kernel} from AMI"
        user = str(manifest.get("default_user") or "").strip()
        if user and user not in (getattr(gst, "users", None) or {}):
            return False, f"Guest is missing AMI default user '{user}'"
        check_pkgs = require_packages or list(manifest.get("packages") or [])[:6]
        installed = getattr(gst, "installed_packages", None) or {}
        for pkg in check_pkgs:
            if pkg not in installed and not (
                hasattr(gst, "is_package_installed") and gst.is_package_installed(pkg)
            ):
                return False, f"Guest is missing package from AMI manifest: {pkg}"
        if not getattr(gst, "ssh_keys_baked", True):
            return False, "Guest SSH keys were not baked — cloud-init / authorized_keys incomplete"

    return True, f"Image chain OK: AMI {ami_id} → instance {inst.get('id')} matches manifest"


def slug_wants_image_chain(slug: str) -> bool:
    """Heuristic: golden-image / import / packer→AMI labs need chain grading."""
    low = (slug or "").lower()
    needles = (
        "golden-image", "golden_image", "import-image", "import_image",
        "ami-from-packer", "packer-ami", "image-to-ami", "image_to_ami",
        "packer-to-ec2", "packer_to_ec2",
    )
    return any(n in low for n in needles)

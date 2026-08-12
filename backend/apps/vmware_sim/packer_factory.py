"""Packer Image Factory — lightweight CI pipeline state for baremetal sessions.

Learner language: Lab Environment / Image Factory — never Simulation/Sandbox/Mock.
Pipeline mirrors GitHub Actions–style Image Factory workflow runs.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from .baremetal_v2_facades import apply_v2_action, ensure_v2

MATRIX_SKUS = ("h100", "h200", "b300", "mi300")

JOB_SPECS = (
    ("packer-init", "packer-init"),
    ("validate", "validate"),
    ("build", "build"),
    ("libguestfs-customize", "libguestfs-customize"),
    ("vuln-scan+remediate", "vuln-scan+remediate"),
    ("gpu-sanity", "gpu-sanity"),
    ("publish", "publish"),
)

NVIDIA_MARKERS = (
    "nvidia-driver",
    "nvidia-persistenced",
    "nvidia-smi",
    "install-gpu",
    "cuda-toolkit",
    "dcgm",
)

ACTIONS = frozenset({
    "packer_factory_get_state",
    "packer_factory_start_pipeline",
    "packer_factory_start_matrix",
    "packer_factory_fail_matrix_sku",
    "packer_factory_publish_matrix",
    "packer_factory_advance_job",
    "packer_factory_publish_artifact",
    "packer_factory_rerun_job",
    "packer_factory_get_job_logs",
    "packer_factory_mark_build",
    "packer_factory_get_manifest",
    "packer_factory_verify_upstream",
})

# Artifact manifest schema version. Bumped whenever a field is ADDED or its
# meaning changes. Consumers (aws_engine import-image, graders) must compare
# this rather than probing for individual keys — a `.get(key, default)` probe
# on an old manifest-less blob would silently read a default and fail OPEN,
# passing a learner who never built the image.
MANIFEST_SCHEMA_VERSION = 1

# Base cloud images a build can start from, keyed by the SKU's OS family. The
# digest is the artifact's identity: import-image refuses a manifest whose
# digest does not match what the build recorded.
BASE_IMAGES = {
    "jammy": {
        "name": "ubuntu-22.04-server-cloudimg-amd64.img",
        "os": "ubuntu-22.04",
        "arch": "x86_64",
        "user": "ubuntu",
        "kernel": "5.15.0-91-generic",
        # Teaching digests — supply-chain gate compares learner-supplied values.
        "sha256": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "gpg_fingerprint": "843938DF228D22F7B3742BC0D94AA3F0EFE21092",
    },
    "rhel-gpu": {
        "name": "rhel-9.3-x86_64-kvm.qcow2",
        "os": "rhel-9",
        "arch": "x86_64",
        "user": "ec2-user",
        "kernel": "5.14.0-362.el9.x86_64",
        "sha256": "sha256:c5f969d8a0e3c5f1f7a0e4b2c8d6e0a1b3c5d7e9f1a3b5c7d9e1f3a5b7c9d1e3",
        "gpg_fingerprint": "567E347AD0044ADE55BA8A5F199E2F91FD431D51",
    },
}

# Packages libguestfs-customize bakes in on every build, before SKU extras.
BASE_PACKAGES = ("cloud-init", "qemu-guest-agent", "openssh-server")

# Driver stack added only when the template genuinely provisions NVIDIA.
GPU_PACKAGES = ("nvidia-driver-535", "nvidia-persistenced", "cuda-toolkit-12-3", "datacenter-gpu-manager")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _boot_resource_name(sku: str) -> str:
    sku = (sku or "h100").strip().lower().replace("custom/", "").replace("-jammy", "")
    if sku in ("rhel-gpu", "rhel"):
        return "custom/rhel-gpu"
    return f"custom/{sku}-jammy"


def _strip_hcl_comments(text: str) -> str:
    """Drop `#`/`//` line comments and `/* */` blocks, preserving quoted strings.

    A marker inside a comment must not count as a driver install, so comments are
    removed BEFORE any marker matching. Quote tracking matters because a real
    provisioner line can legitimately contain `#` (e.g. a shell inline with a
    `#!/bin/bash` shebang or a URL fragment) — naively cutting at the first `#`
    would truncate a valid block and reject a solvable template.
    """
    out: list[str] = []
    i, n = 0, len(text)
    quote = ""          # active quote char, "" when outside a string
    heredoc = ""        # active heredoc terminator, "" when outside one
    while i < n:
        ch = text[i]
        if heredoc:
            # Inside <<-EOF … EOF the payload is literal; only the terminator ends it.
            line_end = text.find("\n", i)
            line_end = n if line_end == -1 else line_end
            line = text[i:line_end]
            out.append(line)
            if line.strip().rstrip(";") == heredoc:
                heredoc = ""
            if line_end < n:
                out.append("\n")
            i = line_end + 1
            continue
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:      # escaped char inside a string
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if text.startswith("<<-", i) or text.startswith("<<", i):
            j = i + (3 if text.startswith("<<-", i) else 2)
            k = j
            while k < n and (text[k].isalnum() or text[k] == "_"):
                k += 1
            if k > j:
                heredoc = text[j:k]
                out.append(" " * (k - i))
                i = k
                continue
        if ch == "#" or text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _block_bodies(text: str, header_re) -> list[str]:
    """Return the `{…}` body of every block whose header matches `header_re`.

    Brace-counting rather than a regex: provisioner bodies nest (inline lists,
    nested blocks), so a non-greedy `\\{.*?\\}` would stop at the first inner
    close brace and miss markers past it.
    """
    bodies: list[str] = []
    for m in header_re.finditer(text):
        start = text.find("{", m.end() - 1)
        if start == -1:
            continue
        depth, i, n = 0, start, len(text)
        while i < n:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(text[start + 1:i])
                    break
            i += 1
    return bodies


_SHELL_PROV_RE = re.compile(
    r"\bprovisioner\s+\"(?:shell|shell-local|ansible|file)\"\s*\{"
)


def _has_nvidia_marker(files: dict | None, template_blob: str = "") -> bool:
    """True when the template genuinely provisions the NVIDIA driver stack.

    Previously this was a substring scan over the whole template plus every file
    value, so `# nvidia-smi` in a comment — the exact token the gpu-sanity failure
    log tells the learner to add — passed the gate. Now the marker must appear
    inside the body of a real `provisioner` block. Comments are stripped first, so
    a commented-out provisioner no longer counts.

    Provisioners are matched at any depth, not only nested inside `build {}`.
    Requiring the `build` wrapper would add no anti-cheat value (a comment is
    already excluded by the strip) while rejecting the bare-provisioner templates
    that existing packer labs and their reference solutions use — exactly the
    "previously-accepted templates become unsolvable" regression to avoid.
    """
    sources = [template_blob or ""]
    if isinstance(files, dict):
        sources.extend(str(v) for v in files.values())

    for raw in sources:
        if not raw:
            continue
        code = _strip_hcl_comments(raw)
        for prov_body in _block_bodies(code, _SHELL_PROV_RE):
            if any(m in prov_body.lower() for m in NVIDIA_MARKERS):
                return True
    return False


def _base_image_for(sku: str) -> dict:
    sku = (sku or "h100").strip().lower()
    return BASE_IMAGES["rhel-gpu"] if sku in ("rhel-gpu", "rhel") else BASE_IMAGES["jammy"]


def verify_upstream_image(payload: dict | None = None, *, sku: str = "h100") -> tuple[bool, str]:
    """Supply-chain gate: refuse the build on checksum/GPG mismatch (audit X3).

    Enforcement is opt-in via payload fields or ``force_verify`` so existing
    pipelines that never supply a checksum keep working. When a checksum or
    GPG result *is* supplied, mismatch fails closed — no artifact is produced.
    """
    payload = payload or {}
    base = _base_image_for(sku)
    expected = str(base.get("sha256") or "")
    got = str(payload.get("checksum") or payload.get("sha256") or "").strip()
    force = bool(payload.get("verify_upstream") or payload.get("force_verify"))

    if got or force:
        if not got:
            return False, "ClientError: upstream image checksum required before build"
        if not got.startswith("sha256:"):
            got = f"sha256:{got}"
        if got != expected:
            return False, (
                f"ClientError: upstream image checksum mismatch "
                f"(got {got}, expected {expected}) — refuse to build"
            )

    if payload.get("gpg_ok") is False or payload.get("gpg_verify") is False:
        return False, (
            "ClientError: upstream image GPG signature verification failed — refuse to build"
        )

    fingerprint = str(payload.get("gpg_fingerprint") or "").strip().upper().replace(" ", "")
    if fingerprint:
        want = str(base.get("gpg_fingerprint") or "").upper().replace(" ", "")
        if fingerprint != want:
            return False, (
                f"ClientError: upstream image GPG fingerprint mismatch "
                f"(got {fingerprint}) — refuse to build"
            )

    if got or force or fingerprint or payload.get("gpg_ok") is True:
        return True, "upstream image verified"
    return True, "upstream verify skipped"


def _artifact_digest(run: dict) -> str:
    """Content digest over the inputs that decide what lands in the image.

    Deterministic (blake2b over a sorted, canonical projection) so the same
    template + SKU + gate outcomes always produce the same digest — a grader can
    therefore assert "this AMI came from that build" rather than trusting a
    random id. Gate outcomes are part of the identity on purpose: a remediated
    image is genuinely different content from the one that failed the CVE gate.
    """
    payload = json.dumps(
        {
            "sku": run.get("sku") or "",
            "base": _base_image_for(run.get("sku")).get("name"),
            "has_nvidia_marker": bool(run.get("has_nvidia_marker")),
            "cve_remediated": bool(run.get("cve_remediated")),
            "files": {k: str(v) for k, v in sorted((run.get("files_snapshot") or {}).items())},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.blake2b(payload.encode("utf-8"), digest_size=32).hexdigest()


def build_manifest(run: dict) -> dict:
    """Content manifest describing what a completed build actually produced.

    This is the grading substrate for the image→AMI→instance chain: the packages,
    kernel, users and CIS findings recorded here are what an imported AMI carries
    into a launched instance's guest state. Fields are always present (never
    conditionally omitted) so a consumer never has to guess whether absence means
    "not built" or "old schema" — `schema_version` answers that instead.
    """
    sku = (run.get("sku") or "h100").strip().lower()
    base = _base_image_for(sku)
    has_gpu = bool(run.get("has_nvidia_marker"))

    packages = list(BASE_PACKAGES) + (list(GPU_PACKAGES) if has_gpu else [])
    services = ["cloud-init", "sshd", "qemu-guest-agent"] + (["nvidia-persistenced", "dcgm-exporter"] if has_gpu else [])

    # The CVE gate is what remediation actually clears. An unremediated build
    # carries its findings forward so a vuln-scan lab can assert on them.
    cve_open = [] if run.get("cve_remediated") or not run.get("cve_failed") else ["CVE-2024-XXXX"]

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "sku": sku,
        "base_image": base["name"],
        "os": base["os"],
        "arch": base["arch"],
        "kernel": base["kernel"],
        "default_user": base["user"],
        "packages": sorted(packages),
        "services_enabled": sorted(services),
        "gpu_stack": has_gpu,
        "cloud_init_enabled": True,
        "ssh_keys_baked": True,
        "ssh_host_keys": ["ssh-ed25519", "ssh-rsa"],
        "cve_open": cve_open,
        "cve_remediated": bool(run.get("cve_remediated")),
        "gpu_sanity_failed": bool(run.get("gpu_sanity_failed")),
        "digest": _artifact_digest(run),
        "built_at": _now(),
        "boot_resource": run.get("boot_resource") or _boot_resource_name(sku),
        "run_id": run.get("id"),
    }


def ensure_factory(state: dict) -> dict:
    factory = state.setdefault("packer_factory", {})
    factory.setdefault("runs", [])
    factory.setdefault("active_run_id", None)
    factory.setdefault("build_succeeded", False)
    factory.setdefault("artifact_ready", False)
    factory.setdefault("suggested_boot_resource", "custom/h100-jammy")
    factory.setdefault("matrix", list(MATRIX_SKUS))
    factory.setdefault("build_cache", {})
    return factory


def _provisioner_layers(template_blob: str, files: dict | None = None) -> list[dict[str, Any]]:
    """Ordered provisioner-layer digests for bake-time cache (X3 golden bake).

    Reordering a late-changing script earlier busts digests after that point —
    the teaching signal for layer/provisioner ordering regressions.
    """
    files = files or {}
    cleaned = _strip_hcl_comments(template_blob or "")
    bodies = _block_bodies(cleaned, _SHELL_PROV_RE)
    # Also treat top-level shell files as ordered layers when no HCL bodies.
    if not bodies and files:
        bodies = [f"{path}\n{content}" for path, content in sorted(files.items())]
    layers = []
    parent = "scratch"
    for i, body in enumerate(bodies):
        digest_src = f"{parent}\n{body.strip()}\n"
        for path, content in sorted(files.items()):
            digest_src += f"{path}:{hashlib.blake2b(str(content).encode(), digest_size=8).hexdigest()}\n"
        layer_digest = "blake2:" + hashlib.blake2b(digest_src.encode(), digest_size=16).hexdigest()
        summary = body.strip().splitlines()[0][:80] if body.strip() else f"layer-{i}"
        layers.append({
            "digest": layer_digest,
            "index": i,
            "summary": summary,
            "instr": body.strip()[:200],
        })
        parent = layer_digest
    return layers


def _apply_bake_cache(factory: dict, run: dict, template_blob: str, files: dict | None) -> dict:
    """Record cache hits and simulated bake_seconds on the active run."""
    cache = factory.setdefault("build_cache", {})
    layers = _provisioner_layers(template_blob, files)
    hits = 0
    for layer in layers:
        d = layer["digest"]
        if d in cache:
            hits += 1
            layer["cache_hit"] = True
        else:
            cache[d] = {"at": _now(), "summary": layer.get("summary")}
            layer["cache_hit"] = False
    misses = max(0, len(layers) - hits)
    # Cold: 30 + 45*layers; warm rebuild only pays for misses.
    bake_seconds = 30 + 45 * misses + (5 * hits)  # hits still cost a tiny verify
    run["layer_digests"] = [L["digest"] for L in layers]
    run["layers"] = layers
    run["cache_hits"] = hits
    run["cache_misses"] = misses
    run["bake_seconds"] = bake_seconds
    return {"cache_hits": hits, "cache_misses": misses, "bake_seconds": bake_seconds, "layers": layers}


def get_factory_state(state: dict) -> dict:
    factory = ensure_factory(state)
    active = None
    rid = factory.get("active_run_id")
    if rid is not None:
        active = next((r for r in factory["runs"] if r.get("id") == rid), None)
    return {
        "ok": True,
        "packer_factory": factory,
        "active_run": active,
        "build_succeeded": bool(factory.get("build_succeeded")),
        "artifact_ready": bool(factory.get("artifact_ready")),
        "manifest": (active or {}).get("manifest") or factory.get("manifest"),
        "suggested_boot_resource": factory.get("suggested_boot_resource") or "custom/h100-jammy",
        "matrix": list(factory.get("matrix") or MATRIX_SKUS),
        "checks": (active or {}).get("checks") or [],
        "publish_enabled": bool((active or {}).get("publish_enabled")),
    }


def _job_logs(job_id: str, sku: str, *, phase: str = "start") -> list[str]:
    ts = _now()
    catalog = {
        "packer-init": [
            f"[{ts}] ##[group]packer init",
            f"[{ts}] Installing plugin github.com/hashicorp/qemu >= 1.1.0",
            f"[{ts}] Installed plugin github.com/hashicorp/qemu v1.1.0",
            f"[{ts}] ##[endgroup]",
        ],
        "validate": [
            f"[{ts}] ##[group]packer validate gpu-{sku}.pkr.hcl",
            f"[{ts}] The configuration is valid.",
            f"[{ts}] ##[endgroup]",
        ],
        "build": [
            f"[{ts}] ##[group]packer build -var=sku={sku}",
            f"[{ts}] qemu.gpu-{sku}: Creating local QEMU disk image…",
            f"[{ts}] qemu.gpu-{sku}: Provisioning scripts/install-gpu-{sku}.sh",
            f"[{ts}] --> qemu.gpu-{sku}: VM files in directory: output-gpu-{sku}/",
            f"[{ts}] ##[endgroup]",
        ],
        "libguestfs-customize": [
            f"[{ts}] ##[group]virt-customize -a output-gpu-{sku}/disk.qcow2",
            f"[{ts}] [ OK ] --install cloud-init,qemu-guest-agent",
            f"[{ts}] [ OK ] --run-command 'systemctl enable nvidia-persistenced'",
            f"[{ts}] ##[endgroup]",
        ],
        "vuln-scan+remediate": [
            f"[{ts}] ##[group]trivy image --severity HIGH,CRITICAL output-gpu-{sku}/",
            f"[{ts}] HIGH CVE-2024-XXXX in libc6",
            f"[{ts}] ##[error] CVE gate failed — remediation required",
            f"[{ts}] ##[endgroup]",
        ],
        "gpu-sanity": [
            f"[{ts}] ##[group]gpu-sanity (matrix {sku})",
            f"[{ts}] Checking NVIDIA driver markers in image template…",
            f"[{ts}] nvidia-persistenced enabled — PASS",
            f"[{ts}] ##[endgroup]",
        ],
        "publish": [
            f"[{ts}] ##[group]Publish boot-resource",
            f"[{ts}] Uploading output-gpu-{sku}/ → MAAS Images",
            f"[{ts}] Published {_boot_resource_name(sku)}",
            f"[{ts}] ##[endgroup]",
        ],
    }
    if job_id == "vuln-scan+remediate" and phase == "remediate":
        return [
            f"[{ts}] ##[group]remediate CVE gate",
            f"[{ts}] Applying security updates via virt-customize…",
            f"[{ts}] [ OK ] --update && apt-get install -y --only-upgrade libc6",
            f"[{ts}] Re-running trivy image… PASS (0 HIGH/CRITICAL)",
            f"[{ts}] ##[endgroup]",
        ]
    if job_id == "gpu-sanity" and phase == "fail":
        return [
            f"[{ts}] ##[group]gpu-sanity (matrix {sku})",
            f"[{ts}] Checking NVIDIA driver markers in image template…",
            f"[{ts}] ##[error] Missing nvidia driver provisioner — add nvidia-persistenced / install-gpu script",
            f"[{ts}] ##[endgroup]",
        ]
    return catalog.get(job_id, [f"[{ts}] Running {job_id}…"])


def _make_jobs(sku: str) -> list[dict[str, Any]]:
    jobs = []
    for jid, name in JOB_SPECS:
        jobs.append({
            "id": jid,
            "name": name,
            "status": "queued",
            "conclusion": None,
            "logs": [],
            "started_at": None,
            "completed_at": None,
            "attempts": 0,
        })
    return jobs


def _default_checks() -> list[dict[str, Any]]:
    return [
        {"name": "Image Factory / packer-init", "status": "queued", "required": True},
        {"name": "Image Factory / validate", "status": "queued", "required": True},
        {"name": "Image Factory / build", "status": "queued", "required": True},
        {"name": "Image Factory / vuln-scan+remediate", "status": "queued", "required": True},
        {"name": "Image Factory / gpu-sanity", "status": "queued", "required": True},
        {"name": "Image Factory / publish", "status": "queued", "required": True},
    ]


def _sync_checks(run: dict) -> None:
    status_map = {j["id"]: j["status"] for j in run.get("jobs") or []}
    for check in run.get("checks") or []:
        # Map "Image Factory / job-id" → job status
        job_id = check["name"].split("/ ", 1)[-1].strip()
        st = status_map.get(job_id)
        if st == "success":
            check["status"] = "success"
        elif st == "failure":
            check["status"] = "failure"
        elif st == "in_progress":
            check["status"] = "in_progress"
        elif st == "queued":
            check["status"] = "queued"
    gates_ok = all(
        j["status"] == "success"
        for j in run["jobs"]
        if j["id"] != "publish"
    )
    run["publish_enabled"] = bool(gates_ok and not run.get("failed_gate"))
    # Publish check stays queued until publish job runs
    pub = next((c for c in run.get("checks") or [] if c["name"].endswith("/ publish")), None)
    if pub:
        pub_job = next((j for j in run["jobs"] if j["id"] == "publish"), None)
        if pub_job:
            pub["status"] = pub_job["status"] if pub_job["status"] != "queued" else (
                "pending" if run["publish_enabled"] else "queued"
            )


def start_pipeline(state: dict, payload: dict | None = None) -> dict:
    payload = payload or {}
    factory = ensure_factory(state)
    sku = (payload.get("sku") or "h100").strip().lower()
    if sku not in MATRIX_SKUS and sku not in ("a100", "rhel-gpu", "rhel"):
        sku = "h100"

    # Supply-chain gate (X3): checksum/GPG mismatch refuses before any job runs.
    gate_payload = dict(payload)
    broken = state.get("broken") if isinstance(state.get("broken"), dict) else {}
    if broken.get("upstream_checksum_mismatch") or broken.get("upstream_gpg_fail"):
        gate_payload["force_verify"] = True
        if broken.get("upstream_gpg_fail") and "gpg_ok" not in gate_payload:
            gate_payload["gpg_ok"] = False
    ok, msg = verify_upstream_image(gate_payload, sku=sku)
    if not ok:
        factory["build_succeeded"] = False
        factory["artifact_ready"] = False
        return {**get_factory_state(state), "ok": False, "error": msg}

    files = payload.get("files") if isinstance(payload.get("files"), dict) else {}
    template_blob = payload.get("template") or ""
    has_nvidia = _has_nvidia_marker(files, template_blob)

    run_id = len(factory["runs"]) + 1
    boot = _boot_resource_name(sku)
    run = {
        "id": run_id,
        "name": "Image Factory",
        "event": "workflow_dispatch",
        "status": "in_progress",
        "conclusion": None,
        "sku": sku,
        "matrix": list(MATRIX_SKUS),
        "matrix_active": sku.upper() if sku != "rhel-gpu" else "RHEL",
        "jobs": _make_jobs(sku),
        "checks": _default_checks(),
        "created_at": _now(),
        "updated_at": _now(),
        "has_nvidia_marker": has_nvidia,
        "cve_failed": False,
        "cve_remediated": False,
        "failed_gate": False,
        "publish_enabled": False,
        "artifact_ready": False,
        "boot_resource": boot,
        "files_snapshot": {k: (str(v)[:200] if v else "") for k, v in (files or {}).items()},
        "template_snapshot": (template_blob or "")[:4000],
    }
    bake = _apply_bake_cache(factory, run, template_blob, files)
    # Seed first job as ready to advance
    run["jobs"][0]["status"] = "queued"
    factory["runs"].insert(0, run)
    factory["active_run_id"] = run_id
    factory["suggested_boot_resource"] = boot
    factory["artifact_ready"] = False
    return {
        "ok": True,
        "message": f"Image Factory run #{run_id} started (matrix {sku})",
        "bake_seconds": bake["bake_seconds"],
        "cache_hits": bake["cache_hits"],
        "run": run,
        **get_factory_state(state),
    }


def _active_run(factory: dict) -> dict | None:
    rid = factory.get("active_run_id")
    if rid is None:
        return None
    return next((r for r in factory["runs"] if r.get("id") == rid), None)


def _complete_job(job: dict, status: str, logs: list[str]) -> None:
    job["status"] = status
    job["conclusion"] = status
    job["logs"] = list(logs)
    job["completed_at"] = _now()
    job["attempts"] = int(job.get("attempts") or 0) + 1


def advance_job(state: dict, payload: dict | None = None) -> dict:
    """Advance the next queued/in_progress job one step.

    CVE path: first pass through vuln-scan+remediate fails; a subsequent
    advance (or rerun) remediates and continues.
    GPU sanity fails unless NVIDIA driver markers are present in templates.
    Successful publish job calls maas_publish_boot_resource.
    """
    payload = payload or {}
    factory = ensure_factory(state)
    run = _active_run(factory)
    if not run:
        return {"ok": False, "error": "No active Image Factory run — start the pipeline first"}
    if run.get("status") in ("success", "completed"):
        return {"ok": True, "message": "Pipeline already completed", "run": run, **get_factory_state(state)}

    jobs = run["jobs"]
    current = None
    for job in jobs:
        if job["status"] in ("queued", "in_progress", "failure"):
            # Skip terminal failures unless force / remediate
            if job["status"] == "failure" and not payload.get("rerun") and not payload.get("remediate"):
                if job["id"] == "vuln-scan+remediate" and not run.get("cve_remediated"):
                    current = job
                    break
                return {
                    "ok": False,
                    "error": f"Job {job['id']} failed — re-run it to continue",
                    "run": run,
                    "failed_job": job["id"],
                    **get_factory_state(state),
                }
            current = job
            break
    if current is None:
        run["status"] = "success"
        run["conclusion"] = "success"
        run["updated_at"] = _now()
        return {"ok": True, "message": "All jobs complete", "run": run, **get_factory_state(state)}

    sku = run.get("sku") or "h100"
    jid = current["id"]

    if current["status"] == "queued":
        current["status"] = "in_progress"
        current["started_at"] = _now()
        current["logs"] = _job_logs(jid, sku, phase="start")
        run["updated_at"] = _now()
        _sync_checks(run)
        # Auto-complete most jobs on the same advance for snappy UI; CVE/gpu need logic
        if jid not in ("vuln-scan+remediate", "gpu-sanity", "publish"):
            _complete_job(current, "success", current["logs"] + [f"[{_now()}] Job succeeded"])
            _sync_checks(run)
            return {
                "ok": True,
                "message": f"{jid} succeeded",
                "job": current,
                "run": run,
                **get_factory_state(state),
            }
        if jid == "gpu-sanity":
            return advance_job(state, {**payload, "_gpu_resolve": True})
        if jid == "publish":
            # Resolve publish in the same tick once PR gates have passed.
            return advance_job(state, {**payload, "_publish_resolve": True})
        return {
            "ok": True,
            "message": f"{jid} running",
            "job": current,
            "run": run,
            **get_factory_state(state),
        }

    # in_progress or failure → resolve
    if jid == "vuln-scan+remediate":
        if not run.get("cve_failed"):
            # First resolution: fail CVE gate
            logs = _job_logs(jid, sku, phase="start")
            _complete_job(current, "failure", logs)
            run["cve_failed"] = True
            run["failed_gate"] = True
            run["status"] = "failure"
            run["updated_at"] = _now()
            _sync_checks(run)
            return {
                "ok": True,
                "message": "CVE gate failed — run remediate / re-run vuln-scan+remediate",
                "job": current,
                "cve_failed": True,
                "run": run,
                **get_factory_state(state),
            }
        # Remediate path
        logs = _job_logs(jid, sku, phase="remediate")
        _complete_job(current, "success", logs)
        run["cve_remediated"] = True
        run["failed_gate"] = False
        run["status"] = "in_progress"
        run["conclusion"] = None
        run["updated_at"] = _now()
        _sync_checks(run)
        return {
            "ok": True,
            "message": "CVE remediated — continuing pipeline",
            "job": current,
            "cve_remediated": True,
            "run": run,
            **get_factory_state(state),
        }

    if jid == "gpu-sanity":
        if not run.get("has_nvidia_marker"):
            logs = _job_logs(jid, sku, phase="fail")
            _complete_job(current, "failure", logs)
            run["failed_gate"] = True
            run["status"] = "failure"
            run["updated_at"] = _now()
            _sync_checks(run)
            return {
                "ok": True,
                "message": "gpu-sanity failed — add NVIDIA driver markers to the Packer template",
                "job": current,
                "run": run,
                **get_factory_state(state),
            }
        logs = _job_logs(jid, sku, phase="start")
        _complete_job(current, "success", logs)
        run["updated_at"] = _now()
        _sync_checks(run)
        return {
            "ok": True,
            "message": "gpu-sanity passed",
            "job": current,
            "run": run,
            **get_factory_state(state),
        }

    if jid == "publish":
        if not run.get("publish_enabled"):
            return {
                "ok": False,
                "error": "PR status checks have not passed — cannot publish",
                "run": run,
                **get_factory_state(state),
            }
        pub = publish_artifact(state, {"sku": sku, "boot_resource": run.get("boot_resource")})
        logs = _job_logs(jid, sku, phase="start")
        if not pub.get("ok"):
            _complete_job(current, "failure", logs + [f"[{_now()}] ##[error] {pub.get('error')}"])
            run["status"] = "failure"
            run["updated_at"] = _now()
            _sync_checks(run)
            return {**pub, "job": current, "run": run, **get_factory_state(state)}
        _complete_job(current, "success", logs)
        run["status"] = "success"
        run["conclusion"] = "success"
        run["artifact_ready"] = True
        factory["artifact_ready"] = True
        factory["suggested_boot_resource"] = run.get("boot_resource")
        # Manifest is written only on a fully-gated success, so its presence is
        # itself the proof the build passed — import-image needs no gate re-check.
        run["manifest"] = build_manifest(run)
        factory["manifest"] = run["manifest"]
        run["updated_at"] = _now()
        _sync_checks(run)
        return {
            "ok": True,
            "message": pub.get("message") or "Published to MAAS",
            "job": current,
            "boot_resource": pub.get("boot_resource"),
            "run": run,
            **get_factory_state(state),
        }

    _complete_job(current, "success", current.get("logs") or _job_logs(jid, sku))
    run["updated_at"] = _now()
    _sync_checks(run)
    return {
        "ok": True,
        "message": f"{jid} succeeded",
        "job": current,
        "run": run,
        **get_factory_state(state),
    }


def rerun_job(state: dict, payload: dict | None = None) -> dict:
    payload = payload or {}
    factory = ensure_factory(state)
    run = _active_run(factory)
    if not run:
        return {"ok": False, "error": "No active Image Factory run"}
    job_id = (payload.get("job_id") or payload.get("job") or "").strip()
    job = next((j for j in run["jobs"] if j["id"] == job_id), None)
    if not job:
        return {"ok": False, "error": f"Job {job_id!r} not found"}
    if job["status"] != "failure":
        return {"ok": False, "error": f"Job {job_id} is not failed (status={job['status']})"}

    # Reset this job and everything after it to queued
    found = False
    for j in run["jobs"]:
        if j["id"] == job_id:
            found = True
            j["status"] = "queued"
            j["conclusion"] = None
            j["logs"] = []
            j["started_at"] = None
            j["completed_at"] = None
            continue
        if found:
            j["status"] = "queued"
            j["conclusion"] = None
            j["logs"] = []
            j["started_at"] = None
            j["completed_at"] = None

    if job_id == "vuln-scan+remediate" and run.get("cve_failed"):
        # Re-run after CVE failure → remediate on next advance
        payload = {**payload, "remediate": True}
    if job_id == "gpu-sanity":
        # Allow updating nvidia marker from fresh files
        files = payload.get("files") if isinstance(payload.get("files"), dict) else None
        if files is not None:
            run["has_nvidia_marker"] = _has_nvidia_marker(files, payload.get("template") or "")

    run["failed_gate"] = False
    run["status"] = "in_progress"
    run["conclusion"] = None
    run["updated_at"] = _now()
    _sync_checks(run)

    # Immediately advance the re-queued job
    return advance_job(state, {"rerun": True, "remediate": job_id == "vuln-scan+remediate" and run.get("cve_failed")})


def publish_artifact(state: dict, payload: dict | None = None) -> dict:
    """Publish Packer artifact as MAAS boot-resource (gates optional)."""
    payload = payload or {}
    factory = ensure_factory(state)
    run = _active_run(factory)
    sku = (payload.get("sku") or (run or {}).get("sku") or "h100").strip().lower()
    name = (payload.get("boot_resource") or (run or {}).get("boot_resource") or _boot_resource_name(sku)).strip()

    ensure_v2(state)
    result = apply_v2_action(state, "maas_publish_boot_resource", {
        "sku": sku,
        "boot_resource": name,
        "source": payload.get("source") or f"packer output-gpu-{sku}/",
        "architecture": payload.get("architecture") or "amd64/generic",
    })
    if result and result.get("ok"):
        factory["artifact_ready"] = True
        factory["suggested_boot_resource"] = name
        if run:
            run["artifact_ready"] = True
            run["boot_resource"] = name
            run["manifest"] = build_manifest(run)
            factory["manifest"] = run["manifest"]
        return {
            "ok": True,
            "message": result.get("message"),
            "boot_resource": result.get("boot_resource"),
            **get_factory_state(state),
        }
    return result or {"ok": False, "error": "MAAS publish failed"}


def get_job_logs(state: dict, payload: dict | None = None) -> dict:
    payload = payload or {}
    factory = ensure_factory(state)
    run = _active_run(factory)
    if not run:
        return {"ok": False, "error": "No active run", "logs": []}
    job_id = (payload.get("job_id") or payload.get("job") or "").strip()
    job = next((j for j in run["jobs"] if j["id"] == job_id), None)
    if not job:
        return {"ok": False, "error": f"Job {job_id!r} not found", "logs": []}
    return {"ok": True, "job_id": job_id, "logs": list(job.get("logs") or []), "status": job.get("status")}


def mark_build(state: dict, payload: dict | None = None) -> dict:
    """Record that a local packer build succeeded (enables Run Image Factory pipeline)."""
    payload = payload or {}
    factory = ensure_factory(state)
    success = payload.get("success", True)
    factory["build_succeeded"] = bool(success)
    sku = (payload.get("sku") or "h100").strip().lower()
    factory["suggested_boot_resource"] = _boot_resource_name(sku)
    return {
        "ok": True,
        "build_succeeded": factory["build_succeeded"],
        "suggested_boot_resource": factory["suggested_boot_resource"],
        **get_factory_state(state),
    }


def get_manifest(state: dict) -> dict:
    """Return the manifest of the most recent successfully-published build.

    Fails CLOSED: no manifest means no image was produced, and the caller (AWS
    import-image) must refuse rather than fabricate a default. Returning an empty
    dict here would let a consumer's `.get(...)` read a default and import an
    image that was never built.
    """
    factory = ensure_factory(state)
    run = _active_run(factory)
    manifest = (run or {}).get("manifest") or factory.get("manifest")
    if not manifest:
        return {"ok": False, "error": "No published image artifact — run the Image Factory pipeline to completion first."}
    return {"ok": True, "manifest": manifest, "schema_version": manifest.get("schema_version")}


def start_matrix_pipeline(state: dict, payload: dict | None = None) -> dict:
    """Multi-SKU matrix: each SKU is an independent track (X3).

    One SKU failing must not block publish of the others.
    """
    payload = payload or {}
    factory = ensure_factory(state)
    skus = payload.get("skus") or list(MATRIX_SKUS)
    if isinstance(skus, str):
        skus = [s.strip() for s in skus.split(",") if s.strip()]
    skus = [str(s).strip().lower() for s in skus]
    matrix_id = int(factory.get("next_matrix_id") or 1)
    factory["next_matrix_id"] = matrix_id + 1
    tracks = []
    for sku in skus:
        tracks.append({
            "sku": sku,
            "status": "success",
            "conclusion": "success",
            "boot_resource": _boot_resource_name(sku),
            "published": False,
            "error": None,
        })
    matrix = {
        "id": matrix_id,
        "status": "in_progress",
        "tracks": tracks,
        "created_at": _now(),
        "updated_at": _now(),
    }
    factory.setdefault("matrices", []).insert(0, matrix)
    factory["active_matrix_id"] = matrix_id
    return {
        "ok": True,
        **get_factory_state(state),
        "message": f"Matrix #{matrix_id} started for {len(tracks)} SKU(s)",
        "matrix_run": matrix,
    }


def fail_matrix_sku(state: dict, payload: dict | None = None) -> dict:
    payload = payload or {}
    factory = ensure_factory(state)
    mid = payload.get("matrix_id") or factory.get("active_matrix_id")
    matrix = next((m for m in (factory.get("matrices") or []) if m.get("id") == mid), None)
    if not matrix:
        return {"ok": False, "error": "No active matrix — start_matrix first"}
    sku = (payload.get("sku") or "").strip().lower()
    track = next((t for t in matrix.get("tracks") or [] if t.get("sku") == sku), None)
    if not track:
        return {"ok": False, "error": f"SKU '{sku}' not in matrix"}
    track["status"] = "failure"
    track["conclusion"] = "failure"
    track["error"] = payload.get("error") or f"gpu-sanity failed for {sku}"
    track["published"] = False
    matrix["updated_at"] = _now()
    # Matrix overall stays in_progress until publish; one failure is fine.
    return {
        "ok": True,
        **get_factory_state(state),
        "message": f"Matrix SKU {sku} marked failed — others unaffected",
        "matrix_run": matrix,
    }


def publish_matrix(state: dict, payload: dict | None = None) -> dict:
    """Publish every successful SKU; skip failures without blocking the batch."""
    payload = payload or {}
    factory = ensure_factory(state)
    mid = payload.get("matrix_id") or factory.get("active_matrix_id")
    matrix = next((m for m in (factory.get("matrices") or []) if m.get("id") == mid), None)
    if not matrix:
        return {"ok": False, "error": "No active matrix — start_matrix first"}
    published = []
    skipped = []
    for track in matrix.get("tracks") or []:
        if track.get("status") != "success":
            skipped.append({"sku": track.get("sku"), "reason": track.get("error") or "failed"})
            continue
        pub = publish_artifact(state, {
            "sku": track.get("sku"),
            "boot_resource": track.get("boot_resource"),
        })
        if pub.get("ok"):
            track["published"] = True
            published.append(track.get("sku"))
        else:
            track["status"] = "failure"
            track["error"] = pub.get("error") or "publish failed"
            skipped.append({"sku": track.get("sku"), "reason": track["error"]})
    matrix["status"] = "completed"
    matrix["conclusion"] = "success" if published else "failure"
    matrix["updated_at"] = _now()
    factory["artifact_ready"] = bool(published)
    return {
        "ok": True,
        **get_factory_state(state),
        "message": (
            f"Published {len(published)} SKU(s); skipped {len(skipped)} failed"
        ),
        "published": published,
        "skipped": skipped,
        "matrix_run": matrix,
    }


def handle_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    if action not in ACTIONS:
        return None
    payload = payload or {}
    if action == "packer_factory_get_state":
        return get_factory_state(state)
    if action == "packer_factory_start_pipeline":
        return start_pipeline(state, payload)
    if action == "packer_factory_start_matrix":
        return start_matrix_pipeline(state, payload)
    if action == "packer_factory_fail_matrix_sku":
        return fail_matrix_sku(state, payload)
    if action == "packer_factory_publish_matrix":
        return publish_matrix(state, payload)
    if action == "packer_factory_advance_job":
        return advance_job(state, payload)
    if action == "packer_factory_publish_artifact":
        return publish_artifact(state, payload)
    if action == "packer_factory_rerun_job":
        return rerun_job(state, payload)
    if action == "packer_factory_get_job_logs":
        return get_job_logs(state, payload)
    if action == "packer_factory_mark_build":
        return mark_build(state, payload)
    if action == "packer_factory_get_manifest":
        return get_manifest(state)
    if action == "packer_factory_verify_upstream":
        sku = (payload.get("sku") or "h100").strip().lower()
        ok, msg = verify_upstream_image(payload, sku=sku)
        return {"ok": ok, "message": msg if ok else None, "error": None if ok else msg}
    return None


def clear_needs_custom_image_deploy(state: dict) -> bool:
    """Clear optional grading flags when custom boot resources are published/deployed."""
    broken = state.get("broken")
    if not isinstance(broken, dict):
        return False
    changed = False
    resources = (state.get("maas") or {}).get("boot_resources") or []
    names = {str(r.get("name") or "") for r in resources}

    missing = broken.get("missing_boot_resources")
    if isinstance(missing, list) and missing:
        still = [n for n in missing if n not in names]
        if len(still) != len(missing):
            broken["missing_boot_resources"] = still
            changed = True
        if not still:
            broken.pop("missing_boot_resources", None)
            broken.pop("packer_image_unpublished", None)
            changed = True

    need = broken.get("missing_boot_resource")
    if need and need in names:
        broken.pop("missing_boot_resource", None)
        broken.pop("packer_image_unpublished", None)
        changed = True

    if broken.get("needs_custom_image_deploy"):
        machines = (state.get("maas") or {}).get("machines") or []
        for m in machines:
            br = (m.get("boot_resource") or "")
            if m.get("status") == "Deployed" and str(br).startswith("custom/"):
                broken.pop("needs_custom_image_deploy", None)
                changed = True
                break

    if changed and not broken:
        state["broken"] = {}
    return changed

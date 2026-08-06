"""Packer Image Factory — lightweight CI pipeline state for baremetal sessions.

Learner language: Lab Environment / Image Factory — never Simulation/Sandbox/Mock.
Pipeline mirrors GitHub Actions–style Image Factory workflow runs.
"""

from __future__ import annotations

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
    "packer_factory_advance_job",
    "packer_factory_publish_artifact",
    "packer_factory_rerun_job",
    "packer_factory_get_job_logs",
    "packer_factory_mark_build",
})


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


def ensure_factory(state: dict) -> dict:
    factory = state.setdefault("packer_factory", {})
    factory.setdefault("runs", [])
    factory.setdefault("active_run_id", None)
    factory.setdefault("build_succeeded", False)
    factory.setdefault("artifact_ready", False)
    factory.setdefault("suggested_boot_resource", "custom/h100-jammy")
    factory.setdefault("matrix", list(MATRIX_SKUS))
    return factory


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
    }
    # Seed first job as ready to advance
    run["jobs"][0]["status"] = "queued"
    factory["runs"].insert(0, run)
    factory["active_run_id"] = run_id
    factory["suggested_boot_resource"] = boot
    factory["artifact_ready"] = False
    return {
        "ok": True,
        "message": f"Image Factory run #{run_id} started (matrix {sku})",
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


def handle_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    if action not in ACTIONS:
        return None
    payload = payload or {}
    if action == "packer_factory_get_state":
        return get_factory_state(state)
    if action == "packer_factory_start_pipeline":
        return start_pipeline(state, payload)
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

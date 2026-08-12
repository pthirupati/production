"""Vault sealed-outage lab primitives — unseal → restore → short-lived DB creds.

Training surface only (in-process). Not the production Vault daemon (L3708).
"""

from __future__ import annotations

import secrets
import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_vault_lab(state: dict) -> dict:
    v = state.setdefault("vault_lab", {})
    v.setdefault("sealed", True)
    v.setdefault("threshold", 3)
    v.setdefault(
        "unseal_keys",
        ["share-alpha", "share-bravo", "share-charlie", "share-delta", "share-echo"],
    )
    v.setdefault("keys_presented", [])
    v.setdefault("auth_method", None)  # "token" | "approle"
    v.setdefault("token", None)
    v.setdefault("approle", {"role_id": "lab-role", "secret_id": "lab-secret"})
    v.setdefault("service_up", False)
    v.setdefault("db_static_password", "s3cret-static")  # anti-pattern baseline
    v.setdefault("leases", [])
    return v


def vault_status(state: dict) -> dict:
    v = ensure_vault_lab(state)
    return {
        "ok": True,
        "sealed": bool(v["sealed"]),
        "service_up": bool(v["service_up"]),
        "threshold": int(v["threshold"]),
        "keys_progress": f"{len(v.get('keys_presented') or [])}/{v['threshold']}",
        "auth_method": v.get("auth_method"),
        "lease_count": len(v.get("leases") or []),
    }


def present_unseal_key(state: dict, key: str) -> dict:
    v = ensure_vault_lab(state)
    if not v["sealed"]:
        return {"ok": False, "error": "Vault already unsealed", "status": vault_status(state)}
    key = (key or "").strip()
    if key not in (v.get("unseal_keys") or []):
        return {"ok": False, "error": "Invalid unseal key", "status": vault_status(state)}
    presented = v.setdefault("keys_presented", [])
    if key in presented:
        return {"ok": False, "error": "Key already presented", "status": vault_status(state)}
    presented.append(key)
    if len(presented) >= int(v["threshold"]):
        v["sealed"] = False
        v["service_up"] = True
        v["keys_presented"] = []
        return {"ok": True, "unsealed": True, "message": "Vault unsealed — service restored", "status": vault_status(state)}
    return {
        "ok": True,
        "unsealed": False,
        "message": f"Progress {len(presented)}/{v['threshold']}",
        "status": vault_status(state),
    }


def seal_vault(state: dict) -> dict:
    v = ensure_vault_lab(state)
    v["sealed"] = True
    v["service_up"] = False
    v["keys_presented"] = []
    v["token"] = None
    v["auth_method"] = None
    # Revoke dynamic leases on seal
    for lease in v.get("leases") or []:
        lease["revoked"] = True
    return {"ok": True, "status": vault_status(state)}


def auth_vault(state: dict, *, method: str, token: str | None = None, role_id: str | None = None, secret_id: str | None = None) -> dict:
    v = ensure_vault_lab(state)
    if v["sealed"]:
        return {"ok": False, "error": "Vault is sealed", "status": vault_status(state)}
    method = (method or "").strip().lower()
    if method == "token":
        tok = (token or "").strip() or f"hvs.{secrets.token_hex(8)}"
        v["auth_method"] = "token"
        v["token"] = tok
        return {"ok": True, "auth_method": "token", "token": tok, "status": vault_status(state)}
    if method == "approle":
        ap = v.get("approle") or {}
        if role_id != ap.get("role_id") or secret_id != ap.get("secret_id"):
            return {"ok": False, "error": "Invalid AppRole credentials", "status": vault_status(state)}
        tok = f"s.{secrets.token_hex(8)}"
        v["auth_method"] = "approle"
        v["token"] = tok
        return {"ok": True, "auth_method": "approle", "token": tok, "status": vault_status(state)}
    return {"ok": False, "error": "method must be token or approle", "status": vault_status(state)}


def issue_db_credentials(state: dict, *, ttl_seconds: int = 60) -> dict:
    """Issue short-lived dynamic DB creds (preferred over static password)."""
    v = ensure_vault_lab(state)
    if v["sealed"] or not v["service_up"]:
        return {"ok": False, "error": "Vault sealed or service down — cannot issue credentials"}
    if not v.get("token"):
        return {"ok": False, "error": "Authenticate first (token or AppRole)"}
    ttl = max(15, min(int(ttl_seconds), 3600))
    lease_id = f"database/creds/app/{secrets.token_hex(4)}"
    username = f"v-app-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(16)
    lease = {
        "id": lease_id,
        "username": username,
        "password": password,
        "ttl_seconds": ttl,
        "issued_at": _now(),
        "expires_at_epoch": time.time() + ttl,
        "revoked": False,
        "renewed": 0,
    }
    v.setdefault("leases", []).insert(0, lease)
    return {
        "ok": True,
        "lease": {k: lease[k] for k in ("id", "username", "password", "ttl_seconds", "issued_at")},
        "hint": "Prefer these over vault_lab.db_static_password",
        "status": vault_status(state),
    }


def renew_lease(state: dict, lease_id: str, *, extend_seconds: int = 60) -> dict:
    v = ensure_vault_lab(state)
    lease = next((L for L in (v.get("leases") or []) if L.get("id") == lease_id), None)
    if not lease:
        return {"ok": False, "error": f"Lease {lease_id} not found"}
    if lease.get("revoked"):
        return {"ok": False, "error": "Lease revoked"}
    if v["sealed"]:
        return {"ok": False, "error": "Vault sealed"}
    extend = max(15, min(int(extend_seconds), 3600))
    lease["expires_at_epoch"] = max(float(lease.get("expires_at_epoch") or time.time()), time.time()) + extend
    lease["ttl_seconds"] = int(lease["expires_at_epoch"] - time.time())
    lease["renewed"] = int(lease.get("renewed") or 0) + 1
    return {"ok": True, "lease_id": lease_id, "ttl_seconds": lease["ttl_seconds"], "renewed": lease["renewed"]}


def revoke_lease(state: dict, lease_id: str) -> dict:
    v = ensure_vault_lab(state)
    lease = next((L for L in (v.get("leases") or []) if L.get("id") == lease_id), None)
    if not lease:
        return {"ok": False, "error": f"Lease {lease_id} not found"}
    lease["revoked"] = True
    lease["password"] = None
    return {"ok": True, "lease_id": lease_id, "revoked": True}


def grade_vault_restore(state: dict) -> dict:
    """Pass when unsealed, service up, authenticated, and a non-revoked dynamic lease exists."""
    v = ensure_vault_lab(state)
    reasons = []
    if v["sealed"]:
        reasons.append("still sealed")
    if not v["service_up"]:
        reasons.append("service down")
    if not v.get("auth_method"):
        reasons.append("not authenticated")
    live = [L for L in (v.get("leases") or []) if not L.get("revoked") and float(L.get("expires_at_epoch") or 0) > time.time()]
    if not live:
        reasons.append("no live dynamic DB lease")
    return {"ok": not reasons, "passed": not reasons, "reasons": reasons, "status": vault_status(state)}

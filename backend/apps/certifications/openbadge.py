"""Open Badge 3.0 (W3C Verifiable Credential) issuer + verifier.

Mints a spec-shaped OB 3.0 JSON-LD credential from an EARNED certification
(``CertEarnedCertificate``, which is only created after objective mock-exam
grading), Ed25519-signs it, and can re-verify it offline. No network, no paid
API — signing/verification use ``cryptography`` (already a dependency).

Key sourcing (offline & self-consistent):
  * ``settings.OPENBADGE_SIGNING_KEY_B64`` — base64 of the raw 32-byte Ed25519
    private seed. Set this in PRODUCTION so every node signs with the same key
    and previously-issued credentials keep verifying across redeploys/hosts.
  * Fallback (dev / self-hosted): lazily generate a keypair and persist the
    private seed to ``MEDIA_ROOT/openbadge_signing_key.json`` (mode 0600). This
    keeps issuing + verifying consistent on a single host with no config, but
    is host-local — hence the production note above.

The private key is NEVER stored on the credential row or returned by any API.
The credential embeds an ``eddsa`` proof as a detached JWS plus the base64
public key, so any verifier (this endpoint, a wallet, a third party) can check
the signature without contacting us.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# W3C VC v2 + Open Badges 3.0 JSON-LD contexts (referenced by URI only; we do
# not fetch them, keeping issuance fully offline).
OB3_CONTEXT = [
    "https://www.w3.org/ns/credentials/v2",
    "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
]

_KEY_FILENAME = "openbadge_signing_key.json"


# ─── base64url (no padding) helpers for detached-JWS proofs ───────────────
def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


# ─── key material ─────────────────────────────────────────────────────────
def _key_path() -> Path:
    return Path(settings.MEDIA_ROOT) / _KEY_FILENAME


def _load_private_from_settings() -> Ed25519PrivateKey | None:
    raw_b64 = (getattr(settings, "OPENBADGE_SIGNING_KEY_B64", "") or "").strip()
    if not raw_b64:
        return None
    try:
        seed = base64.b64decode(raw_b64)
        return Ed25519PrivateKey.from_private_bytes(seed)
    except Exception:
        logger.exception(
            "OPENBADGE_SIGNING_KEY_B64 is set but invalid; falling back to the "
            "persisted dev key. Fix the secret for stable production signing."
        )
        return None


def _load_or_create_persisted_private() -> Ed25519PrivateKey:
    """Load the host-local dev keypair, generating+persisting it on first use."""
    path = _key_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            seed = base64.b64decode(data["private_key_b64"])
            return Ed25519PrivateKey.from_private_bytes(seed)
        except Exception:
            logger.exception("Persisted OB3 signing key unreadable; regenerating")

    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes_raw()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"private_key_b64": base64.b64encode(seed).decode()}))
        os.chmod(path, 0o600)
    except Exception:
        # If we cannot persist (read-only FS), we still return a usable key for
        # this process; a subsequent process would mint under a different key.
        # Setting OPENBADGE_SIGNING_KEY_B64 avoids this entirely in production.
        logger.warning("Could not persist OB3 signing key to %s", path)
    return key


def _signing_key() -> Ed25519PrivateKey:
    return _load_private_from_settings() or _load_or_create_persisted_private()


def public_key_b64_for(private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(private_key.public_key().public_bytes_raw()).decode("ascii")


# ─── recipient hashing (never store cleartext email on the badge) ─────────
def recipient_identity_hash(email: str) -> str:
    """OB-style ``sha256$<hex>`` salted identity hash for the recipient email."""
    email = (email or "").strip().lower()
    salt = getattr(settings, "SECRET_KEY", "") or ""
    digest = hashlib.sha256((salt + email).encode("utf-8")).hexdigest()
    return f"sha256${digest}"


# ─── credential construction ──────────────────────────────────────────────
def build_credential_dict(*, credential_id, issuer_url, issuer_name, issued_on,
                          expires_on, recipient_identity, achievement_id,
                          achievement_name, achievement_description, criteria_narrative,
                          skills, evidence):
    """Return an unsigned OB 3.0 / VC credential dict (proof added by ``sign``)."""
    subject = {
        "type": ["AchievementSubject"],
        # Pseudonymous, hashed recipient identity (no cleartext email).
        "identifier": [
            {
                "type": "IdentityObject",
                "identityType": "emailAddress",
                "hashed": True,
                "identityHash": recipient_identity,
            }
        ],
        "achievement": {
            "id": achievement_id,
            "type": ["Achievement"],
            "name": achievement_name,
            "description": achievement_description,
            "criteria": {"narrative": criteria_narrative},
            "tag": list(skills),
        },
    }
    if skills:
        subject["achievement"]["skills"] = [
            {"type": ["Skill"], "name": s} for s in skills
        ]

    cred = {
        "@context": OB3_CONTEXT,
        "id": credential_id,
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "name": achievement_name,
        "issuer": {
            "id": issuer_url,
            "type": ["Profile"],
            "name": issuer_name,
        },
        "validFrom": _iso(issued_on),
        "credentialSubject": subject,
        "evidence": evidence,
    }
    if expires_on:
        cred["validUntil"] = _iso(expires_on)
    return cred


def _iso(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# ─── detached-JWS EdDSA proof ─────────────────────────────────────────────
def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signing_input(credential_without_proof: dict, protected_header_b64: str) -> bytes:
    payload_b64 = _b64url(_canonical(credential_without_proof))
    return f"{protected_header_b64}.{payload_b64}".encode("ascii")


def sign(credential: dict, private_key: Ed25519PrivateKey) -> dict:
    """Attach an ``eddsa`` proof (detached JWS) to a copy of ``credential``."""
    cred = json.loads(json.dumps(credential))  # deep copy, drop any prior proof
    cred.pop("proof", None)

    protected = {"alg": "EdDSA", "b64": False, "crit": ["b64"]}
    protected_b64 = _b64url(_canonical(protected))
    signature = private_key.sign(_signing_input(cred, protected_b64))
    # Detached JWS: header..signature (payload omitted, recomputed on verify).
    jws = f"{protected_b64}..{_b64url(signature)}"

    cred["proof"] = {
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "created": _iso(timezone.now()),
        "proofPurpose": "assertionMethod",
        "jws": jws,
        "publicKeyBase64": public_key_b64_for(private_key),
    }
    return cred


def verify(credential: dict, public_key_b64: str | None = None) -> bool:
    """Re-check a credential's Ed25519 proof. Offline, no network.

    Returns True only if the detached-JWS signature over the proof-stripped
    credential validates against ``public_key_b64`` (falling back to the key
    embedded in the proof). Any tampering with the credential body or proof
    yields False (never raises for a malformed credential).
    """
    try:
        proof = credential.get("proof") or {}
        jws = proof.get("jws") or ""
        pub_b64 = public_key_b64 or proof.get("publicKeyBase64")
        if not jws or not pub_b64:
            return False
        header_b64, _, sig_b64 = jws.split(".")
        if _ != "":  # detached JWS must have an empty payload segment
            return False

        cred = json.loads(json.dumps(credential))
        cred.pop("proof", None)

        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
        public_key.verify(_b64url_decode(sig_b64), _signing_input(cred, header_b64))
        return True
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return False
    except Exception:
        logger.exception("Unexpected error verifying OB3 credential")
        return False


# ─── high-level: mint from an earned certificate ──────────────────────────
def _achievement_context(track):
    """Derive skills/criteria for a track from its objectives (the cert track)."""
    objectives = list(track.objectives.all().order_by("order"))
    skills = [o.title for o in objectives if o.title]
    if objectives:
        criteria = (
            f"Awarded for passing the FixitLab {track.code} certification mock exam "
            f"(objective-graded, minimum {track.passing_score}% weighted score) "
            f"covering: " + ", ".join(skills) + "."
        )
    else:
        criteria = (
            f"Awarded for passing the FixitLab {track.code} certification mock exam "
            f"with at least {track.passing_score}%."
        )
    return skills, criteria


def issue_for_certificate(cert):
    """Mint (or refresh) and persist an ``OpenBadgeCredential`` for a cert.

    Idempotent per certificate (OneToOne). Safe to call from the award path;
    the caller wraps this so a signing failure never blocks earning the cert.
    """
    from .models import OpenBadgeCredential  # local import avoids app-load cycle

    track = cert.track
    private_key = _signing_key()
    pub_b64 = public_key_b64_for(private_key)

    existing = OpenBadgeCredential.objects.filter(certificate=cert).first()
    credential_uuid = existing.credential_uuid if existing else None
    ob = existing or OpenBadgeCredential(certificate=cert)
    if credential_uuid is None:
        credential_uuid = ob.credential_uuid  # default-generated on the instance

    frontend = getattr(settings, "FRONTEND_URL", "") or "https://fixitlab.local"
    issuer_url = frontend.rstrip("/")
    credential_id = f"urn:uuid:{credential_uuid}"
    achievement_id = f"{issuer_url}/api/certifications/verify/{credential_uuid}/"

    skills, criteria = _achievement_context(track)
    achievement_name = f"{track.name} ({track.code})"
    achievement_desc = (
        track.description
        or f"FixitLab {track.code} certification — objective hands-on lab mastery."
    )

    attempt = cert.attempt
    evidence = [
        {
            "id": achievement_id,
            "type": ["Evidence"],
            "name": f"{track.code} timed mock exam",
            "description": (
                f"Passed the FixitLab {track.code} mock exam with a weighted score "
                f"of {cert.score}% (passing {track.passing_score}%)."
            ),
            "narrative": (
                f"Solved hands-on troubleshooting scenarios across "
                f"{track.objectives.count()} exam objectives; objectively graded."
            ),
        }
    ]
    if attempt is not None:
        solved = [
            s.get("slug")
            for s in (attempt.results or {}).get("scenarios", [])
            if s.get("passed")
        ]
        evidence[0]["scenariosSolved"] = solved
        evidence[0]["examAttemptId"] = str(attempt.id)

    recipient_hash = recipient_identity_hash(getattr(cert.user, "email", "") or "")

    unsigned = build_credential_dict(
        credential_id=credential_id,
        issuer_url=issuer_url,
        issuer_name="FixitLab",
        issued_on=cert.issued_at,
        expires_on=cert.expires_at,
        recipient_identity=recipient_hash,
        achievement_id=achievement_id,
        achievement_name=achievement_name,
        achievement_description=achievement_desc,
        criteria_narrative=criteria,
        skills=skills,
        evidence=evidence,
    )
    signed = sign(unsigned, private_key)

    ob.credential_uuid = credential_uuid
    ob.recipient_hash = recipient_hash
    ob.achievement_name = achievement_name
    ob.achievement_description = achievement_desc
    ob.credential = signed
    ob.public_key_b64 = pub_b64
    ob.proof_value = signed["proof"]["jws"]
    ob.issued_on = cert.issued_at
    ob.save()
    return ob

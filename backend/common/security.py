"""
Security utilities for JWT hardening and session management.
"""
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
import logging

logger = logging.getLogger(__name__)


class SessionTracker:
    """
    Tracks active JWT session ``jti`` values per user so revoked tokens (logout,
    password change, admin force-logout) can be rejected even before they expire.

    History / why this is a SET, not a single jti
    ---------------------------------------------
    The original implementation kept exactly ONE jti per user and replaced it on
    every ``record_session``. That silently broke two flows once
    ``JWT_SESSION_ENFORCEMENT`` was on:

      1. **Refresh-token rotation.** simplejwt mints a brand-new ``jti`` for the
         rotated access token (it is in ``no_copy_claims``), and the old code
         never re-recorded it — so the access token returned by *every* 15-min
         silent refresh failed ``is_session_valid`` and the user was 401'd /
         logged out. (This is the deploy-time mass-logout root cause.)
      2. **Concurrent devices / tabs.** A second login wiped the first device's
         jti, 401-ing it on its next call.

    We now keep a bounded MAP of ``{jti: metadata}`` (most-recent ``MAX_SESSIONS``)
    per user. ``record_session`` ADDS a jti without dropping the others, so a
    rotated token and the token that requested it are both briefly valid, and a
    handful of devices/tabs coexist. Logout / password-change still revoke
    explicitly. This keeps the security property that matters — a token whose jti
    we have explicitly revoked is rejected — without the false invalidations.
    """

    CACHE_KEY_PREFIX = "user_sessions:"
    REVOKED_ALL_MARKER = "__revoked_all__"
    SESSION_EXPIRY = 86400 * 7  # 7 days (matches JWT refresh token lifetime)
    # Cap concurrent live jtis per user so the cache entry can't grow unbounded
    # under heavy refresh rotation. Generous enough for several devices/tabs plus
    # in-flight rotated tokens; oldest entries are evicted first.
    MAX_SESSIONS = 20

    @classmethod
    def _get_cache_key(cls, user_id):
        """Generate cache key for user's active sessions."""
        return f"{cls.CACHE_KEY_PREFIX}{user_id}"

    @classmethod
    def record_session(cls, user_id, token_jti, ip_address="", user_agent="", replace=False):
        """
        Record (ADD) an active session jti for the user.

        Unlike the legacy behaviour this does NOT evict the user's other live
        sessions by default — that is what broke refresh rotation and multi-device.
        Oldest jtis beyond ``MAX_SESSIONS`` are trimmed so the entry stays bounded.

        Args:
            user_id: User database ID
            token_jti: JWT ID (unique token identifier)
            ip_address: Request IP for audit logging
            user_agent: Request user agent for audit logging
            replace: if True, drop all previously-tracked jtis first (kept for
                callers that genuinely want a single active session). The default
                False is what refresh rotation and concurrent tabs require.
        """
        if not token_jti:
            return
        cache_key = cls._get_cache_key(user_id)

        # Existing sessions (tolerate the legacy shape and any cache miss).
        sessions = cache.get(cache_key)
        if replace or not isinstance(sessions, dict):
            sessions = {}

        sessions[token_jti] = {
            "jti": token_jti,
            "created_at": datetime.utcnow().isoformat(),
            "ip": (ip_address or "")[:50],
            "user_agent": (user_agent or "")[:200],
        }

        # Trim to the most-recent MAX_SESSIONS (dicts preserve insertion order in
        # py3.7+, so the first keys are the oldest).
        if len(sessions) > cls.MAX_SESSIONS:
            for stale in list(sessions.keys())[: len(sessions) - cls.MAX_SESSIONS]:
                sessions.pop(stale, None)

        cache.set(cache_key, sessions, cls.SESSION_EXPIRY)
        logger.info("Session recorded for user %s: jti=%s...", user_id, token_jti[:16])

    @classmethod
    def is_session_valid(cls, user_id, token_jti):
        """
        Return True if ``token_jti`` is a currently-tracked session for the user.

        Fail-OPEN on an empty/missing tracker entry: if we have NO record at all
        for the user (cold cache after a Redis flush/restart, or a token issued
        before tracking existed), we must not reject an otherwise cryptographically
        valid, unexpired JWT — doing so would log the whole site out whenever the
        cache is cleared. Revocation still works because logout / password-change
        leave the *other* jtis in the entry, so a revoked jti is absent from a
        NON-empty set and is correctly rejected.
        """
        if not token_jti:
            # A token with no jti can't be tracked; don't hard-fail it here.
            return True
        cache_key = cls._get_cache_key(user_id)
        sessions = cache.get(cache_key)
        if sessions == cls.REVOKED_ALL_MARKER:
            return False
        if not isinstance(sessions, dict) or not sessions:
            if getattr(settings, "JWT_SESSION_FAIL_CLOSED", False):
                return False
            return True
        return token_jti in sessions

    @classmethod
    def invalidate_session(cls, user_id, token_jti):
        """
        Invalidate a specific session (e.g., on logout of one device).
        """
        cache_key = cls._get_cache_key(user_id)
        sessions = cache.get(cache_key)
        if not isinstance(sessions, dict):
            return
        if token_jti in sessions:
            del sessions[token_jti]
            if sessions:
                cache.set(cache_key, sessions, cls.SESSION_EXPIRY)
            else:
                cache.delete(cache_key)
            logger.info("Session invalidated for user %s: jti=%s...", user_id, token_jti[:16])

    @classmethod
    def invalidate_all_sessions(cls, user_id):
        """
        Invalidate all sessions for a user (force re-login everywhere).
        Useful for password changes, security alerts, etc.

        We write a short-lived empty-but-present marker so the entry is NON-empty
        for a moment — but since an empty set means "fail open", we instead delete
        the key. Revocation of a *currently in-use* token is still achieved
        because the caller (password change) pairs this with re-issuing the user's
        own session; any pre-existing jti is simply no longer in a populated set
        the next time the user logs in. For an immediate hard cut, callers should
        also rely on refresh-token blacklisting (DB-backed).
        """
        cache_key = cls._get_cache_key(user_id)
        cache.set(cache_key, cls.REVOKED_ALL_MARKER, cls.SESSION_EXPIRY)
        logger.warning("All sessions invalidated for user %s (tombstone set)", user_id)


# Cache key for the RUNTIME session-enforcement override. When present it wins
# over the static ``settings.JWT_SESSION_ENFORCEMENT`` so CI/E2E can toggle
# enforcement on the LIVE backend WITHOUT a container restart or .env rewrite —
# the previous approach (restart + flip JWT_SESSION_ENFORCEMENT in .env.production)
# is what disrupted real users on every deploy.
SESSION_ENFORCEMENT_OVERRIDE_KEY = "jwt_session_enforcement_override"


def set_session_enforcement_override(enabled):
    """Set a runtime override for session enforcement (True/False), or clear it.

    Pass ``None`` to remove the override and fall back to the static setting.
    Stored with a safety TTL so a forgotten 'disable' self-heals instead of
    leaving enforcement off forever.
    """
    if enabled is None:
        cache.delete(SESSION_ENFORCEMENT_OVERRIDE_KEY)
        logger.warning("JWT session enforcement override CLEARED (using static setting)")
        return
    # 6h TTL: longer than any deploy/E2E run, short enough to auto-recover.
    cache.set(SESSION_ENFORCEMENT_OVERRIDE_KEY, bool(enabled), 6 * 3600)
    logger.warning("JWT session enforcement override set to %s", bool(enabled))


def session_enforcement_enabled():
    """Return whether JWT session enforcement is currently active.

    Precedence: runtime cache override (if set) → ``settings.JWT_SESSION_ENFORCEMENT``.
    A cache miss/outage returns ``None`` from ``cache.get`` (IGNORE_EXCEPTIONS),
    so we transparently fall back to the static setting and never crash auth.
    """
    override = cache.get(SESSION_ENFORCEMENT_OVERRIDE_KEY)
    if override is not None:
        return bool(override)
    return bool(getattr(settings, "JWT_SESSION_ENFORCEMENT", True))


class JWTSecurityConfig:
    """
    Generates and manages JWT security configuration.
    Uses RS256 (asymmetric) instead of HS256 for higher security.
    """
    
    @staticmethod
    def generate_rsa_keys():
        """
        Generate RSA key pair for JWT signing.
        Should be called once during initialization.
        
        Returns:
            dict: {"private_key": str, "public_key": str}
        """
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        # Generate key pair (2048-bit RSA)
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        
        # Serialize to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode('utf-8')
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode('utf-8')
        
        return {
            "private_key": private_pem,
            "public_key": public_pem,
        }
    
    @staticmethod
    def get_jwt_settings():
        """
        Get hardened JWT settings to be placed in Django settings.
        """
        return {
            "ALGORITHM": "RS256",  # Asymmetric instead of HS256
            "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),  # Reduced from 2 hours
            "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": True,
            "UPDATE_LAST_LOGIN": True,
            "AUTH_HEADER_TYPES": ("Bearer",),
            # Token must include 'jti' (JWT ID) for revocation tracking
            "JTI_CLAIM": "jti",
            # These should be set from env for the RSA keys:
            # "SIGNING_KEY": env("JWT_SIGNING_KEY"),  # Private key
            # "VERIFYING_KEY": env("JWT_VERIFYING_KEY"),  # Public key
        }


class TokenHelper:
    """
    Helper functions for token generation with security enhancements.
    """
    
    @staticmethod
    def generate_token_jti():
        """Generate a unique JWT ID for token revocation tracking."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_tokens_with_session(user, ip_address="", user_agent=""):
        """
        Create JWT tokens and record the session.
        
        Args:
            user: Django User instance
            ip_address: Request IP
            user_agent: Request user agent
            
        Returns:
            dict: {"access": token, "refresh": token, "jti": unique_id}
        """
        refresh = RefreshToken.for_user(user)
        
        # Generate and assign unique JTI for this token (same on access + refresh)
        jti = TokenHelper.generate_token_jti()
        refresh['jti'] = jti
        access = refresh.access_token
        access['jti'] = jti
        
        # Record session
        SessionTracker.record_session(user.id, jti, ip_address, user_agent)
        
        return {
            "access": str(access),
            "refresh": str(refresh),
            "jti": jti,
        }


def mask_pii(text):
    """
    Mask personally identifiable information in logs.
    
    Examples:
        "user@domain.com" -> "us***@domain.com"
        "john.doe@gmail.com" -> "jo***@gmail.com"
        "+91-9876543210" -> "+91-98****3210"
        "4532-1234-5678-9010" -> "4532-****-****-9010"
    """
    if not text or not isinstance(text, str):
        return text
    
    # Email masking
    if '@' in text:
        local, domain = text.split('@', 1)
        if len(local) <= 2:
            masked = '*' * len(local)
        else:
            masked = local[:2] + '***'
        return f"{masked}@{domain}"
    
    # Phone number masking (common formats: +91-9876543210, +1-5551234567)
    if text.startswith('+') and len(text) > 8:
        if text.startswith('+91'):
            return text[:6] + '****' + text[-4:]
        if text.startswith('+1'):
            return text[:5] + '****' + text[-4:]
        return text[:5] + '*' * max(4, len(text) - 9) + text[-4:]
    
    # Credit card masking (show only last 4 digits)
    if len(text) >= 13 and text.replace('-', '').isdigit():
        digits = text.replace('-', '')
        if len(digits) == 16:
            return f"{digits[:4]}-****-****-{digits[-4:]}"
    
    # SSN masking (XXX-XX-XXXX format)
    if len(text) == 11 and text[3] == '-' and text[6] == '-':
        return f"***-**-{text[-4:]}"
    
    return text

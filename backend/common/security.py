"""
Security utilities for JWT hardening and session management.
"""
import secrets
import hashlib
import json
from datetime import timedelta
from django.core.cache import cache
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
import logging

logger = logging.getLogger(__name__)


class SessionTracker:
    """
    Tracks active JWT sessions per user to prevent duplicate logins.
    When a user logs in for the 2nd time, the 1st session is invalidated.
    """
    
    CACHE_KEY_PREFIX = "user_sessions:"
    SESSION_EXPIRY = 86400 * 7  # 7 days (matches JWT refresh token lifetime)
    
    @classmethod
    def _get_cache_key(cls, user_id):
        """Generate cache key for user's active sessions."""
        return f"{cls.CACHE_KEY_PREFIX}{user_id}"
    
    @classmethod
    def record_session(cls, user_id, token_jti, ip_address="", user_agent=""):
        """
        Record a new active session for the user.
        If user already has an active session, the old one is invalidated.
        
        Args:
            user_id: User database ID
            token_jti: JWT ID (unique token identifier)
            ip_address: Request IP for audit logging
            user_agent: Request user agent for audit logging
        """
        cache_key = cls._get_cache_key(user_id)
        
        # Get existing sessions
        sessions = cache.get(cache_key, {})
        
        # Record new session
        new_session = {
            "jti": token_jti,
            "created_at": json.dumps(__import__('datetime').datetime.utcnow().isoformat()),
            "ip": ip_address[:50],  # Limit length
            "user_agent": user_agent[:200],
        }
        
        # Keep only latest session (auto-logout previous)
        sessions = {token_jti: new_session}
        
        cache.set(cache_key, sessions, cls.SESSION_EXPIRY)
        logger.info(f"Session recorded for user {user_id}: jti={token_jti[:16]}...")
    
    @classmethod
    def is_session_valid(cls, user_id, token_jti):
        """
        Check if the given JWT is the active session for the user.
        """
        cache_key = cls._get_cache_key(user_id)
        sessions = cache.get(cache_key, {})
        
        return token_jti in sessions
    
    @classmethod
    def invalidate_session(cls, user_id, token_jti):
        """
        Invalidate a specific session (e.g., on logout).
        """
        cache_key = cls._get_cache_key(user_id)
        sessions = cache.get(cache_key, {})
        
        if token_jti in sessions:
            del sessions[token_jti]
            if sessions:
                cache.set(cache_key, sessions, cls.SESSION_EXPIRY)
            else:
                cache.delete(cache_key)
            logger.info(f"Session invalidated for user {user_id}: jti={token_jti[:16]}...")
    
    @classmethod
    def invalidate_all_sessions(cls, user_id):
        """
        Invalidate all sessions for a user (force re-login everywhere).
        Useful for password changes, security alerts, etc.
        """
        cache_key = cls._get_cache_key(user_id)
        cache.delete(cache_key)
        logger.warning(f"All sessions invalidated for user {user_id}")


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

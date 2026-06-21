"""
Custom DRF throttles for resource-intensive operations.
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """
    Brute-force protection for the login endpoint.

    Unlike a plain AnonRateThrottle (which counts *every* request keyed on IP
    alone), this throttle:

      * Keys on (client IP + target email), so it caps guesses against a single
        account from a single source — the actual brute-force vector — instead
        of collectively rate-limiting every user behind a shared egress IP
        (corporate NAT, VPN, or a CI/E2E container firing many logins).
      * Only counts *failed* attempts. A correct-credential login never consumes
        quota, so legitimate users (and reasonable concurrent logins) are never
        locked out no matter how often they sign in. The view calls
        ``record_failure`` only on an authentication failure.

    The ``login`` rate in DEFAULT_THROTTLE_RATES is therefore a ceiling on
    *wrong-password attempts per account per IP per minute*, not on total logins.
    """
    scope = 'login'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        # Email is the account being targeted; fall back to ident-only if absent.
        email = ""
        data = getattr(request, "data", None)
        if isinstance(data, dict):
            email = (data.get("email") or "").strip().lower()
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{ident}:{email}" if email else ident,
        }

    def allow_request(self, request, view):
        """
        Check the recorded *failure* history without recording this request.

        Successful logins go through here too but never add to the history, so
        they cannot exhaust the bucket. Recording happens explicitly via
        ``record_failure`` from the view on a failed authentication.
        """
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.history = self.cache.get(self.key, [])
        self.now = self.timer()

        # Drop attempts that have aged out of the throttle window.
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()

        # Block only once too many *failures* have accumulated.
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        return True

    def record_failure(self, request, view=None):
        """Record one failed login attempt against (IP + email)."""
        if self.rate is None:
            return
        key = getattr(self, "key", None) or self.get_cache_key(request, view)
        if key is None:
            return
        now = getattr(self, "now", None) or self.timer()
        history = self.cache.get(key, [])
        history.insert(0, now)
        self.cache.set(key, history, self.duration)


class OTPRateThrottle(AnonRateThrottle):
    scope = 'otp'


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = 'password_reset'


class PaymentRateThrottle(UserRateThrottle):
    scope = 'payment'


class InterviewRateThrottle(UserRateThrottle):
    scope = 'interview'


class StrictAnonRateThrottle(AnonRateThrottle):
    """For endpoints that anonymous users shouldn't hammer."""
    scope = 'strict_anon'


class LabStartThrottle(UserRateThrottle):
    """
    Limit new lab provisions per user. Staff are exempt; resumed sessions
    for the same scenario do not consume quota.
    """
    scope = "lab_start"
    rate = "60/hour"

    def allow_request(self, request, view):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
                return True
            scenario_id = getattr(view, "kwargs", {}).get("scenario_id")
            if scenario_id:
                from apps.labs.models import LabSession
                if LabSession.objects.filter(
                    user=user,
                    scenario_id=scenario_id,
                    status__in=["RUNNING", "PROVISIONING"],
                ).exists():
                    return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return super().get_cache_key(request, view)

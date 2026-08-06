"""Email suppression list (audit Z6-16).

There was no bounce, complaint or suppression handling of any kind — grepping
`bounce|suppress|complaint` across the codebase returned nothing. So an address
that hard-bounces is retried on every subsequent notification, forever.

On most platforms that is a reputation problem. Here it is also a **capacity**
problem, and that is the sharper edge: transactional mail runs on a shared Gmail
allowance of roughly 500 messages a day (ADR 0005), and OTP and password-reset
delivery come out of the same pool. Every send to a dead address is one fewer
message available for somebody trying to sign in. A handful of bounced accounts on
a weekly digest is a measurable bite out of the auth budget.

**Derived from `EmailLog`, not a new table.** Failures were already being recorded;
nothing was reading them. Adding a parallel store would create two sources of truth
about the same address, and the interesting failure is the one where they disagree.

Three decisions worth stating, because each is the difference between a
suppression list that helps and one that loses mail:

1. **Critical mail is never suppressed.** OTP and password reset always attempt
   delivery. Suppressing them would convert a delivery problem into a permanent
   account lockout, and a user whose mailbox was full last week must still be able
   to sign in today.
2. **Suppression expires.** Mailboxes come back — full inboxes are emptied, DNS is
   fixed, a company changes provider. A permanent list quietly accumulates users
   who can never be contacted again.
3. **It requires repeated failures.** One timeout is a network blip, not a dead
   address. Suppressing on a single failure would silence real users during any
   transient outage of our own.
"""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# How many recorded failures, within the window, before an address is suppressed.
# One failure is a blip; three in a row is a pattern.
SUPPRESSION_FAILURE_THRESHOLD = 3

# Only failures inside this window count, so an address that failed three times in
# March is not suppressed in December on the strength of ancient history.
SUPPRESSION_LOOKBACK_DAYS = 30

# How long suppression lasts before the address is retried. Long enough to stop the
# bleeding, short enough that a recovered mailbox is not lost for good.
SUPPRESSION_DURATION_DAYS = 14

# Delivery classes that are never suppressed — see decision 1 above.
NEVER_SUPPRESSED_TYPES = frozenset({"otp", "password_reset", "security", "critical"})


def is_suppressed(email: str, email_type: str = "") -> bool:
    """Whether we should skip sending to this address right now.

    Fails **open** on any error: a broken suppression check must not stop mail
    going out. The cost of a wrongly-sent email is one wasted message; the cost of
    a wrongly-suppressed one can be a user unable to reach their account.
    """
    if not email:
        return False
    if email_type in NEVER_SUPPRESSED_TYPES:
        return False

    try:
        from .models import EmailLog

        window_start = timezone.now() - timedelta(days=SUPPRESSION_LOOKBACK_DAYS)
        recent = list(
            EmailLog.objects.filter(to_email__iexact=email, created_at__gte=window_start)
            .order_by("-created_at")
            .values_list("status", "created_at")[:SUPPRESSION_FAILURE_THRESHOLD]
        )
        if len(recent) < SUPPRESSION_FAILURE_THRESHOLD:
            return False

        # Consecutive failures only. A success anywhere in the recent run proves the
        # address is alive, and the count restarts from there — otherwise an account
        # that failed three times a month ago stays suppressed despite working since.
        if not all(status == "failed" for status, _ in recent):
            return False

        newest_failure = recent[0][1]
        expires = newest_failure + timedelta(days=SUPPRESSION_DURATION_DAYS)
        return timezone.now() < expires
    except Exception as exc:
        logger.warning("Suppression check failed for %s (%s); allowing send", email, exc)
        return False


def suppression_status(email: str) -> dict:
    """Why an address is or is not suppressed. For the admin and for support.

    "Your emails stopped arriving" is a common support question, and without this
    the answer requires reading the log table by hand.
    """
    try:
        from .models import EmailLog

        window_start = timezone.now() - timedelta(days=SUPPRESSION_LOOKBACK_DAYS)
        qs = EmailLog.objects.filter(to_email__iexact=email, created_at__gte=window_start)
        recent = list(qs.order_by("-created_at").values_list("status", "created_at")[:SUPPRESSION_FAILURE_THRESHOLD])
        suppressed = is_suppressed(email, email_type="notification")
        return {
            "email": email,
            "suppressed": suppressed,
            "recent_failures": sum(1 for s, _ in recent if s == "failed"),
            "consecutive_required": SUPPRESSION_FAILURE_THRESHOLD,
            "expires_at": (
                (recent[0][1] + timedelta(days=SUPPRESSION_DURATION_DAYS)).isoformat()
                if suppressed and recent else None
            ),
            "note": (
                "Critical mail (OTP, password reset) is never suppressed — "
                "suppression must not become an account lockout."
            ),
        }
    except Exception as exc:
        return {"email": email, "suppressed": False, "error": str(exc)}

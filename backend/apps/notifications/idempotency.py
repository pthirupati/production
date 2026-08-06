"""Email idempotency (audit Z6-16 remainder).

`send_notification_email` retries on any exception, up to three times. The failure
that produced this module is the ambiguous one: the provider **accepts** the message
and then the connection times out before it answers. From our side that is
indistinguishable from a total failure, so the task raises, Celery retries, and the
user gets the same mail two, three or four times. For a digest that is annoying; for
an OTP it is worse than annoying, because two codes arrive and only one works and
the user has no way to tell which.

The guarantee here is deliberately **at-least-once, deduplicated where delivery can
be proven** — not exactly-once, which is not available to us:

* **Confirmed sends are never repeated.** Once a provider has answered "accepted",
  the key is recorded and any later retry of the same message is dropped outright.
* **Unconfirmed sends are still retried.** In the ambiguous window we do not know
  whether the mail went out, and for OTP and password reset a missing message costs
  account access while a duplicate costs a moment of confusion. Retrying is the
  right side of that trade, and taking the other side would silently reintroduce
  the lost-OTP bug this work started from.
* **The duplicate is made collapsible.** Every message carries a `Message-ID`
  derived from the same key, so a retry in the ambiguous window reuses the
  identifier of the original. Mail clients that de-duplicate on `Message-ID` — Gmail
  among them — show one message rather than two. This does not make delivery
  exactly-once; it makes the unavoidable duplicate mostly invisible.

The key is derived from the message content, so two genuinely different messages
never collide: a user who requests a second OTP gets a different code, therefore a
different key, therefore a real second email. Only a *retry of the same message*,
which Celery re-runs with byte-identical arguments, dedupes.
"""

import hashlib
import json
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# How long a confirmed send is remembered. Comfortably longer than the retry
# schedule (three retries at a 10s backoff), with enough margin that a queue backed
# up for hours still dedupes. Short enough that the cache does not accumulate keys
# for messages nobody will ever retry.
DELIVERY_MEMORY_SECONDS = 24 * 60 * 60

_SENT_PREFIX = "email:delivered:"


def idempotency_key(subject: str, to_email: str, template: str, context=None) -> str:
    """A stable fingerprint of one message.

    Derived from content rather than assigned at call time on purpose: Celery
    re-runs a retried task with the arguments it serialised at enqueue, so a retry
    reproduces this value exactly, while a genuinely new message (a fresh OTP code,
    a different recipient) does not.

    `sort_keys` matters — dict ordering is not guaranteed across a serialisation
    round trip, and an unstable key would make every retry look like a new message,
    which is the failure this module exists to prevent and the one that would be
    hardest to notice.
    """
    payload = json.dumps(
        {
            "subject": subject or "",
            "to": (to_email or "").strip().lower(),
            "template": template or "",
            "context": context or {},
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


def message_id_for(key: str, domain: str = "fixitlab.in") -> str:
    """A deterministic RFC 5322 Message-ID for this message.

    Because it is derived from the key, a retry in the ambiguous window carries the
    same identifier as the send that may already have arrived — so a client that
    de-duplicates on Message-ID collapses them into one.
    """
    return f"<{key}@{domain}>"


def already_delivered(key: str) -> bool:
    """Whether a provider has already confirmed acceptance of this exact message.

    Fails **open**: if the cache is unavailable we do not know, and the safe answer
    when we do not know is to send. A false "already delivered" here would drop an
    OTP entirely — precisely the bug this module sits next to.
    """
    try:
        return cache.get(_SENT_PREFIX + key) is not None
    except Exception as exc:
        logger.warning("Idempotency lookup failed for %s (%s); allowing send", key, exc)
        return False


def mark_delivered(key: str) -> None:
    """Record that a provider accepted this message.

    Called only after acceptance, never before. Marking on attempt would mean a send
    that failed outright is never retried, converting a transient provider error
    into a permanently lost email.
    """
    try:
        cache.set(_SENT_PREFIX + key, True, DELIVERY_MEMORY_SECONDS)
    except Exception as exc:
        logger.warning("Could not record delivery of %s (%s)", key, exc)

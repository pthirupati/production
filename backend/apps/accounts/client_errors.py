"""Client-side error intake (audit Z6-6).

`ErrorBoundary.jsx` and `SimErrorBoundary.jsx` caught React render crashes and
reported them to `console.error` — that is, to a console nobody is reading. A
white screen in production was invisible until a user wrote in, so "did that
deploy break checkout?" had no answer.

**Why not `@sentry/react`.** The obvious fix is the Sentry SDK, and it would give
source maps and session replay this does not. It also adds a browser-side
third-party processor that receives user data, which means a DPDP consent
decision and a privacy-policy change (the processor list was only just enumerated
in Z4-6) — an owner call, not an engineering one. Meanwhile `SENTRY_DSN` is
already wired **server-side** and already fully env-gated, so posting to our own
origin and logging through Django reaches the same dashboard with no new vendor,
no new disclosure, and no new npm dependency. If the owner later adopts the SDK,
this endpoint becomes redundant and can be deleted.

Everything here is shaped by the endpoint being public and unauthenticated:
hard-throttled, hard-truncated, and it never echoes input back.
"""

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import ClientErrorThrottle

logger = logging.getLogger("fixitlab.client")

# A minified React stack is a few KB; anything larger is not a stack trace.
MAX_FIELD_CHARS = 2000
MAX_MESSAGE_CHARS = 500


def _clip(value, limit):
    text = "" if value is None else str(value)
    return text[:limit]


class ClientErrorView(APIView):
    """Record a browser-side crash so it reaches the same place as server errors."""

    permission_classes = [AllowAny]
    throttle_classes = [ClientErrorThrottle]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}

        message = _clip(data.get("message"), MAX_MESSAGE_CHARS).strip()
        if not message:
            # Nothing actionable; accept quietly rather than teach a caller to retry.
            return Response(status=status.HTTP_204_NO_CONTENT)

        # `user` is attached from the session, never from the payload — otherwise
        # any anonymous caller could file errors against someone else's account.
        user = request.user if getattr(request.user, "is_authenticated", False) else None

        logger.error(
            "client error: %s",
            message,
            extra={
                "client_error": {
                    "message": message,
                    "stack": _clip(data.get("stack"), MAX_FIELD_CHARS),
                    "component_stack": _clip(data.get("component_stack"), MAX_FIELD_CHARS),
                    # The route, not the full URL: query strings on this platform can
                    # carry a reset token or a payment token.
                    "route": _clip(data.get("route"), 200),
                    "release": _clip(data.get("release"), 100),
                    "kind": _clip(data.get("kind"), 50) or "react_error_boundary",
                    "user_id": getattr(user, "id", None),
                    "user_agent": _clip(request.META.get("HTTP_USER_AGENT"), 300),
                }
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

"""SSRF guard for user-supplied outbound URLs (org webhooks).

An organisation owner can set ``Organization.webhook_url``, and the server then
POSTs to it. Before this module existed the value went through ``setattr`` +
``save(update_fields=...)``, which bypasses ``URLField`` validation entirely (no
``full_clean()``), and the request was made **synchronously in the request path**
from ``labs/completion.py`` and ``accounts/views.py``.

That is a blind SSRF: any org owner could point the webhook at
``http://169.254.169.254/`` (cloud instance metadata — credentials), at the Vault
API on the private network, or at Postgres, and use lab-completion events as the
trigger. It also gave a 5s latency amplifier per completion.

Design notes:

* **Resolve before allowing.** Validating the hostname string is not enough —
  ``http://spoof.example.com`` can resolve to 127.0.0.1. We resolve every A/AAAA
  record and reject if *any* of them is non-public.
* **Reject on resolution failure.** Fail closed. A name we cannot resolve is a
  name we cannot vouch for.
* **https only.** ``http://`` would send the signature header in cleartext, and
  plain-HTTP webhooks are almost always an internal target.
* **Block non-standard ports.** Restricting to 443 removes the "scan the private
  network by port" primitive even if an attacker finds a public host that proxies
  inward.

Residual risk we accept and document: TOCTOU between this check and the actual
request (DNS rebinding). Fully closing it means pinning the resolved IP and
connecting to it directly with SNI/Host preserved, which is a bigger change to
the request layer. Combined with https-only and 443-only, and with the request
moved off the synchronous path, the remaining window is narrow. If you later need
to close it completely, pin the address here and pass it through to the adapter.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Ranges that must never be reachable from a user-supplied URL. `is_global` on a
# resolved address covers most of this, but we keep the cloud metadata addresses
# explicit because they are the highest-value target and the reason this exists.
_METADATA_ADDRESSES = frozenset({
    "169.254.169.254",   # AWS / GCP / Azure / DigitalOcean IMDS
    "100.100.100.200",   # Alibaba Cloud
    "192.0.0.192",       # Oracle Cloud
    "fd00:ec2::254",     # AWS IMDSv6
})

ALLOWED_SCHEMES = frozenset({"https"})
ALLOWED_PORTS = frozenset({443})


class UnsafeURLError(ValueError):
    """Raised when a user-supplied URL must not be requested server-side."""


def _address_is_public(raw: str) -> bool:
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False
    if raw in _METADATA_ADDRESSES:
        return False
    # is_global excludes private, loopback, link-local, multicast, reserved and
    # unspecified. Belt-and-braces on the individual flags in case a stdlib
    # version disagrees about a range.
    return bool(
        addr.is_global
        and not addr.is_private
        and not addr.is_loopback
        and not addr.is_link_local
        and not addr.is_multicast
        and not addr.is_reserved
        and not addr.is_unspecified
    )


def resolve_public_addresses(host: str) -> list[str]:
    """Resolve ``host`` and return its addresses, or raise if any is non-public."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host {host!r}.") from exc

    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise UnsafeURLError(f"Host {host!r} resolved to no addresses.")

    for addr in addresses:
        if not _address_is_public(addr):
            # Deliberately vague to the caller: do not confirm which internal
            # addresses exist. The full detail is logged by the caller.
            raise UnsafeURLError(
                "URL resolves to a private, loopback, link-local or metadata "
                "address, which is not permitted."
            )
    return addresses


def validate_outbound_url(value: str) -> str:
    """Return a normalised URL that is safe to request, or raise UnsafeURLError.

    Empty input is allowed and returned as ``""`` — clearing a webhook is valid.
    """
    if value is None:
        return ""
    url = str(value).strip()
    if not url:
        return ""

    if len(url) > 500:
        raise UnsafeURLError("URL is too long.")

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Webhook URLs must use https.")

    if not parsed.hostname:
        raise UnsafeURLError("URL has no host.")

    # Credentials in the URL are a redirect/parsing-confusion vector and have no
    # legitimate use for a webhook target.
    if parsed.username or parsed.password:
        raise UnsafeURLError("URL must not contain credentials.")

    port = parsed.port or 443
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError("Webhook URLs must use port 443.")

    # Raises if the host resolves anywhere non-public.
    resolve_public_addresses(parsed.hostname)

    return url

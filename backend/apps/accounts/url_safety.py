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

* **Pin the resolved address.** Validating and then letting ``requests`` resolve
  the name a second time is a TOCTOU: an attacker-controlled DNS zone can answer
  public on the first lookup and ``127.0.0.1`` on the second (DNS rebinding).
  ``pinned_session`` opens the socket against the exact address this module
  vetted, so there is no second lookup to poison. See ``PinnedHTTPAdapter`` for
  why SNI, the ``Host`` header and certificate verification all stay on the
  *hostname* — dropping any of them would break CDN- and shared-hosting-fronted
  webhook endpoints, which is most of them.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

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


class PinnedHTTPAdapter(HTTPAdapter):
    """Connect to a pre-validated IP instead of re-resolving the hostname.

    Three things must survive the substitution or we break far more webhooks than
    we protect:

    * **SNI** — a CDN or shared host serves many certificates off one IP and
      picks by SNI. Sending the IP (or nothing) gets the wrong certificate or a
      handshake failure.
    * **Certificate verification** — must still be checked against the hostname.
      Verifying against the IP would fail for every name-based certificate, and
      turning verification off to compensate would trade an SSRF for a MITM.
    * **The Host header** — name-based virtual hosts route on it. urllib3 derives
      it from the pool host, which is now an address, so we set it explicitly.

    Redirects are the caller's responsibility (``allow_redirects=False`` in
    webhooks.py): a redirect to a new hostname would not be covered by this pin.
    """

    def __init__(self, addresses: list[str], **kwargs):
        if not addresses:
            raise UnsafeURLError("Refusing to send with no validated address.")
        self._pinned_address = addresses[0]
        super().__init__(**kwargs)

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(
            request, verify, cert
        )
        hostname = host_params["host"]
        host_params = {**host_params, "host": self._pinned_address}
        # server_hostname drives SNI; assert_hostname keeps certificate
        # verification on the name rather than the address we dialled.
        pool_kwargs = {
            **pool_kwargs,
            "server_hostname": hostname,
            "assert_hostname": hostname,
        }
        return host_params, pool_kwargs

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        host_header = parsed.hostname or ""
        if parsed.port and parsed.port != 443:
            host_header = f"{host_header}:{parsed.port}"
        request.headers["Host"] = host_header
        return super().send(request, **kwargs)


def pinned_session(addresses: list[str]) -> requests.Session:
    """A Session that only ever dials ``addresses[0]`` for https requests."""
    session = requests.Session()
    session.mount("https://", PinnedHTTPAdapter(addresses))
    # http:// is unreachable by construction (ALLOWED_SCHEMES is https-only), but
    # leaving the default adapter mounted would silently un-pin anything that
    # slipped through a future change to that set.
    session.adapters.pop("http://", None)
    return session


def validate_outbound_url(value: str) -> str:
    """Return a normalised URL that is safe to request, or raise UnsafeURLError.

    Empty input is allowed and returned as ``""`` — clearing a webhook is valid.
    """
    return validate_and_resolve(value)[0]


def validate_and_resolve(value: str) -> tuple[str, list[str]]:
    """Validate ``value`` and return ``(url, vetted_addresses)``.

    The addresses are returned so the caller can pin them for the actual request
    instead of letting the resolver run a second time. ``([], "")`` for empty
    input, which means "no webhook configured", not "unsafe".
    """
    if value is None:
        return "", []
    url = str(value).strip()
    if not url:
        return "", []

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
    addresses = resolve_public_addresses(parsed.hostname)

    return url, addresses

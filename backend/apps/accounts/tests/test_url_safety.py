"""SSRF guard tests for user-supplied outbound URLs (org webhooks).

These assert the guard actually blocks the attack, not merely that a validator
exists. Resolution is patched so the suite never makes real DNS queries and the
result does not depend on the CI network.
"""
import os
import socket
import ssl
import subprocess
import tempfile
import threading
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.accounts.url_safety import (
    PinnedHTTPAdapter,
    UnsafeURLError,
    pinned_session,
    validate_and_resolve,
    validate_outbound_url,
)


def _resolves_to(*addresses):
    """Patch getaddrinfo so a hostname resolves to the given addresses."""
    infos = [(2, 1, 6, "", (addr, 443)) for addr in addresses]
    return patch("apps.accounts.url_safety.socket.getaddrinfo", return_value=infos)


class OutboundURLGuardTests(SimpleTestCase):
    # ── the attacks this exists to stop ──────────────────────────────────────
    def test_blocks_cloud_metadata_endpoint(self):
        """The highest-value target: IMDS hands out instance credentials."""
        with _resolves_to("169.254.169.254"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://metadata.example.com/latest/meta-data/")

    def test_blocks_literal_metadata_ip(self):
        with _resolves_to("169.254.169.254"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://169.254.169.254/")

    def test_blocks_loopback(self):
        with _resolves_to("127.0.0.1"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://localhost/")

    def test_blocks_private_ranges(self):
        for addr in ("10.0.0.10", "172.16.4.5", "192.168.1.20"):
            with self.subTest(addr=addr), _resolves_to(addr):
                with self.assertRaises(UnsafeURLError):
                    validate_outbound_url("https://internal.example.com/hook")

    def test_blocks_dns_pointing_public_name_at_private_ip(self):
        """A public-looking hostname that resolves inward must still be rejected.

        This is why the guard resolves rather than pattern-matching the host.
        """
        with _resolves_to("10.1.2.3"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://totally-legit-webhooks.com/hook")

    def test_blocks_when_any_address_is_private(self):
        """Mixed A records must fail closed on the private one."""
        with _resolves_to("93.184.216.34", "127.0.0.1"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://mixed.example.com/hook")

    def test_blocks_ipv6_loopback_and_link_local(self):
        for addr in ("::1", "fe80::1"):
            with self.subTest(addr=addr), _resolves_to(addr):
                with self.assertRaises(UnsafeURLError):
                    validate_outbound_url("https://v6.example.com/hook")

    def test_blocks_unresolvable_host_fails_closed(self):
        import socket

        with patch(
            "apps.accounts.url_safety.socket.getaddrinfo",
            side_effect=socket.gaierror("nope"),
        ):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://does-not-exist.invalid/hook")

    # ── scheme / port / shape ────────────────────────────────────────────────
    def test_rejects_http(self):
        with _resolves_to("93.184.216.34"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("http://example.com/hook")

    def test_rejects_non_http_schemes(self):
        for url in ("file:///etc/passwd", "gopher://x/", "ftp://example.com/"):
            with self.subTest(url=url):
                with self.assertRaises(UnsafeURLError):
                    validate_outbound_url(url)

    def test_rejects_non_443_port(self):
        """Removes the scan-the-private-network-by-port primitive."""
        with _resolves_to("93.184.216.34"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://example.com:8200/v1/secret")

    def test_rejects_embedded_credentials(self):
        with _resolves_to("93.184.216.34"):
            with self.assertRaises(UnsafeURLError):
                validate_outbound_url("https://user:pw@example.com/hook")

    def test_rejects_overlong_url(self):
        with self.assertRaises(UnsafeURLError):
            validate_outbound_url("https://example.com/" + "a" * 600)

    # ── the legitimate cases must still work ─────────────────────────────────
    def test_allows_public_https_webhook(self):
        with _resolves_to("93.184.216.34"):
            self.assertEqual(
                validate_outbound_url("https://hooks.example.com/services/abc"),
                "https://hooks.example.com/services/abc",
            )

    def test_allows_explicit_443(self):
        with _resolves_to("93.184.216.34"):
            self.assertTrue(validate_outbound_url("https://example.com:443/hook"))

    def test_empty_clears_the_webhook(self):
        """Clearing a webhook is a legitimate action and must not raise."""
        self.assertEqual(validate_outbound_url(""), "")
        self.assertEqual(validate_outbound_url(None), "")
        self.assertEqual(validate_outbound_url("   "), "")

    # ── the vetted addresses must reach the caller ───────────────────────────
    def test_validate_and_resolve_returns_the_vetted_addresses(self):
        """Pinning is impossible if validation throws the resolution away."""
        with _resolves_to("93.184.216.34", "93.184.216.35"):
            url, addresses = validate_and_resolve("https://hooks.example.com/x")
        self.assertEqual(url, "https://hooks.example.com/x")
        self.assertEqual(addresses, ["93.184.216.34", "93.184.216.35"])

    def test_validate_and_resolve_empty_is_not_an_error(self):
        self.assertEqual(validate_and_resolve(""), ("", []))


class _TLSServer:
    """Single-shot https server on 127.0.0.1 with a cert for ``hostname``."""

    def __init__(self, hostname):
        self.hostname = hostname
        self.received = {}
        self._dir = tempfile.mkdtemp()
        self.cert = os.path.join(self._dir, "cert.pem")
        key = os.path.join(self._dir, "key.pem")
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", key, "-out", self.cert, "-days", "1", "-nodes",
                "-subj", f"/CN={hostname}",
                "-addext", f"subjectAltName=DNS:{hostname}",
            ],
            check=True, capture_output=True,
        )
        self._ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._ctx.load_cert_chain(self.cert, key)
        self._ctx.sni_callback = self._on_sni
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]

    def _on_sni(self, sock, name, ctx):
        self.received["sni"] = name

    def __enter__(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._sock.close()

    def _serve(self):
        try:
            raw, _ = self._sock.accept()
        except OSError:
            return
        try:
            tls = self._ctx.wrap_socket(raw, server_side=True)
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = tls.recv(4096)
                if not chunk:
                    break
                buf += chunk
            self.received["request"] = buf.decode(errors="replace")
            tls.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            tls.close()
        except Exception as exc:  # surfaced by the assertions in the test
            self.received["error"] = repr(exc)

    def header(self, name):
        head = self.received.get("request", "").split("\r\n\r\n")[0]
        for line in head.splitlines()[1:]:
            key, _, value = line.partition(":")
            if key.strip().lower() == name.lower():
                return value.strip()
        return None


class _LoopbackPinAdapter(PinnedHTTPAdapter):
    """Pins to 127.0.0.1 and to the ephemeral test port.

    Production pins address only; the port override exists purely so the test
    server does not need to bind 443.
    """

    def __init__(self, addresses, port, **kwargs):
        self._forced_port = port
        super().__init__(addresses, **kwargs)

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(
            request, verify, cert
        )
        return {**host_params, "port": self._forced_port}, pool_kwargs


class PinnedRequestTests(SimpleTestCase):
    """The pin must close the rebinding window WITHOUT breaking name-based hosts.

    These drive a real TLS handshake against a local server rather than asserting
    on mock kwargs: SNI, the Host header and certificate verification are all
    things that only fail on the wire.
    """

    HOSTNAME = "hooks.example.com"

    def _post_via_pin(self, server):
        import requests

        session = requests.Session()
        session.mount("https://", _LoopbackPinAdapter(["127.0.0.1"], server.port))
        with session:
            return session.post(
                f"https://{self.HOSTNAME}/hook",
                data=b"{}",
                verify=server.cert,
                timeout=10,
                allow_redirects=False,
            )

    def test_connects_to_the_pinned_address_not_the_hostname(self):
        """The socket goes to the vetted IP; the name is never resolved again.

        hooks.example.com does not resolve to 127.0.0.1 anywhere, so a 200 from
        the loopback server is only possible if the pin decided the destination.
        """
        with _TLSServer(self.HOSTNAME) as server:
            resp = self._post_via_pin(server)
        self.assertEqual(resp.status_code, 200, server.received.get("error"))

    def test_sni_still_carries_the_hostname(self):
        """Without this a CDN-fronted endpoint gets the wrong cert and fails."""
        with _TLSServer(self.HOSTNAME) as server:
            self._post_via_pin(server)
        self.assertEqual(
            server.received.get("sni"),
            self.HOSTNAME,
            "SNI must be the hostname, not the pinned address, or every "
            "shared-hosting webhook target breaks.",
        )

    def test_host_header_still_carries_the_hostname(self):
        """urllib3 derives Host from the pool host, which is now an IP."""
        with _TLSServer(self.HOSTNAME) as server:
            self._post_via_pin(server)
        self.assertEqual(
            server.header("Host"),
            self.HOSTNAME,
            "Host must be the hostname; name-based virtual hosts route on it.",
        )

    def test_certificate_is_verified_against_the_hostname(self):
        """Pinning must not silently become 'skip verification'.

        The server presents a cert for hooks.example.com only, so pinning a
        request for a *different* name at it has to fail the handshake.
        """
        import requests

        with _TLSServer(self.HOSTNAME) as server:
            session = requests.Session()
            session.mount("https://", _LoopbackPinAdapter(["127.0.0.1"], server.port))
            with session, self.assertRaises(requests.exceptions.SSLError):
                session.post(
                    "https://not-the-cert-name.example.com/hook",
                    data=b"{}",
                    verify=server.cert,
                    timeout=10,
                    allow_redirects=False,
                )

    def test_pinned_session_refuses_to_build_without_addresses(self):
        """Fail closed rather than falling back to an unpinned resolve."""
        with self.assertRaises(UnsafeURLError):
            pinned_session([])

    def test_pinned_session_does_not_leave_an_unpinned_http_adapter(self):
        with pinned_session(["93.184.216.34"]) as session:
            self.assertNotIn("http://", session.adapters)
            self.assertIsInstance(session.adapters["https://"], PinnedHTTPAdapter)

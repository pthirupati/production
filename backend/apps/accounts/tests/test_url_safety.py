"""SSRF guard tests for user-supplied outbound URLs (org webhooks).

These assert the guard actually blocks the attack, not merely that a validator
exists. Resolution is patched so the suite never makes real DNS queries and the
result does not depend on the CI network.
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.accounts.url_safety import UnsafeURLError, validate_outbound_url


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

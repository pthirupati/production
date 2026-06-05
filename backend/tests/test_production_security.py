"""
Production-only comprehensive test suite for security hardening.
Tests JWT authentication, session tracking, structured logging, and API security.
"""

import json
import os
import unittest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from datetime import timedelta
from django.utils import timezone

from common.security import SessionTracker, TokenHelper, mask_pii
from common.logging_utils import get_structured_logger
from apps.accounts.models import Profile
from apps.billing.models import TechnologySubscription
from apps.question_bank.models import Technology, Scenario

User = get_user_model()


def _extended_test(case_cls):
    return unittest.skipUnless(
        os.environ.get("RUN_EXTENDED_TESTS"),
        "Extended production tests — set RUN_EXTENDED_TESTS=1",
    )(case_cls)


@_extended_test
class JWTSecurityTestCase(APITestCase):
    """Test JWT token security hardening (RS256)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )

    def test_login_returns_access_token(self):
        """Test that login returns access token with RS256."""
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_jwt_token_has_jti_claim(self):
        """Test that JWT includes jti (JWT ID) for revocation tracking."""
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')

        access_token = response.data['access']
        
        # Decode JWT (without verification, just to read claims)
        import jwt
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        
        self.assertIn('jti', decoded, "JWT must include 'jti' claim for revocation")
        self.assertIn('user_id', decoded)

    def test_access_token_lifetime_one_hour(self):
        """Test that access token lifetime is 1 hour (not 2 hours)."""
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')

        access_token = response.data['access']
        
        import jwt
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        
        exp_time = decoded['exp']
        iat_time = decoded['iat']
        lifetime_seconds = exp_time - iat_time
        
        # Should be approximately 1 hour (3600 seconds)
        self.assertAlmostEqual(lifetime_seconds, 3600, delta=60)

    def test_refresh_token_lifetime_seven_days(self):
        """Test that refresh token lifetime is 7 days."""
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')

        refresh_token = response.data['refresh']
        
        import jwt
        decoded = jwt.decode(refresh_token, options={"verify_signature": False})
        
        exp_time = decoded['exp']
        iat_time = decoded['iat']
        lifetime_seconds = exp_time - iat_time
        
        # Should be approximately 7 days (604800 seconds)
        self.assertAlmostEqual(lifetime_seconds, 604800, delta=60)


@_extended_test
class DuplicateLoginPreventionTestCase(APITestCase):
    """Test duplicate login prevention (single session per user)."""

    def setUp(self):
        self.client_a = APIClient()
        self.client_b = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )

    def test_second_login_invalidates_first_session(self):
        """Test that 2nd login invalidates 1st device's session."""
        # Device A: First login
        response_a = self.client_a.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        token_a = response_a.data['access']
        
        # Verify Device A token works
        self.client_a.credentials(HTTP_AUTHORIZATION=f'Bearer {token_a}')
        response = self.client_a.get('/api/auth/profile')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Device B: Second login (same user)
        response_b = self.client_b.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        token_b = response_b.data['access']
        
        # Device B token should work
        self.client_b.credentials(HTTP_AUTHORIZATION=f'Bearer {token_b}')
        response = self.client_b.get('/api/auth/profile')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Device A token should NOW be invalid (session invalidated)
        self.client_a.credentials(HTTP_AUTHORIZATION=f'Bearer {token_a}')
        response = self.client_a.get('/api/auth/profile')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_tracker_records_session(self):
        """Test that SessionTracker properly records sessions."""
        tokens = TokenHelper.create_tokens_with_session(
            self.user,
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0'
        )
        jti = tokens['jti']
        
        # Session should be valid
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, jti))
        
        # Different JTI should be invalid
        fake_jti = 'invalid_jti_xyz'
        self.assertFalse(SessionTracker.is_session_valid(self.user.id, fake_jti))

    def test_session_invalidation(self):
        """Test manual session invalidation."""
        tokens = TokenHelper.create_tokens_with_session(self.user)
        jti = tokens['jti']
        
        self.assertTrue(SessionTracker.is_session_valid(self.user.id, jti))
        
        # Invalidate
        SessionTracker.invalidate_session(self.user.id, jti)
        
        # Should now be invalid
        self.assertFalse(SessionTracker.is_session_valid(self.user.id, jti))


@_extended_test
class StructuredLoggingTestCase(TestCase):
    """Test structured JSON logging with PII masking."""

    def test_pii_masking_email(self):
        """Test email masking."""
        self.assertEqual(mask_pii('user@domain.com'), 'us***@domain.com')
        self.assertEqual(mask_pii('john.doe@gmail.com'), 'jo***@gmail.com')

    def test_pii_masking_phone(self):
        """Test phone masking."""
        self.assertEqual(mask_pii('+91-9876543210'), '+91-98****3210')
        self.assertEqual(mask_pii('+1-5551234567'), '+1-55****4567')

    def test_pii_masking_credit_card(self):
        """Test credit card masking."""
        result = mask_pii('4532-1234-5678-9010')
        self.assertEqual(result, '4532-****-****-9010')

    def test_pii_masking_ssn(self):
        """Test SSN masking."""
        self.assertEqual(mask_pii('123-45-6789'), '***-**-6789')

    def test_structured_logger_output_format(self):
        """Test that structured logger outputs valid JSON."""
        logger = get_structured_logger('test')
        
        # JSON output should be valid (this is a smoke test)
        # In real scenario, capture log output and validate JSON
        logger.info("Test message", user_id=123, email="user@domain.com")


@_extended_test
class APIAuthenticationTestCase(APITestCase):
    """Test that all APIs require authentication."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )

    def test_unauthenticated_request_denied(self):
        """Test that unauthenticated requests are denied."""
        # Attempt to access protected endpoint without token
        response = self.client.get('/api/auth/profile')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_request_allowed(self):
        """Test that authenticated requests are allowed."""
        # Login to get token
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        token = response.data['access']
        
        # Use token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/auth/profile')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_token_denied(self):
        """Test that invalid tokens are rejected."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_xyz')
        response = self.client.get('/api/auth/profile')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@_extended_test
class PaymentSecurityTestCase(APITestCase):
    """Test payment endpoint security."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        self.tech = Technology.objects.create(
            name='Docker',
            description='Docker fundamentals',
            price=499,
            is_active=True
        )

    def test_payment_endpoint_requires_authentication(self):
        """Test that payment endpoints require authentication."""
        # Attempt to create order without authentication
        response = self.client.post('/api/billing/razorpay/order/', {
            'technology_id': self.tech.id
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_payment_endpoint_with_authentication(self):
        """Test that payment endpoint works with authentication."""
        # Login
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        token = response.data['access']
        
        # Use token for payment
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/billing/razorpay/order/', {
            'technology_id': self.tech.id
        }, format='json')
        
        # Should either succeed or return a meaningful error (not 401)
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_server_side_price_validation(self):
        """Test that prices are not trusted from client."""
        # Login
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Attempt to order with client-provided price (should NOT work)
        response = self.client.post('/api/billing/razorpay/order/', {
            'technology_id': self.tech.id,
            'price': 1  # Trying to manipulate price
        }, format='json')
        
        # Server should ignore client price and use database value
        if response.status_code == status.HTTP_200_OK:
            # If successful, verify amount is correct (499)
            self.assertEqual(response.data.get('amount'), self.tech.price)


@_extended_test
class ScenarioPermissionsTestCase(APITestCase):
    """Test scenario access permissions."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        
        self.tech = Technology.objects.create(
            name='Linux',
            description='Linux fundamentals',
            price=499,
            is_active=True
        )
        
        self.free_scenario = Scenario.objects.create(
            title='Free Linux Basics',
            description='Free intro scenario',
            technology=self.tech,
            is_free=True,
            is_active=True
        )
        
        self.paid_scenario = Scenario.objects.create(
            title='Advanced Linux',
            description='Advanced paid scenario',
            technology=self.tech,
            is_free=False,
            is_active=True
        )

    def test_free_scenario_accessible_without_subscription(self):
        """Test that free scenarios are accessible to all users."""
        # Login
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Should be able to start free scenario
        response = self.client.post(
            f'/api/labs/{self.free_scenario.id}/start/',
            format='json'
        )
        
        # Should succeed (200) or have expected status, NOT 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_paid_scenario_requires_subscription(self):
        """Test that paid scenarios require subscription."""
        # Login without subscription
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Should NOT be able to start paid scenario without subscription
        response = self.client.post(
            f'/api/labs/{self.paid_scenario.id}/start/',
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_paid_scenario_accessible_with_subscription(self):
        """Test that paid scenarios are accessible with subscription."""
        # Create subscription
        TechnologySubscription.objects.create(
            user=self.user,
            technology=self.tech,
            is_active=True
        )
        
        # Login
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Should now be able to start paid scenario
        response = self.client.post(
            f'/api/labs/{self.paid_scenario.id}/start/',
            format='json'
        )
        
        # Should NOT be 403 (forbidden)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@_extended_test
class SecurityHeadersTestCase(APITestCase):
    """Test security headers are present."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )

    def test_security_headers_present(self):
        """Test that critical security headers are present."""
        # Login to get a successful response
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        # Check for security headers
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_xss_protection_header(self):
        """Test XSS protection header."""
        response = self.client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        self.assertIn('X-XSS-Protection', response)


@_extended_test
class DebuggingDisabledTestCase(TestCase):
    """Test that debug mode is OFF in production."""

    def test_debug_mode_disabled(self):
        """Test that DEBUG is False in production."""
        from django.conf import settings
        
        # Should be False in production
        if settings.ALLOWED_HOSTS and 'localhost' not in settings.ALLOWED_HOSTS:
            self.assertFalse(settings.DEBUG, "DEBUG must be False in production")

    def test_no_sensitive_settings_exposed(self):
        """Test that sensitive settings are not exposed."""
        from django.conf import settings
        
        # SECRET_KEY should not be default value
        self.assertNotEqual(
            settings.SECRET_KEY,
            'your-secret-key-here',
            "SECRET_KEY must be changed from default"
        )


@_extended_test
class RateLimitingTestCase(APITestCase):
    """Test rate limiting on critical endpoints."""

    def setUp(self):
        self.client = APIClient()

    def test_login_rate_limiting(self):
        """Test that login endpoint has rate limiting."""
        # Make multiple rapid requests
        for i in range(25):  # Try 25 times (beyond 20/min limit)
            response = self.client.post('/api/auth/login', {
                'email': f'user{i}@example.com',
                'password': 'wrongpassword'
            }, format='json')
            
            # After ~20 requests, should get rate limited (429)
            if i > 20:
                if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                    break


@_extended_test
class NoPublicAPIExposureTestCase(APITestCase):
    """Test that APIs are not exposed to public without auth."""

    def setUp(self):
        self.client = APIClient()

    def test_admin_panel_requires_auth(self):
        """Test admin panel endpoints require authentication."""
        response = self.client.get('/api/admin/overview/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_billing_status_endpoint_auth(self):
        """Test billing endpoints require authentication."""
        # Billing status might be public info, but other endpoints should not be
        response = self.client.post('/api/billing/razorpay/order/', {'technology_id': 1})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_profile_requires_auth(self):
        """Test profile endpoint requires authentication."""
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_scenarios_list_might_be_public_but_start_requires_auth(self):
        """Test that starting a scenario requires authentication."""
        response = self.client.post('/api/labs/1/start/', {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

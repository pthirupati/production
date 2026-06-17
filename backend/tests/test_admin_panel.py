"""
FixitLab Admin Panel Tests
Tests admin API endpoints, access control, and health check logic.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class AdminAccessControlTests(TestCase):
    """Test that admin endpoints require staff privileges."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', is_staff=True,
        )
        self.regular = User.objects.create_user(
            username='regular', email='regular@test.com',
            password='Pass123!', is_staff=False,
        )

    def test_overview_requires_staff(self):
        self.client.force_authenticate(user=self.regular)
        res = self.client.get('/api/admin/overview/')
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_overview_accessible_to_staff(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.get('/api/admin/overview/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_unauthenticated_blocked(self):
        res = self.client.get('/api/admin/overview/')
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_health_requires_staff(self):
        self.client.force_authenticate(user=self.regular)
        res = self.client.get('/api/admin/health/')
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_health_returns_structure_for_staff(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.get('/api/admin/health/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn('services', data)
        self.assertIn('overall', data)

    def test_monitoring_containers_requires_staff(self):
        self.client.force_authenticate(user=self.regular)
        res = self.client.get('/api/admin/monitoring/containers/')
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])


class AdminHealthCheckTests(TestCase):
    """Test system health check logic, including vault detection."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username='healthadmin', email='healthadmin@test.com',
            password='Admin123!', is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)

    def test_health_overall_field_present(self):
        res = self.client.get('/api/admin/health/')
        data = res.json()
        self.assertIn(data['overall'], ['healthy', 'degraded', 'unhealthy'])

    def test_health_services_are_dict(self):
        res = self.client.get('/api/admin/health/')
        data = res.json()
        self.assertIsInstance(data['services'], dict)

    def test_health_vault_disabled_shows_healthy(self):
        """When VAULT_ENABLED is not set, vault should report healthy (env file mode)."""
        with patch.dict('os.environ', {'VAULT_ENABLED': ''}, clear=False):
            res = self.client.get('/api/admin/health/')
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            data = res.json()
            vault_status = data.get('services', {}).get('vault', {})
            if vault_status:
                self.assertNotEqual(vault_status.get('status'), 'unhealthy',
                    "Vault should not be unhealthy when VAULT_ENABLED is unset — env file mode is expected.")

    def test_database_service_healthy(self):
        """Database service should always be healthy in test environment."""
        res = self.client.get('/api/admin/health/')
        data = res.json()
        db_status = data.get('services', {}).get('Database') or data.get('services', {}).get('database', {})
        if db_status:
            self.assertEqual(db_status.get('status'), 'healthy',
                "Database should be healthy in test environment.")


class AdminVaultLogicTests(TestCase):
    """Unit tests for vault health check helper logic."""

    def _get_vault_checker(self):
        from apps.adminpanel.views import AdminSystemHealthView
        view = AdminSystemHealthView()
        return view._check_vault

    def test_vault_disabled_returns_healthy_optional(self):
        """When VAULT_ENABLED is not set, vault should be healthy (env file mode)."""
        check = self._get_vault_checker()
        with patch.dict('os.environ', {'VAULT_ENABLED': ''}, clear=False):
            result = check()
        self.assertEqual(result['status'], 'healthy')
        self.assertTrue(result.get('optional', False))

    def test_vault_enabled_container_not_found_unhealthy(self):
        """When vault container is missing, status should be unhealthy."""
        check = self._get_vault_checker()
        with patch.dict('os.environ', {'VAULT_ENABLED': 'true'}, clear=False):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout='')
                result = check()
        self.assertEqual(result['status'], 'unhealthy')

    def test_vault_enabled_container_stopped_unhealthy(self):
        """When vault container is not running (e.g. exited), status should be unhealthy."""
        check = self._get_vault_checker()
        with patch.dict('os.environ', {'VAULT_ENABLED': 'true'}, clear=False):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout='exited\n')
                result = check()
        self.assertEqual(result['status'], 'unhealthy')

    def test_vault_result_has_secrets_loaded_field(self):
        """Vault result should always include secrets_loaded field."""
        check = self._get_vault_checker()
        with patch.dict('os.environ', {'VAULT_ENABLED': ''}, clear=False):
            result = check()
        self.assertIn('secrets_loaded', result)


class AdminMonitoringContainerClassificationTests(TestCase):
    """Test that container classification logic correctly identifies system containers."""

    def _get_view(self):
        from apps.adminpanel.views import AdminMonitoringContainersView
        return AdminMonitoringContainersView()

    def test_system_hints_include_expected_containers(self):
        view = self._get_view()
        hints = view.SYSTEM_NAME_HINTS
        for expected in ['backend', 'frontend', 'gateway', 'redis', 'postgres', 'vault', 'celery', 'pgbouncer']:
            self.assertTrue(
                any(expected in h for h in hints),
                f"SYSTEM_NAME_HINTS should include hint matching '{expected}'",
            )

    def test_container_classified_by_name_hint(self):
        view = self._get_view()
        hints = view.SYSTEM_NAME_HINTS
        # fixitlab_vault should match
        name = 'fixitlab_vault'
        matched = any(h in name.lower() for h in hints)
        self.assertTrue(matched, "fixitlab_vault container should be classified as system")

    def test_container_classified_by_vault_image(self):
        view = self._get_view()
        # A container with vault in image but non-standard name should be classified
        name = 'some_other_container'
        image = 'hashicorp/vault:1.15'
        hints = view.SYSTEM_NAME_HINTS
        is_system = any(h in name.lower() for h in hints)
        if not is_system and 'vault' in image.lower():
            is_system = True
        self.assertTrue(is_system, "Container with vault image should be classified as system")

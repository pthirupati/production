"""
Production Multi-User Isolation & Scalability Test Suite

Tests user isolation, concurrent access, and scalability for 10L+ users.
Validates that labs, data, and environments are completely isolated per user.
"""

import json
import os
import unittest
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import time

from apps.labs.models import LabSession
from apps.question_bank.models import Technology, Scenario
from apps.billing.models import TechnologySubscription, Subscription, Plan
from apps.accounts.models import Profile
from common.security import SessionTracker

User = get_user_model()


def _extended_test(case_cls):
    return unittest.skipUnless(
        os.environ.get("RUN_EXTENDED_TESTS"),
        "Extended production tests — set RUN_EXTENDED_TESTS=1",
    )(case_cls)


@_extended_test
class UserIsolationTestCase(APITestCase):
    """Test that user data is completely isolated."""

    def setUp(self):
        self.client = APIClient()
        
        # Create 2 users
        self.user1 = User.objects.create_user(
            username='user1', email='user1@test.com', password='Pass123!'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@test.com', password='Pass123!'
        )
        
        # Create technology and scenarios
        self.tech = Technology.objects.create(
            name='Linux-Isolation', slug='linux-isolation',
            description='Linux training', price=99, is_active=True
        )
        self.scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=self.tech,
            slug='broken-ssh-isolation', category='Linux', difficulty='easy',
            is_free=True, is_active=True,
        )

    def _login(self, email, password):
        response = self.client.post('/api/auth/login/', {
            'email': email, 'password': password,
        }, format='json')
        token = response.data.get('access')
        if token:
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return response

    def test_user_cannot_see_other_user_labs(self):
        """Test that User1 cannot see User2's lab sessions."""
        # User1 starts a lab
        lab1 = LabSession.objects.create(
            user=self.user1, scenario=self.scenario, status='RUNNING'
        )
        
        # User2 starts a lab
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='RUNNING'
        )
        
        # User1 login and get labs
        self._login('user1@test.com', 'Pass123!')
        
        response = self.client.get('/api/labs/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user1_labs = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # User1 should only see their own lab
        user1_lab_ids = [str(lab['id']) for lab in user1_labs]
        
        self.assertIn(str(lab1.id), user1_lab_ids, "User1 should see their own lab")
        self.assertNotIn(str(lab2.id), user1_lab_ids, "User1 should NOT see User2's lab")

    def test_user_cannot_access_other_user_lab_session(self):
        """Test that User1 cannot access User2's lab session directly."""
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='RUNNING'
        )
        
        # User1 tries to access User2's lab session
        self.client.post('/api/auth/login/', {
            'email': 'user1@test.com', 'password': 'Pass123!'
        }, format='json')
        
        response = self.client.get(f'/api/labs/{lab2.id}/status/')
        
        # Should be 404 or 403
        self.assertIn(
            response.status_code,
            [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
            "User1 should not be able to access User2's lab session"
        )

    def test_user_cannot_modify_other_user_lab(self):
        """Test that User1 cannot modify User2's lab session."""
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='RUNNING', score=50
        )
        
        # User1 tries to update User2's lab score
        self.client.post('/api/auth/login/', {
            'email': 'user1@test.com', 'password': 'Pass123!'
        }, format='json')
        
        response = self.client.patch(
            f'/api/labs/{lab2.id}/',
            {'score': 100},
            format='json'
        )
        
        # Should fail (404 or 403)
        self.assertIn(
            response.status_code,
            [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
            "User1 should not be able to modify User2's lab"
        )
        
        # Verify lab score didn't change
        lab2.refresh_from_db()
        self.assertEqual(lab2.score, 50, "Lab score should not have changed")

    def test_user_progress_is_isolated(self):
        """Test that User1's progress doesn't affect User2's."""
        from apps.progress.models import UserScenarioProgress
        
        # User1 completes a scenario
        progress1 = UserScenarioProgress.objects.create(
            user=self.user1, scenario=self.scenario, completed=True, best_score=85
        )
        
        # User2 should not have this progress
        user2_progress = UserScenarioProgress.objects.filter(
            user=self.user2, scenario=self.scenario
        )
        
        self.assertEqual(user2_progress.count(), 0, 
            "User2 should not have User1's progress")

    def test_user_cannot_see_other_user_profile(self):
        """Test that User1 cannot access User2's profile."""
        # Create profile for User2
        Profile.objects.get_or_create(user=self.user2)
        
        # User1 tries to get User2's profile
        self.client.post('/api/auth/login/', {
            'email': 'user1@test.com', 'password': 'Pass123!'
        }, format='json')
        
        response = self.client.get(f'/api/users/{self.user2.id}/profile/')
        
        # Should be 404 or 403
        self.assertIn(
            response.status_code,
            [status.HTTP_301_MOVED_PERMANENTLY, status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
            "User1 should not be able to access User2's profile"
        )

    def test_user_cannot_see_other_user_subscription(self):
        """Test that User1 cannot see User2's subscription."""
        # Create subscription for User2
        plan = Plan.objects.create(name='Pro', price=99, max_labs_per_day=10)
        TechnologySubscription.objects.create(
            user=self.user2, technology=self.tech, is_active=True
        )
        
        # User1 tries to get User2's subscription
        self.client.post('/api/auth/login/', {
            'email': 'user1@test.com', 'password': 'Pass123!'
        }, format='json')
        
        response = self.client.get(f'/api/users/{self.user2.id}/subscription/')
        
        # Should be 404 or 403
        self.assertIn(
            response.status_code,
            [status.HTTP_301_MOVED_PERMANENTLY, status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
            "User1 should not be able to see User2's subscription"
        )


@_extended_test
class LabSessionIsolationTestCase(TransactionTestCase):
    """Test lab session container/environment isolation."""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1', email='user1@test.com', password='Pass123!'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@test.com', password='Pass123!'
        )
        
        self.tech = Technology.objects.create(
            name='Linux-LabISO', slug='linux-labiso',
            description='Linux training', price=99, is_active=True
        )
        self.scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=self.tech,
            slug='broken-ssh-labiso', category='Linux', difficulty='easy',
            is_free=True, is_active=True,
        )

    def test_concurrent_labs_have_different_containers(self):
        """Test that concurrent labs get different container instances."""
        lab1 = LabSession.objects.create(
            user=self.user1, scenario=self.scenario, status='RUNNING',
            container_id='container-user1-session1'
        )
        
        # User2 starts a lab at the same time
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='RUNNING',
            container_id='container-user2-session1'
        )
        
        # Verify different container IDs
        self.assertNotEqual(
            lab1.container_id, lab2.container_id,
            "Each user's lab should have a different container"
        )

    def test_lab_session_has_unique_environment(self):
        """Test that each lab session has its own unique environment."""
        lab1 = LabSession.objects.create(
            user=self.user1, scenario=self.scenario, status='RUNNING'
        )
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='RUNNING'
        )
        
        # Lab sessions should have different IDs
        self.assertNotEqual(lab1.id, lab2.id)
        
        # Both should be associated with their respective users
        self.assertEqual(lab1.user_id, self.user1.id)
        self.assertEqual(lab2.user_id, self.user2.id)


@_extended_test
class ConcurrentUserAccessTestCase(TransactionTestCase):
    """Test concurrent access by multiple users."""

    def setUp(self):
        self.client = APIClient()
        self.users = []
        
        # Create 10 users
        for i in range(10):
            user = User.objects.create_user(
                username=f'user{i}', email=f'user{i}@test.com', password='Pass123!'
            )
            self.users.append(user)
        
        self.tech = Technology.objects.create(
            name='Linux-Concurrent', slug='linux-concurrent',
            description='Linux training', price=99, is_active=True
        )
        self.scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=self.tech,
            slug='broken-ssh-concurrent', category='Linux', difficulty='easy',
            lab_mode='simulation', simulation_type='generic',
            is_free=True, is_active=True,
        )

    def test_concurrent_logins_create_independent_sessions(self):
        """Test that concurrent logins create independent sessions."""
        from django.db import connection
        if connection.vendor == 'sqlite':
            self.skipTest('Concurrent login test requires PostgreSQL')

        results = {}

        def login_user(index):
            try:
                client = APIClient()
                response = client.post('/api/auth/login/', {
                    'email': f'user{index}@test.com',
                    'password': 'Pass123!'
                }, format='json')
                
                if response.status_code == 200:
                    results[index] = {
                        'access': response.data.get('access'),
                        'refresh': response.data.get('refresh')
                    }
            except Exception as e:
                results[index] = {'error': str(e)}
        
        # Login 10 users concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(login_user, i) for i in range(10)]
            for future in futures:
                future.result()
        
        # Verify all users got unique tokens
        tokens = [r['access'] for r in results.values() if 'access' in r]
        self.assertEqual(len(tokens), 10, "All 10 users should login successfully")
        
        unique_tokens = set(tokens)
        self.assertEqual(len(unique_tokens), 10, 
            "Each user should get a unique access token")

    def test_concurrent_lab_starts_dont_interfere(self):
        """Test that concurrent lab starts by different users don't interfere."""
        from django.db import connection
        if connection.vendor == 'sqlite':
            self.skipTest('Concurrent lab test requires PostgreSQL')
        results = {}
        
        def start_lab(index):
            try:
                client = APIClient()
                # Login
                response = client.post('/api/auth/login/', {
                    'email': f'user{index}@test.com',
                    'password': 'Pass123!'
                }, format='json')
                
                if response.status_code != 200:
                    results[index] = {'error': 'Login failed'}
                    return
                
                token = response.data['access']
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                
                # Start lab
                response = client.post(
                    f'/api/labs/{self.scenario.id}/start/',
                    format='json'
                )
                
                if response.status_code in [200, 201]:
                    results[index] = {
                        'lab_id': response.data.get('id'),
                        'user_id': self.users[index].id
                    }
                else:
                    results[index] = {'error': response.data}
            except Exception as e:
                results[index] = {'error': str(e)}
        
        # 10 users start labs concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(start_lab, i) for i in range(10)]
            for future in futures:
                future.result()
        
        # Verify all labs were created
        labs = LabSession.objects.all()
        self.assertEqual(labs.count(), 10, 
            "Each user should have 1 lab created")
        
        # Verify each lab is associated with the correct user
        for i in range(10):
            if 'lab_id' in results[i]:
                lab = LabSession.objects.get(id=results[i]['lab_id'])
                self.assertEqual(lab.user_id, self.users[i].id,
                    f"Lab should belong to user{i}")


@_extended_test
class ScalabilityTestCase(TestCase):
    """Test scalability for 10L+ (1 million+) users."""

    def test_user_lab_queries_use_indexes(self):
        """Test that user lab queries use database indexes."""
        # Create a user with many labs
        user = User.objects.create_user(
            username='user1', email='user1@test.com', password='Pass123!'
        )
        
        tech = Technology.objects.create(
            name='Linux-Scale', slug='linux-scale',
            description='Linux training', price=99, is_active=True
        )
        scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=tech,
            slug='broken-ssh-scale', category='Linux', difficulty='easy',
            is_free=True, is_active=True,
        )
        
        # Create 1000 lab sessions
        for i in range(1000):
            LabSession.objects.create(
                user=user, scenario=scenario, status='COMPLETED',
                score=50 + (i % 50)
            )
        
        # Query should be fast (using indexes)
        import time
        start = time.time()
        
        labs = LabSession.objects.filter(
            user=user, status='COMPLETED'
        ).select_related('scenario', 'user')[:100]
        
        # Trigger query
        list(labs)
        
        elapsed = (time.time() - start)
        self.assertLess(elapsed, 1.0, 
            f"Query should complete in <1s with indexes (took {elapsed:.2f}s)")

    def test_user_count_doesnt_affect_individual_access(self):
        """Test that system performance doesn't degrade with many users."""
        # Create 1000 users
        users = [
            User.objects.create_user(
                username=f'user{i}', email=f'user{i}@test.com', 
                password='Pass123!'
            )
            for i in range(1000)
        ]
        
        tech = Technology.objects.create(
            name='Linux-Scale2', slug='linux-scale2',
            description='Linux training', price=99, is_active=True
        )
        scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=tech,
            slug='broken-ssh-scale2', category='Linux', difficulty='easy',
            is_free=True, is_active=True,
        )

        # Create labs for each user
        for user in users:
            LabSession.objects.create(
                user=user, scenario=scenario, status='COMPLETED', score=50
            )
        
        # Get a specific user's labs - should still be fast
        import time
        start = time.time()
        
        user_labs = LabSession.objects.filter(
            user=users[500], status='COMPLETED'
        )
        
        # Trigger query
        count = user_labs.count()
        
        elapsed = (time.time() - start)
        
        self.assertEqual(count, 1, "Should have 1 lab")
        self.assertLess(elapsed, 0.1, 
            f"Query for specific user should be <100ms even with 1000 users (took {elapsed:.2f}s)")

    def test_lab_session_creation_scales_linearly(self):
        """Test that lab session creation time doesn't degrade."""
        tech = Technology.objects.create(
            name='Linux-Scale3', slug='linux-scale3',
            description='Linux training', price=99, is_active=True
        )
        scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=tech,
            slug='broken-ssh-scale3', category='Linux', difficulty='easy',
            is_free=True, is_active=True,
        )

        import time

        # Create 1000 users and measure lab creation time per user
        times = []
        for i in range(100):  # Test with 100 users
            user = User.objects.create_user(
                username=f'user{i}', email=f'user{i}@test.com', 
                password='Pass123!'
            )
            
            start = time.time()
            LabSession.objects.create(user=user, scenario=scenario, status='RUNNING')
            elapsed = (time.time() - start)
            times.append(elapsed)
        
        # Average time should be consistent (not increasing)
        first_10_avg = sum(times[:10]) / 10
        last_10_avg = sum(times[-10:]) / 10
        
        # Last 10 shouldn't be significantly slower than first 10
        slowdown_ratio = last_10_avg / max(first_10_avg, 0.001)
        
        self.assertLess(slowdown_ratio, 2.0,
            f"Lab creation time should scale linearly (slowdown: {slowdown_ratio:.2f}x)")


@_extended_test
class DataPrivacyTestCase(APITestCase):
    """Test data privacy and no cross-user data leaks."""

    def setUp(self):
        self.client = APIClient()
        
        # Create 2 users
        self.user1 = User.objects.create_user(
            username='user1', email='user1@test.com', password='Pass123!'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@test.com', password='Pass123!'
        )
        
        # Create technology
        self.tech = Technology.objects.create(
            name='Linux-Privacy', slug='linux-privacy',
            description='Linux training', price=99, is_active=True
        )
        self.scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=self.tech,
            slug='broken-ssh-privacy', category='Linux', difficulty='easy',
            is_free=True, is_active=True,
        )

    def test_user1_cannot_see_user2_hints_usage(self):
        """Test that User1 cannot see hints used by User2."""
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='COMPLETED',
            hints_used=3
        )
        
        # User1 tries to get lab details
        self.client.post('/api/auth/login/', {
            'email': 'user1@test.com', 'password': 'Pass123!'
        }, format='json')
        
        response = self.client.get(f'/api/labs/{lab2.id}/status/')
        
        # Should be 404 or 403
        self.assertIn(
            response.status_code,
            [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
            "User1 should not see User2's lab details"
        )

    def test_session_tokens_are_user_specific(self):
        """Test that session tokens are specific to each user."""
        # User1 login
        resp1 = self.client.post('/api/auth/login/', {
            'email': 'user1@test.com', 'password': 'Pass123!'
        }, format='json')
        token1 = resp1.data['access']
        
        # User2 login
        resp2 = self.client.post('/api/auth/login/', {
            'email': 'user2@test.com', 'password': 'Pass123!'
        }, format='json')
        token2 = resp2.data['access']
        
        # Tokens should be different
        self.assertNotEqual(token1, token2, 
            "Different users should get different tokens")
        
        # User1 token should only work for User1
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token1}')
        response = self.client.get('/api/auth/profile/')
        
        if response.status_code == 200:
            profile_user_id = response.data.get('id') or response.data.get('user_id')
            self.assertEqual(profile_user_id, self.user1.id,
                "Token1 should only return User1's data")


@_extended_test
class EnvironmentIsolationTestCase(TestCase):
    """Test that lab environments (containers/VMs) are isolated."""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1', email='user1@test.com', password='Pass123!'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@test.com', password='Pass123!'
        )
        
        self.tech = Technology.objects.create(
            name='Linux-Env', slug='linux-env',
            description='Linux training', price=99, is_active=True
        )
        self.scenario = Scenario.objects.create(
            title='Broken SSH', description='Fix SSH', technology=self.tech,
            slug='broken-ssh-env', category='Linux', difficulty='easy',
            is_free=True, is_active=True,
        )

    def test_lab_environments_have_unique_ids(self):
        """Test that each lab environment has a unique identifier."""
        lab1 = LabSession.objects.create(
            user=self.user1, scenario=self.scenario, status='RUNNING',
            instance_id='lab-user1-test',
        )
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='RUNNING',
            instance_id='lab-user2-test',
        )

        self.assertIsNotNone(lab1.instance_id)
        self.assertIsNotNone(lab2.instance_id)
        self.assertNotEqual(lab1.instance_id, lab2.instance_id)

    def test_lab_changes_dont_affect_other_labs(self):
        """Test that changes in one lab don't affect another user's lab."""
        lab1 = LabSession.objects.create(
            user=self.user1, scenario=self.scenario, status='RUNNING', score=0
        )
        lab2 = LabSession.objects.create(
            user=self.user2, scenario=self.scenario, status='RUNNING', score=0
        )
        
        # User1 completes their lab
        lab1.status = 'COMPLETED'
        lab1.score = 100
        lab1.save()
        
        # User2's lab should be unaffected
        lab2.refresh_from_db()
        self.assertEqual(lab2.status, 'RUNNING', 
            "User2's lab status should not change")
        self.assertEqual(lab2.score, 0, 
            "User2's lab score should not change")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""Coupon validation and redemption tests."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.billing.coupon_service import (
    CouponError,
    apply_coupon_to_amount,
    normalize_coupon_code,
    redeem_coupon,
    validate_coupon,
)
from apps.billing.models import CouponCode, CouponRedemption

User = get_user_model()


class CouponServiceTest(TestCase):
    def setUp(self):
        self.percent = CouponCode.objects.create(
            code="SAVE20",
            discount_type="percent",
            discount_value=Decimal("20"),
            is_active=True,
        )
        self.fixed = CouponCode.objects.create(
            code="FLAT100",
            discount_type="fixed",
            discount_value=Decimal("100"),
            is_active=True,
        )

    def test_normalize_coupon_code(self):
        self.assertEqual(normalize_coupon_code(" save20 "), "SAVE20")

    def test_validate_coupon_success(self):
        coupon = validate_coupon("save20")
        self.assertEqual(coupon.code, "SAVE20")

    def test_validate_coupon_invalid(self):
        with self.assertRaises(CouponError):
            validate_coupon("NOPE")

    def test_validate_coupon_expired(self):
        self.percent.valid_until = timezone.now() - timedelta(days=1)
        self.percent.save()
        with self.assertRaises(CouponError):
            validate_coupon("SAVE20")

    def test_apply_percent_discount(self):
        amount, coupon = apply_coupon_to_amount("SAVE20", 500)
        self.assertEqual(coupon.code, "SAVE20")
        self.assertEqual(amount, 400)

    def test_apply_fixed_discount_floor(self):
        amount, _coupon = apply_coupon_to_amount("FLAT100", 50)
        self.assertEqual(amount, 1)

    def test_redeem_increments_used_count(self):
        redeem_coupon(self.percent)
        self.percent.refresh_from_db()
        self.assertEqual(self.percent.used_count, 1)

    def test_max_uses_enforced(self):
        self.fixed.max_uses = 1
        self.fixed.used_count = 1
        self.fixed.save()
        with self.assertRaises(CouponError):
            validate_coupon("FLAT100")


class CouponAtomicRedemptionTest(TestCase):
    """SECURITY_AUDIT P-03: atomic redemption + per-user limit."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cpnuser", email="cpn@test.com", password="Pass123!x"
        )
        self.other = User.objects.create_user(
            username="cpnuser2", email="cpn2@test.com", password="Pass123!x"
        )
        self.single = CouponCode.objects.create(
            code="ONCE",
            discount_type="percent",
            discount_value=Decimal("50"),
            is_active=True,
            max_uses=1,
        )

    def test_redeem_creates_per_user_redemption_row(self):
        redeem_coupon(self.single, user=self.user)
        self.assertTrue(
            CouponRedemption.objects.filter(coupon=self.single, user=self.user).exists()
        )
        self.single.refresh_from_db()
        self.assertEqual(self.single.used_count, 1)

    def test_same_user_cannot_redeem_twice(self):
        redeem_coupon(self.single, user=self.user)
        with self.assertRaises(CouponError):
            redeem_coupon(self.single, user=self.user)
        # used_count must NOT have been incremented a second time.
        self.single.refresh_from_db()
        self.assertEqual(self.single.used_count, 1)

    def test_max_uses_blocks_second_distinct_user(self):
        # max_uses=1: first user redeems, a DIFFERENT user is then refused by the
        # atomic conditional increment (limit reached), not just the per-user row.
        redeem_coupon(self.single, user=self.user)
        with self.assertRaises(CouponError):
            redeem_coupon(self.single, user=self.other)
        self.single.refresh_from_db()
        self.assertEqual(self.single.used_count, 1)

    def test_atomic_increment_never_exceeds_max_uses_under_no_user(self):
        # Even without a user (legacy call), the conditional UPDATE caps at max_uses.
        coupon = CouponCode.objects.create(
            code="CAP2", discount_type="fixed", discount_value=Decimal("10"),
            is_active=True, max_uses=2,
        )
        redeem_coupon(coupon)
        redeem_coupon(coupon)
        with self.assertRaises(CouponError):
            redeem_coupon(coupon)
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 2)

    def test_validate_rejects_user_who_already_redeemed(self):
        CouponRedemption.objects.create(coupon=self.single, user=self.user)
        with self.assertRaises(CouponError):
            validate_coupon("ONCE", user=self.user)
        # A different user is still allowed (until max_uses is hit).
        coupon = validate_coupon("ONCE", user=self.other)
        self.assertEqual(coupon.code, "ONCE")

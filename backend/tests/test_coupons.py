"""Coupon validation and redemption tests."""
from decimal import Decimal

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
from apps.billing.models import CouponCode


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

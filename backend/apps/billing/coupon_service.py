"""Coupon validation and discount application."""

from __future__ import annotations

from django.utils import timezone

from .models import CouponCode


class CouponError(Exception):
    pass


def normalize_coupon_code(code: str) -> str:
    return (code or "").strip().upper()


def validate_coupon(code: str) -> CouponCode:
    normalized = normalize_coupon_code(code)
    if not normalized:
        raise CouponError("Coupon code is required")

    coupon = CouponCode.objects.filter(code__iexact=normalized).first()
    if not coupon:
        raise CouponError("Invalid coupon code")
    if not coupon.is_valid_now():
        raise CouponError("This coupon is expired or no longer active")
    return coupon


def apply_coupon_to_amount(code: str, amount_inr: int) -> tuple[int, CouponCode]:
    coupon = validate_coupon(code)
    discounted = coupon.apply_to_amount(amount_inr)
    return discounted, coupon


def redeem_coupon(coupon: CouponCode) -> None:
    coupon.used_count += 1
    coupon.save(update_fields=["used_count", "updated_at"])

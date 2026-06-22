"""Coupon validation and discount application."""

from __future__ import annotations

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from .models import CouponCode, CouponRedemption


class CouponError(Exception):
    pass


def normalize_coupon_code(code: str) -> str:
    return (code or "").strip().upper()


def validate_coupon(code: str, user=None) -> CouponCode:
    normalized = normalize_coupon_code(code)
    if not normalized:
        raise CouponError("Coupon code is required")

    coupon = CouponCode.objects.filter(code__iexact=normalized).first()
    if not coupon:
        raise CouponError("Invalid coupon code")
    if not coupon.is_valid_now():
        raise CouponError("This coupon is expired or no longer active")
    # SECURITY_AUDIT P-03: enforce one redemption per user. Checked at
    # order-create/preview time when a user is known so the UI can surface it
    # early; the DB unique constraint in redeem_coupon is the authoritative,
    # race-proof guard at fulfilment time.
    if user is not None and getattr(user, "id", None) is not None:
        if CouponRedemption.objects.filter(coupon=coupon, user=user).exists():
            raise CouponError("You have already used this coupon")
    return coupon


def apply_coupon_to_amount(code: str, amount_inr: int, user=None) -> tuple[int, CouponCode]:
    coupon = validate_coupon(code, user=user)
    discounted = coupon.apply_to_amount(amount_inr)
    return discounted, coupon


def redeem_coupon(coupon: CouponCode, user=None) -> None:
    """Atomically consume one use of ``coupon`` for ``user``.

    SECURITY_AUDIT P-03 — race-safe redemption. The previous implementation did
    a read-modify-write (``used_count += 1; save()``) with no lock, so N
    concurrent fulfilments all read the same ``used_count`` and a ``max_uses=1``
    coupon could be redeemed many times (lost update). Two fixes:

      1. A single conditional ``UPDATE ... SET used_count = used_count + 1 WHERE
         max_uses IS NULL OR used_count < max_uses`` — atomic at the DB level, so
         the limit can never be exceeded regardless of concurrency.
      2. A per-user ``CouponRedemption`` row guarded by a unique constraint, so
         the same user can't redeem the same coupon twice (idempotent).

    Raises ``CouponError`` if the usage limit is reached or the user already
    redeemed this coupon. Callers redeem only AFTER a payment is verified, so a
    raise here means "don't double-count", not "fail the payment".
    """
    with transaction.atomic():
        # Per-user uniqueness first (cheap, and the common abuse vector).
        if user is not None and getattr(user, "id", None) is not None:
            try:
                CouponRedemption.objects.create(coupon=coupon, user=user)
            except IntegrityError:
                raise CouponError("You have already used this coupon")

        # Atomic conditional increment — never exceeds max_uses.
        updated = (
            CouponCode.objects.filter(pk=coupon.pk)
            .filter(
                models.Q(max_uses__isnull=True)
                | models.Q(used_count__lt=models.F("max_uses"))
            )
            .update(used_count=models.F("used_count") + 1, updated_at=timezone.now())
        )
        if not updated:
            # Limit reached. The transaction (incl. the CouponRedemption row, if
            # any) is rolled back by the raised exception.
            raise CouponError("Coupon usage limit reached")

"""Server-authoritative Indian GST computation for paid subscriptions/orders.

PRODUCTION_AUDIT FIN-01. A registered Indian seller must compute GST server-side
and itemise it on a tax invoice (intra-state = CGST + SGST, inter-state = IGST).
The client must never influence price or tax — every figure here is derived from
the server-side catalog price and the ``GST_RATE`` / ``GST_ENABLED`` settings.

Pricing model: the catalog ``technology.price`` (an INR integer) is treated as
the GST-INCLUSIVE total the customer sees and pays. GST is *extracted* from that
total (tax-inclusive pricing), so the Razorpay order amount always equals the
displayed total and the customer is never charged more than the sticker price.
The taxable (pre-tax) value and the tax component are derived as:

    taxable = total / (1 + rate)
    tax     = total - taxable

All money math uses :class:`~decimal.Decimal`; there is no float anywhere in the
tax path. Amounts are quantised to 2 decimal places (paise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

# Two-paise precision for all monetary values.
_CENTS = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    """Quantise to 2 dp (paise) with banker-safe half-up rounding."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def gst_rate() -> Decimal:
    """Combined GST rate as a Decimal fraction (e.g. ``Decimal('0.18')``)."""
    rate = getattr(settings, "GST_RATE", Decimal("0.18"))
    if not isinstance(rate, Decimal):
        rate = Decimal(str(rate))
    return rate


def gst_should_charge() -> bool:
    """Whether GST is actually levied on orders.

    Gated on BOTH ``GST_ENABLED`` and a configured ``BUSINESS_GSTIN`` — you
    cannot legally levy GST without a registration, so a missing GSTIN means we
    price at the bare amount with zero tax (safe pre-registration default). The
    schema + breakup still exist so enabling GST later is a settings flip.
    """
    if not getattr(settings, "GST_ENABLED", False):
        return False
    return bool((getattr(settings, "BUSINESS_GSTIN", "") or "").strip())


@dataclass(frozen=True)
class GstBreakup:
    """Immutable, server-computed tax breakup for one order/invoice.

    ``total_amount`` is the GST-inclusive amount the customer pays and the value
    that must be sent to Razorpay (``total_amount * 100`` paise). ``taxable_amount``
    + ``gst_amount`` == ``total_amount`` exactly.
    """

    total_amount: Decimal          # GST-inclusive total the customer pays
    taxable_amount: Decimal        # pre-tax value
    gst_amount: Decimal            # total tax (cgst + sgst, or igst)
    gst_rate: Decimal              # fraction applied (0 when not charged)
    cgst_amount: Decimal = field(default=Decimal("0.00"))
    sgst_amount: Decimal = field(default=Decimal("0.00"))
    igst_amount: Decimal = field(default=Decimal("0.00"))
    is_inter_state: bool = False
    place_of_supply: str = ""
    gstin: str = ""

    @property
    def total_paise(self) -> int:
        """GST-inclusive total in paise — exactly what the Razorpay order uses."""
        return int((self.total_amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_gst(total_inclusive_inr, place_of_supply: str = "") -> GstBreakup:
    """Compute the GST breakup for a GST-inclusive INR total.

    ``total_inclusive_inr`` is the server-side price (catalog price, post-coupon)
    — the GST-inclusive amount the customer sees and pays.

    When ``gst_should_charge()`` is False (GST disabled or no GSTIN) the breakup
    is the full amount as ``taxable_amount`` with zero tax, so the total is
    unchanged and downstream code is uniform.

    Place of supply: if the customer's state differs from ``BUSINESS_STATE`` the
    supply is inter-state → a single IGST. Otherwise intra-state → CGST + SGST
    (each half the rate). When no customer state is supplied we default to the
    seller's state (intra-state).
    """
    total = _q(Decimal(str(total_inclusive_inr)))

    if not gst_should_charge() or total <= 0:
        return GstBreakup(
            total_amount=total,
            taxable_amount=total,
            gst_amount=Decimal("0.00"),
            gst_rate=Decimal("0"),
            place_of_supply=(place_of_supply or getattr(settings, "BUSINESS_STATE", "") or "").strip(),
            gstin=(getattr(settings, "BUSINESS_GSTIN", "") or "").strip(),
        )

    rate = gst_rate()
    # Tax-inclusive extraction: taxable = total / (1 + rate); tax = total - taxable.
    taxable = _q(total / (Decimal("1") + rate))
    tax = _q(total - taxable)  # keeps taxable + tax == total exactly

    seller_state = (getattr(settings, "BUSINESS_STATE", "") or "").strip()
    customer_state = (place_of_supply or "").strip()
    pos = customer_state or seller_state
    # Inter-state only when we positively know the customer is in a different
    # state from the seller; missing data defaults to intra-state (CGST+SGST).
    is_inter_state = bool(seller_state and customer_state and customer_state.lower() != seller_state.lower())

    if is_inter_state:
        igst = tax
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
    else:
        # Split the (already-rounded) total tax so cgst + sgst == tax exactly.
        cgst = _q(tax / Decimal("2"))
        sgst = _q(tax - cgst)
        igst = Decimal("0.00")

    return GstBreakup(
        total_amount=total,
        taxable_amount=taxable,
        gst_amount=tax,
        gst_rate=rate,
        cgst_amount=cgst,
        sgst_amount=sgst,
        igst_amount=igst,
        is_inter_state=is_inter_state,
        place_of_supply=pos,
        gstin=(getattr(settings, "BUSINESS_GSTIN", "") or "").strip(),
    )

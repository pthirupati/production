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


def _platform():
    """Admin-editable PlatformSettings singleton, or None if unavailable.

    Lets the owner enable GST / set the GSTIN from the admin panel without a
    redeploy. DB values win when present; otherwise we fall back to the env
    settings (the original behaviour), so nothing breaks pre-migration.
    """
    try:
        from apps.adminpanel.models import PlatformSettings
        return PlatformSettings.objects.first()
    except Exception:
        return None


def _gstin() -> str:
    ps = _platform()
    if ps is not None and (ps.business_gstin or "").strip():
        return ps.business_gstin.strip()
    return (getattr(settings, "BUSINESS_GSTIN", "") or "").strip()


def _business_state() -> str:
    ps = _platform()
    if ps is not None and (ps.business_state or "").strip():
        return ps.business_state.strip()
    return (getattr(settings, "BUSINESS_STATE", "") or "").strip()


def gst_rate() -> Decimal:
    """Combined GST rate as a Decimal fraction (e.g. ``Decimal('0.18')``)."""
    ps = _platform()
    rate = ps.gst_rate if (ps is not None and ps.gst_rate is not None) else getattr(settings, "GST_RATE", Decimal("0.18"))
    if not isinstance(rate, Decimal):
        rate = Decimal(str(rate))
    return rate


def gst_should_charge() -> bool:
    """Whether GST is actually levied on orders.

    Gated on BOTH an enabled flag AND a configured GSTIN — you cannot legally
    levy GST without a registration, so a missing GSTIN means we price at the
    bare amount with zero tax (the "skip GST" state: payments still work). Both
    are admin-editable (PlatformSettings) with an env fallback, so enabling GST
    later is a one-click save in the admin panel, no redeploy.
    """
    ps = _platform()
    # Levy GST when EITHER the admin toggle OR the env flag enables it, AND a
    # GSTIN is configured (from admin or env). Default — both off — is the
    # "skip GST" state: payments still work at the bare price. A default
    # PlatformSettings row (gst_enabled=False) therefore never silently disables
    # an env-configured GST setup.
    enabled = bool(ps and ps.gst_enabled) or getattr(settings, "GST_ENABLED", False)
    return bool(enabled and _gstin())


# Indian states and union territories, as GST place-of-supply values. Kept here
# rather than in the model so both validation and the tax path read one list.
INDIAN_STATES = (
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
    "Bihar", "Chandigarh", "Chhattisgarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir",
    "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
    "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
)


def place_of_supply_for(user) -> str:
    """The customer's GST place of supply, or "" when nothing is on record.

    Audit Z1-13: every order-creation path called ``compute_gst(amount)`` with no
    place of supply, so the seller's state was assumed and **every** sale booked
    intra-state CGST+SGST. Nothing was ever wrong in `compute_gst` itself — the
    argument simply never arrived. This is the single place that answers the
    question, so a new checkout path cannot quietly re-open the hole.

    Returning "" is a real answer, not a failure: with no address on record the
    place-of-supply rules for B2C services fall back to the supplier's location,
    which is what `compute_gst` already does with an empty value.

    Queries `Profile` directly instead of going through ``user.profile``. Django
    caches the reverse one-to-one on the user instance, and the post-save signal
    that creates the profile populates that cache at registration — so
    ``user.profile`` on a long-lived instance can hand back a Profile loaded
    *before* the customer set their state, and the order would be taxed against a
    stale value. That is one extra query on a checkout path, which is the right
    side of the trade for a figure that ends up on a tax invoice.
    """
    if user is None or not getattr(user, "is_authenticated", True):
        return ""
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return ""

    from apps.accounts.models import Profile

    state = (
        Profile.objects.filter(user_id=user_id)
        .values_list("billing_state", flat=True)
        .first()
    )
    return (state or "").strip()


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
    is_export: bool = False   # non-INR: export of services, zero-rated

    @property
    def total_paise(self) -> int:
        """GST-inclusive total in paise — exactly what the Razorpay order uses."""
        return int((self.total_amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_gst(total_inclusive_inr, place_of_supply: str = "", currency: str = "INR") -> GstBreakup:
    """Compute the GST breakup for a GST-inclusive INR total.

    ``total_inclusive_inr`` is the server-side price (catalog price, post-coupon)
    — the GST-inclusive amount the customer sees and pays.

    When ``gst_should_charge()`` is False (GST disabled or no GSTIN) the breakup
    is the full amount as ``taxable_amount`` with zero tax, so the total is
    unchanged and downstream code is uniform.

    ``currency`` other than INR is treated as an export of services and zero-rated.

    Place of supply: if the customer's state differs from ``BUSINESS_STATE`` the
    supply is inter-state → a single IGST. Otherwise intra-state → CGST + SGST
    (each half the rate). When no customer state is supplied we default to the
    seller's state (intra-state).
    """
    total = _q(Decimal(str(total_inclusive_inr)))

    # Non-INR charges are export of services and zero-rated; levying CGST+SGST on a
    # USD card would be both wrong and unrecoverable from the customer (audit Z1-13).
    # `is_export` is recorded so a zero-tax export invoice is distinguishable from a
    # zero-tax "we are not GST-registered yet" invoice — they look identical in the
    # numbers and mean completely different things to an auditor.
    is_export = (currency or "INR").upper() != "INR"

    if is_export or not gst_should_charge() or total <= 0:
        return GstBreakup(
            total_amount=total,
            taxable_amount=total,
            gst_amount=Decimal("0.00"),
            gst_rate=Decimal("0"),
            place_of_supply=(place_of_supply or _business_state()).strip(),
            gstin=_gstin(),
            is_export=is_export,
        )

    rate = gst_rate()
    # Tax-inclusive extraction: taxable = total / (1 + rate); tax = total - taxable.
    taxable = _q(total / (Decimal("1") + rate))
    tax = _q(total - taxable)  # keeps taxable + tax == total exactly

    seller_state = _business_state()
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
        gstin=_gstin(),
    )

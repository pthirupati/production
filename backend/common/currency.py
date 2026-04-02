"""
Currency conversion utilities for FixitLab.
Fetches live INR ↔ USD exchange rates and caches for 1 hour.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache key for exchange rate
RATE_CACHE_KEY = "currency:usd_to_inr"
RATE_CACHE_TIMEOUT = 3600  # 1 hour


def get_usd_to_inr_rate():
    """Fetch live USD → INR rate. Returns cached value if available."""
    cached = cache.get(RATE_CACHE_KEY)
    if cached:
        return Decimal(str(cached))

    rate = _fetch_live_rate()
    if rate:
        cache.set(RATE_CACHE_KEY, float(rate), RATE_CACHE_TIMEOUT)
        return rate

    # Fallback: use a reasonable default
    fallback = Decimal("83.50")
    logger.warning(f"Using fallback USD/INR rate: {fallback}")
    return fallback


def _fetch_live_rate():
    """Fetch live exchange rate from a free API."""
    import urllib.request
    import json

    apis = [
        # Primary: exchangerate-api (free, no key required)
        ("https://open.er-api.com/v6/latest/USD", lambda d: Decimal(str(d["rates"]["INR"]))),
        # Fallback: frankfurter.app
        ("https://api.frankfurter.app/latest?from=USD&to=INR", lambda d: Decimal(str(d["rates"]["INR"]))),
    ]

    for url, parser in apis:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FixitLab/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                rate = parser(data)
                if rate and rate > 0:
                    logger.info(f"Fetched USD/INR rate: {rate} from {url}")
                    return rate
        except Exception as e:
            logger.warning(f"Failed to fetch rate from {url}: {e}")
            continue

    return None


def convert_inr_to_usd(amount_inr):
    """Convert INR amount to USD using live rate."""
    rate = get_usd_to_inr_rate()
    usd = (Decimal(str(amount_inr)) / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return usd


def convert_usd_to_inr(amount_usd):
    """Convert USD amount to INR using live rate."""
    rate = get_usd_to_inr_rate()
    inr = (Decimal(str(amount_usd)) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return inr


def get_price_in_currency(amount_inr, currency="INR"):
    """Get price in the requested currency."""
    if currency == "INR":
        return {
            "amount": int(amount_inr),
            "display": f"₹{int(amount_inr)}",
            "currency": "INR",
            "symbol": "₹",
        }
    elif currency == "USD":
        usd = convert_inr_to_usd(amount_inr)
        return {
            "amount": float(usd),
            "display": f"${usd}",
            "currency": "USD",
            "symbol": "$",
            "inr_amount": int(amount_inr),
            "exchange_rate": float(get_usd_to_inr_rate()),
        }
    return {
        "amount": int(amount_inr),
        "display": f"₹{int(amount_inr)}",
        "currency": "INR",
        "symbol": "₹",
    }

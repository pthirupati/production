"""Admin-managed IP/country blocks stored in Django cache."""

from django.core.cache import cache

BLOCKED_IPS_KEY = "admin:security:blocked_ips"
BLOCKED_COUNTRIES_KEY = "admin:security:blocked_countries"


def _list(key: str) -> list[str]:
    val = cache.get(key)
    return list(val) if isinstance(val, list) else []


def get_blocked_ips() -> list[str]:
    return _list(BLOCKED_IPS_KEY)


def get_blocked_countries() -> list[str]:
    return _list(BLOCKED_COUNTRIES_KEY)


def block_ip(ip: str) -> list[str]:
    ip = (ip or "").strip()
    if not ip:
        return get_blocked_ips()
    items = get_blocked_ips()
    if ip not in items:
        items.append(ip)
        cache.set(BLOCKED_IPS_KEY, items, None)
    return items


def unblock_ip(ip: str) -> list[str]:
    ip = (ip or "").strip()
    items = [x for x in get_blocked_ips() if x != ip]
    cache.set(BLOCKED_IPS_KEY, items, None)
    return items


def block_country(code: str) -> list[str]:
    code = (code or "").strip().upper()
    if not code:
        return get_blocked_countries()
    items = get_blocked_countries()
    if code not in items:
        items.append(code)
        cache.set(BLOCKED_COUNTRIES_KEY, items, None)
    return items


def unblock_country(code: str) -> list[str]:
    code = (code or "").strip().upper()
    items = [x for x in get_blocked_countries() if x != code]
    cache.set(BLOCKED_COUNTRIES_KEY, items, None)
    return items


def is_ip_blocked(ip: str | None) -> bool:
    if not ip:
        return False
    return ip in get_blocked_ips()

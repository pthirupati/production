"""Cache helpers for question_bank public API."""

from django.core.cache import cache

TECHNOLOGIES_LIST_KEY = "technologies_list"


def invalidate_technologies_cache() -> None:
    cache.delete(TECHNOLOGIES_LIST_KEY)

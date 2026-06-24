"""Merge textbook chapters into tutorial sections."""

from __future__ import annotations

from .tech_books import build_book_section


def get_book_body(
    topic: str,
    module: str,
    section_key: str,
    level: str,
) -> str:
    return build_book_section(topic, module, section_key, level)

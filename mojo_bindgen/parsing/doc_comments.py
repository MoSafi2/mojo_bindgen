"""Helpers for extracting source documentation comments from libclang cursors."""

from __future__ import annotations

import clang.cindex as cx

from mojo_bindgen.ir import DocComment


def cursor_doc_comment(cursor: cx.Cursor) -> DocComment | None:
    """Return the raw documentation comment attached to ``cursor``, if any."""
    raw = _cursor_text_attr(cursor, "raw_comment")
    if raw is None or not raw.strip():
        return None
    brief = _cursor_text_attr(cursor, "brief_comment")
    return DocComment(
        text=raw,
        brief=(brief.strip() if brief is not None and brief.strip() else None),
    )


def _cursor_text_attr(cursor: cx.Cursor, attr: str) -> str | None:
    try:
        value = getattr(cursor, attr, None)
    except Exception:
        return None
    if callable(value):
        try:
            value = value()
        except Exception:
            return None
    return value if isinstance(value, str) else None


__all__ = ["cursor_doc_comment"]

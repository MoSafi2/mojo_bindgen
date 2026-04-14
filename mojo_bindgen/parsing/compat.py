"""Libclang compatibility helpers for parser lowering stages.

This module owns small shims for libclang Python binding differences. It does
not build IR and does not participate in top-level parser orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass

import clang.cindex as cx


@dataclass
class ClangCompat:
    """Compatibility helpers for libclang Python binding differences."""

    def get_calling_convention(self, t: cx.Type) -> str | None:
        """Return a readable calling-convention string if available."""
        if hasattr(t, "get_canonical"):
            t = t.get_canonical()
        getter = getattr(t, "get_calling_conv", None)
        if getter is None:
            getter = getattr(t, "calling_conv", None)
        if getter is None:
            return None
        try:
            value = getter() if callable(getter) else getter
        except Exception:
            return None
        if value is None:
            return None
        name = getattr(value, "name", None)
        if isinstance(name, str) and name:
            return name
        try:
            return str(value)
        except Exception:
            return None

    def get_element_type(self, t: cx.Type) -> cx.Type:
        """Return a vector or complex element type across libclang variants."""
        getter = getattr(t, "get_element_type", None)
        if callable(getter):
            return getter()
        return getattr(t, "element_type")

    def get_num_elements(self, t: cx.Type) -> int | None:
        """Return vector element count across libclang variants."""
        getter = getattr(t, "get_num_elements", None)
        if not callable(getter):
            return None
        try:
            count = getter()
        except Exception:
            return None
        return count if isinstance(count, int) and count >= 0 else None

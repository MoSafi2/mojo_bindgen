"""Fail closed when a call cannot use the platform C ABI."""


def require_c_calling_convention(convention: str | None) -> None:
    if convention not in (None, "", "c", "C", "DEFAULT"):
        raise ValueError(
            f"unsupported calling convention {convention!r}; only platform C is supported"
        )

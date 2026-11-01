"""Fail closed when a call cannot use the platform C ABI."""


def require_c_calling_convention(convention: Optional[String]) raises:
    if (
        convention
        and convention.value() != ""
        and convention.value() != "c"
        and convention.value() != "C"
        and convention.value() != "DEFAULT"
    ):
        raise Error(
            "unsupported calling convention '"
            + convention.value()
            + "'; only platform C is supported"
        )

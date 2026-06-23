# Helpers for constructing libclang argument lists.
#
# Ported from `mojo_bindgen/utils.py`.


def normalize_std_flag(arg: String) -> String:
    """Normalize C standard flags to ``-std=...`` form.

    Accepted inputs:
    - ``-std=c99`` (unchanged)
    - ``--std=c99`` (normalized)
    - ``std=c99`` (normalized)
    """
    if arg.startswith("--std="):
        return "-std=" + String(arg[byte=6:])
    if arg.startswith("std="):
        return "-" + arg
    return arg


def build_c_parse_args(
    compile_args: List[String],
    *,
    default_std: String = "-std=gnu11",
) -> List[String]:
    """Build parse args for C translation units with predictable std handling.

    User-provided C standard flags take precedence. ``default_std`` is only
    added when no normalized ``-std=...`` flag is present.
    """
    var normalized_args: List[String] = []
    for arg in compile_args:
        normalized_args.append(normalize_std_flag(arg))

    var has_std = False
    for arg in normalized_args:
        if arg.startswith("-std="):
            has_std = True
            break

    var has_language = False
    for arg in normalized_args:
        if arg == "-x" or arg.startswith("-x"):
            has_language = True
            break

    var prefix: List[String] = []
    if not has_language:
        prefix.append("-x")
        prefix.append("c")
    if not has_std:
        prefix.append(default_std)

    var result: List[String] = []
    for a in prefix:
        result.append(a)
    for a in normalized_args:
        result.append(a)
    return result^
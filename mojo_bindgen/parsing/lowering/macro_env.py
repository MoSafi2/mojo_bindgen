"""Translation-unit macro environment for resolving object-like ``#define`` chains.

Primary-header bindings only *emit* macros from the main file, but replacement
lists may reference names defined in included headers. We index object-like
macros from the entire TU (last definition wins) and expand primary macros
against that environment before parsing, matching a small subset of CPP
behavior without emitting every intermediate ``comptime``.
"""

from __future__ import annotations

import re

import clang.cindex as cx

from mojo_bindgen.parsing.lowering.const_expr import (
    _is_predefined_macro_name,
    looks_function_like_macro_body,
)


def collect_object_like_macro_env(tu: cx.TranslationUnit) -> dict[str, list[str]]:
    """Build a name → replacement token list map for all object-like macros in the TU.

    Walks the whole translation unit (including system and nested includes).
    Function-like macros are skipped. Duplicate names use **last wins** (later
    ``#define`` in translation unit order overwrites earlier).
    """
    env: dict[str, list[str]] = {}
    for cursor in tu.cursor.walk_preorder():
        if cursor.kind != cx.CursorKind.MACRO_DEFINITION:  # type: ignore[attr-defined]
            continue
        name = cursor.spelling
        if not name:
            continue
        raw = list(cursor.get_tokens())
        if len(raw) < 2:
            continue
        body = [t.spelling for t in raw[1:]]
        if not body:
            continue
        if len(body) == 1 and _is_predefined_macro_name(body[0]):
            continue
        is_function_like = getattr(cursor, "is_macro_function_like", None)
        if (callable(is_function_like) and is_function_like()) or (
            is_function_like is not None
            and not callable(is_function_like)
            and bool(is_function_like)
        ):
            continue
        if looks_function_like_macro_body(body):
            continue
        env[name] = body
    return env


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_ident(tok: str) -> bool:
    return bool(_IDENT_RE.match(tok))


def expand_object_like_macro_tokens(
    tokens: list[str],
    env: dict[str, list[str]],
    *,
    max_expansion_steps: int = 10_000,
) -> list[str]:
    """Expand object-like macro references using ``env`` (subset of CPP semantics).

    While expanding a macro ``M``, ``M`` is disabled in the replacement list to
    avoid infinite recursion (classic object-like rule). Expansion stops after
    ``max_expansion_steps`` total macro invocations.
    """
    steps = [0]

    def go(ts: list[str], banned: frozenset[str]) -> list[str]:
        out: list[str] = []
        for t in ts:
            if steps[0] >= max_expansion_steps:
                out.append(t)
                continue
            if _is_ident(t) and t in env and t not in banned:
                steps[0] += 1
                inner = env[t]
                out.extend(go(inner, banned | {t}))
            else:
                out.append(t)
        return out

    return go(tokens, frozenset())

"""Tests for TU-wide macro expansion and constant folding."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mojo_bindgen.ir import BinaryExpr, IntLiteral, MacroDecl, UnaryExpr
from mojo_bindgen.parsing.lowering.const_expr import fold_const_expr
from mojo_bindgen.parsing.lowering.macro_env import (
    collect_object_like_macro_env,
    expand_object_like_macro_tokens,
)
from mojo_bindgen.parsing.parser import ClangParser


def _has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_libclang(),
    reason="libclang not available (use pixi run)",
)


def test_fold_const_expr_unary_neg_int() -> None:
    inner = IntLiteral(2147483647)
    expr = UnaryExpr(op="-", operand=inner)
    out = fold_const_expr(expr)
    assert isinstance(out, IntLiteral)
    assert out.value == -2147483647


def test_fold_const_expr_binary_bitwise_chain() -> None:
    # ((1 | 2) | 4) -> 7 after recursive fold
    inner = BinaryExpr(
        op="|",
        lhs=IntLiteral(1),
        rhs=IntLiteral(2),
    )
    expr = BinaryExpr(op="|", lhs=inner, rhs=IntLiteral(4))
    out = fold_const_expr(expr)
    assert isinstance(out, IntLiteral)
    assert out.value == 7


def test_expand_object_like_respects_recursion_guard() -> None:
    env = {"A": ["A"]}
    out = expand_object_like_macro_tokens(["A"], env, max_expansion_steps=100)
    assert out == ["A"]


def test_expand_object_like_substitutes_included_name() -> None:
    env = {"INNER_VAL": ["2147483647"]}
    body = ["-", "(", "INNER_VAL", ")"]
    expanded = expand_object_like_macro_tokens(body, env)
    assert expanded == ["-", "(", "2147483647", ")"]


def test_macro_closure_cross_include_header(tmp_path: Path) -> None:
    inc = tmp_path / "macro_dep.h"
    inc.write_text(
        textwrap.dedent(
            """\
            #define INNER_VAL 2147483647
            #define INNER_FLAG 256
            """
        ),
        encoding="utf-8",
    )
    primary = tmp_path / "macro_primary.h"
    primary.write_text(
        textwrap.dedent(
            f"""\
            #include "macro_dep.h"
            #define OUTER_NEG -(INNER_VAL)
            #define OUTER_FMT (INNER_FLAG | 1)
            """
        ),
        encoding="utf-8",
    )

    unit = ClangParser(
        primary,
        library="macro_closure",
        link_name="macro_closure",
        compile_args=["-I", str(tmp_path)],
    ).run()

    by_name: dict[str, MacroDecl] = {
        d.name: d for d in unit.decls if isinstance(d, MacroDecl)
    }
    neg = by_name["OUTER_NEG"]
    assert neg.kind == "object_like_supported"
    assert neg.expr is not None
    assert isinstance(neg.expr, IntLiteral)
    assert neg.expr.value == -2147483647

    fmt = by_name["OUTER_FMT"]
    assert fmt.kind == "object_like_supported"
    assert fmt.expr is not None
    assert isinstance(fmt.expr, IntLiteral)
    assert fmt.expr.value == 257


def test_collect_object_like_macro_env_last_wins(tmp_path: Path) -> None:
    p = tmp_path / "dup.h"
    p.write_text(
        textwrap.dedent(
            """\
            #define DUP 1
            #define DUP 2
            """
        ),
        encoding="utf-8",
    )
    parser = ClangParser(p, library="dup", link_name="dup")
    session = parser._build_parser_session()  # noqa: SLF001
    env = collect_object_like_macro_env(session.tu)
    assert env.get("DUP") == ["2"]

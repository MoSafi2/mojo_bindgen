"""Tests for TU-wide macro expansion and constant folding."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mojo_bindgen.ir import (
    BinaryExpr,
    Function,
    IntLiteral,
    IntType,
    MacroDecl,
    RefExpr,
    Struct,
    UnaryExpr,
)
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
            """\
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

    by_name: dict[str, MacroDecl] = {d.name: d for d in unit.decls if isinstance(d, MacroDecl)}
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


def test_include_headers_emit_translation_unit_declarations_and_macros(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private_dep.h"
    private.write_text(
        textwrap.dedent(
            """\
            #define PRIVATE_VALUE 40
            void private_fn(void);
            """
        ),
        encoding="utf-8",
    )
    extra = tmp_path / "extra_public.h"
    extra.write_text(
        textwrap.dedent(
            """\
            #include "private_dep.h"
            #define PUBLIC_VALUE (PRIVATE_VALUE + 2)
            typedef struct extra_record {
                int x;
            } extra_record;
            void extra_fn(extra_record value);
            """
        ),
        encoding="utf-8",
    )
    primary = tmp_path / "primary.h"
    primary.write_text("void primary_fn(void);\n", encoding="utf-8")

    unit = ClangParser(
        primary,
        library="include_headers",
        link_name="include_headers",
        include_headers=[extra, primary, extra],
        compile_args=["-I", str(tmp_path)],
    ).run()

    functions = [d.name for d in unit.decls if isinstance(d, Function)]
    macros = {d.name: d for d in unit.decls if isinstance(d, MacroDecl)}
    records = [d.name for d in unit.decls if isinstance(d, Struct)]

    assert functions == ["primary_fn", "private_fn", "extra_fn"]
    assert "extra_record" in records
    assert "PUBLIC_VALUE" in macros
    assert "PRIVATE_VALUE" in macros
    assert isinstance(macros["PRIVATE_VALUE"].expr, IntLiteral)
    assert macros["PRIVATE_VALUE"].expr.value == 40
    assert isinstance(macros["PUBLIC_VALUE"].expr, IntLiteral)
    assert macros["PUBLIC_VALUE"].expr.value == 42


def test_empty_macros_are_pruned_from_translation_unit(tmp_path: Path) -> None:
    header = tmp_path / "empty_macro.h"
    header.write_text(
        textwrap.dedent(
            """\
            #define EMPTY
            #define VALUE 1
            """
        ),
        encoding="utf-8",
    )

    unit = ClangParser(header, library="empty_macro", link_name="empty_macro").run()
    macros = {decl.name: decl for decl in unit.decls if isinstance(decl, MacroDecl)}

    assert "EMPTY" not in macros
    assert macros["VALUE"].kind == "object_like_supported"
    assert isinstance(macros["VALUE"].expr, IntLiteral)
    assert macros["VALUE"].expr.value == 1


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


def test_ordered_macro_values_do_not_fold_through_later_definitions(tmp_path: Path) -> None:
    header = tmp_path / "ordered.h"
    header.write_text(
        textwrap.dedent(
            """\
            #define BEFORE AFTER
            #define AFTER 42
            #define AGAIN AFTER
            """
        ),
        encoding="utf-8",
    )

    unit = ClangParser(header, library="ordered", link_name="ordered").run()
    macros = {decl.name: decl for decl in unit.decls if isinstance(decl, MacroDecl)}

    assert isinstance(macros["BEFORE"].expr, RefExpr)
    assert macros["BEFORE"].expr.name == "AFTER"
    assert isinstance(macros["AGAIN"].expr, IntLiteral)
    assert macros["AGAIN"].expr.value == 42


def test_clang_macro_fallback_evaluates_unsupported_integer_macro(tmp_path: Path) -> None:
    header = tmp_path / "fallback.h"
    header.write_text("#define FALLBACK_VALUE ((int)sizeof(long))\n", encoding="utf-8")

    without_fallback = ClangParser(
        header,
        library="fallback",
        link_name="fallback",
    ).run()
    with_fallback = ClangParser(
        header,
        library="fallback",
        link_name="fallback",
        clang_macro_fallback=True,
        clang_macro_fallback_build_dir=tmp_path / "fallback-build",
    ).run()

    without_macros = {
        decl.name: decl for decl in without_fallback.decls if isinstance(decl, MacroDecl)
    }
    with_macros = {decl.name: decl for decl in with_fallback.decls if isinstance(decl, MacroDecl)}

    assert without_macros["FALLBACK_VALUE"].kind == "object_like_unsupported"
    assert isinstance(with_macros["FALLBACK_VALUE"].expr, IntLiteral)
    assert with_macros["FALLBACK_VALUE"].expr.value > 0


def test_clang_macro_fallback_evaluates_parsed_but_unclean_macro(tmp_path: Path) -> None:
    header = tmp_path / "fallback_ref.h"
    header.write_text("#define FROM_COMPILER_MAX (__INT_MAX__ - 1)\n", encoding="utf-8")

    without_fallback = ClangParser(
        header,
        library="fallback_ref",
        link_name="fallback_ref",
    ).run()
    with_fallback = ClangParser(
        header,
        library="fallback_ref",
        link_name="fallback_ref",
        clang_macro_fallback=True,
    ).run()

    without_macros = {
        decl.name: decl for decl in without_fallback.decls if isinstance(decl, MacroDecl)
    }
    with_macros = {decl.name: decl for decl in with_fallback.decls if isinstance(decl, MacroDecl)}

    assert isinstance(without_macros["FROM_COMPILER_MAX"].expr, BinaryExpr)
    assert isinstance(with_macros["FROM_COMPILER_MAX"].expr, IntLiteral)
    assert with_macros["FROM_COMPILER_MAX"].expr.value == 2147483646


def test_clang_macro_fallback_preserves_parsed_unsigned_macro_type(tmp_path: Path) -> None:
    header = tmp_path / "fallback_unsigned.h"
    header.write_text("#define FALLBACK_UNSIGNED (1u || 0u)\n", encoding="utf-8")

    unit = ClangParser(
        header,
        library="fallback_unsigned",
        link_name="fallback_unsigned",
        clang_macro_fallback=True,
    ).run()

    macros = {decl.name: decl for decl in unit.decls if isinstance(decl, MacroDecl)}
    macro = macros["FALLBACK_UNSIGNED"]

    assert isinstance(macro.expr, IntLiteral)
    assert macro.expr.value == 1
    assert isinstance(macro.type, IntType)
    assert macro.type.int_kind.value == "UINT"


def test_macro_env_does_not_fold_through_unemitted_compiler_macros(tmp_path: Path) -> None:
    header = tmp_path / "compiler_macro_ref.h"
    header.write_text(
        "#define LOCAL_GNUC __GNUC__\n#define LOCAL_NUM 7\n",
        encoding="utf-8",
    )

    parser = ClangParser(header, library="compiler_macro_ref", link_name="compiler_macro_ref")
    session = parser._build_parser_session()  # noqa: SLF001
    env = collect_object_like_macro_env(session.tu)
    unit = parser.run()
    macros = {decl.name: decl for decl in unit.decls if isinstance(decl, MacroDecl)}

    assert "__GNUC__" not in macros
    assert "__GNUC__" not in env
    assert isinstance(macros["LOCAL_GNUC"].expr, RefExpr)
    assert macros["LOCAL_GNUC"].expr.name == "__GNUC__"
    assert isinstance(macros["LOCAL_NUM"].expr, IntLiteral)
    assert macros["LOCAL_NUM"].expr.value == 7

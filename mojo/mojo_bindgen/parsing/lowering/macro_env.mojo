"""Bounded object-like token expansion, with per-expansion recursion suppression."""
from clang.cindex import TranslationUnit, Cursor, CursorKind
from ..frontend import tokens, walk
from .const_expr import identifier, predefined, looks_function_like


def expand_object_like_macro_tokens(
    tokens: List[String], env: Dict[String, List[String]], max_expansion_steps: Int = 10000
) raises -> List[String]:
    var steps = 0
    return _expand(tokens, env, [], steps, max_expansion_steps)


def _expand(
    tokens: List[String],
    env: Dict[String, List[String]],
    disabled: List[String],
    mut steps: Int,
    limit: Int,
) raises -> List[String]:
    var result = List[String]()
    for token in tokens:
        if steps < limit and identifier(token) and token in env and token not in disabled:
            steps += 1
            var next = disabled.copy()
            next.append(token.copy())
            result.extend(_expand(env[token], env, next, steps, limit))
        else:
            result.append(token.copy())
    return result^


def collect_object_like_macro_env(ref tu: TranslationUnit) raises -> Dict[String, List[String]]:
    var root = tu.cursor()
    var nodes = List[Cursor]()
    walk(root, nodes)
    var result = Dict[String, List[String]]()
    for cursor in nodes:
        if cursor.kind() != CursorKind.MACRO_DEFINITION or not cursor.location().file_name():
            continue
        var body = tokens(cursor)
        if len(body) < 2:
            continue
        _ = body.pop(0)
        if (
            (len(body) == 1 and predefined(body[0]))
            or cursor.is_macro_function_like()
            or looks_function_like(body)
        ):
            continue
        result[cursor.spelling()] = body^
    return result^

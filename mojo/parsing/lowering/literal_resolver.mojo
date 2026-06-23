"""ABI-correct resolution of C integer literal suffix families to IR primitives.

Port of `mojo_bindgen/parsing/lowering/literal_resolver.py` for the Mojo
parser path.
"""

from clang.cindex import (
    CursorKind,
    Index,
    TranslationUnit,
    TranslationUnitFlags,
    UnsavedFile,
)
from emberjson import Value, serialize
from mojo.ir import IntKind, IntType, deserialize_ir
from mojo.parsing.frontend import _parse_translation_unit_direct
from mojo.parsing.lowering.primitive import (
    PrimitiveResolver,
    default_signed_int_primitive,
)
from mojo.utils import build_c_parse_args


comptime _PROBE_FILENAME = "__bindgen_suffix_probe.c"
comptime _PROBE_DECL_NAME = "__bindgen_m"


def _prewarm_suffixes() -> List[String]:
    var suffixes: List[String] = [
        "",
        "u",
        "U",
        "l",
        "L",
        "ll",
        "LL",
        "ul",
        "uL",
        "Ul",
        "UL",
        "lu",
        "lU",
        "Lu",
        "LU",
        "llu",
        "llU",
        "LLu",
        "LLU",
        "ull",
        "uLL",
        "Ull",
        "ULL",
    ]
    return suffixes^


def _integer_spelling_for_suffix(suffix: String) -> String:
    """Return the canonical C integer spelling implied by a literal suffix."""
    if suffix == "":
        return "int"

    var s = suffix.lower()
    var has_unsigned = s.find("u") != -1
    var long_count = 0
    for part in s.split("l"):
        _ = part
        long_count += 1
    long_count -= 1

    if long_count >= 2:
        if has_unsigned:
            return "unsigned long long"
        return "long long"
    if long_count == 1:
        if has_unsigned:
            return "unsigned long"
        return "long"
    if has_unsigned:
        return "unsigned int"
    return "int"


def _parse_args_for_probe(compile_args: List[String]) -> List[String]:
    """Return parse args for a tiny integer-type probe translation unit."""
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


def _probe_source(type_spelling: String) -> String:
    """Return the source text for a tiny variable declaration probe."""
    return type_spelling + " " + _PROBE_DECL_NAME + ";\n"


def _fallback_int_type(type_spelling: String) -> IntType:
    """Return a conservative integer fallback if probing fails."""
    var prim = default_signed_int_primitive()
    if type_spelling.find("unsigned") != -1:
        return IntType(
            kind="IntType",
            int_kind=IntKind.UINT,
            size_bytes=prim.size_bytes,
            align_bytes=prim.align_bytes,
            ext_bits=None,
        )
    return prim^


def _extract_int_type(value: Value) raises -> Optional[IntType]:
    if not value.is_object():
        return None

    var obj = value.object().copy()
    if not ("kind" in obj):
        return None
    if String(obj["kind"].string().copy()) != "IntType":
        return None

    return Optional[IntType](deserialize_ir[IntType](serialize(value)))


def _extract_probed_int_type(tu: TranslationUnit) raises -> Optional[IntType]:
    """Extract the probed integer declaration type from a parsed TU."""
    var resolver = PrimitiveResolver()
    for cursor in tu.cursor().children():
        if (
            cursor.kind() == CursorKind.VAR_DECL
            and cursor.spelling() == _PROBE_DECL_NAME
        ):
            var scalar = resolver.resolve_primitive(cursor.type())
            if not scalar:
                return None
            return _extract_int_type(scalar.value())
    return None


def _contains_string(strings: List[String], needle: String) -> Bool:
    for item in strings:
        if item == needle:
            return True
    return False


struct LiteralResolver(Copyable, Movable):
    """Resolve integer literal suffix families under one compile configuration.
    """

    var compile_args: List[String]
    var _parse_args: List[String]
    var _integer_suffix_cache: Dict[String, IntType]
    var _type_spelling_int_cache: Dict[String, IntType]
    var _missing_type_spellings: List[String]

    def __init__(
        out self,
        compile_args: List[String],
        *,
        prewarm: Bool = True,
    ) raises:
        self.compile_args = compile_args.copy()
        self._parse_args = _parse_args_for_probe(self.compile_args)
        self._integer_suffix_cache = Dict[String, IntType]()
        self._type_spelling_int_cache = Dict[String, IntType]()
        self._missing_type_spellings = List[String]()

        if prewarm:
            for suffix in _prewarm_suffixes():
                _ = self.int_type_for_integer_literal_suffix(suffix)

    def _probe_int_type(self, suffix: String) raises -> IntType:
        """Probe Clang for the ABI-correct integer type for a suffix family."""
        var type_spelling = _integer_spelling_for_suffix(suffix)
        var idx = Index.create()
        var unsaved = UnsavedFile(
            filename=_PROBE_FILENAME,
            contents=_probe_source(type_spelling),
        )
        var unsaved_files: List[UnsavedFile] = [unsaved^]
        var tu = _parse_translation_unit_direct(
            idx,
            _PROBE_FILENAME,
            self._parse_args,
            unsaved_files,
            TranslationUnitFlags.SKIP_FUNCTION_BODIES,
        )
        var probed = _extract_probed_int_type(tu)
        if probed:
            return probed.value().copy()
        return _fallback_int_type(type_spelling)

    def int_type_for_integer_literal_suffix(
        mut self, suffix: String
    ) raises -> IntType:
        """Return the ABI-correct integer primitive for a C literal suffix."""
        var cached = self._integer_suffix_cache.get(suffix)
        if cached:
            return cached.value().copy()

        var prim = self._probe_int_type(suffix)
        self._integer_suffix_cache[suffix] = prim.copy()
        return prim^

    def int_type_for_type_spelling(
        mut self, spelling: String
    ) raises -> Optional[IntType]:
        """Resolve a C type name to an integer primitive, or `None`."""
        var cached = self._type_spelling_int_cache.get(spelling)
        if cached:
            return Optional[IntType](cached.value().copy())
        if _contains_string(self._missing_type_spellings, spelling):
            return None

        var idx = Index.create()
        var unsaved = UnsavedFile(
            filename=_PROBE_FILENAME,
            contents=_probe_source(spelling),
        )
        var unsaved_files: List[UnsavedFile] = [unsaved^]
        var tu = _parse_translation_unit_direct(
            idx,
            _PROBE_FILENAME,
            self._parse_args,
            unsaved_files,
            TranslationUnitFlags.SKIP_FUNCTION_BODIES,
        )
        var prim = _extract_probed_int_type(tu)
        if prim:
            self._type_spelling_int_cache[spelling] = prim.value().copy()
            return Optional[IntType](prim.value().copy())

        self._missing_type_spellings.append(spelling)
        return None

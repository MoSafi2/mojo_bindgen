# Record lookup, naming, caching, and source-driven record materialization.
#
# Ported from `mojo_bindgen/parsing/registry.py`. This module is record-focused
# and source-driven. The definition lowerer binding (`bind_definition_lowerer`
# and `materialize_record_definition`) is deferred to the lowering/ port.

from clang.cindex import Cursor, CursorKind, TranslationUnit
from mojo.parsing.frontend import ClangFrontend
from mojo.ir import Struct, StructRef
from std.collections import Dict
from std.python import Python
from std.pathlib import Path


def _is_record_kind(kind: CursorKind) -> Bool:
    return kind == CursorKind.STRUCT_DECL or kind == CursorKind.UNION_DECL


def _is_named_decl_kind(kind: CursorKind) -> Bool:
    return kind == CursorKind.STRUCT_DECL or
           kind == CursorKind.UNION_DECL or
           kind == CursorKind.ENUM_DECL or
           kind == CursorKind.TYPEDEF_DECL or
           kind == CursorKind.FUNCTION_DECL or
           kind == CursorKind.VAR_DECL


def _location_key(cursor: Cursor) raises -> String:
    """Return a stable source-location key for a cursor."""
    var loc = cursor.location()
    var file_name = "<unknown>"
    var file_opt = loc.file()
    if file_opt:
        file_name = file_opt.value().name()
    return (
        file_name + ":" + String(loc.line()) + ":" + String(loc.column()) +
        ":" + cursor.kind().spelling() + ":" + cursor.spelling()
    )


def _is_anonymous_record_spelling(spelling: String) -> Bool:
    """Heuristic for clang's synthetic spellings for anonymous records."""
    if spelling == "":
        return True
    if spelling.find("(unnamed at ") != -1:
        return True
    if spelling.find("(anonymous at ") != -1:
        return True
    return False


def _sanitize_name_stem(raw: String, *, fallback: String) -> String:
    """Return a readable identifier-like stem for synthetic names."""
    var text = raw.strip()
    if text == "":
        return fallback

    # Replace any char that isn't [0-9A-Za-z_] with _
    var result = ""
    for i in range(text.byte_length()):
        var ch = text[byte=i]
        var c = ord(ch)
        if (c >= 48 and c <= 57) or (c >= 65 and c <= 90) or
           (c >= 97 and c <= 122) or c == 95:
            result += ch
        else:
            result += "_"

    # Collapse runs of _
    while result.find("__") != -1:
        result = result.replace("__", "_")

    # Strip leading/trailing _
    result = String(result.strip("_"))

    if result == "":
        return fallback

    # Prepend _ if first char is digit
    var first_c = ord(String(result[byte=0]))
    if first_c >= 48 and first_c <= 57:
        result = "_" + result

    return result


def _use_location_identity_for_cursor(cursor: Cursor) raises -> Bool:
    """Return whether cursor needs source-local identity instead of USR."""
    if not _is_record_kind(cursor.kind()):
        return False
    return _is_anonymous_record_spelling(cursor.spelling())


@fieldwise_init
struct RecordNaming(Copyable, Movable, Writable):
    """Stable lowered naming metadata for one record declaration."""

    var name: String
    var c_name: String
    var is_anonymous: Bool

    def __init__(out self):
        self.name = ""
        self.c_name = ""
        self.is_anonymous = False


struct RecordRegistry(Copyable, Movable):
    """Record-scoped lookup, cache, and raw materialization service for one TU."""

    var top_level_cursors_in_order: List[Cursor]
    var record_definition_by_decl_id: Dict[String, Cursor]
    var anonymous_record_name_by_decl_id: Dict[String, String]
    var _records_by_decl_id: Dict[String, Struct]

    def __init__(out self):
        self.top_level_cursors_in_order = List[Cursor]()
        self.record_definition_by_decl_id = Dict[String, Cursor]()
        self.anonymous_record_name_by_decl_id = Dict[String, String]()
        self._records_by_decl_id = Dict[String, Struct]()

    @staticmethod
    def build_from_translation_unit(
        tu: TranslationUnit,
        frontend: ClangFrontend,
    ) raises -> RecordRegistry:
        """Index one translation unit for record declarations."""
        var top_level = frontend.iter_translation_unit_cursors(tu)
        var registry = RecordRegistry()
        registry.top_level_cursors_in_order = top_level.copy()

        var all_cursors = tu.cursor().walk_preorder()
        for cursor in all_cursors:
            if _is_record_kind(cursor.kind()) and cursor.is_definition():
                var decl_id = registry.decl_id_for_cursor(cursor)
                registry.record_definition_by_decl_id[decl_id] = cursor.copy()

        return registry^

    def decl_id_for_cursor(self, cursor: Cursor) raises -> String:
        """Return a stable declaration identity for a clang cursor."""
        var usr_opt = cursor.usr()
        if usr_opt:
            var usr = usr_opt.value()
            if usr != "" and not _use_location_identity_for_cursor(cursor):
                return usr

        var spelling = cursor.spelling()
        if spelling != "" and _is_named_decl_kind(cursor.kind()):
            return cursor.kind().spelling() + ":" + spelling

        var loc_key = _location_key(cursor)
        var digest = _sha256_hex16(loc_key)
        return "anon:" + digest

    def record_definition_for_decl(
        self, cursor: Cursor
    ) raises -> Optional[Cursor]:
        """Return the complete clang definition cursor for a record declaration."""
        var decl_id = self.decl_id_for_cursor(cursor)
        return self.record_definition_by_decl_id.get(decl_id)

    def is_complete_record_decl(self, cursor: Cursor) raises -> Bool:
        """Return whether a record cursor is backed by a complete definition."""
        if not _is_record_kind(cursor.kind()):
            return False
        return self.record_definition_for_decl(cursor) is not None

    def record_naming(mut self, cursor: Cursor) raises -> RecordNaming:
        """Return stable lowered naming metadata for a record declaration."""
        var decl_id = self.decl_id_for_cursor(cursor)
        if not _is_anonymous_record_spelling(cursor.spelling()):
            var naming = RecordNaming()
            naming.name = cursor.spelling()
            naming.c_name = cursor.spelling()
            naming.is_anonymous = False
            return naming^
        var synth = self._anonymous_record_name(cursor, decl_id)
        var naming = RecordNaming()
        naming.name = synth
        naming.c_name = synth
        naming.is_anonymous = True
        return naming^

    def get(self, decl_id: String) -> Optional[Struct]:
        """Return a cached lowered record definition when available."""
        return self._records_by_decl_id.get(decl_id)

    def store(mut self, struct_decl: Struct):
        """Store a lowered record definition by declaration id."""
        self._records_by_decl_id[struct_decl.decl_id] = struct_decl.copy()

    @staticmethod
    def make_struct_ref(struct_decl: Struct) -> StructRef:
        """Build a stable StructRef from one lowered Struct."""
        var struct_ref = StructRef()
        struct_ref.decl_id = struct_decl.decl_id
        struct_ref.name = struct_decl.name
        struct_ref.c_name = struct_decl.c_name
        struct_ref.is_union = struct_decl.is_union
        struct_ref.size_bytes = struct_decl.size_bytes
        struct_ref.align_bytes = Optional[Int](struct_decl.align_bytes)
        struct_ref.is_anonymous = struct_decl.is_anonymous
        return struct_ref^

    def materialize_record_definition(self, cursor: Cursor) raises -> Struct:
        """Lower one complete record definition cursor and return cached Struct.

        Deferred to the lowering/ port.
        """
        raise Error("RecordRegistry.materialize_record_definition: "
                     "definition lowerer not yet ported (deferred to lowering/)")

    def _anonymous_record_name(
        mut self, cursor: Cursor, decl_id: String
    ) raises -> String:
        """Synthesize a stable IR-friendly name for an anonymous record."""
        var cached_opt = self.anonymous_record_name_by_decl_id.get(decl_id)
        if cached_opt:
            return cached_opt.value()

        var parent_opt = self._naming_parent(cursor)
        var parent_stem = ""
        if parent_opt:
            parent_stem = self._scope_stem(parent_opt.value())

        var kind = "anon_union"
        if cursor.kind() != CursorKind.UNION_DECL:
            kind = "anon_struct"

        var ordinal = self._anonymous_record_ordinal(cursor, parent_opt)
        var synth = ""
        if parent_stem == "":
            synth = kind + "_" + String(ordinal)
        else:
            synth = parent_stem + "__" + kind + "_" + String(ordinal)

        self.anonymous_record_name_by_decl_id[decl_id] = synth
        return synth

    def _scope_stem(mut self, cursor: Cursor) raises -> String:
        """Compute the hierarchical scope stem part of an anonymous name."""
        if cursor.kind() == CursorKind.FIELD_DECL:
            var field_name = _sanitize_name_stem(cursor.spelling(), fallback="field")
            var parent_opt = self._naming_parent(cursor)
            var parent_stem = ""
            if parent_opt:
                parent_stem = self._scope_stem(parent_opt.value())
            if parent_stem == "":
                return field_name
            return parent_stem + "__" + field_name

        if _is_record_kind(cursor.kind()):
            if _is_anonymous_record_spelling(cursor.spelling()):
                return self._anonymous_record_name(
                    cursor, self.decl_id_for_cursor(cursor)
                )
            return _sanitize_name_stem(cursor.spelling(), fallback="record")

        var spelling = cursor.spelling()
        if spelling != "":
            return _sanitize_name_stem(spelling, fallback="scope")

        var parent_opt = self._naming_parent(cursor)
        if parent_opt:
            return self._scope_stem(parent_opt.value())
        return ""

    def _naming_parent(self, cursor: Cursor) raises -> Optional[Cursor]:
        """Choose the parent cursor used to derive an anonymous record scope stem."""
        var parent_opt = cursor.lexical_parent()
        if not parent_opt:
            parent_opt = cursor.semantic_parent()
        if not parent_opt:
            return None
        var parent = parent_opt.value().copy()
        if parent.kind() == CursorKind.TRANSLATION_UNIT:
            return None
        return Optional[Cursor](parent^)

    def _anonymous_record_ordinal(
        self, cursor: Cursor, parent_opt: Optional[Cursor]
    ) raises -> Int:
        """Compute a stable ordinal among sibling anonymous record definitions."""
        var siblings: List[Cursor] = []
        if parent_opt is None:
            siblings = self.top_level_cursors_in_order.copy()
        else:
            siblings = parent_opt.value().children()

        var target_loc = _location_key(cursor)
        var ordinal = 0
        for sibling in siblings:
            if sibling.kind() != cursor.kind():
                continue
            if not sibling.is_definition():
                continue
            if not _is_anonymous_record_spelling(sibling.spelling()):
                continue
            ordinal += 1
            if _location_key(sibling) == target_loc:
                return ordinal
        return max(ordinal, 1)


def _sha256_hex16(data: String) raises -> String:
    """Return first 16 hex chars of SHA-256 hash of data (via Python interop)."""
    var py = Python()
    var hashlib = Python.import_module("hashlib")
    var py_str = Python.str(data)
    var encoded = py_str.encode()
    var h = hashlib.sha256(encoded)
    var hex = h.hexdigest()
    var hex_s = String(py.as_string_slice(hex))
    return String(hex_s[byte=0:16])


def _ord(ch: String) raises -> Int:
    """Return the ASCII code of the first byte of a 1-byte string."""
    return Int(ch[byte=0])

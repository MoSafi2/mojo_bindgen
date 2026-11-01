"""Private record construction states and stable source declaration identities."""
from std.collections.string import chr
from clang.cindex import Cursor, CursorKind
from .frontend import children, walk
from ._identity import sha256_prefix
from ..ir import Struct, StructRef, IRDiagnostic


def is_record(ref cursor: Cursor) raises -> Bool:
    return cursor.kind() == CursorKind.STRUCT_DECL or cursor.kind() == CursorKind.UNION_DECL


def anonymous(spelling: String) -> Bool:
    return not spelling or "(unnamed at " in spelling or "(anonymous at " in spelling


def kind_name(ref cursor: Cursor) raises -> String:
    var kind = cursor.kind()
    if kind == CursorKind.STRUCT_DECL:
        return "STRUCT_DECL"
    if kind == CursorKind.UNION_DECL:
        return "UNION_DECL"
    if kind == CursorKind.ENUM_DECL:
        return "ENUM_DECL"
    if kind == CursorKind.TYPEDEF_DECL:
        return "TYPEDEF_DECL"
    if kind == CursorKind.FUNCTION_DECL:
        return "FUNCTION_DECL"
    if kind == CursorKind.VAR_DECL:
        return "VAR_DECL"
    if kind == CursorKind.FIELD_DECL:
        return "FIELD_DECL"
    if kind == CursorKind.PARM_DECL:
        return "PARM_DECL"
    return cursor.kind().spelling()


def location_key(ref cursor: Cursor) raises -> String:
    var loc = cursor.location()
    return (
        loc.file_name()
        + ":"
        + String(loc.line())
        + ":"
        + String(loc.column())
        + ":CursorKind."
        + kind_name(cursor)
        + ":"
        + cursor.spelling()
    )


def decl_id(ref cursor: Cursor) raises -> String:
    var usr = cursor.usr()
    if usr and not (is_record(cursor) and anonymous(cursor.spelling())):
        return usr.value()
    var name = cursor.spelling()
    var kind = cursor.kind()
    if name and (
        is_record(cursor)
        or kind == CursorKind.ENUM_DECL
        or kind == CursorKind.TYPEDEF_DECL
        or kind == CursorKind.FUNCTION_DECL
        or kind == CursorKind.VAR_DECL
    ):
        return kind_name(cursor) + ":" + name
    return "anon:" + sha256_prefix(location_key(cursor))


def sanitize(text: String, fallback: String) -> String:
    var result = String()
    var pending = False
    for b in text.as_bytes():
        if (b >= 65 and b <= 90) or (b >= 97 and b <= 122) or (b >= 48 and b <= 57):
            if pending and result:
                result += "_"
            pending = False
            result += chr(Int(b))
        else:
            pending = True
    if not result:
        return fallback.copy()
    if result.as_bytes()[0] >= 48 and result.as_bytes()[0] <= 57:
        result = "_" + result
    return result^


__enum RecordState(Copyable, Movable):
    case declared(Struct)
    case building(Struct)
    case completed(Struct)

    def __deinit__(deinit self):
        pass

    def header(self) -> Struct:
        match self:
            case .declared(v):
                return v.copy()
            case .building(v):
                return v.copy()
            case .completed(v):
                return v.copy()


struct RecordRegistry(Copyable, Movable):
    var top_level: List[Cursor]
    var definitions: Dict[String, Cursor]
    var names: Dict[String, String]
    var states: Dict[String, RecordState]
    var completed: List[String]
    var diagnostics: List[IRDiagnostic]

    def __init__(out self, ref root: Cursor) raises:
        self.top_level = children(root)
        self.definitions = Dict[String, Cursor]()
        self.names = Dict[String, String]()
        self.states = Dict[String, RecordState]()
        self.completed = List[String]()
        self.diagnostics = List[IRDiagnostic]()
        var all_nodes = List[Cursor]()
        walk(root, all_nodes)
        for node in all_nodes:
            if is_record(node) and node.is_definition():
                self.definitions[decl_id(node)] = node.copy()

    def begin(mut self, header: Struct) raises -> Optional[RecordState]:
        var prior = self.states.get(header.decl_id)
        if prior:
            match prior.value():
                case .building(_):
                    raise Error("record " + header.name + " is already being built")
                case _:
                    pass
        self.states[header.decl_id] = RecordState.building(header.copy())
        return prior^

    def abort(mut self, key: String, prior: Optional[RecordState]) raises:
        if prior:
            self.states[key] = prior.value().copy()
        else:
            _ = self.states.pop(key)

    def publish(mut self, record: Struct) raises:
        if not record.is_complete:
            raise Error("cannot publish an unfinished record definition")
        self.states[record.decl_id] = RecordState.completed(record.copy())
        if record.decl_id not in self.completed:
            self.completed.append(record.decl_id.copy())

    def naming(mut self, ref cursor: Cursor) raises -> String:
        var spelling = cursor.spelling()
        if not anonymous(spelling):
            return spelling^
        var key = decl_id(cursor)
        if key in self.names:
            return self.names[key].copy()
        var parent = cursor.lexical_parent()
        if not parent:
            parent = cursor.semantic_parent()
        var stem = String()
        var siblings = self.top_level.copy()
        if parent and parent.value().kind() != CursorKind.TRANSLATION_UNIT:
            stem = self.scope_stem(parent.value())
            siblings = children(parent.value())
        var ordinal = 0
        var target = location_key(cursor)
        for sibling in siblings:
            if (
                sibling.kind() == cursor.kind()
                and sibling.is_definition()
                and anonymous(sibling.spelling())
            ):
                ordinal += 1
                if location_key(sibling) == target:
                    break
        if ordinal < 1:
            ordinal = 1
        var result = String(
            "anon_union_" if cursor.kind() == CursorKind.UNION_DECL else "anon_struct_"
        ) + String(ordinal)
        if stem:
            result = stem + "__" + result
        self.names[key] = result.copy()
        return result^

    def scope_stem(mut self, ref cursor: Cursor) raises -> String:
        if is_record(cursor):
            if anonymous(cursor.spelling()):
                return self.naming(cursor)
            return sanitize(cursor.spelling(), "record")
        if cursor.kind() != CursorKind.FIELD_DECL and cursor.spelling():
            return sanitize(cursor.spelling(), "scope")
        var parent = cursor.lexical_parent()
        if not parent:
            parent = cursor.semantic_parent()
        var stem = String()
        if parent and parent.value().kind() != CursorKind.TRANSLATION_UNIT:
            stem = self.scope_stem(parent.value())
        if cursor.kind() == CursorKind.FIELD_DECL:
            var name = sanitize(cursor.spelling(), "field")
            return name if not stem else stem + "__" + name
        return stem^

    def add_cursor_diag(mut self, severity: String, ref cursor: Cursor, message: String) raises:
        var loc = cursor.location()
        self.diagnostics.append(
            IRDiagnostic(severity.copy(), message.copy(), loc.file_name(), loc.line(), loc.column())
        )


def make_struct_ref(record: Struct) -> StructRef:
    return StructRef(
        record.decl_id.copy(),
        record.name.copy(),
        record.c_name.copy(),
        record.is_union,
        record.size_bytes,
        record.align_bytes,
        record.is_anonymous,
    )

"""Parse-context integer facts, cached by C spelling rather than node identity."""
from clang.cindex import Index, CursorKind, UnsavedFile
from ..frontend import children, normalized_args
from ...ir import IntType, IntKind
from .primitive import primitive, default_int


struct LiteralResolver(Copyable, Movable):
    var args: List[String]
    var types: Dict[String, Optional[IntType]]

    def __init__(out self, args: List[String]):
        self.args = normalized_args(args)
        self.types = Dict[String, Optional[IntType]]()

    def for_spelling(mut self, spelling: String) raises -> Optional[IntType]:
        if spelling in self.types:
            return self.types[spelling].copy()
        var index = Index.create()
        var tu = index.parse(
            "__bindgen_suffix_probe.c",
            self.args,
            [UnsavedFile("__bindgen_suffix_probe.c", spelling + " __bindgen_m;\n")],
        )
        var result = Optional[IntType]()
        var root = tu.cursor()
        for cursor in children(root):
            if cursor.kind() == CursorKind.VAR_DECL and cursor.spelling() == "__bindgen_m":
                var shape = cursor.type()
                var p = primitive(shape)
                if p:
                    match p.value():
                        case .int_type(v):
                            result = v.copy()
                        case _:
                            pass
        self.types[spelling] = result.copy()
        return result^

    def for_suffix(mut self, suffix: String) raises -> IntType:
        var lower = suffix.lower()
        var unsigned = "u" in lower
        var long_count = lower.count("l")
        var name = String("unsigned " if unsigned else "")
        if long_count >= 2:
            name += "long long"
        elif long_count == 1:
            name += "long"
        else:
            name += "int"
        var result = self.for_spelling(name)
        if result:
            return result.value().copy()
        return IntType(IntKind.UINT if unsigned else IntKind.INT, 4, 4)

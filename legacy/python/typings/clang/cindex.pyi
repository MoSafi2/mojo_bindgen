from collections.abc import Iterable, Iterator, Sequence
from typing import Any, ClassVar


class _NamedValue:
    name: str


class TypeKind(_NamedValue):
    INVALID: ClassVar[TypeKind]
    UNEXPOSED: ClassVar[TypeKind]
    VOID: ClassVar[TypeKind]
    BOOL: ClassVar[TypeKind]
    CHAR_U: ClassVar[TypeKind]
    UCHAR: ClassVar[TypeKind]
    CHAR16: ClassVar[TypeKind]
    CHAR32: ClassVar[TypeKind]
    USHORT: ClassVar[TypeKind]
    UINT: ClassVar[TypeKind]
    ULONG: ClassVar[TypeKind]
    ULONGLONG: ClassVar[TypeKind]
    UINT128: ClassVar[TypeKind]
    CHAR_S: ClassVar[TypeKind]
    SCHAR: ClassVar[TypeKind]
    WCHAR: ClassVar[TypeKind]
    SHORT: ClassVar[TypeKind]
    INT: ClassVar[TypeKind]
    LONG: ClassVar[TypeKind]
    LONGLONG: ClassVar[TypeKind]
    INT128: ClassVar[TypeKind]
    HALF: ClassVar[TypeKind]
    FLOAT: ClassVar[TypeKind]
    DOUBLE: ClassVar[TypeKind]
    LONGDOUBLE: ClassVar[TypeKind]
    POINTER: ClassVar[TypeKind]
    RECORD: ClassVar[TypeKind]
    ENUM: ClassVar[TypeKind]
    TYPEDEF: ClassVar[TypeKind]
    CONSTANTARRAY: ClassVar[TypeKind]
    INCOMPLETEARRAY: ClassVar[TypeKind]
    VARIABLEARRAY: ClassVar[TypeKind]
    DEPENDENTSIZEDARRAY: ClassVar[TypeKind]
    FUNCTIONPROTO: ClassVar[TypeKind]
    FUNCTIONNOPROTO: ClassVar[TypeKind]
    ELABORATED: ClassVar[TypeKind]
    COMPLEX: ClassVar[TypeKind]
    VECTOR: ClassVar[TypeKind]
    EXTVECTOR: ClassVar[TypeKind]
    ATOMIC: ClassVar[TypeKind]


class CursorKind(_NamedValue):
    TRANSLATION_UNIT: ClassVar[CursorKind]
    FUNCTION_DECL: ClassVar[CursorKind]
    STRUCT_DECL: ClassVar[CursorKind]
    UNION_DECL: ClassVar[CursorKind]
    ENUM_DECL: ClassVar[CursorKind]
    ENUM_CONSTANT_DECL: ClassVar[CursorKind]
    TYPEDEF_DECL: ClassVar[CursorKind]
    VAR_DECL: ClassVar[CursorKind]
    FIELD_DECL: ClassVar[CursorKind]
    PARM_DECL: ClassVar[CursorKind]
    MACRO_DEFINITION: ClassVar[CursorKind]
    PACKED_ATTR: ClassVar[CursorKind]
    ALIGNED_ATTR: ClassVar[CursorKind]
    UNEXPOSED_ATTR: ClassVar[CursorKind]


class Token:
    spelling: str


class File:
    name: str


class SourceLocation:
    file: File | None
    line: int
    column: int


class Diagnostic:
    Note: ClassVar[int]
    Warning: ClassVar[int]
    Error: ClassVar[int]
    Fatal: ClassVar[int]
    severity: int
    location: SourceLocation
    spelling: str


class Type:
    kind: TypeKind
    spelling: str
    element_type: Type
    element_count: int
    enum_type: Type

    @staticmethod
    def from_result(value: Any) -> Type: ...
    def get_canonical(self) -> Type: ...
    def get_named_type(self) -> Type: ...
    def is_const_qualified(self) -> bool: ...
    def is_volatile_qualified(self) -> bool: ...
    def is_restrict_qualified(self) -> bool: ...
    def get_size(self) -> int: ...
    def get_align(self) -> int: ...
    def get_offset(self, field_name: str) -> int: ...
    def get_fields(self) -> Iterator[Cursor]: ...
    def get_declaration(self) -> Cursor: ...
    def get_result(self) -> Type: ...
    def get_pointee(self) -> Type: ...
    def get_array_element_type(self) -> Type: ...
    def get_array_size(self) -> int: ...
    def argument_types(self) -> Iterable[Type]: ...
    def is_function_variadic(self) -> bool: ...
    def get_element_type(self) -> Type: ...
    def get_num_elements(self) -> int: ...
    def get_calling_conv(self) -> Any: ...
    def get_value_type(self) -> Type: ...


class Cursor:
    kind: CursorKind
    spelling: str
    type: Type
    enum_type: Type
    enum_value: int
    underlying_typedef_type: Type
    location: SourceLocation
    is_macro_function_like: bool

    def is_definition(self) -> bool: ...
    def get_usr(self) -> str: ...
    def get_definition(self) -> Cursor | None: ...
    def get_children(self) -> Iterator[Cursor]: ...
    def walk_preorder(self) -> Iterator[Cursor]: ...
    def get_tokens(self) -> Iterator[Token]: ...
    def get_arguments(self) -> Iterator[Cursor]: ...
    def is_bitfield(self) -> bool: ...
    def get_bitfield_width(self) -> int | None: ...
    def get_field_offsetof(self) -> int: ...


class TranslationUnit:
    PARSE_DETAILED_PROCESSING_RECORD: ClassVar[int]
    PARSE_SKIP_FUNCTION_BODIES: ClassVar[int]
    PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION: ClassVar[int]
    cursor: Cursor
    diagnostics: Sequence[Diagnostic]


class TranslationUnitLoadError(Exception): ...


class Index:
    @staticmethod
    def create() -> Index: ...
    def parse(
        self,
        path: str,
        *,
        args: Sequence[str] | None = ...,
        unsaved_files: Sequence[tuple[str, str]] | None = ...,
        options: int = ...,
    ) -> TranslationUnit: ...


class _Conf:
    lib: Any


conf: _Conf
c_object_p: Any
_CXString: Any


def register_function(lib: Any, item: tuple[str, list[Any], Any, Any], ignore_errors: bool) -> None: ...

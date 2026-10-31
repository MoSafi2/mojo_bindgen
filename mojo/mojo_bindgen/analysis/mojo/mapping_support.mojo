from std.memory import ArcPointer
from ...ir import *
from ..common import mojo_ident, strip_whitespace
from .type_mapping import MapTypePass


def field_display_name(field: Field, index: Int) -> String:
    var name = strip_whitespace(field.source_name)
    if name.byte_length():
        return name^
    name = strip_whitespace(field.name)
    return name^ if name.byte_length() else String("field_" + String(index))


def field_mojo_name(field: Field, index: Int) -> String:
    if field.source_name.byte_length():
        return mojo_ident(field.source_name)
    if field.name.byte_length():
        return mojo_ident(field.name)
    return String("_anon_" + String(index))


def record_name(decl: Struct) -> String:
    var name = strip_whitespace(decl.name)
    if not name.byte_length():
        name = strip_whitespace(decl.c_name)
    return mojo_ident(name, "anonymous_union" if decl.is_union else "anonymous_struct")


def mapping_note(message: String, category: String) -> MappingNote:
    return MappingNote(MappingSeverity.NOTE, message.copy(), category.copy())


def stub_note(message: String) -> MappingNote:
    return mapping_note(message, "stub_mapping")


def struct_note(message: String) -> MappingNote:
    return mapping_note(message, "struct_mapping")


def union_note(message: String) -> MappingNote:
    return mapping_note(message, "union_mapping")


def try_map_type(
    mapper: MapTypePass, t: CType, subject: String, failure_suffix: String
) -> Tuple[Optional[ArcPointer[MojoType]], Optional[String]]:
    try:
        var mapped = mapper.run(t)
        match mapped:
            case .builtin_type(v):
                if v.name == MojoBuiltin.UNSUPPORTED:
                    return (
                        {},
                        String(subject + " mapped to an unsupported Mojo type; " + failure_suffix),
                    )
            case _:
                pass
        return (ArcPointer(mapped^), {})
    except error:
        return (
            {},
            String(subject + " could not be mapped (" + String(error) + "); " + failure_suffix),
        )

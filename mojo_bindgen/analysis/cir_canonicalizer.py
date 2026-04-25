from mojo_bindgen.ir import Decl, Struct
from mojo_bindgen.parsing.parser import Unit


class CIRCanonicalizer:
    """Start of Canonicalization pass, for now only deduping structs."""

    def __init__(
        self,
    ) -> None:
        self._struct_by_usr: dict[str, Struct] = {}

    def canonicalize(self, unit: Unit) -> Unit:
        decls = self._walk_unit(unit)
        unit.decls = decls
        return unit

    def _walk_unit(self, unit: Unit) -> list[Decl]:
        out = list[Decl]()
        for decl in unit.decls:
            if isinstance(decl, Struct):
                if not self._struct_by_usr.get(decl.decl_id):
                    self._struct_by_usr[decl.decl_id] = decl

                self._struct_by_usr[decl.decl_id] = _compare(
                    decl, self._struct_by_usr[decl.decl_id]
                )
            else:
                out.append(decl)
        out.extend(self._struct_by_usr.values())
        return out


def _compare(new: Struct, old: Struct) -> Struct:
    if not new.is_complete:
        return old
    if not old.is_complete:
        return new
    return old

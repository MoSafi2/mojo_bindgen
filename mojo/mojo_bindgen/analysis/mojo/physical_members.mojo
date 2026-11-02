"""Expand logical padding while retaining its identity for ABI validation."""
from ...ir import *


def physical_members(decl: StructDecl) raises -> List[StructMember]:
    var names = Dict[String, Bool]()
    for m in decl.members:
        match m:
            case .stored_member(v):
                names[v.name] = True
            case .opaque_storage_member(v):
                names[v.name] = True
            case .padding_member(v):
                names[v.name] = True
            case .bitfield_group_member(v):
                names[v.storage_name] = True
    var out = List[StructMember]()
    for m in decl.members:
        if case .padding_member(v) = m:
            if v.storage_width_bytes:
                out.append(m.copy())
                continue
            var chunks = List[Tuple[Int, Int]]()
            var offset = v.byte_offset
            var remaining = v.size_bytes
            if remaining < 0:
                raise Error("negative padding span")
            while remaining > 0:
                for width in [8, 4, 2, 1]:
                    if remaining >= width and offset % width == 0:
                        chunks.append((offset, width))
                        offset += width
                        remaining -= width
                        break
            for i in range(len(chunks)):
                var base = v.name.copy() if len(chunks) == 1 else v.name + "_" + String(i)
                var name = base.copy()
                var suffix = 2
                while name in names and name != v.name:
                    name = base + "_" + String(suffix)
                    suffix += 1
                names[name] = True
                out.append(
                    StructMember.padding_member(
                        PaddingMember(name, chunks[i][1], chunks[i][0], chunks[i][1])
                    )
                )
        else:
            out.append(m.copy())
    return out^

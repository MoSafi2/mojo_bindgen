# ─────────────────────────────────────────────────────────────────────────────
# Optional debug SerDe for the mojo_bindgen IR.
#
# This module is the ONLY Mojo module that depends on EmberJson for JSON
# serialization/deserialization. The main code paths (`mojo.ir`,
# `mojo.parsing.*`, `mojo.parsing.lowering.*`) never import from here and never
# import EmberJson functions (`serialize` / `deserialize` / `parse`); they only
# use EmberJson's `Value`/`Object` as the storage representation for recursive
# IR union fields (see `mojo/ir.mojo`).
#
# Gating: EmberJson remains a top-level dependency until `Value` is replaced
# with tagged-union structs. Once that lands, EmberJson (and this module) move
# under a `serde` pixi feature env so runtime builds are EmberJson-free.
# ─────────────────────────────────────────────────────────────────────────────

from emberjson import serialize, deserialize, parse, Value, Object
from mojo.ir import IRBase, TypeNode, Unit, MojoModule


# Deserialize `s` into `T`, tolerating fields omitted by the Python SerDe's
# `omit_if_default`/`omit_when` rules. Missing keys are first back-filled
# from a default-constructed `T`; then EmberJson's native reflection-based
# `deserialize` does the actual field-by-field construction.
def deserialize_ir[T: IRBase](s: String) raises -> T:
    var v = parse(s)
    if v.is_object():
        var defaults = parse(serialize(T()))
        var keys_to_add: List[String] = []
        for key in defaults.object().copy():
            if not (key in v.object()):
                keys_to_add.append(key)
        for key in keys_to_add:
            v[key] = parse(serialize(defaults.object().copy()[key].copy()))
    return deserialize[T](serialize(v))


# Bridge helper: recover a concrete `T: TypeNode` from a `Value` produced by
# `to_value()` or stored in a union-typed field. Mirrors Python's
# `type_from_json` dispatch but via static generics rather than a runtime
# kind→class table.
def deserialize_type_node[T: TypeNode & IRBase](v: Value) raises -> T:
    return deserialize_ir[T](serialize(v))


# Free-function replacement for the former `TypeNode.to_value()` method.
# Lifts a typed IR node into the `Value` storage representation via a
# serialize→parse round-trip.
def to_value[T: TypeNode & IRBase](node: T) raises -> Value:
    return parse(serialize(node))


# Proof-of-concept: any function constrained by `[T: TypeNode]` is statically
# restricted to the type-tree variants. Passing a ConstExpr or Decl node
# (which do not conform to TypeNode) is a compile-time error.
def type_node_kind[T: TypeNode](node: T) -> NodeKind:
    return node.node_kind()


# Top-level container SerDe — convenience entry points for debug tooling.
def unit_to_json[*, pretty: Bool = True](node: Unit) raises -> String:
    return serialize[pretty=pretty](node)


def unit_from_json(s: String) raises -> Unit:
    return deserialize_ir[Unit](s)


def mojo_module_to_json[*, pretty: Bool = True](node: MojoModule) raises -> String:
    return serialize[pretty=pretty](node)


def mojo_module_from_json(s: String) raises -> MojoModule:
    return deserialize_ir[MojoModule](s)

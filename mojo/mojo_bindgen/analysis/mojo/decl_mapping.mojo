from ..calling_convention import require_c_calling_convention
from std.memory import ArcPointer
from ...ir import *
from ..common import mojo_ident
from ..facts.type_layout import peel_layout_wrappers
from .mojo_emit_options import MojoEmitOptions
from .type_mapping import MapTypePass
from .const_expr_mapping import MapConstExprPass
from .const_value_mapping import typed_const_value
from .struct_mapping import StructMappingContext, map_struct
from .union_mapping import MapUnionPass
from .alias_mapping import map_typedef_alias
from .macro_mapping import MacroMapper, has_null
from .mapping_support import stub_note


@fieldwise_init
struct MappingSession(Copyable, Movable):
    var unit: ArcPointer[Unit]
    var options: MojoEmitOptions
    var type_mapper: MapTypePass
    var const_expr_mapper: MapConstExprPass
    var struct_context: StructMappingContext


struct UnitDeclMapper(Movable):
    var session: MappingSession
    var emitted_const_names: Dict[String, Bool]

    def __init__(out self, var session: MappingSession):
        self.session = session^
        self.emitted_const_names = Dict[String, Bool]()

    def map_decl(mut self, decl: Decl) raises -> List[MojoDecl]:
        var out = List[MojoDecl]()
        match decl:
            case .typedef(v):
                var alias = map_typedef_alias(
                    v.name, v.aliased.ptr()[], self.session.type_mapper, v.doc
                )
                if alias:
                    out.append(MojoDecl.alias_decl(alias.value().copy()))
            case .enum_decl(v):
                var underlying = ArcPointer(
                    self.session.type_mapper.run(CType.int_type(v.underlying.copy()))
                )
                var name = mojo_ident(v.name)
                out.append(
                    MojoDecl.alias_decl(
                        AliasDecl(
                            name.copy(),
                            AliasKind.TYPE_ALIAS,
                            type_value=underlying.copy(),
                            doc=v.doc.copy(),
                        )
                    )
                )
                for alias in v.alias_names:
                    out.append(
                        MojoDecl.alias_decl(
                            AliasDecl(
                                mojo_ident(alias),
                                AliasKind.TYPE_ALIAS,
                                type_value=ArcPointer(MojoType.named_type(NamedType(name.copy()))),
                            )
                        )
                    )
                for member in v.enumerants:
                    var args = List[ArcPointer[MojoConstExpr]]()
                    args.append(
                        ArcPointer(
                            MojoConstExpr.mojo_cast_expr(
                                MojoCastExpr(
                                    underlying.copy(),
                                    ArcPointer(
                                        MojoConstExpr.int_literal(IntLiteral(member.value.copy()))
                                    ),
                                )
                            )
                        )
                    )
                    var value = MojoConstExpr.mojo_call_expr(
                        MojoCallExpr(
                            ArcPointer(MojoConstExpr.mojo_ref_expr(MojoRefExpr(name.copy()))), args^
                        )
                    )
                    out.append(
                        MojoDecl.alias_decl(
                            AliasDecl(
                                mojo_ident(member.name),
                                AliasKind.CONST_VALUE,
                                const_type=ArcPointer(MojoType.named_type(NamedType(name.copy()))),
                                const_value=ArcPointer(value^),
                                doc=member.doc.copy(),
                            )
                        )
                    )
                self.emitted_const_names[name] = True
                for member in v.enumerants:
                    self.emitted_const_names[mojo_ident(member.name)] = True
                for alias in v.alias_names:
                    self.emitted_const_names[mojo_ident(alias)] = True
            case .function(v):
                out.append(MojoDecl.function_decl(self._function(v)))
            case .global_var(v):
                var core = peel_layout_wrappers(v.type.ptr()[])
                var kind = GlobalKind.WRAPPER
                match core:
                    case .atomic_type(_):
                        kind = GlobalKind.STUB
                    case _:
                        pass
                out.append(
                    MojoDecl.global_decl(
                        GlobalDecl(
                            mojo_ident(v.name),
                            v.link_name.copy(),
                            ArcPointer(self.session.type_mapper.run(v.type.ptr()[])),
                            v.is_const,
                            kind,
                            doc=v.doc.copy(),
                        )
                    )
                )
            case .const_decl(v):
                var notes = List[MappingNote]()
                var name = mojo_ident(v.name)
                if has_null(v.expr.ptr()[]):
                    notes.append(
                        stub_note(
                            "constant expression could not be mapped; placeholder alias emitted"
                        )
                    )
                    out.append(
                        MojoDecl.alias_decl(
                            AliasDecl(
                                name^, AliasKind.CONST_VALUE, diagnostics=notes^, doc=v.doc.copy()
                            )
                        )
                    )
                else:
                    var value = self.session.const_expr_mapper.run(v.expr.ptr()[])
                    var typed = typed_const_value(value, v.type.ptr()[], self.session.type_mapper)
                    self.emitted_const_names[name] = True
                    out.append(
                        MojoDecl.alias_decl(
                            AliasDecl(
                                name^,
                                AliasKind.CONST_VALUE,
                                const_value=ArcPointer(typed^),
                                doc=v.doc.copy(),
                            )
                        )
                    )
            case .macro_decl(v):
                var mapper = MacroMapper(
                    self.session.const_expr_mapper.copy(), self.session.type_mapper.copy()
                )
                var alias = mapper.map(v, self.emitted_const_names)
                if alias:
                    out.append(MojoDecl.alias_decl(alias.value().copy()))
            case .struct_decl(v):
                if v.is_union:
                    out.append(
                        MojoDecl.alias_decl(MapUnionPass(self.session.type_mapper.copy()).run(v))
                    )
                else:
                    out.append(MojoDecl.struct_decl(map_struct(v, self.session.struct_context)))
        return out^

    def _function(self, v: Function) raises -> FunctionDecl:
        require_c_calling_convention(v.calling_convention)
        var kind = FunctionKind.WRAPPER
        var notes = List[MappingNote]()
        if v.attrs.inline_disposition != InlineDisposition.NONE:
            kind = FunctionKind.DIRECTIVE_STUB
            notes.append(
                stub_note(
                    "inline declaration may not provide a stable external symbol; wrapper omitted"
                )
            )
        elif v.is_variadic and self.session.options.linking == LinkMode.OWNED_DL_HANDLE:
            kind = FunctionKind.VARIADIC_STUB
            notes.append(stub_note("OwnedDLHandle does not expose variadic C ABI metadata"))
        var params = List[MojoParam]()
        for i in range(len(v.params)):
            var p = v.params[i].copy()
            var fallback = String("a" + String(i))
            var name = mojo_ident(p.name, fallback) if p.name.byte_length() else fallback.copy()
            params.append(
                MojoParam(
                    name^, ArcPointer(self.session.type_mapper.run(p.type.ptr()[])), p.doc.copy()
                )
            )
        var fixed: Optional[Int] = {}
        if v.is_variadic:
            fixed = len(v.params)
        return FunctionDecl(
            mojo_ident(v.name),
            v.link_name.copy(),
            params^,
            ArcPointer(self.session.type_mapper.run(v.ret.ptr()[])),
            kind,
            CallTarget(self.session.options.linking, v.link_name.copy()),
            v.attrs.copy(),
            fixed,
            notes^,
            v.doc.copy(),
        )

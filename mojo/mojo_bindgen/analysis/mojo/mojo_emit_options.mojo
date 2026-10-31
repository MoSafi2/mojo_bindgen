from ...ir import LinkMode, PointerOrigin


struct MojoEmitOptions(Copyable, Movable):
    var linking: LinkMode
    var library_path_hint: Optional[String]
    var module_comment: Bool
    var emit_doc_comments: Bool
    var warn_abi: Bool
    var strict_abi: Bool
    var ffi_origin: PointerOrigin

    def __init__(
        out self,
        linking: LinkMode = LinkMode.EXTERNAL_CALL,
        var library_path_hint: Optional[String] = {},
        module_comment: Bool = True,
        emit_doc_comments: Bool = True,
        warn_abi: Bool = True,
        strict_abi: Bool = False,
        ffi_origin: PointerOrigin = PointerOrigin.EXTERNAL,
    ):
        self.linking = linking
        self.library_path_hint = library_path_hint^
        self.module_comment = module_comment
        self.emit_doc_comments = emit_doc_comments
        self.warn_abi = warn_abi
        self.strict_abi = strict_abi
        self.ffi_origin = ffi_origin

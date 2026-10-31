"""Shared binding support source, kept byte-identical to the Python backend."""
from ..ir import LinkMode, MojoModule

comptime _DYNAMIC_LIBRARY_LOADER = '\ndef _bindgen_env_path(name: String) -> String:\n    var value = getenv(name)\n    if value:\n        return value\n    return ""\n\ndef _bindgen_append_dylib_candidate(mut paths: List[Path], path: String):\n    if path != "":\n        paths.append(Path(path))\n\ndef _bindgen_dylib_candidates() -> List[Path]:\n    var paths = List[Path]()\n    _bindgen_append_dylib_candidate(paths, _bindgen_env_path(_BINDGEN_LIB_PATH_ENV))\n    _bindgen_append_dylib_candidate(paths, _bindgen_env_path(_BINDGEN_GENERIC_LIB_PATH_ENV))\n    _bindgen_append_dylib_candidate(paths, _BINDGEN_LIB_PATH_CANDIDATE)\n    comptime suffix = platform_map["shared library suffix", linux=".so", macos=".dylib"]()\n    var filename = "lib" + String(_BINDGEN_LINK_NAME) + String(suffix)\n    var prefix = _bindgen_env_path("CONDA_PREFIX")\n    if prefix:\n        paths.append(Path(prefix + "/lib/" + filename))\n        paths.append(Path(prefix + "/bin/" + filename))\n    var project_root = _bindgen_env_path("PIXI_PROJECT_ROOT")\n    var env_name = _bindgen_env_path("PIXI_ENVIRONMENT_NAME")\n    if project_root and env_name:\n        paths.append(Path(project_root + "/.pixi/envs/" + env_name + "/lib/" + filename))\n    paths.append(Path(String(_BINDGEN_LINK_NAME)))\n    paths.append(Path(filename))\n    comptime if CompilationTarget.is_linux():\n        paths.append(Path(filename + ".1"))\n    elif CompilationTarget.is_macos():\n        paths.append(Path("/usr/local/lib/" + filename))\n        paths.append(Path("/opt/homebrew/lib/" + filename))\n    return paths^\n\ndef _bindgen_init_dylib() -> OwnedDLHandle:\n    var paths = _bindgen_dylib_candidates()\n    for path in paths:\n        try:\n            return OwnedDLHandle(path)\n        except:\n            pass\n    abort(t"bindgen: failed to load dynamic library \'{_BINDGEN_LIB_NAME}\' from {paths}")\n'
comptime _CACHED_DL_HELPERS = "# The cached owner lives until process teardown; do not close it.\ndef _bindgen_dylib() -> Pointer[OwnedDLHandle, MutUntrackedOrigin]:\n    try:\n        return _BINDGEN_DYLIB.get_or_create_ptr()\n    except e:\n        abort(t\"bindgen: failed to initialize dynamic library '{_BINDGEN_LIB_NAME}': {e}\")"
comptime _GLOBAL_SYMBOL_HELPERS = "struct GlobalVar[T: Copyable & Deinitable, //, link: StaticString]:\n    @staticmethod\n    def _raw() -> Pointer[Self.T, MutUntrackedOrigin]:\n        var owner = _bindgen_dylib()\n        if case .Some(ptr) = owner[].get_symbol[Self.T](StringSpan(Self.link)):\n            return ptr\n        abort(t\"bindgen: missing C global symbol '{Self.link}' in dynamic library '{_BINDGEN_LIB_NAME}'\")\n\n    @staticmethod\n    def ptr() -> Pointer[Self.T, MutUntrackedOrigin]:\n        return Self._raw()\n\n    @staticmethod\n    def load() -> Self.T:\n        return Self._raw()[].copy()\n\n    @staticmethod\n    def store(value: Self.T):\n        var p = Self._raw()\n        p[] = value.copy()\n\nstruct GlobalConst[T: Copyable & Deinitable, //, link: StaticString]:\n    @staticmethod\n    def _raw() -> Pointer[Self.T, ImmUntrackedOrigin]:\n        var owner = _bindgen_dylib().as_imm()\n        if case .Some(ptr) = owner[].get_symbol[Self.T](StringSpan(Self.link)):\n            return ptr\n        abort(t\"bindgen: missing C global symbol '{Self.link}' in dynamic library '{_BINDGEN_LIB_NAME}'\")\n\n    @staticmethod\n    def ptr() -> Pointer[Self.T, ImmUntrackedOrigin]:\n        return Self._raw()\n\n    @staticmethod\n    def load() -> Self.T:\n        return Self._raw()[].copy()"
comptime _VARIADIC_HELPERS = 'def _bindgen_check_vararg[T: AnyType]():\n    # Qualified reflection names identify std pointer families without accepting\n    # user structs named Pointer/Optional. Restrict pointers to generic address space.\n    comptime name = reflect[T].name[qualified_builtins=True]()\n    comptime pointer = name.startswith("std.memory.pointer.Pointer[") and name.endswith(", 0]")\n    comptime nullable_pointer = name.startswith("std.collections.optional.Optional[std.memory.pointer.Pointer[") and name.endswith(", 0]]")\n    comptime assert (\n        T == c_int or T == c_uint or T == c_long or T == c_ulong\n        or T == c_long_long or T == c_ulong_long or T == c_double\n        or ((pointer or nullable_pointer) and conforms_to(T, RegisterPassable))\n    ), "C vararg requires a promoted C integer, Float64, or raw pointer; promote narrow integers/Bool to c_int and Float32 to Float64"\n'


def escape_mojo_string(value: String) -> String:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\0", "\\0")
    )


def _library_path_env_var(name: String) -> String:
    var token = String()
    var pending = False
    for cp in name.codepoints():
        if cp.is_ascii() and (cp.is_ascii_lower() or cp.is_ascii_upper() or cp.is_ascii_digit()):
            if pending and token:
                token += "_"
            token += String(cp).upper()
            pending = False
        else:
            pending = True
    return "MOJO_BINDGEN_" + (token if token else String("LIBRARY")) + "_LIBRARY_PATH"


def render_dl_handle_helpers(module: MojoModule) -> String:
    var library = escape_mojo_string(module.library)
    var header = (
        'comptime _BINDGEN_LIB_NAME = "'
        + library
        + '"\ncomptime _BINDGEN_LINK_NAME = "'
        + escape_mojo_string(module.link_name)
        + '"\n'
    )
    var loader: String
    if module.link_mode == LinkMode.EXTERNAL_CALL:
        loader = '\ndef _bindgen_init_dylib() -> OwnedDLHandle:\n    try:\n        return OwnedDLHandle()\n    except e:\n        abort(t"bindgen: failed to open process dynamic symbol table: {e}")\n'
    else:
        header += (
            'comptime _BINDGEN_LIB_PATH_CANDIDATE: String = "'
            + escape_mojo_string(
                module.library_path_hint.value() if module.library_path_hint else String()
            )
            + '"\ncomptime _BINDGEN_LIB_PATH_ENV = "'
            + _library_path_env_var(module.link_name)
            + '"\ncomptime _BINDGEN_GENERIC_LIB_PATH_ENV = "MOJO_BINDGEN_LIBRARY_PATH"\n'
        )
        loader = _DYNAMIC_LIBRARY_LOADER
    return (
        header
        + loader
        + '\n# Private storage adapter: keep the owner alive for existing free-function bindings.\ncomptime _BINDGEN_DYLIB = _Global["mojo_bindgen/'
        + library
        + '", _bindgen_init_dylib]\n\n'
        + _CACHED_DL_HELPERS
    )


def render_global_symbol_helpers() -> String:
    return _GLOBAL_SYMBOL_HELPERS


def render_variadic_helpers() -> String:
    return _VARIADIC_HELPERS

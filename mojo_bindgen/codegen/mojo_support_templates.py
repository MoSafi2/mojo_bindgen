"""Mojo support-code templates used by the printer."""

from __future__ import annotations

import re

from mojo_bindgen.ir import LinkMode, MojoModule


def escape_mojo_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\0", "\\0")
    )


def render_dl_handle_helpers(module: MojoModule) -> str:
    library = escape_mojo_string(module.library)
    header = (
        f'comptime _BINDGEN_LIB_NAME = "{library}"\n'
        f'comptime _BINDGEN_LINK_NAME = "{escape_mojo_string(module.link_name)}"\n'
    )
    if module.link_mode == LinkMode.EXTERNAL_CALL:
        loader = """
def _bindgen_init_dylib() -> OwnedDLHandle:
    try:
        return OwnedDLHandle()
    except e:
        abort(t"bindgen: failed to open process dynamic symbol table: {e}")
"""
    else:
        header += (
            f'comptime _BINDGEN_LIB_PATH_CANDIDATE: String = "{escape_mojo_string(module.library_path_hint or "")}"\n'
            f'comptime _BINDGEN_LIB_PATH_ENV = "{_library_path_env_var(module.link_name)}"\n'
            'comptime _BINDGEN_GENERIC_LIB_PATH_ENV = "MOJO_BINDGEN_LIBRARY_PATH"\n'
        )
        loader = _DYNAMIC_LIBRARY_LOADER
    return (
        header
        + loader
        + "\n# Private storage adapter: keep the owner alive for existing free-function bindings.\n"
        + f'comptime _BINDGEN_DYLIB = _Global["mojo_bindgen/{library}", _bindgen_init_dylib]\n\n'
        + _CACHED_DL_HELPERS
    )


def render_global_symbol_helpers() -> str:
    return _GLOBAL_SYMBOL_HELPERS


def render_variadic_helpers() -> str:
    return _VARIADIC_HELPERS


def _library_path_env_var(link_name: str) -> str:
    token = re.sub(r"[^0-9A-Za-z]+", "_", link_name).strip("_").upper()
    return f"MOJO_BINDGEN_{token or 'LIBRARY'}_LIBRARY_PATH"


_DYNAMIC_LIBRARY_LOADER = """
def _bindgen_env_path(name: String) -> String:
    var value = getenv(name)
    if value:
        return value
    return ""

def _bindgen_append_dylib_candidate(mut paths: List[Path], path: String):
    if path != "":
        paths.append(Path(path))

def _bindgen_dylib_candidates() -> List[Path]:
    var paths = List[Path]()
    _bindgen_append_dylib_candidate(paths, _bindgen_env_path(_BINDGEN_LIB_PATH_ENV))
    _bindgen_append_dylib_candidate(paths, _bindgen_env_path(_BINDGEN_GENERIC_LIB_PATH_ENV))
    _bindgen_append_dylib_candidate(paths, _BINDGEN_LIB_PATH_CANDIDATE)
    comptime suffix = platform_map["shared library suffix", linux=".so", macos=".dylib"]()
    var filename = "lib" + String(_BINDGEN_LINK_NAME) + String(suffix)
    var prefix = _bindgen_env_path("CONDA_PREFIX")
    if prefix:
        paths.append(Path(prefix + "/lib/" + filename))
        paths.append(Path(prefix + "/bin/" + filename))
    var project_root = _bindgen_env_path("PIXI_PROJECT_ROOT")
    var env_name = _bindgen_env_path("PIXI_ENVIRONMENT_NAME")
    if project_root and env_name:
        paths.append(Path(project_root + "/.pixi/envs/" + env_name + "/lib/" + filename))
    paths.append(Path(String(_BINDGEN_LINK_NAME)))
    paths.append(Path(filename))
    comptime if CompilationTarget.is_linux():
        paths.append(Path(filename + ".1"))
    elif CompilationTarget.is_macos():
        paths.append(Path("/usr/local/lib/" + filename))
        paths.append(Path("/opt/homebrew/lib/" + filename))
    return paths^

def _bindgen_init_dylib() -> OwnedDLHandle:
    var paths = _bindgen_dylib_candidates()
    for path in paths:
        try:
            return OwnedDLHandle(path)
        except:
            pass
    abort(t"bindgen: failed to load dynamic library '{_BINDGEN_LIB_NAME}' from {paths}")
"""


_CACHED_DL_HELPERS = """# The cached owner lives until process teardown; do not close it.
def _bindgen_dylib() -> Pointer[OwnedDLHandle, MutUntrackedOrigin]:
    try:
        return _BINDGEN_DYLIB.get_or_create_ptr()
    except e:
        abort(t"bindgen: failed to initialize dynamic library '{_BINDGEN_LIB_NAME}': {e}")"""


_GLOBAL_SYMBOL_HELPERS = """struct GlobalVar[T: Copyable & Deinitable, //, link: StaticString]:
    @staticmethod
    def _raw() -> Pointer[Self.T, MutUntrackedOrigin]:
        var owner = _bindgen_dylib()
        if case .Some(ptr) = owner[].get_symbol[Self.T](StringSpan(Self.link)):
            return ptr
        abort(t"bindgen: missing C global symbol '{Self.link}' in dynamic library '{_BINDGEN_LIB_NAME}'")

    @staticmethod
    def ptr() -> Pointer[Self.T, MutUntrackedOrigin]:
        return Self._raw()

    @staticmethod
    def load() -> Self.T:
        return Self._raw()[].copy()

    @staticmethod
    def store(value: Self.T):
        var p = Self._raw()
        p[] = value.copy()

struct GlobalConst[T: Copyable & Deinitable, //, link: StaticString]:
    @staticmethod
    def _raw() -> Pointer[Self.T, ImmUntrackedOrigin]:
        var owner = _bindgen_dylib().as_imm()
        if case .Some(ptr) = owner[].get_symbol[Self.T](StringSpan(Self.link)):
            return ptr
        abort(t"bindgen: missing C global symbol '{Self.link}' in dynamic library '{_BINDGEN_LIB_NAME}'")

    @staticmethod
    def ptr() -> Pointer[Self.T, ImmUntrackedOrigin]:
        return Self._raw()

    @staticmethod
    def load() -> Self.T:
        return Self._raw()[].copy()"""


_VARIADIC_HELPERS = """def _bindgen_check_vararg[T: AnyType]():
    # Qualified reflection names identify std pointer families without accepting
    # user structs named Pointer/Optional. Restrict pointers to generic address space.
    comptime name = reflect[T].name[qualified_builtins=True]()
    comptime pointer = name.startswith("std.memory.pointer.Pointer[") and name.endswith(", 0]")
    comptime nullable_pointer = name.startswith("std.collections.optional.Optional[std.memory.pointer.Pointer[") and name.endswith(", 0]]")
    comptime assert (
        T == c_int or T == c_uint or T == c_long or T == c_ulong
        or T == c_long_long or T == c_ulong_long or T == c_double
        or ((pointer or nullable_pointer) and conforms_to(T, RegisterPassable))
    ), "C vararg requires a promoted C integer, Float64, or raw pointer; promote narrow integers/Bool to c_int and Float32 to Float64"
"""

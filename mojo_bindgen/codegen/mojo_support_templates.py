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
    library_lit = escape_mojo_string(module.library)
    link_lit = escape_mojo_string(module.link_name)
    if module.link_mode == LinkMode.EXTERNAL_CALL:
        return _render_external_call_dl_handle_helpers(library_lit, link_lit)
    return _render_owned_dl_handle_helpers(module, library_lit, link_lit)


def render_global_symbol_helpers() -> str:
    return _GLOBAL_SYMBOL_HELPERS


def _render_external_call_dl_handle_helpers(library_lit: str, link_lit: str) -> str:
    return (
        f'comptime _BINDGEN_LIB_NAME = "{library_lit}"\n'
        f'comptime _BINDGEN_LINK_NAME = "{link_lit}"\n'
        "\n"
        "def _bindgen_init_dylib() -> OwnedDLHandle:\n"
        "    try:\n"
        "        return OwnedDLHandle(DEFAULT_RTLD)\n"
        "    except e:\n"
        '        abort(t"bindgen: failed to open process dynamic symbol table: {e}")\n'
        "\n"
        'comptime _BINDGEN_DYLIB = _Global["mojo_bindgen/'
        f'{library_lit}", _bindgen_init_dylib]\n'
        "\n" + _CACHED_DL_HELPERS
    )


def _render_owned_dl_handle_helpers(
    module: MojoModule,
    library_lit: str,
    link_lit: str,
) -> str:
    path_lit = escape_mojo_string(module.library_path_hint or "")
    env_name_lit = escape_mojo_string(_library_path_env_var(module.link_name))
    return (
        f'comptime _BINDGEN_LIB_NAME = "{library_lit}"\n'
        f'comptime _BINDGEN_LINK_NAME = "{link_lit}"\n'
        f'comptime _BINDGEN_LIB_PATH_CANDIDATE: String = "{path_lit}"\n'
        f'comptime _BINDGEN_LIB_PATH_ENV = "{env_name_lit}"\n'
        'comptime _BINDGEN_GENERIC_LIB_PATH_ENV = "MOJO_BINDGEN_LIBRARY_PATH"\n'
        "\n"
        "def _bindgen_env_path(name: String) -> String:\n"
        "    var value = getenv(name)\n"
        "    if value:\n"
        "        return value\n"
        '    return ""\n'
        "\n"
        "def _bindgen_prefix_lib_path(prefix_name: String, subdir: String) -> String:\n"
        "    var prefix = getenv(prefix_name)\n"
        "    if prefix:\n"
        '        return prefix + "/" + subdir\n'
        '    return ""\n'
        "\n"
        "def _bindgen_pixi_env_lib_path(subdir: String) -> String:\n"
        '    var project_root = getenv("PIXI_PROJECT_ROOT")\n'
        '    var env_name = getenv("PIXI_ENVIRONMENT_NAME")\n'
        "    if project_root and env_name:\n"
        '        return project_root + "/.pixi/envs/" + env_name + "/" + subdir\n'
        '    return ""\n'
        "\n"
        "def _bindgen_append_dylib_candidate(mut paths: List[Path], path: String) -> None:\n"
        '    if path != "":\n'
        "        paths.append(Path(path))\n"
        "\n"
        "def _bindgen_dylib_candidates() -> List[Path]:\n"
        "    var paths = List[Path]()\n"
        "    _bindgen_append_dylib_candidate(paths, _bindgen_env_path(_BINDGEN_LIB_PATH_ENV))\n"
        "    _bindgen_append_dylib_candidate(paths, _bindgen_env_path(_BINDGEN_GENERIC_LIB_PATH_ENV))\n"
        "    _bindgen_append_dylib_candidate(paths, _BINDGEN_LIB_PATH_CANDIDATE)\n"
        '    _bindgen_append_dylib_candidate(paths, _bindgen_prefix_lib_path("CONDA_PREFIX", "lib/lib" + String(_BINDGEN_LINK_NAME) + ".so"))\n'
        '    _bindgen_append_dylib_candidate(paths, _bindgen_prefix_lib_path("CONDA_PREFIX", "lib/lib" + String(_BINDGEN_LINK_NAME) + ".so.1"))\n'
        '    _bindgen_append_dylib_candidate(paths, _bindgen_prefix_lib_path("CONDA_PREFIX", "lib/lib" + String(_BINDGEN_LINK_NAME) + ".dylib"))\n'
        '    _bindgen_append_dylib_candidate(paths, _bindgen_prefix_lib_path("CONDA_PREFIX", "bin/lib" + String(_BINDGEN_LINK_NAME) + ".so"))\n'
        '    _bindgen_append_dylib_candidate(paths, _bindgen_prefix_lib_path("CONDA_PREFIX", "bin/lib" + String(_BINDGEN_LINK_NAME) + ".dylib"))\n'
        '    _bindgen_append_dylib_candidate(paths, _bindgen_pixi_env_lib_path("lib/lib" + String(_BINDGEN_LINK_NAME) + ".so"))\n'
        '    _bindgen_append_dylib_candidate(paths, _bindgen_pixi_env_lib_path("lib/lib" + String(_BINDGEN_LINK_NAME) + ".so.1"))\n'
        '    _bindgen_append_dylib_candidate(paths, _bindgen_pixi_env_lib_path("lib/lib" + String(_BINDGEN_LINK_NAME) + ".dylib"))\n'
        "    _bindgen_append_dylib_candidate(paths, String(_BINDGEN_LINK_NAME))\n"
        '    _bindgen_append_dylib_candidate(paths, "lib" + String(_BINDGEN_LINK_NAME) + ".so")\n'
        '    _bindgen_append_dylib_candidate(paths, "lib" + String(_BINDGEN_LINK_NAME) + ".so.1")\n'
        '    _bindgen_append_dylib_candidate(paths, "lib" + String(_BINDGEN_LINK_NAME) + ".dylib")\n'
        '    _bindgen_append_dylib_candidate(paths, "/lib/lib" + String(_BINDGEN_LINK_NAME) + ".so")\n'
        '    _bindgen_append_dylib_candidate(paths, "/lib/lib" + String(_BINDGEN_LINK_NAME) + ".so.1")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/lib/lib" + String(_BINDGEN_LINK_NAME) + ".so")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/lib/lib" + String(_BINDGEN_LINK_NAME) + ".so.1")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/local/lib/lib" + String(_BINDGEN_LINK_NAME) + ".so")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/local/lib/lib" + String(_BINDGEN_LINK_NAME) + ".so.1")\n'
        '    _bindgen_append_dylib_candidate(paths, "/lib/x86_64-linux-gnu/lib" + String(_BINDGEN_LINK_NAME) + ".so")\n'
        '    _bindgen_append_dylib_candidate(paths, "/lib/x86_64-linux-gnu/lib" + String(_BINDGEN_LINK_NAME) + ".so.1")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/lib/x86_64-linux-gnu/lib" + String(_BINDGEN_LINK_NAME) + ".so")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/lib/x86_64-linux-gnu/lib" + String(_BINDGEN_LINK_NAME) + ".so.1")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/local/lib/lib" + String(_BINDGEN_LINK_NAME) + ".dylib")\n'
        '    _bindgen_append_dylib_candidate(paths, "/opt/homebrew/lib/lib" + String(_BINDGEN_LINK_NAME) + ".dylib")\n'
        '    _bindgen_append_dylib_candidate(paths, "/usr/lib/lib" + String(_BINDGEN_LINK_NAME) + ".dylib")\n'
        "    return paths^\n"
        "\n"
        "def _bindgen_init_dylib() -> OwnedDLHandle:\n"
        "    var paths = _bindgen_dylib_candidates()\n"
        "    return _find_dylib[_BINDGEN_LIB_NAME](paths)\n"
        "\n"
        'comptime _BINDGEN_DYLIB = _Global["mojo_bindgen/'
        f'{library_lit}", _bindgen_init_dylib]\n'
        "\n" + _CACHED_DL_HELPERS
    )


def _library_path_env_var(link_name: str) -> str:
    token = re.sub(r"[^0-9A-Za-z]+", "_", link_name).strip("_").upper()
    if not token:
        token = "LIBRARY"
    return f"MOJO_BINDGEN_{token}_LIBRARY_PATH"


_CACHED_DL_HELPERS = """# Returns a borrowed process-lifetime dynamic library handle; do not close it.
def _bindgen_dylib() -> _DLHandle:
    var dylib_ptr = _get_global[
        _BINDGEN_DYLIB.name,
        _BINDGEN_DYLIB._init_wrapper,
        _BINDGEN_DYLIB._deinit_wrapper,
    ]()
    var dylib = unsafe_cast[Type=_BINDGEN_DYLIB.StorageType](dylib_ptr).value()[].borrow()
    if not dylib:
        abort(t"bindgen: failed to load dynamic library '{_BINDGEN_LIB_NAME}'")
    return dylib

def _bindgen_function[Fn: TrivialRegisterPassable](symbol: StringSlice) -> Fn:
    var fn_ptr = _bindgen_dylib().get_symbol[NoneType](symbol)
    if not fn_ptr:
        abort(
            t"bindgen: missing C function symbol '{symbol}' "
            t"in dynamic library '{_BINDGEN_LIB_NAME}'"
        )
    return UnsafePointer(to=fn_ptr.value()).bitcast[Fn]()[]"""


_GLOBAL_SYMBOL_HELPERS = """struct GlobalVar[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:
    @staticmethod
    def _raw() -> UnsafePointer[Self.T, MutUntrackedOrigin]:
        var opt: Optional[UnsafePointer[Self.T, MutUntrackedOrigin]] = _bindgen_dylib().get_symbol[Self.T](StringSlice(Self.link))
        if not opt:
            abort(
                t"bindgen: missing C global symbol '{Self.link}' "
                t"in dynamic library '{_BINDGEN_LIB_NAME}'"
            )
        return opt.value()

    @staticmethod
    def ptr() -> UnsafePointer[Self.T, MutUntrackedOrigin]:
        return rebind[UnsafePointer[Self.T, MutUntrackedOrigin]](Self._raw())

    @staticmethod
    def load() -> Self.T:
        return Self._raw()[].copy()

    @staticmethod
    def store(value: Self.T) -> None:
        var p = rebind[UnsafePointer[Self.T, MutUntrackedOrigin]](Self._raw())
        p[] = value.copy()

struct GlobalConst[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:
    @staticmethod
    def _raw() -> UnsafePointer[Self.T, MutUntrackedOrigin]:
        var opt: Optional[UnsafePointer[Self.T, MutUntrackedOrigin]] = _bindgen_dylib().get_symbol[Self.T](StringSlice(Self.link))
        if not opt:
            abort(
                t"bindgen: missing C global symbol '{Self.link}' "
                t"in dynamic library '{_BINDGEN_LIB_NAME}'"
            )
        return opt.value()

    @staticmethod
    def ptr() -> UnsafePointer[Self.T, ImmutUntrackedOrigin]:
        return rebind[UnsafePointer[Self.T, ImmutUntrackedOrigin]](Self._raw())

    @staticmethod
    def load() -> Self.T:
        return Self._raw()[].copy()"""

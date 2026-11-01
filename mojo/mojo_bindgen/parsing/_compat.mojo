"""Localized build-1 unsaved-file keepalive adapter.

Upstream Index.parse drops its untracked UnsavedFileArena after extracting the
pointer/count. Borrow the arena across the C call so it cannot be destroyed
before clang_parseTranslationUnit2 returns. Remove after an upstream fix.
"""
from clang.cindex import Index, TranslationUnit, UnsavedFile, TranslationUnitFlags
from clang.common import UnsavedFileArena, _alloc_c_string, _c_string
from clang._ffi import CXTranslationUnit, clang_parseTranslationUnit2
from std.ffi import c_char, c_int
from std.memory.alloc import unsafe_alloc


def _parse_borrowed(
    ref index: Index,
    ref arena: UnsavedFileArena,
    ref path: String,
    ref args: List[String],
    options: TranslationUnitFlags,
) raises -> TranslationUnit:
    var filename = _alloc_c_string(path)
    var strings = List[Pointer[c_char, MutUntrackedOrigin]]()
    var arguments = unsafe_alloc[Optional[Pointer[c_char, ImmUntrackedOrigin]]](max(1, len(args)))
    try:
        for arg in args:
            var text = _alloc_c_string(arg)
            strings.append(text)
            arguments[unsafe_offset=len(strings) - 1] = _c_string(text)
        var output = CXTranslationUnit()
        var error = clang_parseTranslationUnit2(
            index._raw_handle(),
            _c_string(filename),
            rebind[Pointer[Optional[Pointer[c_char, ImmUntrackedOrigin]], ImmUntrackedOrigin]](
                arguments
            ),
            c_int(len(args)),
            arena.ptr(),
            arena.count(),
            options.as_c_uint(),
            Pointer(to=output).unsafe_origin_cast[MutUntrackedOrigin](),
        )
        if error != 0:
            raise Error("TranslationUnitLoadError: parse failed: error code=" + String(error))
        return TranslationUnit(index._shared_state(), output)
    finally:
        for text in strings:
            text.unsafe_free()
        arguments.unsafe_free()
        filename.unsafe_free()


def parse_translation_unit(
    ref index: Index,
    path: String,
    args: List[String],
    files: List[UnsavedFile] = [],
    options: TranslationUnitFlags = TranslationUnitFlags.NONE,
) raises -> TranslationUnit:
    var arena = UnsavedFileArena(files)
    return _parse_borrowed(index, arena, path, args, options)

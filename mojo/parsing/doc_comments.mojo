# Helpers for extracting source documentation comments from libclang cursors.
#
# Ported from `mojo_bindgen/parsing/doc_comments.py`.

from clang.cindex import Cursor
from mojo.ir import DocComment


def cursor_doc_comment(cursor: Cursor) raises -> Optional[DocComment]:
    """Return the raw documentation comment attached to cursor, if any."""
    var raw_opt = cursor.raw_comment()
    if not raw_opt:
        return None

    var raw = raw_opt.value()
    if raw.strip() == "":
        return None

    var brief_opt = cursor.brief_comment()
    var brief: Optional[String] = None
    if brief_opt:
        var brief_str = String(brief_opt.value().strip())
        if brief_str.byte_length() > 0:
            brief = Optional[String](brief_str)

    return Optional[DocComment](DocComment(
        kind="DocComment",
        text=raw,
        brief=brief,
        source="clang_raw",
    ))
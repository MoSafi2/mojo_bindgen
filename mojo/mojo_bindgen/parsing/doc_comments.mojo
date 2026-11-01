from clang.cindex import Cursor
from ..ir import DocComment
from ..analysis.common import strip_whitespace


def cursor_doc_comment(ref cursor: Cursor) raises -> Optional[DocComment]:
    var raw = cursor.raw_comment()
    if not raw or not strip_whitespace(raw.value()):
        return None
    var brief = cursor.brief_comment()
    if brief:
        var text = strip_whitespace(brief.value())
        brief = Optional[String](text) if text else Optional[String]()
    return DocComment(raw.value(), brief^)

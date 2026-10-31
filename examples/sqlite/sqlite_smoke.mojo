import sqlite3_bindings as sql
from std.ffi import c_int, c_char
from std.memory.alloc import alloc, Layout


# ---------------------------
# Assertions + diagnostics
# ---------------------------


def _assert(label: String, cond: Bool) raises:
    if not cond:
        raise Error("ASSERT FAILED: " + label)
    print(label + "|ok")


def _cstr(s: StaticString) -> Pointer[c_char, ImmUntrackedOrigin]:
    return rebind[Pointer[c_char, ImmUntrackedOrigin]](s.unsafe_ptr())


def _ignore_exec_row(
    data: Optional[OpaquePointer[mut=True, MutUntrackedOrigin]],
    columns: c_int,
    values: Optional[Pointer[Optional[Pointer[c_char, MutUntrackedOrigin]], MutUntrackedOrigin]],
    names: Optional[Pointer[Optional[Pointer[c_char, MutUntrackedOrigin]], MutUntrackedOrigin]],
) abi("C") -> c_int:
    return 0


def _ignore_bound_value(
    value: Optional[Pointer[NoneType, MutUntrackedOrigin]],
) abi("C"):
    pass


def _errmsg(db: Pointer[sql.sqlite3, MutUntrackedOrigin]) -> String:
    var p = sql.sqlite3_errmsg(db)
    if p == Optional[Pointer[c_char, ImmUntrackedOrigin]]():
        return "<null errmsg>"
    return String(p.value())


def _check_db_rc(label: String, db: Pointer[sql.sqlite3, MutUntrackedOrigin], rc: Int32) raises:
    if rc != Int32(sql.SQLITE_OK):
        raise Error(label + " rc=" + String(rc) + " err=" + _errmsg(db))
    print(label + "|ok")


# ---------------------------
# Core helpers
# ---------------------------


def _open_memory() raises -> Pointer[sql.sqlite3, MutUntrackedOrigin]:
    var ppDb = alloc(
        Layout[Optional[Pointer[sql.sqlite3, MutUntrackedOrigin]]](count=1)
    ).unsafe_leak()
    var rc = sql.sqlite3_open_v2(
        _cstr(":memory:\0"),
        ppDb,
        Int32(sql.SQLITE_OPEN_READWRITE | sql.SQLITE_OPEN_CREATE),
        Optional[Pointer[c_char, ImmUntrackedOrigin]](),
    )
    _assert("open.rc", rc == Int32(sql.SQLITE_OK))
    _assert(
        "open.nonnull",
        ppDb[unsafe_offset=0] != Optional[Pointer[sql.sqlite3, MutUntrackedOrigin]](),
    )
    return ppDb[unsafe_offset=0].value()


def _exec(
    db: Pointer[sql.sqlite3, MutUntrackedOrigin],
    s: StaticString,
    label: String,
) raises:
    var rc = sql.sqlite3_exec(
        db,
        _cstr(s),
        _ignore_exec_row,
        Optional[OpaquePointer[mut=True, MutUntrackedOrigin]](),
        alloc(Layout[Optional[Pointer[c_char, MutUntrackedOrigin]]](count=1)).unsafe_leak(),
    )
    _check_db_rc(label, db, rc)


def _prepare(
    db: Pointer[sql.sqlite3, MutUntrackedOrigin],
    s: StaticString,
    label: String,
) raises -> Pointer[sql.sqlite3_stmt, MutUntrackedOrigin]:
    var pp = alloc(
        Layout[Optional[Pointer[sql.sqlite3_stmt, MutUntrackedOrigin]]](count=1)
    ).unsafe_leak()
    var rc = sql.sqlite3_prepare_v2(
        db,
        _cstr(s),
        -1,
        pp,
        alloc(Layout[Optional[Pointer[c_char, ImmUntrackedOrigin]]](count=1)).unsafe_leak(),
    )
    _check_db_rc(label, db, rc)
    return pp[unsafe_offset=0].value()


def _finalize(stmt: Pointer[sql.sqlite3_stmt, MutUntrackedOrigin], label: String) raises:
    var rc = sql.sqlite3_finalize(stmt)
    _assert(label, rc == Int32(sql.SQLITE_OK))


# ---------------------------
# Tests
# ---------------------------


def run_basic_checks() raises:
    _assert("libversion_number", sql.sqlite3_libversion_number() > 0)
    var v = sql.sqlite3_libversion()
    _assert("libversion_ptr", v != Optional[Pointer[c_char, ImmUntrackedOrigin]]())
    print("basic|PASS")


def run_exec_and_rowid(
    db: Pointer[sql.sqlite3, MutUntrackedOrigin],
) raises -> None:
    _exec(
        db,
        "CREATE TABLE t (id INTEGER PRIMARY KEY, v INT);\0",
        "exec.create",
    )

    _exec(db, "INSERT INTO t(v) VALUES (42);\0", "exec.insert")

    var rid = sql.sqlite3_last_insert_rowid(db)
    _assert("rowid.valid", rid >= 1)

    print("exec_rowid|PASS")


def run_prepare_reuse(db: Pointer[sql.sqlite3, MutUntrackedOrigin]) raises:
    _exec(db, "CREATE TABLE t2 (v INT);\0", "prep.schema")

    var stmt = _prepare(db, "INSERT INTO t2(v) VALUES (?);\0", "prep.insert")

    var rc = sql.sqlite3_bind_int(stmt, 1, 7)
    _assert("bind.int", rc == Int32(sql.SQLITE_OK))

    _assert("step.done", sql.sqlite3_step(stmt) == Int32(sql.SQLITE_DONE))

    # reuse
    _assert("reset", sql.sqlite3_reset(stmt) == Int32(sql.SQLITE_OK))

    rc = sql.sqlite3_bind_int(stmt, 1, 9)
    _assert("bind.int2", rc == Int32(sql.SQLITE_OK))

    _assert("step.done2", sql.sqlite3_step(stmt) == Int32(sql.SQLITE_DONE))

    _finalize(stmt, "finalize.reuse")

    print("prepare_reuse|PASS")


def run_text_roundtrip(
    db: Pointer[sql.sqlite3, MutUntrackedOrigin],
) raises -> None:
    _exec(db, "CREATE TABLE txt (v TEXT);\0", "text.schema")

    var stmt = _prepare(db, "INSERT INTO txt(v) VALUES (?);\0", "text.prepare")

    var txt = _cstr("hello-world\0")
    var rc = sql.sqlite3_bind_text(
        stmt,
        1,
        txt,
        -1,
        _ignore_bound_value,
    )
    _assert("bind.text", rc == Int32(sql.SQLITE_OK))

    _assert("step.text.insert", sql.sqlite3_step(stmt) == Int32(sql.SQLITE_DONE))
    _finalize(stmt, "finalize.text.insert")

    stmt = _prepare(db, "SELECT v FROM txt;\0", "text.select")

    _assert("step.text.row", sql.sqlite3_step(stmt) == Int32(sql.SQLITE_ROW))

    _assert(
        "col.type.text",
        sql.sqlite3_column_type(stmt, 0) == Int32(sql.SQLITE_TEXT),
    )

    var p = sql.sqlite3_column_text(stmt, 0)
    _assert("col.text.ptr", p != Optional[Pointer[UInt8, ImmUntrackedOrigin]]())

    _finalize(stmt, "finalize.text.select")

    print("text|PASS")


def run_blob_roundtrip(db: Pointer[sql.sqlite3, MutUntrackedOrigin]) raises:
    _exec(db, "CREATE TABLE b (v BLOB);\0", "blob.schema")

    var stmt = _prepare(db, "INSERT INTO b(v) VALUES (?);\0", "blob.prepare")

    var buf = alloc(Layout[UInt8](count=4)).unsafe_leak()
    buf[unsafe_offset=0] = 1
    buf[unsafe_offset=1] = 2
    buf[unsafe_offset=2] = 3
    buf[unsafe_offset=3] = 4

    var rc = sql.sqlite3_bind_blob(
        stmt,
        1,
        rebind[OpaquePointer[mut=False, ImmUntrackedOrigin]](buf),
        4,
        _ignore_bound_value,
    )
    _assert("bind.blob", rc == Int32(sql.SQLITE_OK))

    _assert("step.blob.insert", sql.sqlite3_step(stmt) == Int32(sql.SQLITE_DONE))
    _finalize(stmt, "finalize.blob.insert")

    stmt = _prepare(db, "SELECT v FROM b;\0", "blob.select")

    _assert("step.blob.row", sql.sqlite3_step(stmt) == Int32(sql.SQLITE_ROW))

    _assert(
        "col.type.blob",
        sql.sqlite3_column_type(stmt, 0) == Int32(sql.SQLITE_BLOB),
    )

    var size = sql.sqlite3_column_bytes(stmt, 0)
    _assert("blob.size", size == 4)

    var data = sql.sqlite3_column_blob(stmt, 0)
    _assert("blob.ptr", data != Optional[OpaquePointer[mut=False, ImmUntrackedOrigin]]())

    _finalize(stmt, "finalize.blob.select")

    print("blob|PASS")


# ---------------------------
# Main
# ---------------------------


def main() raises:
    print("=== SQLite sharpened smoke ===")

    run_basic_checks()

    var db = _open_memory()

    run_exec_and_rowid(db)
    run_prepare_reuse(db)
    run_text_roundtrip(db)
    run_blob_roundtrip(db)

    _assert("close", sql.sqlite3_close(db) == Int32(sql.SQLITE_OK))

    print("")
    print("=== ALL TESTS PASSED ===")

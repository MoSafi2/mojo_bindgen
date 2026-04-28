import sqlite3_bindings as sql
from std.ffi import c_int
from std.memory import alloc


# ---------------------------
# Assertions + diagnostics
# ---------------------------


def _assert(label: String, cond: Bool) raises:
    if not cond:
        raise Error("ASSERT FAILED: " + label)
    print(label + "|ok")


def _cstr(s: StaticString) -> UnsafePointer[Int8, ImmutExternalOrigin]:
    return rebind[UnsafePointer[Int8, ImmutExternalOrigin]](s.unsafe_ptr())


def _ignore_exec_row(
    data: MutOpaquePointer[MutExternalOrigin],
    columns: c_int,
    values: UnsafePointer[UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin],
    names: UnsafePointer[UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin],
) abi("C") -> c_int:
    return 0


def _ignore_bound_value(value: MutOpaquePointer[MutExternalOrigin]) abi("C"):
    pass


def _errmsg(db: UnsafePointer[sql.sqlite3, MutExternalOrigin]) -> String:
    var p = sql.sqlite3_errmsg(db)
    if p == UnsafePointer[Int8, ImmutExternalOrigin]():
        return "<null errmsg>"
    return String(p)


def _check_db_rc(
    label: String, db: UnsafePointer[sql.sqlite3, MutExternalOrigin], rc: Int32
) raises:
    if rc != sql.SQLITE_OK:
        raise Error(label + " rc=" + String(rc) + " err=" + _errmsg(db))
    print(label + "|ok")


# ---------------------------
# Core helpers
# ---------------------------


def _open_memory() raises -> UnsafePointer[sql.sqlite3, MutExternalOrigin]:
    var ppDb = alloc[UnsafePointer[sql.sqlite3, MutExternalOrigin]](1)
    var rc = sql.sqlite3_open_v2(
        _cstr(":memory:\0"),
        ppDb,
        sql.SQLITE_OPEN_READWRITE | sql.SQLITE_OPEN_CREATE,
        UnsafePointer[Int8, ImmutExternalOrigin](),
    )
    _assert("open.rc", rc == sql.SQLITE_OK)
    _assert(
        "open.nonnull",
        ppDb[0] != UnsafePointer[sql.sqlite3, MutExternalOrigin](),
    )
    return ppDb[0]


def _exec(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin],
    s: StaticString,
    label: String,
) raises:
    var rc = sql.sqlite3_exec(
        db,
        _cstr(s),
        _ignore_exec_row,
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _check_db_rc(label, db, rc)


def _prepare(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin],
    s: StaticString,
    label: String,
) raises -> UnsafePointer[sql.sqlite3_stmt, MutExternalOrigin]:
    var pp = alloc[UnsafePointer[sql.sqlite3_stmt, MutExternalOrigin]](1)
    var rc = sql.sqlite3_prepare_v2(
        db,
        _cstr(s),
        -1,
        pp,
        UnsafePointer[
            UnsafePointer[Int8, ImmutExternalOrigin], MutExternalOrigin
        ](),
    )
    _check_db_rc(label, db, rc)
    return pp[0]


def _finalize(
    stmt: UnsafePointer[sql.sqlite3_stmt, MutExternalOrigin], label: String
) raises:
    var rc = sql.sqlite3_finalize(stmt)
    _assert(label, rc == sql.SQLITE_OK)


# ---------------------------
# Tests
# ---------------------------


def run_basic_checks() raises:
    _assert("libversion_number", sql.sqlite3_libversion_number() > 0)
    var v = sql.sqlite3_libversion()
    _assert("libversion_ptr", v != UnsafePointer[Int8, ImmutExternalOrigin]())
    print("basic|PASS")


def run_exec_and_rowid(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin],
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


def run_prepare_reuse(db: UnsafePointer[sql.sqlite3, MutExternalOrigin]) raises:
    _exec(db, "CREATE TABLE t2 (v INT);\0", "prep.schema")

    var stmt = _prepare(db, "INSERT INTO t2(v) VALUES (?);\0", "prep.insert")

    var rc = sql.sqlite3_bind_int(stmt, 1, 7)
    _assert("bind.int", rc == sql.SQLITE_OK)

    _assert("step.done", sql.sqlite3_step(stmt) == sql.SQLITE_DONE)

    # reuse
    _assert("reset", sql.sqlite3_reset(stmt) == sql.SQLITE_OK)

    rc = sql.sqlite3_bind_int(stmt, 1, 9)
    _assert("bind.int2", rc == sql.SQLITE_OK)

    _assert("step.done2", sql.sqlite3_step(stmt) == sql.SQLITE_DONE)

    _finalize(stmt, "finalize.reuse")

    print("prepare_reuse|PASS")


def run_text_roundtrip(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin],
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
    _assert("bind.text", rc == sql.SQLITE_OK)

    _assert("step.text.insert", sql.sqlite3_step(stmt) == sql.SQLITE_DONE)
    _finalize(stmt, "finalize.text.insert")

    stmt = _prepare(db, "SELECT v FROM txt;\0", "text.select")

    _assert("step.text.row", sql.sqlite3_step(stmt) == sql.SQLITE_ROW)

    _assert(
        "col.type.text",
        sql.sqlite3_column_type(stmt, 0) == sql.SQLITE_TEXT,
    )

    var p = sql.sqlite3_column_text(stmt, 0)
    _assert("col.text.ptr", p != UnsafePointer[UInt8, ImmutExternalOrigin]())

    _finalize(stmt, "finalize.text.select")

    print("text|PASS")


def run_blob_roundtrip(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin]
) raises:
    _exec(db, "CREATE TABLE b (v BLOB);\0", "blob.schema")

    var stmt = _prepare(db, "INSERT INTO b(v) VALUES (?);\0", "blob.prepare")

    var buf = alloc[UInt8](4)
    buf[0] = 1
    buf[1] = 2
    buf[2] = 3
    buf[3] = 4

    var rc = sql.sqlite3_bind_blob(
        stmt,
        1,
        rebind[ImmutOpaquePointer[ImmutExternalOrigin]](buf),
        4,
        _ignore_bound_value,
    )
    _assert("bind.blob", rc == sql.SQLITE_OK)

    _assert("step.blob.insert", sql.sqlite3_step(stmt) == sql.SQLITE_DONE)
    _finalize(stmt, "finalize.blob.insert")

    stmt = _prepare(db, "SELECT v FROM b;\0", "blob.select")

    _assert("step.blob.row", sql.sqlite3_step(stmt) == sql.SQLITE_ROW)

    _assert(
        "col.type.blob",
        sql.sqlite3_column_type(stmt, 0) == sql.SQLITE_BLOB,
    )

    var size = sql.sqlite3_column_bytes(stmt, 0)
    _assert("blob.size", size == 4)

    var data = sql.sqlite3_column_blob(stmt, 0)
    _assert("blob.ptr", data != ImmutOpaquePointer[ImmutExternalOrigin]())

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

    _assert("close", sql.sqlite3_close(db) == sql.SQLITE_OK)

    print("")
    print("=== ALL TESTS PASSED ===")

# Composite runtime smoke for mojo_bindgen SQLite FFI bindings.
# Requires sqlite3_bindings.mojo (see generate.sh).
import sqlite3_bindings as sql
from std.memory import alloc


def _assert(label: String, cond: Bool) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + label)
    print(label + "|ok")


def _cstr(s: StaticString) -> UnsafePointer[Int8, ImmutExternalOrigin]:
    return rebind[UnsafePointer[Int8, ImmutExternalOrigin]](s.unsafe_ptr())


def _null_exec_cb() -> UnsafePointer[sql.sqlite3_exec_cb, MutExternalOrigin]:
    return UnsafePointer[sql.sqlite3_exec_cb, MutExternalOrigin]()


def _open_memory() raises -> UnsafePointer[sql.sqlite3, MutExternalOrigin]:
    var ppDb = alloc[UnsafePointer[sql.sqlite3, MutExternalOrigin]](1)
    var path = _cstr(":memory:\0")
    var flags = sql.SQLITE_OPEN_READWRITE | sql.SQLITE_OPEN_CREATE
    var zvfs = UnsafePointer[Int8, ImmutExternalOrigin]()
    var rc = sql.sqlite3_open_v2(path, ppDb, flags, zvfs)
    _assert("sqlite.open_v2_rc", rc == sql.SQLITE_OK)
    _assert(
        "sqlite.open_v2_nonnull",
        ppDb[0] != UnsafePointer[sql.sqlite3, MutExternalOrigin](),
    )
    return ppDb[0]


def run_version_and_init_checks() raises:
    var vn = sql.sqlite3_libversion_number()
    _assert("sqlite.libversion_number_positive", vn > 0)
    var ts = sql.sqlite3_threadsafe()
    _assert("sqlite.threadsafe_range", (ts == 0) or (ts == 1) or (ts == 2))
    var ini = sql.sqlite3_initialize()
    _assert("sqlite.initialize_ok", ini == sql.SQLITE_OK)
    print("sqlite.version_init|PASS")


def run_exec_checks(db: UnsafePointer[sql.sqlite3, MutExternalOrigin]) raises:
    var sql_create = _cstr(
        "CREATE TABLE IF NOT EXISTS smoke_exec (id INTEGER PRIMARY KEY, v"
        " INT);\0"
    )
    var rc = sql.sqlite3_exec(
        db,
        sql_create,
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.exec_create", rc == sql.SQLITE_OK)

    var sql_ins = _cstr("INSERT INTO smoke_exec (v) VALUES (99);\0")
    rc = sql.sqlite3_exec(
        db,
        sql_ins,
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.exec_insert", rc == sql.SQLITE_OK)
    print("sqlite.exec|PASS")


def run_prepare_statement_checks(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin]
) raises:
    var sql_create = _cstr(
        "CREATE TABLE IF NOT EXISTS smoke_prep (id INTEGER PRIMARY KEY, i INT,"
        " d REAL, n INT);\0"
    )
    var rc = sql.sqlite3_exec(
        db,
        sql_create,
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.prep_exec_schema", rc == sql.SQLITE_OK)

    var ins = _cstr("INSERT INTO smoke_prep (i, d, n) VALUES (?, ?, ?);\0")
    var ppStmt = alloc[UnsafePointer[sql.sqlite3_stmt, MutExternalOrigin]](1)
    var pzTail = UnsafePointer[
        UnsafePointer[Int8, ImmutExternalOrigin], MutExternalOrigin
    ]()
    rc = sql.sqlite3_prepare_v2(db, ins, -1, ppStmt, pzTail)
    _assert("sqlite.prepare_insert", rc == sql.SQLITE_OK)
    _assert(
        "sqlite.prepare_param_count",
        sql.sqlite3_bind_parameter_count(ppStmt[0]) == 3,
    )

    rc = sql.sqlite3_bind_int(ppStmt[0], 1, 7)
    _assert("sqlite.bind_int", rc == sql.SQLITE_OK)
    rc = sql.sqlite3_bind_double(ppStmt[0], 2, 2.5)
    _assert("sqlite.bind_double", rc == sql.SQLITE_OK)
    rc = sql.sqlite3_bind_null(ppStmt[0], 3)
    _assert("sqlite.bind_null", rc == sql.SQLITE_OK)

    var step = sql.sqlite3_step(ppStmt[0])
    _assert("sqlite.step_insert_done", step == sql.SQLITE_DONE)
    rc = sql.sqlite3_finalize(ppStmt[0])
    _assert("sqlite.finalize_insert", rc == sql.SQLITE_OK)

    var sel = _cstr("SELECT i, d, n FROM smoke_prep WHERE id = 1;\0")
    ppStmt = alloc[UnsafePointer[sql.sqlite3_stmt, MutExternalOrigin]](1)
    rc = sql.sqlite3_prepare_v2(db, sel, -1, ppStmt, pzTail)
    _assert("sqlite.prepare_select", rc == sql.SQLITE_OK)
    step = sql.sqlite3_step(ppStmt[0])
    _assert("sqlite.step_select_row", step == sql.SQLITE_ROW)
    _assert("sqlite.column_count", sql.sqlite3_column_count(ppStmt[0]) == 3)
    _assert("sqlite.column_int", sql.sqlite3_column_int(ppStmt[0], 0) == 7)
    _assert(
        "sqlite.column_double", sql.sqlite3_column_double(ppStmt[0], 1) == 2.5
    )
    _assert(
        "sqlite.column_type_null",
        sql.sqlite3_column_type(ppStmt[0], 2) == sql.SQLITE_NULL,
    )
    step = sql.sqlite3_step(ppStmt[0])
    _assert("sqlite.step_select_done", step == sql.SQLITE_DONE)
    rc = sql.sqlite3_finalize(ppStmt[0])
    _assert("sqlite.finalize_select", rc == sql.SQLITE_OK)
    print("sqlite.prepare|PASS")


def run_transaction_metadata_checks(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin]
) raises:
    var rc = sql.sqlite3_exec(
        db,
        _cstr("BEGIN;\0"),
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.tx_begin", rc == sql.SQLITE_OK)
    _assert("sqlite.autocommit_off", sql.sqlite3_get_autocommit(db) == 0)

    rc = sql.sqlite3_exec(
        db,
        _cstr(
            "CREATE TABLE IF NOT EXISTS smoke_tx (id INTEGER PRIMARY KEY, x"
            " INT);\0"
        ),
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.tx_create", rc == sql.SQLITE_OK)

    rc = sql.sqlite3_exec(
        db,
        _cstr("INSERT INTO smoke_tx (x) VALUES (1001);\0"),
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.tx_insert", rc == sql.SQLITE_OK)
    _assert("sqlite.last_insert_rowid", sql.sqlite3_last_insert_rowid(db) >= 1)
    _assert("sqlite.changes_ge1", sql.sqlite3_changes(db) >= 1)

    rc = sql.sqlite3_exec(
        db,
        _cstr("COMMIT;\0"),
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.tx_commit", rc == sql.SQLITE_OK)
    _assert("sqlite.autocommit_on", sql.sqlite3_get_autocommit(db) != 0)
    print("sqlite.transaction_metadata|PASS")


def run_blob_checks(db: UnsafePointer[sql.sqlite3, MutExternalOrigin]) raises:
    var rc = sql.sqlite3_exec(
        db,
        _cstr(
            "CREATE TABLE IF NOT EXISTS smoke_blob (id INTEGER PRIMARY KEY, b"
            " BLOB);\0"
        ),
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.blob_create_table", rc == sql.SQLITE_OK)
    rc = sql.sqlite3_exec(
        db,
        _cstr("INSERT INTO smoke_blob (b) VALUES (zeroblob(8));\0"),
        _null_exec_cb(),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[
            UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin
        ](),
    )
    _assert("sqlite.blob_insert_zeroblob", rc == sql.SQLITE_OK)

    var ppBlob = alloc[UnsafePointer[sql.sqlite3_blob, MutExternalOrigin]](1)
    rc = sql.sqlite3_blob_open(
        db,
        _cstr("main\0"),
        _cstr("smoke_blob\0"),
        _cstr("b\0"),
        1,
        1,
        ppBlob,
    )
    _assert("sqlite.blob_open", rc == sql.SQLITE_OK)
    _assert("sqlite.blob_bytes", sql.sqlite3_blob_bytes(ppBlob[0]) == 8)

    var payload = alloc[UInt8](4)
    payload[0] = 10
    payload[1] = 20
    payload[2] = 30
    payload[3] = 40
    var pay_imm = rebind[ImmutOpaquePointer[ImmutExternalOrigin]](payload)
    rc = sql.sqlite3_blob_write(ppBlob[0], pay_imm, 4, 0)
    _assert("sqlite.blob_write", rc == sql.SQLITE_OK)

    var buf = alloc[UInt8](4)
    var buf_mut = rebind[MutOpaquePointer[MutExternalOrigin]](buf)
    rc = sql.sqlite3_blob_read(ppBlob[0], buf_mut, 4, 0)
    _assert("sqlite.blob_read", rc == sql.SQLITE_OK)
    _assert("sqlite.blob_roundtrip_0", buf[0] == 10)
    _assert("sqlite.blob_roundtrip_3", buf[3] == 40)

    rc = sql.sqlite3_blob_close(ppBlob[0])
    _assert("sqlite.blob_close", rc == sql.SQLITE_OK)
    print("sqlite.blob|PASS")


def run_mutex_checks() raises:
    var mx = sql.sqlite3_mutex_alloc(sql.SQLITE_MUTEX_FAST)
    _assert(
        "sqlite.mutex_alloc_nonnull",
        mx != UnsafePointer[sql.sqlite3_mutex, MutExternalOrigin](),
    )
    sql.sqlite3_mutex_enter(mx)
    sql.sqlite3_mutex_leave(mx)
    sql.sqlite3_mutex_free(mx)
    print("sqlite.mutex|PASS")


def run_status_memory_checks() raises:
    var cur = alloc[Int32](1)
    var hi = alloc[Int32](1)
    var st = sql.sqlite3_status(sql.SQLITE_STATUS_MEMORY_USED, cur, hi, 0)
    _assert("sqlite.status_memory_rc", st == sql.SQLITE_OK)
    var mu = sql.sqlite3_memory_used()
    _assert("sqlite.memory_used_nonneg", mu >= 0)
    print("sqlite.status_memory|PASS")


def run_get_table_checks(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin]
) raises:
    var paz = alloc[
        UnsafePointer[UnsafePointer[Int8, MutExternalOrigin], MutExternalOrigin]
    ](1)
    var pnRow = alloc[Int32](1)
    var pnCol = alloc[Int32](1)
    var pzErr = alloc[UnsafePointer[Int8, MutExternalOrigin]](1)
    var rc = sql.sqlite3_get_table(
        db,
        _cstr("SELECT 1 AS one, 2 AS two;\0"),
        paz,
        pnRow,
        pnCol,
        pzErr,
    )
    _assert("sqlite.get_table_rc", rc == sql.SQLITE_OK)
    _assert("sqlite.get_table_rows", pnRow[0] == 1)
    _assert("sqlite.get_table_cols", pnCol[0] == 2)
    sql.sqlite3_free_table(paz[0])
    print("sqlite.get_table|PASS")


def run_vfs_misc_checks(
    db: UnsafePointer[sql.sqlite3, MutExternalOrigin]
) raises:
    var vfs = sql.sqlite3_vfs_find(UnsafePointer[Int8, ImmutExternalOrigin]())
    _assert(
        "sqlite.vfs_find_default",
        vfs != UnsafePointer[sql.sqlite3_vfs, MutExternalOrigin](),
    )

    var c = sql.sqlite3_complete(_cstr("SELECT 1;\0"))
    _assert("sqlite.complete_select", c != 0)

    var rc = sql.sqlite3_busy_timeout(db, 0)
    _assert("sqlite.busy_timeout", rc == sql.SQLITE_OK)

    var ppProbe = alloc[UnsafePointer[sql.sqlite3_stmt, MutExternalOrigin]](1)
    var pzTailProbe = UnsafePointer[
        UnsafePointer[Int8, ImmutExternalOrigin], MutExternalOrigin
    ]()
    rc = sql.sqlite3_prepare_v2(
        db, _cstr("SELECT 1;\0"), -1, ppProbe, pzTailProbe
    )
    _assert("sqlite.db_handle_prepare", rc == sql.SQLITE_OK)
    var db2 = sql.sqlite3_db_handle(ppProbe[0])
    _assert("sqlite.db_handle_roundtrip", db2 == db)
    rc = sql.sqlite3_finalize(ppProbe[0])
    _assert("sqlite.db_handle_finalize", rc == sql.SQLITE_OK)
    print("sqlite.vfs_misc|PASS")


def main() raises:
    print("=== SQLite bindgen composite smoke test ===")
    run_version_and_init_checks()

    var db = _open_memory()
    run_exec_checks(db)
    run_prepare_statement_checks(db)
    run_transaction_metadata_checks(db)
    run_blob_checks(db)
    run_mutex_checks()
    run_status_memory_checks()
    run_get_table_checks(db)
    run_vfs_misc_checks(db)

    var close_rc = sql.sqlite3_close(db)
    _assert("sqlite.close", close_rc == sql.SQLITE_OK)

    print("")
    print("=== ALL TESTS PASSED ===")

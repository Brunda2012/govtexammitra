"""Versioned database migrations. Run on every startup by app/db.init_db.

Base schema (app/db.py) is version 1. Each migration below runs once, in order,
and is recorded in schema_migrations. Migrations must be idempotent-safe: they only
run when their version is absent, so their SQL must transform exactly the schema
state of the previous version.

For fresh databases the base schema already includes every applied change, so
migrations are written to be harmless if run on an up-to-date schema.
"""

MIGRATIONS = [
    (2, "dedupe_overlap_mappings_and_add_unique", """
        DELETE FROM overlap_mappings WHERE id NOT IN (
          SELECT MIN(id) FROM overlap_mappings GROUP BY micro_a, micro_b
        )
    """, """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_map_pair ON overlap_mappings(micro_a, micro_b)
    """),
    (3, "index_tasks_by_user", None, """
        CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)
    """),
    (4, "index_attempts_by_user", None, """
        CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user_id)
    """),
    (5, "dedupe_questions", """
        DELETE FROM attempts WHERE question_id NOT IN (
          SELECT MIN(id) FROM questions GROUP BY exam_id, q_type, question
        )
    """, """
        DELETE FROM questions WHERE id NOT IN (
          SELECT MIN(id) FROM questions GROUP BY exam_id, q_type, question
        )
    """),
    (6, "unique_questions", None, """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_q_unique ON questions(exam_id, q_type, question)
    """),
]

def _table_exists(conn, name, sqlite_mode):
    if sqlite_mode:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                           (name,)).fetchone()
    else:
        row = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name=%s",
                           (name,)).fetchone()
    return row is not None

def _ensure_table(conn, sqlite_mode):
    ddl_sqlite = """CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"""
    ddl_pg = """CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY, name TEXT,
        applied_at TEXT NOT NULL DEFAULT (now()::timestamp(0)::text))"""
    conn.execute(ddl_pg if not sqlite_mode else ddl_sqlite)

def run_migrations(conn, sqlite_mode=True):
    _ensure_table(conn, sqlite_mode)
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    for version, name, pre_sql, post_sql in MIGRATIONS:
        if version in applied:
            continue
        if pre_sql:
            conn.execute(pre_sql)
        if post_sql:
            conn.execute(post_sql)
        conn.execute("INSERT INTO schema_migrations (version, name) VALUES (?,?)",
                     (version, name))
    conn.commit()

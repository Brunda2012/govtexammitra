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
    (7, "gov_source_registry_and_documents", None, """
        CREATE TABLE IF NOT EXISTS gov_sources (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          organisation TEXT NOT NULL,
          base_url TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'HTML' CHECK (kind IN ('HTML','RSS')),
          listing_path TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          frequency_hours INTEGER NOT NULL DEFAULT 12,
          max_pages INTEGER NOT NULL DEFAULT 8,
          robots_policy TEXT,
          last_crawl_at TEXT,
          last_status TEXT,
          last_error TEXT,
          added_by TEXT,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS gov_documents (
          id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES gov_sources(id),
          url TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          organisation TEXT NOT NULL,
          doc_type TEXT NOT NULL DEFAULT 'OTHER',
          published_at TEXT,
          collected_at TEXT,
          updated_at TEXT,
          content_hash TEXT NOT NULL,
          version INTEGER NOT NULL DEFAULT 1,
          extracted_text TEXT,
          exam_ids_json TEXT NOT NULL DEFAULT '[]',
          classification_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'
                CHECK (classification_status IN ('AUTO_CLASSIFIED','PENDING_REVIEW','ADMIN_APPROVED','REJECTED')),
          verification_status TEXT NOT NULL DEFAULT 'PENDING_VERIFICATION',
          copyright_status TEXT NOT NULL DEFAULT 'OFFICIAL_PUBLIC',
          last_checked_at TEXT,
          review_note TEXT
        );
        CREATE TABLE IF NOT EXISTS gov_crawl_log (
          id TEXT PRIMARY KEY,
          source_id TEXT,
          started_at TEXT,
          finished_at TEXT,
          status TEXT,
          pages_fetched INTEGER NOT NULL DEFAULT 0,
          docs_new INTEGER NOT NULL DEFAULT 0,
          docs_updated INTEGER NOT NULL DEFAULT 0,
          error TEXT
        );
        CREATE TABLE IF NOT EXISTS gov_audit_log (
          id TEXT PRIMARY KEY,
          admin_id TEXT NOT NULL,
          action TEXT NOT NULL,
          target TEXT NOT NULL,
          detail TEXT,
          created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_govdoc_source ON gov_documents(source_id);
        CREATE INDEX IF NOT EXISTS idx_govdoc_type ON gov_documents(doc_type);
        CREATE INDEX IF NOT EXISTS idx_govcrawl_source ON gov_crawl_log(source_id);
    """),
    (8, "notes_mock_and_mains_tables", None, """
        CREATE TABLE IF NOT EXISTS notes (
          user_id TEXT NOT NULL,
          micro_topic_id INTEGER NOT NULL REFERENCES micro_topics(id),
          body TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (user_id, micro_topic_id)
        );
        CREATE TABLE IF NOT EXISTS mock_attempts (
          id INTEGER PRIMARY KEY,
          user_id TEXT NOT NULL,
          exam_id TEXT NOT NULL REFERENCES exams(id),
          paper TEXT NOT NULL,
          sections_json TEXT NOT NULL DEFAULT '[]',
          total_score REAL NOT NULL DEFAULT 0,
          max_score REAL NOT NULL DEFAULT 0,
          correct INTEGER NOT NULL DEFAULT 0,
          wrong INTEGER NOT NULL DEFAULT 0,
          unattempted INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mains_attempts (
          id INTEGER PRIMARY KEY,
          user_id TEXT NOT NULL,
          exam_id TEXT NOT NULL REFERENCES exams(id),
          prompt_id TEXT NOT NULL,
          body TEXT NOT NULL,
          word_count INTEGER NOT NULL DEFAULT 0,
          self_scores_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mains_prompts (
          id TEXT PRIMARY KEY,
          exam_id TEXT NOT NULL REFERENCES exams(id),
          paper TEXT NOT NULL,
          subject_name TEXT NOT NULL,
          topic_name TEXT,
          prompt TEXT NOT NULL,
          word_limit INTEGER NOT NULL DEFAULT 250,
          guidance TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id);
        CREATE INDEX IF NOT EXISTS idx_mock_user ON mock_attempts(user_id);
        CREATE INDEX IF NOT EXISTS idx_mains_user ON mains_attempts(user_id);
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

def _split(script):
    return [s.strip() for s in script.split(";") if s.strip()]

def run_migrations(conn, sqlite_mode=True):
    _ensure_table(conn, sqlite_mode)
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    for version, name, pre_sql, post_sql in MIGRATIONS:
        if version in applied:
            continue
        for stmt in _split(pre_sql or ""):
            conn.execute(stmt)
        for stmt in _split(post_sql or ""):
            conn.execute(stmt)
        conn.execute("INSERT INTO schema_migrations (version, name) VALUES (?,?)",
                     (version, name))
    conn.commit()

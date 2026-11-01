"""User progress with cross-examination propagation.

Rules (documented, deliberately conservative):
- EXACT_MATCH mapping: completing a topic (status COMPLETED with mastery M) propagates the
  same status/mastery to the mapped topic of the other exam.
- PARTIAL_OVERLAP: propagates to the other exam only as IN_PROGRESS with mastery capped at
  PARTIAL_CAP (60), because scope/depth differ. The learner must explicitly complete the
  remaining depth in the other exam.
- RELATED_CONCEPT: does NOT propagate progress. It only records a cross-reference note.
- EXAM-SPECIFIC topics never propagate.
- Progress is always per (user, micro_topic) — the mapped topic keeps its own record.
- Progress only changes through explicit user action; nothing is auto-completed.
"""
from .db import get_conn

PARTIAL_CAP = 60
VALID_STATUS = ("NOT_STARTED", "IN_PROGRESS", "COMPLETED")

def set_progress(conn, user_id, micro_topic_id, status, mastery, exam_id=None):
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status: {status}")
    mastery = max(0, min(100, int(mastery)))
    if status == "NOT_STARTED":
        mastery = 0
    if status == "COMPLETED":
        mastery = max(mastery, 100)
    row = conn.execute("SELECT exam_id FROM micro_topics WHERE id=?", (micro_topic_id,)).fetchone()
    if not row:
        raise ValueError("Unknown micro-topic")
    exam_id = exam_id or row["exam_id"]
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""INSERT INTO topic_progress (user_id, micro_topic_id, exam_id, status, mastery, updated_at)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT(user_id, micro_topic_id)
                    DO UPDATE SET status=excluded.status, mastery=excluded.mastery, updated_at=excluded.updated_at""",
                 (user_id, micro_topic_id, exam_id, status, mastery, now))
    return {"micro_topic_id": micro_topic_id, "exam_id": exam_id, "status": status, "mastery": mastery}

def propagate(conn, user_id, micro_topic_id, status, mastery):
    """Apply set_progress plus documented propagation. Returns list of applied updates."""
    applied = [set_progress(conn, user_id, micro_topic_id, status, mastery)]
    m = conn.execute("SELECT micro_a, micro_b, classification FROM overlap_mappings WHERE micro_a=? OR micro_b=?",
                     (micro_topic_id, micro_topic_id)).fetchone()
    if not m:
        return applied
    other = m["micro_b"] if m["micro_a"] == micro_topic_id else m["micro_a"]
    cls = m["classification"]
    if cls == "EXACT_MATCH":
        applied.append(set_progress(conn, user_id, other, status, mastery))
    elif cls == "PARTIAL_OVERLAP" and status == "COMPLETED":
        applied.append(set_progress(conn, user_id, other, "IN_PROGRESS", min(PARTIAL_CAP, mastery)))
    return applied

def get_progress(conn, user_id, exam_id=None):
    if exam_id:
        rows = conn.execute("SELECT * FROM topic_progress WHERE user_id=? AND exam_id=?", (user_id, exam_id)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM topic_progress WHERE user_id=?", (user_id,)).fetchall()
    return [dict(r) for r in rows]

def coverage(conn, user_id, exam_id):
    """Per-subject completion for one exam. A subject counts as complete only when every
    micro-topic under it is COMPLETED."""
    rows = conn.execute("""
        SELECT s.id subject_id, s.name subject_name, s.group_key, s.stage, s.paper,
               COUNT(m.id) total,
               SUM(CASE WHEN tp.status='COMPLETED' THEN 1 ELSE 0 END) completed,
               SUM(CASE WHEN tp.status='IN_PROGRESS' THEN 1 ELSE 0 END) in_progress
        FROM subjects s
        LEFT JOIN micro_topics m ON m.subject_id = s.id
        LEFT JOIN topic_progress tp ON tp.micro_topic_id = m.id AND tp.user_id = ?
        WHERE s.exam_id = ?
        GROUP BY s.id ORDER BY s.ordering, s.name
    """, (user_id, exam_id)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["completion"] = round(100 * (d["completed"] or 0) / d["total"], 1) if d["total"] else 0.0
        out.append(d)
    return out

def overall(conn, user_id, exam_id):
    row = conn.execute("""
        SELECT COUNT(m.id) total,
               SUM(CASE WHEN tp.status='COMPLETED' THEN 1 ELSE 0 END) completed,
               SUM(CASE WHEN tp.status='IN_PROGRESS' THEN 1 ELSE 0 END) in_progress
        FROM micro_topics m
        LEFT JOIN topic_progress tp ON tp.micro_topic_id = m.id AND tp.user_id = ?
        WHERE m.exam_id = ?
    """, (user_id, exam_id)).fetchone()
    total = row["total"] or 0
    completed = row["completed"] or 0
    return {"exam_id": exam_id, "total": total, "completed": completed,
            "in_progress": row["in_progress"] or 0,
            "completion_pct": round(100 * completed / total, 1) if total else 0.0}

def weak_topics(conn, user_id, exam_id, min_attempts=2, max_accuracy=60.0):
    rows = conn.execute("""
        SELECT q.micro_topic_id, m.name topic_name, s.name subject_name,
               COUNT(a.id) attempts,
               ROUND(100.0 * SUM(a.correct) / COUNT(a.id), 1) accuracy
        FROM attempts a
        JOIN questions q ON q.id = a.question_id
        LEFT JOIN micro_topics m ON m.id = q.micro_topic_id
        LEFT JOIN subjects s ON s.id = q.subject_id
        WHERE a.user_id = ? AND q.exam_id = ? AND q.micro_topic_id IS NOT NULL
        GROUP BY q.micro_topic_id, m.name, s.name
        HAVING COUNT(a.id) >= ? AND 100.0 * SUM(a.correct) / COUNT(a.id) < ?
        ORDER BY accuracy ASC
    """, (user_id, exam_id, min_attempts, max_accuracy)).fetchall()
    return [dict(r) for r in rows]

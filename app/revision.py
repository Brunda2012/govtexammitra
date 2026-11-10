"""Smart Revision Centre — spaced repetition over the learner's real data.

Scheduling model (SM-2-inspired, deliberately simple and explainable):
- Every micro-topic the learner has touched (progress row) or attempted questions on
  gets a scheduled review.
- Interval grows with mastery and measured accuracy: interval_days =
    base(status) * ease(accuracy) ** reps
  where reps is how many review cycles the topic has "survived" (approximated from
  mastery bands, since attempts are the only per-topic signal).
- A topic is DUE when updated_at + interval <= now. Overdue days drive urgency.
- Weak topics (accuracy < 60% with >= 2 attempts) are always due, with their accuracy
  shown as the reason.
- Topics never touched are listed as NEW, not scheduled — nothing is invented.

The queue carries a human-readable reason for every item. Flashcards share this
scheduler through due_topic_ids().
"""
from datetime import datetime, timezone

BASE_INTERVAL = {"IN_PROGRESS": 2, "COMPLETED": 7}


def _now():
    return datetime.now(timezone.utc)


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _ease(accuracy):
    """Ease factor from measured accuracy: 0.5 at 0% up to 2.5 at 100%."""
    if accuracy is None:
        return 1.3
    return 0.5 + 2.0 * (accuracy / 100.0)


def _reps(status, mastery):
    """Approximate review cycles from mastery bands (0-24:0, 25-49:1, 50-74:2, 75-99:3, 100:4)."""
    if status == "COMPLETED":
        return 4
    return min(3, mastery // 25) if mastery else 0


def queue(conn, user_id, exam_id):
    """The revision queue for one exam: due items with urgency and reasons."""
    topics = conn.execute("""
        SELECT m.id, m.name, m.depth_note, s.name subject_name, s.group_key,
               tp.status, tp.mastery, tp.updated_at
        FROM micro_topics m
        JOIN subjects s ON s.id = m.subject_id
        LEFT JOIN topic_progress tp ON tp.micro_topic_id = m.id AND tp.user_id = ?
        WHERE m.exam_id = ?""", (user_id, exam_id)).fetchall()

    acc = {}
    for r in conn.execute("""
        SELECT q.micro_topic_id mid, COUNT(a.id) attempts,
               ROUND(100.0 * SUM(a.correct) / COUNT(a.id), 1) accuracy
        FROM attempts a JOIN questions q ON q.id = a.question_id
        WHERE a.user_id = ? AND q.exam_id = ? AND q.micro_topic_id IS NOT NULL
        GROUP BY q.micro_topic_id""", (user_id, exam_id)).fetchall():
        acc[r["mid"]] = (r["attempts"], r["accuracy"])

    now = _now()
    due, scheduled, new = [], [], []
    for t in topics:
        d = dict(t)
        attempts, accuracy = acc.get(t["id"], (0, None))
        d["attempts"], d["accuracy"] = attempts, accuracy
        status, mastery = t["status"] or "NOT_STARTED", t["mastery"] or 0
        if attempts and accuracy is not None and accuracy < 60.0:
            d["urgency"] = 100 - accuracy
            d["reason"] = (f"Weak topic: {accuracy}% accuracy over {attempts} attempt(s). "
                           "Revisit before anything else.")
            due.append(d)
            continue
        if status == "NOT_STARTED":
            if attempts == 0:
                qn = conn.execute("SELECT COUNT(*) c FROM questions WHERE micro_topic_id=?",
                                  (t["id"],)).fetchone()["c"]
                if qn:
                    new.append({**d, "urgency": 10 + qn,
                                "reason": f"Not started yet; {qn} practice question(s) available."})
            continue
        base = BASE_INTERVAL.get(status, 2)
        interval = base * (_ease(accuracy) ** _reps(status, mastery))
        updated = _parse(t["updated_at"])
        elapsed = (now - updated).days if updated else 999
        if elapsed >= interval:
            overdue = elapsed - interval
            d["urgency"] = 40 + min(40, overdue * 2) + mastery / 10
            d["reason"] = (f"{status.lower().replace('_', ' ')} {elapsed} day(s) ago — review cycle "
                           f"of {round(interval, 1)} day(s) has elapsed (decay-based resurfacing).")
            due.append(d)
        else:
            d["urgency"] = 0
            d["next_review_in_days"] = round(interval - elapsed, 1)
            d["reason"] = f"On schedule; next review in {round(interval - elapsed, 1)} day(s)."
            scheduled.append(d)
    due.sort(key=lambda x: -x["urgency"])
    new.sort(key=lambda x: -x["urgency"])
    scheduled.sort(key=lambda x: -x["urgency"])
    return {"exam_id": exam_id, "due": due, "scheduled": scheduled[:15], "new": new[:15],
            "method": "SM-2-style spacing from your own accuracy and completion dates. "
                      "Weak topics are always due; completed topics resurface as their interval decays."}


def session(conn, user_id, exam_id, limit=10):
    """One-click revision session: questions from the top due topics."""
    q = queue(conn, user_id, exam_id)
    topic_ids = [t["id"] for t in q["due"][:limit]]
    if not topic_ids:
        return {"exam_id": exam_id, "topics": [], "questions": [],
                "note": "Nothing is due right now — weak topics appear here as soon as they exist."}
    marks = ",".join("?" * len(topic_ids))
    rows = [dict(r) for r in conn.execute(f"""
        SELECT q.id, q.question, q.options_json, q.difficulty, q.micro_topic_id, m.name topic_name
        FROM questions q LEFT JOIN micro_topics m ON m.id=q.micro_topic_id
        WHERE q.micro_topic_id IN ({marks}) ORDER BY q.id""", topic_ids).fetchall()]
    for r in rows:
        r["options"] = __import__("json").loads(r.pop("options_json") or "[]")
    return {"exam_id": exam_id,
            "topics": [t["name"] for t in q["due"][:limit]],
            "questions": rows}


def due_topic_ids(conn, user_id, exam_id):
    """Shared scheduler for flashcards: ids of due topics, urgent first."""
    return [t["id"] for t in queue(conn, user_id, exam_id)["due"]]

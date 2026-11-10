"""Mains Answer Writing — prompts derived from the syllabus, honest self-evaluation.

- Prompts come from the exam's own syllabus subjects (MAINS/essay/descriptive papers)
  and are stored as seed data with a stable id, word limit and expected structure.
- Attempts are stored verbatim with the learner's own rubric self-scores.
- GovtExamMitra produces NO score here: a descriptive answer cannot be honestly
  auto-scored without a verified evaluation engine. Self-scoring is a rubric the
  learner applies to their own answer.
"""
import json
from datetime import datetime, timezone

RUBRIC = [
    {"key": "content", "label": "Content & relevance", "max": 5,
     "guide": "Does the answer address every part of the question with facts and examples?"},
    {"key": "structure", "label": "Structure & flow", "max": 5,
     "guide": "Introduction, body with sub-headings or clear paragraphs, conclusion."},
    {"key": "analysis", "label": "Analysis & balance", "max": 5,
     "guide": "Multi-dimensional treatment (social, economic, political…); both sides weighed."},
    {"key": "examples", "label": "Examples & evidence", "max": 5,
     "guide": "Current affairs, reports, committee recommendations, data cited."},
    {"key": "presentation", "label": "Presentation & word limit", "max": 5,
     "guide": "Within the word limit; clean language; no padding."},
]

RUBRIC_NOTE = ("Self-evaluation only. GovtExamMitra does not generate a score for descriptive "
               "answers — apply the rubric to your own answer honestly. Advisory AI feedback "
               "exists separately under AI Answer Evaluation once an engine is configured.")


def prompts(conn, exam_id):
    if not conn.execute("SELECT 1 FROM exams WHERE id=?", (exam_id,)).fetchone():
        raise ValueError("Unknown exam")
    rows = [dict(r) for r in conn.execute(
        "SELECT id, exam_id, paper, subject_name, topic_name, prompt, word_limit, guidance "
        "FROM mains_prompts WHERE exam_id=? ORDER BY id", (exam_id,)).fetchall()]
    return {"exam_id": exam_id, "prompts": rows, "rubric": RUBRIC, "rubric_note": RUBRIC_NOTE}


def submit(conn, user_id, payload):
    p = conn.execute("SELECT * FROM mains_prompts WHERE id=? AND exam_id=?",
                     (payload["prompt_id"], payload["exam_id"])).fetchone()
    if not p:
        raise ValueError("Unknown prompt for this exam")
    body = payload["body"].strip()
    if len(body) < 10:
        raise ValueError("Answer body is too short to store (min 10 characters)")
    words = len(body.split())
    scores = payload.get("self_scores") or {}
    clean = {}
    for item in RUBRIC:
        v = scores.get(item["key"])
        if v is None:
            continue
        v = max(0, min(item["max"], int(v)))
        clean[item["key"]] = v
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("""INSERT INTO mains_attempts
        (user_id, exam_id, prompt_id, body, word_count, self_scores_json, created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (user_id, payload["exam_id"], payload["prompt_id"], body, words,
         json.dumps(clean), now))
    conn.commit()
    return {"attempt_id": cur.lastrowid, "word_count": words, "word_limit": p["word_limit"],
            "within_limit": words <= p["word_limit"],
            "self_scores": clean, "rubric_note": RUBRIC_NOTE, "submitted_at": now}


def history(conn, user_id, exam_id=None):
    sql = ("SELECT id, exam_id, prompt_id, word_count, self_scores_json, created_at "
           "FROM mains_attempts WHERE user_id=?")
    args = [user_id]
    if exam_id:
        sql += " AND exam_id=?"
        args.append(exam_id)
    rows = [dict(r) for r in conn.execute(sql + " ORDER BY id DESC LIMIT 20", args).fetchall()]
    for r in rows:
        r["self_scores"] = json.loads(r.pop("self_scores_json") or "{}")
        p = conn.execute("SELECT subject_name, topic_name FROM mains_prompts WHERE id=?",
                         (r["prompt_id"],)).fetchone()
        if p:
            r["subject_name"], r["topic_name"] = p["subject_name"], p["topic_name"]
    return rows

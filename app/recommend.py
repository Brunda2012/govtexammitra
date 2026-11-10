"""Learning Recommendations — a rules engine over the learner's own data.

Every recommendation carries an explicit `reason` string naming the rule and the
numbers behind it. Rules, in priority order:
1. WEAK_TOPIC   — accuracy below 60% over 2+ attempts.
2. COVERAGE_GAP — subjects with 0% completion that hold practice questions.
3. OVERLAP_LEVERAGE — EXACT_MATCH topics of the paired exam already completed here,
   or PARTIAL_OVERLAP topics where one side is done and the other is not.
4. PLANNER_NEXT — pending planner tasks whose topics are not complete.
5. KEEP_STREAK  — topics in progress but untouched for 7+ days.
No ranking is invented: where there is no data, the endpoint says so.
"""
import json
from . import revision as rev
from . import progress as prog


def _parse(ts):
    return rev._parse(ts)


def recommend(conn, user_id, exam_id, pair_exam_id=None):
    if not conn.execute("SELECT 1 FROM exams WHERE id=?", (exam_id,)).fetchone():
        raise ValueError("Unknown exam")
    recs = []
    # 1. weak topics
    for w in prog.weak_topics(conn, user_id, exam_id):
        recs.append({
            "rule": "WEAK_TOPIC", "priority": 1,
            "micro_topic_id": w["micro_topic_id"], "title": f"Revise {w['topic_name']}",
            "reason": f"Your accuracy on {w['topic_name']} is {w['accuracy']}% over "
                      f"{w['attempts']} attempt(s) — below the 60% threshold.",
            "action": "practice", "exam_id": exam_id,
        })
    # 2. coverage gaps with questions available
    gaps = conn.execute("""
        SELECT s.id sid, s.name subject_name, s.group_key,
               COUNT(m.id) topics,
               SUM(CASE WHEN tp.status IS NULL OR tp.status='NOT_STARTED' THEN 1 ELSE 0 END) untouched,
               (SELECT COUNT(*) FROM questions q WHERE q.micro_topic_id IN
                  (SELECT id FROM micro_topics WHERE subject_id=s.id)) qcount
        FROM subjects s
        LEFT JOIN micro_topics m ON m.subject_id=s.id
        LEFT JOIN topic_progress tp ON tp.micro_topic_id=m.id AND tp.user_id=?
        WHERE s.exam_id=?
        GROUP BY s.id HAVING untouched > 0 ORDER BY qcount DESC""", (user_id, exam_id)).fetchall()
    for g in gaps:
        if not g["qcount"]:
            continue
        recs.append({
            "rule": "COVERAGE_GAP", "priority": 2,
            "title": f"Start {g['subject_name']}",
            "reason": f"{g['untouched']} of {g['topics']} micro-topics in {g['subject_name']} are "
                      f"untouched, and {g['qcount']} practice question(s) are ready.",
            "action": "syllabus", "exam_id": exam_id,
        })
    # 3. overlap leverage
    if pair_exam_id:
        try:
            from . import overlap as ov
            result = ov.compare(conn, exam_id, pair_exam_id)
            pset = {p["micro_topic_id"]: p for p in prog.get_progress(conn, user_id)}
            for p in result["pairs"]:
                pa, pb = pset.get(p["id_a"]), pset.get(p["id_b"])
                sa = pa["status"] if pa else "NOT_STARTED"
                sb = pb["status"] if pb else "NOT_STARTED"
                if p["classification"] == "EXACT_MATCH" and sa == "COMPLETED" and sb != "COMPLETED":
                    recs.append({
                        "rule": "OVERLAP_LEVERAGE", "priority": 3,
                        "micro_topic_id": p["id_b"], "title": f"Claim {p['name_b']} on {pair_exam_id}",
                        "reason": f"You completed {p['name_a']} on {exam_id}; the exact-match topic "
                                  f"{p['name_b']} carries the same syllabus content for {pair_exam_id}.",
                        "action": "syllabus", "exam_id": pair_exam_id,
                    })
                elif (p["classification"] == "PARTIAL_OVERLAP" and sa == "COMPLETED"
                      and sb != "COMPLETED"):
                    recs.append({
                        "rule": "OVERLAP_LEVERAGE", "priority": 3,
                        "micro_topic_id": p["id_b"], "title": f"Finish the extra depth of {p['name_b']}",
                        "reason": f"{p['name_a']} is done on {exam_id}; {p['name_b']} shares the core "
                                  f"but needs {pair_exam_id}-specific depth (mastery capped at 60 until then).",
                        "action": "syllabus", "exam_id": pair_exam_id,
                    })
        except ValueError:
            pass
    # 4. pending planner tasks
    tasks = conn.execute("""SELECT id, title, micro_topic_ids_json FROM tasks
                            WHERE user_id=? AND status='PENDING' ORDER BY id LIMIT 5""",
                         (user_id,)).fetchall()
    pset = {p["micro_topic_id"]: p for p in prog.get_progress(conn, user_id)}
    for t in tasks:
        ids = json.loads(t["micro_topic_ids_json"] or "[]")
        pending = [i for i in ids if not pset.get(i) or pset[i]["status"] != "COMPLETED"]
        if pending:
            recs.append({
                "rule": "PLANNER_NEXT", "priority": 4, "title": f"Work on: {t['title']}",
                "reason": f"Your planner has this pending task covering {len(pending)} "
                          "unfinished micro-topic(s).",
                "action": "planner", "exam_id": exam_id,
            })
    # 5. stale in-progress topics
    stale = conn.execute("""
        SELECT m.id, m.name, tp.updated_at FROM topic_progress tp
        JOIN micro_topics m ON m.id=tp.micro_topic_id
        WHERE tp.user_id=? AND tp.exam_id=? AND tp.status='IN_PROGRESS'""",
        (user_id, exam_id)).fetchall()
    now = rev._now()
    for s in stale:
        updated = _parse(s["updated_at"])
        days = (now - updated).days if updated else 999
        if days >= 7:
            recs.append({
                "rule": "KEEP_STREAK", "priority": 5, "micro_topic_id": s["id"],
                "title": f"Resume {s['name']}",
                "reason": f"Marked in-progress {days} day(s) ago and untouched since.",
                "action": "syllabus", "exam_id": exam_id,
            })
    recs.sort(key=lambda r: (r["priority"], r["title"]))
    return {"exam_id": exam_id, "recommendations": recs,
            "note": ("Every suggestion names the rule and data behind it. "
                     "No data yet? The best first step is practising a few questions — "
                     "recommendations sharpen as your data grows.") if not recs else None}

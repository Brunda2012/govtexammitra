"""Combined preparation planner.

Builds a merged, de-duplicated study sequence across two examinations:
1. Shared topics first (EXACT_MATCH before PARTIAL_OVERLAP, each by confidence then progress),
   so one study session serves both exams.
2. Then exam-specific topics per exam.
Each item carries what extra depth the other exam needs, links to practice questions, and
current progress. Generates planner tasks on request; never auto-marks completion.
"""
from .db import get_conn
from . import overlap as ov
from . import progress as prog

def build_plan(conn, user_id, exam_a, exam_b):
    result = ov.compare(conn, exam_a, exam_b)
    pairs, spec_a, spec_b = result["pairs"], result["specific_a"], result["specific_b"]
    pset = prog.get_progress(conn, user_id)
    pmap = {p["micro_topic_id"]: p for p in pset}
    qcounts = {}
    for r in conn.execute("""SELECT micro_topic_id, COUNT(*) c FROM questions
                             WHERE micro_topic_id IS NOT NULL GROUP BY micro_topic_id""").fetchall():
        qcounts[r["micro_topic_id"]] = r["c"]

    order_rank = {"EXACT_MATCH": 0, "PARTIAL_OVERLAP": 1, "RELATED_CONCEPT": 2}
    items = []
    for p in pairs:
        pa, pb = pmap.get(p["id_a"]), pmap.get(p["id_b"])
        items.append({
            "kind": "SHARED",
            "classification": p["classification"],
            "topic_a": p["name_a"], "topic_b": p["name_b"],
            "id_a": p["id_a"], "id_b": p["id_b"],
            "group_key": p["group_key"],
            "exam_a": exam_a, "exam_b": exam_b,
            "stage_a": p["stage_a"], "paper_a": p["paper_a"],
            "stage_b": p["stage_b"], "paper_b": p["paper_b"],
            "rationale": p["rationale"],
            "extra_depth_a": p.get("map_note_a") or p.get("note_a"),
            "extra_depth_b": p.get("map_note_b") or p.get("note_b"),
            "confidence": p["confidence"],
            "verification_status": p["verification_status"],
            "status_a": pa["status"] if pa else "NOT_STARTED",
            "status_b": pb["status"] if pb else "NOT_STARTED",
            "mastery_a": (pa or {}).get("mastery", 0),
            "mastery_b": (pb or {}).get("mastery", 0),
            "question_count": qcounts.get(p["id_a"], 0) + qcounts.get(p["id_b"], 0),
            "study_once": p["classification"] == "EXACT_MATCH",
        })
    for side, source in (("A", spec_a), ("B", spec_b)):
        for d in source:
            pd = pmap.get(d["id"])
            topic_a = d["name"] if side == "A" else None
            topic_b = d["name"] if side == "B" else None
            id_a = d["id"] if side == "A" else None
            id_b = d["id"] if side == "B" else None
            items_out = {
                "kind": "EXAM_SPECIFIC",
                "classification": d["classification"],
                "topic_a": topic_a,
                "topic_b": topic_b,
                "id_a": id_a,
                "id_b": id_b,
                "group_key": d["group_key"],
                "exam_a": exam_a if side == "A" else exam_b,
                "stage_a": d["stage"] if side == "A" else None,
                "paper_a": d["paper"] if side == "A" else None,
                "stage_b": d["stage"] if side == "B" else None,
                "paper_b": d["paper"] if side == "B" else None,
                "rationale": "Not established as part of the other examination's syllabus. Absence of a syllabus reference is not proof it can never be asked.",
                "confidence": None,
                "verification_status": "PENDING_VERIFICATION",
                "status_a": (pd["status"] if side == "A" else "NOT_STARTED") if pd else "NOT_STARTED",
                "status_b": (pd["status"] if side == "B" else "NOT_STARTED") if pd else "NOT_STARTED",
                "mastery_a": pd.get("mastery", 0) if pd and side == "A" else 0,
                "mastery_b": pd.get("mastery", 0) if pd and side == "B" else 0,
                "question_count": qcounts.get(d["id"], 0),
                "study_once": False,
            }
            items.append(items_out)
    items.sort(key=lambda i: (i["kind"] != "SHARED", order_rank.get(i["classification"], 3),
                              -(i["confidence"] or 0),
                              (i["status_a"] != "COMPLETED") + (i["status_b"] != "COMPLETED")))
    return items

def create_tasks(conn, user_id, exam_a, exam_b, limit=10, due_date=None):
    """Turn the top pending plan items into planner tasks."""
    items = build_plan(conn, user_id, exam_a, exam_b)
    created = []
    for it in items:
        if len(created) >= limit:
            break
        done = (it["status_a"] == "COMPLETED" and it["status_b"] == "COMPLETED")
        if done:
            continue
        if it["kind"] == "SHARED":
            title = f"[{it['classification']}] {it['topic_a']}"
            detail = f"Study once for both {exam_a} and {exam_b}."
            if it["classification"] == "PARTIAL_OVERLAP":
                detail += f" Extra depth: exam A - {it['extra_depth_a'] or 'see syllabus'}; exam B - {it['extra_depth_b'] or 'see syllabus'}."
            ids = [i for i in (it["id_a"], it["id_b"]) if i]
            exams = [exam_a, exam_b]
        else:
            exam = it["exam_a"]
            title = f"[{exam.upper()} only] {it['topic_a'] or it['topic_b']}"
            detail = f"Exam-specific topic for {exam}. {it['rationale']}"
            ids = [it["id_a"] or it["id_b"]]
            exams = [exam]
        cur = conn.execute("""INSERT INTO tasks (user_id,title,detail,micro_topic_ids_json,exam_ids_json,kind,due_date)
                              VALUES (?,?,?,?,?,?,?)""",
                           (user_id, title, detail, __import__("json").dumps(ids),
                            __import__("json").dumps(exams), "STUDY", due_date))
        created.append({"id": cur.lastrowid, "title": title, "detail": detail,
                        "micro_topic_ids": ids, "exam_ids": exams})
    conn.commit()
    return created

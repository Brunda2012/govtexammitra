"""Exam Overlap Intelligence engine.

Methodology (documented, no invented similarity scores):
- Coverage: each micro-topic row belongs to exactly one exam-subject (official wording row).
- Mappings: overlap_mappings pair one micro-topic per exam. Classification comes from the
  mapping table (human/AI reviewed against official subject-level wording), never computed.
- Classification is tripartite (EXACT_MATCH / PARTIAL_OVERLAP / RELATED_CONCEPT). A micro-topic
  of either exam with no mapping in the pair is EXAM-SPECIFIC for that exam.
- Absence of an explicit syllabus reference is NOT proof a topic can never be asked; the UI
  must convey that.
"""
from .db import get_conn, rows_to_dicts

CLASSIFICATIONS = ("EXACT_MATCH", "PARTIAL_OVERLAP", "RELATED_CONCEPT")

def pair_code(a, b):
    return "-vs-".join(sorted([a, b]))

def get_exam(conn, exam_id):
    row = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    return dict(row) if row else None

def list_exams(conn):
    return rows_to_dicts(conn.execute("SELECT * FROM exams ORDER BY supported DESC, name").fetchall())

def compare(conn, exam_a, exam_b):
    for e in (exam_a, exam_b):
        if not get_exam(conn, e):
            raise ValueError(f"Unknown exam: {e}")
    rows = conn.execute("""
        SELECT ma.id id_a, ma.name name_a, ma.depth_note note_a, sa.stage stage_a, sa.paper paper_a,
               sa.name subject_a, sa.group_key group_key, sa.official_text official_a,
               mb.id id_b, mb.name name_b, mb.depth_note note_b, sb.stage stage_b, sb.paper paper_b,
               sb.name subject_b, sb.official_text official_b,
               om.classification, om.rationale, om.confidence, om.verification_status,
               om.source_url, om.last_verified, om.depth_note_a map_note_a, om.depth_note_b map_note_b
        FROM overlap_mappings om
        JOIN micro_topics ma ON ma.id = om.micro_a
        JOIN micro_topics mb ON mb.id = om.micro_b
        JOIN subjects sa ON sa.id = ma.subject_id
        JOIN subjects sb ON sb.id = mb.subject_id
        WHERE (ma.exam_id = :a AND mb.exam_id = :b) OR (ma.exam_id = :b AND mb.exam_id = :a)
    """, {"a": exam_a, "b": exam_b}).fetchall()

    mapped_a, mapped_b, pairs = set(), set(), []
    for r in rows:
        d = dict(r)
        exam_of_a = conn.execute("SELECT exam_id FROM micro_topics WHERE id=?", (d["id_a"],)).fetchone()["exam_id"]
        if exam_of_a != exam_a:
            for ka, kb in [("id_a", "id_b"), ("name_a", "name_b"), ("note_a", "note_b"),
                           ("stage_a", "stage_b"), ("paper_a", "paper_b"),
                           ("subject_a", "subject_b"), ("official_a", "official_b")]:
                d[ka], d[kb] = d[kb], d[ka]
            d["depth_note_a"], d["depth_note_b"] = d["map_note_b"], d["map_note_a"]
        else:
            d["depth_note_a"], d["depth_note_b"] = d["map_note_a"], d["map_note_b"]
        mapped_a.add(d["id_a"]); mapped_b.add(d["id_b"])
        pairs.append(d)

    unmatched = conn.execute("""
        SELECT m.id, m.exam_id, m.name, m.depth_note, s.name subject_name, s.group_key, s.stage, s.paper
        FROM micro_topics m JOIN subjects s ON s.id = m.subject_id
        WHERE m.exam_id IN (:a, :b)
    """, {"a": exam_a, "b": exam_b}).fetchall()
    specific_a, specific_b = [], []
    for r in unmatched:
        d = dict(r)
        if d["id"] in mapped_a or d["id"] in mapped_b:
            continue
        d["classification"] = (f"EXAM_SPECIFIC_{exam_a.upper()}" if d["exam_id"] == exam_a
                                else f"EXAM_SPECIFIC_{exam_b.upper()}")
        (specific_a if d["exam_id"] == exam_a else specific_b).append(d)

    return {"pairs": pairs, "specific_a": specific_a, "specific_b": specific_b}

def stats(pairs, specific_a, specific_b):
    counts = {c: 0 for c in CLASSIFICATIONS}
    for p in pairs:
        counts[p["classification"]] += 1
    return {
        "compared_pairs": len(pairs),
        "exact_match": counts["EXACT_MATCH"],
        "partial_overlap": counts["PARTIAL_OVERLAP"],
        "related_concept": counts["RELATED_CONCEPT"],
        "exam_a_specific": len(specific_a),
        "exam_b_specific": len(specific_b),
    }

def group_by_subject(pairs, specific_a, specific_b):
    groups = {}
    for p in pairs:
        groups.setdefault(p["group_key"], {"group_key": p["group_key"], "items": [], "specific_a": [], "specific_b": []})
        groups[p["group_key"]]["items"].append(p)
    for d in specific_a:
        groups.setdefault(d["group_key"], {"group_key": d["group_key"], "items": [], "specific_a": [], "specific_b": []})
        groups[d["group_key"]]["specific_a"].append(d)
    for d in specific_b:
        groups.setdefault(d["group_key"], {"group_key": d["group_key"], "items": [], "specific_a": [], "specific_b": []})
        groups[d["group_key"]]["specific_b"].append(d)
    order = {"history": 0, "polity": 1, "geography": 2, "economy": 3, "environment": 4,
             "science_tech": 5, "security": 6, "current_affairs": 7, "mental_ability": 8, "essay": 9}
    out = sorted(groups.values(), key=lambda g: order.get(g["group_key"], 99))
    for g in out:
        g["items"].sort(key=lambda p: (-p["confidence"], p["name_a"]))
    return out

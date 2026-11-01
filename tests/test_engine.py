import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_db, get_conn
from app.seed import seed
from app import overlap as ov
from app import progress as prog
from app import planner as plan

DB = None


def _init():
    global DB
    if DB is None:
        fd, DB = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        seed(DB)
    return DB


_init()


class OverlapEngineTests(unittest.TestCase):
    def setUp(self):
        self.conn = get_conn(DB)

    def tearDown(self):
        self.conn.close()

    def test_compare_returns_all_three_classifications(self):
        r = ov.compare(self.conn, "upsc-cse", "capf-ac")
        classes = {p["classification"] for p in r["pairs"]}
        self.assertIn("EXACT_MATCH", classes)
        self.assertIn("PARTIAL_OVERLAP", classes)
        self.assertTrue(r["specific_a"] or r["specific_b"])

    def test_mapping_columns_normalised_to_exam_a(self):
        r = ov.compare(self.conn, "capf-ac", "upsc-cse")
        r2 = ov.compare(self.conn, "upsc-cse", "capf-ac")
        names = {frozenset((p["name_a"], p["name_b"])) for p in r["pairs"]}
        names2 = {frozenset((p["name_a"], p["name_b"])) for p in r2["pairs"]}
        self.assertEqual(names, names2)

    def test_stats_counts_add_up(self):
        r = ov.compare(self.conn, "upsc-cse", "capf-ac")
        s = ov.stats(r["pairs"], r["specific_a"], r["specific_b"])
        self.assertEqual(s["exact_match"] + s["partial_overlap"] + s["related_concept"],
                         s["compared_pairs"])

    def test_group_by_subject_covers_everything(self):
        r = ov.compare(self.conn, "upsc-cse", "capf-ac")
        groups = ov.group_by_subject(r["pairs"], r["specific_a"], r["specific_b"])
        total = sum(len(g["items"]) + len(g["specific_a"]) + len(g["specific_b"]) for g in groups)
        self.assertEqual(total, len(r["pairs"]) + len(r["specific_a"]) + len(r["specific_b"]))

    def test_unknown_exam_raises(self):
        with self.assertRaises(ValueError):
            ov.compare(self.conn, "upsc-cse", "nope")

    def test_every_pair_has_verification_metadata(self):
        r = ov.compare(self.conn, "upsc-cse", "capf-ac")
        for p in r["pairs"]:
            self.assertIn(p["verification_status"],
                          ("VERIFIED_OFFICIAL", "SECONDARY_SOURCE", "PENDING_VERIFICATION", "DEMONSTRATION_DATA"))
            self.assertTrue(p["rationale"])
            self.assertTrue(0 <= p["confidence"] <= 1)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.conn = get_conn(DB)

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def _mapped(self, cls):
        row = self.conn.execute("SELECT micro_a, micro_b FROM overlap_mappings WHERE classification=?",
                                (cls,)).fetchone()
        return row["micro_a"], row["micro_b"]

    def test_exact_match_propagates_same_mastery(self):
        a, b = self._mapped("EXACT_MATCH")
        prog.propagate(self.conn, "u1", a, "COMPLETED", 100)
        other = prog.get_progress(self.conn, "u1")
        by_id = {p["micro_topic_id"]: p for p in other}
        self.assertEqual(by_id[b]["status"], "COMPLETED")
        self.assertEqual(by_id[b]["mastery"], 100)

    def test_partial_overlap_caps_other_exam(self):
        a, b = self._mapped("PARTIAL_OVERLAP")
        prog.propagate(self.conn, "u2", a, "COMPLETED", 100)
        by_id = {p["micro_topic_id"]: p for p in prog.get_progress(self.conn, "u2")}
        self.assertEqual(by_id[b]["status"], "IN_PROGRESS")
        self.assertLessEqual(by_id[b]["mastery"], prog.PARTIAL_CAP)

    def test_related_concept_does_not_propagate(self):
        a, b = self._mapped("RELATED_CONCEPT")
        prog.propagate(self.conn, "u3", a, "COMPLETED", 100)
        by_id = {p["micro_topic_id"]: p for p in prog.get_progress(self.conn, "u3")}
        self.assertNotIn(b, by_id)

    def test_completion_requires_explicit_action_and_mastery_bounds(self):
        a, _ = self._mapped("EXACT_MATCH")
        prog.set_progress(self.conn, "u4", a, "IN_PROGRESS", 150)
        p = prog.get_progress(self.conn, "u4")[0]
        self.assertEqual(p["mastery"], 100)
        with self.assertRaises(ValueError):
            prog.set_progress(self.conn, "u4", a, "BOGUS", 0)

    def test_coverage_and_overall(self):
        a, _ = self._mapped("EXACT_MATCH")
        prog.propagate(self.conn, "u5", a, "COMPLETED", 100)
        overall = prog.overall(self.conn, "u5", "upsc-cse")
        self.assertGreater(overall["completed"], 0)
        cov = prog.coverage(self.conn, "u5", "upsc-cse")
        self.assertTrue(all("completion" in c for c in cov))


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.conn = get_conn(DB)

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def test_plan_orders_shared_before_specific_and_exact_first(self):
        items = plan.build_plan(self.conn, "u6", "upsc-cse", "capf-ac")
        kinds = [i["kind"] for i in items]
        first_specific = kinds.index("EXAM_SPECIFIC") if "EXAM_SPECIFIC" in kinds else len(kinds)
        self.assertTrue(all(k == "SHARED" for k in kinds[:first_specific]))
        shared_classes = [i["classification"] for i in items[:first_specific]]
        ranks = {"EXACT_MATCH": 0, "PARTIAL_OVERLAP": 1, "RELATED_CONCEPT": 2}
        self.assertEqual(shared_classes, sorted(shared_classes, key=lambda c: ranks[c]))

    def test_create_tasks_persists_rows(self):
        created = plan.create_tasks(self.conn, "u7", "upsc-cse", "capf-ac", limit=3)
        self.assertEqual(len(created), 3)
        n = self.conn.execute("SELECT COUNT(*) c FROM tasks WHERE user_id='u7'").fetchone()["c"]
        self.assertEqual(n, 3)


if __name__ == "__main__":
    with open(os.path.join(os.path.dirname(DB), "test_results.txt"), "w") as f:
        unittest.main(testRunner=unittest.TextTestRunner(stream=f, verbosity=2), exit=False, argv=sys.argv)

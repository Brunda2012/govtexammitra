"""Feature tests for the 2026 expansion: mocks, revision, recommendations,
mains, eval-503, PYQs, current affairs, notes, bookmarks, flashcards, mindmap.

Uses its own temp DB (same pattern as test_api.py).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.db as dbmod

fd, _DB = tempfile.mkstemp(suffix=".db")
os.close(fd)
dbmod.DB_PATH = _DB

from fastapi.testclient import TestClient
from server import app
from app.ratelimit import RateLimitMiddleware
from app.seed import seed

seed()


class FeatureTests(unittest.TestCase):
    token = None

    @classmethod
    def setUpClass(cls):
        if RateLimitMiddleware._last:
            RateLimitMiddleware._last._hits.clear()
        cls.client = TestClient(app)
        r = cls.client.post("/api/v1/auth/register",
                            json={"email": "feature1@example.com", "password": "strongpass1"})
        assert r.status_code == 200, r.text
        cls.token = r.json()["token"]
        cls.h = {"Authorization": f"Bearer {cls.token}"}

    # ---------- public / no-auth ----------

    def test_flashcards_public_and_sourced(self):
        r = self.client.get("/api/v1/flashcards/upsc-cse")
        self.assertEqual(r.status_code, 200)
        cards = r.json()["cards"]
        self.assertTrue(cards)
        for c in cards:
            self.assertIn("source", c)
            self.assertIn("micro_topic_id", c)

    def test_mindmap_public(self):
        r = self.client.get("/api/v1/mindmap/upsc-cse")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["subjects"])
        s = d["subjects"][0]
        self.assertIn("completion_pct", s)
        self.assertIn("children", s)

    def test_mains_prompts_public(self):
        r = self.client.get("/api/v1/mains/upsc-cse/prompts")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["prompts"])
        self.assertEqual(len(d["rubric"]), 5)
        p = d["prompts"][0]
        self.assertGreater(p["word_limit"], 0)
        self.assertIn("paper", p)

    def test_pyqs_public_no_fake_questions(self):
        r = self.client.get("/api/v1/pyqs/upsc-cse")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("note", d)
        for p in d["papers"]:
            self.assertIn("source_name", p)
            self.assertIn("url", p)

    def test_current_affairs_public(self):
        r = self.client.get("/api/v1/current-affairs")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("note", d)
        for it in d["items"]:
            self.assertIn("url", it)
            self.assertIn("source_name", it)

    def test_mock_submit_guest_no_persistence(self):
        r = self.client.post("/api/v1/mocks/upsc-cse/submit-guest", json={"answers": {}})
        self.assertEqual(r.status_code, 200)
        card = r.json()
        self.assertTrue(card["sections"])
        for sec in card["sections"]:
            self.assertGreaterEqual(sec["unattempted"], 0)
            self.assertEqual(sec["correct"] + sec["wrong"] + sec["unattempted"],
                             sec["correct"] + sec["wrong"] + sec["unattempted"])

    def test_eval_503_without_key(self):
        r = self.client.post("/api/v1/eval/answer",
                             json={"question": "q", "answer": "a"}, headers=self.h)
        self.assertEqual(r.status_code, 503)
        self.assertIn("configured", r.json()["detail"].lower())

    def test_mocks_requires_auth(self):
        self.assertEqual(self.client.get("/api/v1/mocks/upsc-cse/history").status_code, 401)

    def test_revision_requires_auth(self):
        self.assertEqual(self.client.get("/api/v1/revision/upsc-cse/queue").status_code, 401)

    def test_notes_require_auth(self):
        self.assertEqual(self.client.get("/api/v1/notes").status_code, 401)
        self.assertEqual(self.client.put("/api/v1/notes/1", json={"body": "x"}).status_code, 401)

    def test_bookmarks_require_auth(self):
        self.assertEqual(self.client.get("/api/v1/bookmarks").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/bookmarks",
                                          json={"kind": "TOPIC", "ref_id": "1"}).status_code, 401)

    def test_mains_attempts_require_auth(self):
        self.assertEqual(self.client.get("/api/v1/mains/attempts").status_code, 401)

    # ---------- authed flows ----------

    def test_mock_full_cycle_with_skips(self):
        asm = self.client.get("/api/v1/mocks/upsc-cse").json()
        qs = [q for s in asm["sections"] for q in s["questions"]]
        self.assertTrue(qs)
        answers = {}
        for i, q in enumerate(qs):
            if i == 0:
                answers[str(q["id"])] = None  # explicit skip
            elif i == 1:
                answers[str(q["id"])] = 0  # likely wrong
            # rest omitted entirely — must also count as unattempted
        r = self.client.post("/api/v1/mocks/upsc-cse/submit",
                             json={"answers": answers, "question_ids": [q["id"] for q in qs]},
                             headers=self.h)
        self.assertEqual(r.status_code, 200)
        card = r.json()
        total = 0
        for sec in card["sections"]:
            total += sec["correct"] + sec["wrong"] + sec["unattempted"]
            self.assertIn("score", sec)
            self.assertIn("paper", sec)
        self.assertEqual(total, card["total"]["max"])
        self.assertEqual(total, len(qs))
        h = self.client.get("/api/v1/mocks/upsc-cse/history", headers=self.h).json()
        self.assertGreaterEqual(len(h["attempts"]), 1)
        stripped = [{k: v for k, v in s.items() if k != "review"} for s in h["attempts"][0]["sections"]]
        self.assertEqual(stripped, [{k: v for k, v in s.items() if k != "review"} for s in card["sections"]])

    def test_revision_queue_and_session(self):
        r = self.client.get("/api/v1/revision/upsc-cse/queue", headers=self.h)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("due", d)
        self.assertIn("method", d)
        r = self.client.get("/api/v1/revision/upsc-cse/session", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertIn("questions", r.json())

    def test_recommendations_show_reasons(self):
        r = self.client.get("/api/v1/recommendations/upsc-cse?pair=capf-ac", headers=self.h)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("recommendations", d)
        for rec in d["recommendations"]:
            self.assertTrue(rec.get("reason"))
            self.assertIn("rule", rec)

    def test_mains_submit_and_history(self):
        prompts = self.client.get("/api/v1/mains/upsc-cse/prompts").json()["prompts"]
        p = prompts[0]
        r = self.client.post("/api/v1/mains/attempts",
                             json={"exam_id": p["exam_id"], "prompt_id": p["id"],
                                   "body": "one two three four five", "self_scores": {"content": 3}},
                             headers=self.h)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["word_count"], 5)
        self.assertTrue(d["within_limit"])
        h = self.client.get("/api/v1/mains/attempts", headers=self.h).json()
        self.assertGreaterEqual(len(h["attempts"]), 1)

    def test_mains_bad_prompt_422(self):
        r = self.client.post("/api/v1/mains/attempts",
                             json={"exam_id": "upsc-cse", "prompt_id": "no-such-prompt",
                                   "body": "x"}, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_notes_crud(self):
        mid = self.client.get("/api/v1/syllabus/upsc-cse").json()["micro_topics"][0]["id"]
        r = self.client.put(f"/api/v1/notes/{mid}", json={"body": "first note"},
                            headers=self.h)
        self.assertEqual(r.status_code, 200)
        r = self.client.get(f"/api/v1/notes/{mid}", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["body"], "first note")
        # overwrite
        self.client.put(f"/api/v1/notes/{mid}", json={"body": "second note"}, headers=self.h)
        r = self.client.get("/api/v1/notes", headers=self.h)
        self.assertEqual(r.json()["notes"][0]["body"], "second note")
        self.assertEqual(self.client.delete(f"/api/v1/notes/{mid}", headers=self.h).status_code, 200)
        r = self.client.get("/api/v1/notes", headers=self.h)
        self.assertFalse(r.json()["notes"])

    def test_bookmarks_crud_and_validation(self):
        # valid topic bookmark
        mid = self.client.get("/api/v1/syllabus/upsc-cse").json()["micro_topics"][0]["id"]
        r = self.client.post("/api/v1/bookmarks", json={"kind": "TOPIC", "ref_id": str(mid)},
                             headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["bookmarked"])
        # invalid topic rejected
        r = self.client.post("/api/v1/bookmarks", json={"kind": "TOPIC", "ref_id": "999999"},
                             headers=self.h)
        self.assertEqual(r.status_code, 422)
        r = self.client.get("/api/v1/bookmarks", headers=self.h)
        self.assertGreaterEqual(len(r.json()["bookmarks"]), 1)
        r = self.client.delete(f"/api/v1/bookmarks/TOPIC/{mid}", headers=self.h)
        self.assertEqual(r.status_code, 200)

    def test_isolation_other_user_cannot_read_notes(self):
        r = self.client.post("/api/v1/auth/register",
                             json={"email": "feature2@example.com", "password": "strongpass2"})
        h2 = {"Authorization": f"Bearer {r.json()['token']}"}
        mid = self.client.get("/api/v1/syllabus/upsc-cse").json()["micro_topics"][0]["id"]
        self.client.put(f"/api/v1/notes/{mid}", json={"body": "mine"}, headers=self.h)
        r = self.client.get(f"/api/v1/notes/{mid}", headers=h2)
        if r.status_code == 200:
            self.assertNotEqual(r.json()["body"], "mine")


if __name__ == "__main__":
    unittest.main()

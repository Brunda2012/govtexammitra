"""API-level tests using FastAPI TestClient (httpx).

Covers: catalogue, overlap, syllabus, auth (register/login), two-user data
isolation, progress propagation, planner, practice, analytics, mentor 503.
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
from app.seed import seed

seed()


class ApiTests(unittest.TestCase):
    token_a = None
    token_b = None

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        r = cls.client.post("/api/v1/auth/register",
                            json={"email": "aspirant1@example.com", "password": "strongpass1"})
        assert r.status_code == 200, r.text
        cls.token_a = r.json()["token"]
        r = cls.client.post("/api/v1/auth/register",
                            json={"email": "aspirant2@example.com", "password": "strongpass2"})
        assert r.status_code == 200, r.text
        cls.token_b = r.json()["token"]
        cls.ha = {"Authorization": f"Bearer {cls.token_a}"}
        cls.hb = {"Authorization": f"Bearer {cls.token_b}"}

    def test_exams_list_and_detail(self):
        r = self.client.get("/api/v1/exams")
        self.assertEqual(r.status_code, 200)
        ids = [e["id"] for e in r.json()]
        self.assertIn("upsc-cse", ids)
        self.assertIn("capf-ac", ids)
        r = self.client.get("/api/v1/exams/upsc-cse")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["authority"], "Union Public Service Commission")
        self.assertEqual(self.client.get("/api/v1/exams/zzz").status_code, 404)

    def test_overlap_endpoint_and_filters(self):
        r = self.client.get("/api/v1/overlap/upsc-cse/capf-ac")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertGreater(d["stats"]["compared_pairs"], 0)
        self.assertTrue(d["groups"])
        r = self.client.get("/api/v1/overlap/upsc-cse/capf-ac?classification=EXACT_MATCH")
        self.assertEqual(r.status_code, 200)
        for g in r.json()["groups"]:
            for p in g["items"]:
                self.assertEqual(p["classification"], "EXACT_MATCH")
        r = self.client.get("/api/v1/overlap/upsc-cse/capf-ac?q=geography")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/api/v1/overlap/upsc-cse/zzz")
        self.assertEqual(r.status_code, 404)
        r = self.client.get("/api/v1/overlap/upsc-cse/capf-ac?classification=NOPE")
        self.assertEqual(r.status_code, 422)

    def test_syllabus_endpoint(self):
        r = self.client.get("/api/v1/syllabus/upsc-cse")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["subjects"])
        self.assertTrue(all(s["official_text"] for s in d["subjects"]))
        self.assertEqual(self.client.get("/api/v1/syllabus/zzz").status_code, 404)

    def test_auth_register_login_validation(self):
        dup = self.client.post("/api/v1/auth/register",
                               json={"email": "aspirant1@example.com", "password": "strongpass1"})
        self.assertEqual(dup.status_code, 422)
        bad = self.client.post("/api/v1/auth/register",
                               json={"email": "not-an-email", "password": "strongpass1"})
        self.assertEqual(bad.status_code, 422)
        short = self.client.post("/api/v1/auth/register",
                                 json={"email": "x@example.com", "password": "short"})
        self.assertEqual(short.status_code, 422)
        ok = self.client.post("/api/v1/auth/login",
                              json={"email": "aspirant1@example.com", "password": "strongpass1"})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["token"])
        bad_login = self.client.post("/api/v1/auth/login",
                                     json={"email": "aspirant1@example.com", "password": "wrongpassword"})
        self.assertEqual(bad_login.status_code, 401)
        me = self.client.get("/api/v1/me", headers=self.ha)
        self.assertTrue(me.json()["authenticated"])
        self.assertEqual(me.json()["email"], "aspirant1@example.com")

    def test_personal_endpoints_require_auth(self):
        for path in ("/api/v1/progress", "/api/v1/dashboard", "/api/v1/tasks",
                     "/api/v1/analytics?exam_id=upsc-cse", "/api/v1/plan/upsc-cse/capf-ac"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_two_user_isolation(self):
        ra = self.client.post("/api/v1/auth/register",
                              json={"email": "iso-a@example.com", "password": "isopass99"})
        rb = self.client.post("/api/v1/auth/register",
                              json={"email": "iso-b@example.com", "password": "isopass99"})
        ha = {"Authorization": f"Bearer {ra.json()['token']}"}
        hb = {"Authorization": f"Bearer {rb.json()['token']}"}
        mapping = self.client.get("/api/v1/overlap/upsc-cse/capf-ac?classification=EXACT_MATCH").json()
        pair = next(p for g in mapping["groups"] for p in g["items"])
        r = self.client.post("/api/v1/progress", headers=ha,
                             json={"micro_topic_id": pair["id_a"], "status": "COMPLETED", "mastery": 100})
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()["applied"]), 2)
        cov_a = self.client.get("/api/v1/progress/upsc-cse/coverage", headers=ha).json()
        cov_b = self.client.get("/api/v1/progress/upsc-cse/coverage", headers=hb).json()
        self.assertGreater(cov_a["overall"]["completed"], 0)
        self.assertEqual(cov_b["overall"]["completed"], 0)
        tasks_b = self.client.get("/api/v1/tasks", headers=hb).json()["tasks"]
        self.assertEqual(tasks_b, [])
        self.client.post("/api/v1/plan/upsc-cse/capf-ac/generate?limit=2", headers=hb)
        tasks_b = self.client.get("/api/v1/tasks", headers=hb).json()["tasks"]
        self.assertEqual(len(tasks_b), 2)
        self.assertEqual(self.client.get("/api/v1/tasks", headers=ha).json()["tasks"], [])
        self.assertEqual(self.client.get("/api/v1/progress/upsc-cse/coverage").status_code, 401)

    def test_plan_generate_and_tasks(self):
        r = self.client.get("/api/v1/plan/upsc-cse/capf-ac", headers=self.hb)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["items"])
        r = self.client.post("/api/v1/plan/upsc-cse/capf-ac/generate?limit=3", headers=self.hb)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["created"], 3)
        tasks = self.client.get("/api/v1/tasks", headers=self.hb).json()["tasks"]
        self.assertEqual(len(tasks), 3)
        tid = tasks[0]["id"]
        self.assertEqual(self.client.post(f"/api/v1/tasks/{tid}/complete", headers=self.hb).json()["status"], "DONE")
        other = self.client.post(f"/api/v1/tasks/{tid}/complete", headers=self.ha)
        self.assertEqual(other.status_code, 404)
        self.assertEqual(self.client.post("/api/v1/tasks/99999/complete", headers=self.hb).status_code, 404)

    def test_questions_answer_and_validation(self):
        r = self.client.get("/api/v1/questions?exam_id=capf-ac")
        self.assertEqual(r.status_code, 200)
        qs = r.json()["questions"]
        self.assertTrue(qs)
        self.assertTrue(all(q["q_type"] == "DEMONSTRATION" for q in qs))
        qid = qs[0]["id"]
        a = self.client.post(f"/api/v1/questions/{qid}/answer", headers=self.ha, json={"chosen": 0})
        self.assertEqual(a.status_code, 200)
        self.assertIn("correct", a.json())
        self.assertEqual(self.client.get("/api/v1/questions?exam_id=zzz").status_code, 404)
        an = self.client.get("/api/v1/analytics?exam_id=capf-ac", headers=self.ha)
        self.assertEqual(an.status_code, 200)
        self.assertGreaterEqual(an.json()["attempts"]["total"], 1)
        an_b = self.client.get("/api/v1/analytics?exam_id=capf-ac", headers=self.hb)
        self.assertEqual(an_b.json()["attempts"]["total"], 0)

    def test_mentor_reports_unconfigured(self):
        r = self.client.post("/api/v1/mentor", headers=self.ha,
                             json={"question": "What is the overlap between polity syllabuses?"})
        self.assertEqual(r.status_code, 503)
        r = self.client.post("/api/v1/mentor", headers=self.ha, json={})
        self.assertEqual(r.status_code, 422)

    def test_dashboard(self):
        r = self.client.get("/api/v1/dashboard", headers=self.ha)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["exams"])
        self.assertIsNotNone(d["overlap_summary"])


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(_DB), "test_api_results.txt")
    with open(out, "w") as f:
        unittest.main(testRunner=unittest.TextTestRunner(stream=f, verbosity=2), exit=False, argv=sys.argv)

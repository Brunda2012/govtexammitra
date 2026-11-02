"""End-to-end tests for the Government Source Discovery & Ingestion Engine.

Uses an embedded HTTP server (localhost) serving robots.txt, listing pages,
an RSS feed and documents — no internet access needed. Covers: source
registration, admin authorisation, ingestion, exam classification, dedup,
change detection (versioning), robots.txt respect, RSS without dates,
search filters, admin review and the audit trail.
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.db as dbmod

fd, _DB = tempfile.mkstemp(suffix=".db")
os.close(fd)
dbmod.DB_PATH = _DB
os.environ["GOV_INGEST_ALLOW_LOCAL"] = "1"  # localhost test sources only

from fastapi.testclient import TestClient
from server import app
from app.seed import seed
from app.db import get_conn

seed()

PAGES = {
    "/robots.txt": b"User-agent: *\nDisallow: /secret/\n",
    "/whats-new": """<html><head><title>What's New</title></head><body>
      <a href="/docs/cse-notice">Civil Services Examination Notification 2025</a>
      <a href="/docs/capf-notice">CAPF Assistant Commandant Examination Notice</a>
      <a href="/docs/mutable">Press Release: Results of Recruitment Test</a>
      <a href="/secret/hidden">Secret Hidden Document</a>
      <a href="https://external.example.com/x">External</a>
      </body></html>""",
    "/docs/cse-notice": b"<html><body>Application window opens for the Civil Services Examination. "
                        b"Eligibility: graduation. Last date to apply as per official notice.</body></html>",
    "/docs/capf-notice": b"<html><body>CAPF Assistant Commandant written examination syllabus notice. "
                         b"Answer key will be released after the examination.</body></html>",
    "/docs/mutable": b"<html><body>Press Release: initial version of the results press note.</body></html>",
    "/secret/hidden": b"<html><body>Secret document that robots disallow.</body></html>",
    "/feed.xml": """<?xml version="1.0"?>
      <rss version="2.0"><channel><title>PIB Feed</title>
      <item><title>Ministry issues circular on examination scheme</title>
      <link>http://localhost:0/feed-item-1</link></item>
      <item><title>Recruitment notification for vacancies announced</title>
      <link>http://localhost:0/feed-item-2</link><pubDate>Mon, 02 Jun 2025 10:00:00 +0530</pubDate></item>
      </channel></rss>""",
}
PAGES["/feed.xml"] = PAGES["/feed.xml"].encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def log_message(self, *a):
        pass


class GovSourceTests(unittest.TestCase):
    port = None
    gid = None

    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        from app.ratelimit import RateLimitMiddleware
        if RateLimitMiddleware._last:
            RateLimitMiddleware._last._hits.clear()
        cls.client = TestClient(app)
        PAGES["/feed.xml"] = PAGES["/feed.xml"].replace(b"localhost:0", f"localhost:{cls.port}".encode())
        r = cls.client.post("/api/v1/auth/register",
                            json={"email": "admin@example.com", "password": "strongpass1"})
        cls.admin = r.json()["token"]
        conn = get_conn()
        conn.execute("UPDATE users SET role='admin' WHERE email='admin@example.com'")
        conn.commit()
        conn.close()
        r = cls.client.post("/api/v1/auth/register",
                            json={"email": "plain@example.com", "password": "strongpass2"})
        cls.user = r.json()["token"]
        cls.ha = {"Authorization": f"Bearer {cls.admin}"}
        cls.hu = {"Authorization": f"Bearer {cls.user}"}

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def _add_source(self, name, listing, kind="HTML", **kw):
        payload = {"name": name, "organisation": "Test Ministry", "kind": kind,
                   "base_url": f"http://localhost:{self.port}", "listing_path": listing,
                   "frequency_hours": 12, "max_pages": 5}
        payload.update(kw)
        r = self.client.post("/api/v1/gov/sources", json=payload, headers=self.ha)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def _run_ingest(self, source_id):
        before = {j["id"] for j in
                  self.client.get("/api/v1/gov/jobs?limit=50", headers=self.ha).json()["jobs"]}
        r = self.client.post("/api/v1/gov/ingest/run", json={"source_id": source_id}, headers=self.ha)
        self.assertEqual(r.status_code, 200, r.text)
        deadline = time.time() + 30
        while time.time() < deadline:
            jobs = self.client.get("/api/v1/gov/jobs?limit=50", headers=self.ha).json()["jobs"]
            fresh = [j for j in jobs if j["source_id"] == source_id and j["id"] not in before]
            if fresh:
                return fresh[0]
            time.sleep(0.5)
        self.fail("ingestion run did not complete in time")

    def _docs(self, **params):
        return self.client.get("/api/v1/gov/documents", params=params).json()

    # ---------- tests ----------

    def test_01_auth_required_for_admin_endpoints(self):
        base = f"http://localhost:{self.port}"
        self.assertEqual(self.client.post("/api/v1/gov/sources",
                                          json={"name": "xx", "organisation": "yy", "base_url": base}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/gov/sources",
                                          json={"name": "xx", "organisation": "yy", "base_url": base},
                                          headers=self.hu).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/gov/jobs", headers=self.hu).status_code, 403)

    def test_02_official_domain_validation(self):
        r = self.client.post("/api/v1/gov/sources",
                             json={"name": "Bad", "organisation": "Bad", "base_url": "https://example.com"},
                             headers=self.ha)
        self.assertEqual(r.status_code, 422)

    def test_03_ingest_listing_and_classify(self):
        sid = self._add_source("Test WhatsNew", "/whats-new")
        job = self._run_ingest(sid)
        self.assertEqual(job["status"], "OK")
        self.assertGreaterEqual(job["pages_fetched"], 2)
        docs = self._docs(limit=50)["documents"]
        self.assertGreaterEqual(len(docs), 3)
        by_title = {d["title"]: d for d in docs}
        self.assertIn("Civil Services Examination Notification 2025", by_title)
        cse = by_title["Civil Services Examination Notification 2025"]
        self.assertEqual(cse["doc_type"], "NOTIFICATION")
        self.assertEqual(cse["exam_ids"], ["upsc-cse"])
        self.assertEqual(cse["classification_status"], "AUTO_CLASSIFIED")
        capf = by_title["CAPF Assistant Commandant Examination Notice"]
        self.assertEqual(capf["doc_type"], "EXAM_ANNOUNCEMENT")
        self.assertIn("capf-ac", capf["exam_ids"])
        # secret path must never be fetched (robots)
        titles = [d["title"] for d in docs]
        self.assertNotIn("Secret Hidden Document", titles)
        GovSourceTests.gid = sid

    def test_04_dedupe_on_second_run(self):
        before = self._docs(limit=50)["total"]
        job = self._run_ingest(self.gid)
        self.assertEqual(job["docs_new"], 0)
        self.assertEqual(self._docs(limit=50)["total"], before)

    def test_05_change_detection_versions_document(self):
        PAGES["/docs/mutable"] = b"<html><body>Press Release: revised version of the results press note.</body></html>"
        job = self._run_ingest(self.gid)
        self.assertEqual(job["docs_updated"], 1)
        docs = self._docs(q="press release", limit=50)["documents"]
        self.assertEqual(docs[0]["version"], 2)
        PAGES["/docs/mutable"] = b"<html><body>Press Release: initial version of the results press note.</body></html>"

    def test_06_search_and_filters(self):
        r = self._docs(q="Civil Services")
        self.assertEqual(r["total"], 1)
        r = self._docs(exam="capf-ac")
        self.assertEqual(r["total"], 1)
        r = self._docs(doc_type="NOTIFICATION")
        self.assertEqual(r["total"], 1)

    def test_07_rss_source_without_invented_dates(self):
        sid = self._add_source("Test RSS Feed", "/feed.xml", kind="RSS")
        job = self._run_ingest(sid)
        self.assertEqual(job["status"], "OK")
        self.assertEqual(job["docs_new"], 2)
        docs = self._docs(limit=50)["documents"]
        dated = [d for d in docs if d["title"].startswith("Recruitment notification for vacancies")]
        self.assertTrue(dated and dated[0]["published_at"])
        nodate = [d for d in docs if d["title"].startswith("Ministry issues circular")]
        self.assertTrue(nodate and nodate[0]["published_at"] is None)

    def test_08_robots_blocked_source_recorded(self):
        sid = self._add_source("Test Blocked", "/secret/")
        job = self._run_ingest(sid)
        self.assertEqual(job["status"], "ROBOTS_BLOCKED")
        before = self._docs(limit=50)["total"]
        self._run_ingest(sid)
        self.assertEqual(self._docs(limit=50)["total"], before)

    def test_09_admin_review_approve_and_reject(self):
        doc = self._docs(q="Civil Services")["documents"][0]
        r = self.client.post(f"/api/v1/gov/documents/{doc['id']}/review",
                             json={"decision": "approve", "note": "confirmed on UPSC site"}, headers=self.ha)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["classification_status"], "ADMIN_APPROVED")

    def test_10_rejected_document_hidden_from_users(self):
        doc = self._docs(q="CAPF")["documents"][0]
        r = self.client.post(f"/api/v1/gov/documents/{doc['id']}/review",
                             json={"decision": "reject", "note": "misclassified"}, headers=self.ha)
        self.assertEqual(r.status_code, 200)
        titles = [d["title"] for d in self._docs(limit=50)["documents"]]
        self.assertNotIn(doc["title"], titles)

    def test_11_stats_audit_and_delete(self):
        stats = self.client.get("/api/v1/gov/stats").json()
        self.assertGreater(stats["documents"], 0)
        self.assertGreater(stats["sources_total"], 0)
        audit = self.client.get("/api/v1/gov/audit", headers=self.ha).json()["audit"]
        actions = {a["action"] for a in audit}
        self.assertIn("ADD_SOURCE", actions)
        self.assertIn("DOCUMENT_REJECT", actions)
        sid = self._add_source("Test DeleteMe", "/whats-new")
        r = self.client.delete(f"/api/v1/gov/sources/{sid}", headers=self.ha)
        self.assertEqual(r.status_code, 200)
        ids = [s["id"] for s in self.client.get("/api/v1/gov/sources").json()["sources"]]
        self.assertNotIn(sid, ids)


if __name__ == "__main__":
    unittest.main()

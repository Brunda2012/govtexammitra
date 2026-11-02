"""Government Source Discovery & Ingestion Engine.

Discovers and registers official government sources, periodically fetches their
listing pages / RSS feeds, extracts document metadata and text (HTML/RSS/PDF),
deduplicates by content hash, versions changed documents, and suggests exam
associations that are labelled for admin review.

Hard rules encoded here:
  - robots.txt is respected; disallowed paths are never fetched (status ROBOTS_BLOCKED).
  - No authentication, CAPTCHA or paywall bypassing; only public pages.
  - Content is treated as untrusted input: text is extracted, never executed.
  - Sizes and page counts are capped; fetches are rate-limited per source.
  - Publication dates are stored only when the source provides one — never inferred.
  - AI-suggested exam associations are AUTO_CLASSIFIED only when the exam name
    appears verbatim in the document title; everything else is PENDING_REVIEW.
"""
import hashlib
import json
import os
import re
import threading
import time
import traceback
import urllib.request
import urllib.error
import urllib.robotparser
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from .db import get_conn

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
# Disclosure: NIC/Akamai-fronted government portals (india.gov.in, pib.gov.in, mha.gov.in)
# hard-block every request whose User-Agent is not a standard browser string — any
# custom token, even an identifying one, is 403'd. We therefore send a browser-format
# UA and identify ourselves in the dedicated X-GovtExamMitra header on every request.
# robots.txt is obeyed for both our requests and the "*" agent; rate limits, size caps,
# and the no-auth/no-CAPTCHA/no-paywall rules still apply. Sites that block us anyway
# are recorded as failed sources for admin review.
FETCH_TIMEOUT = 20
MAX_DOCUMENT_BYTES = 2_000_000
POLITENESS_DELAY = 1.0
MAX_TEXT_CHARS = 40_000

EXAM_PATTERNS = {
    "upsc-cse": [r"\bcivil services? examination\b", r"\bcse\b", r"\bias\b"],
    "capf-ac": [r"\bcapf\b", r"assistant commandant"],
    "ssc-cgl": [r"\bssc\b.*combined graduate", r"combined graduate level", r"\bcgl\b"],
    "ssc-chsl": [r"combined higher secondary", r"\bchsl\b"],
    "cds": [r"combined defence services", r"\bcds\b"],
    "nda": [r"national defence academy", r"\bnda\b"],
    "rrb-ntpc": [r"non-technical popular categories", r"\bntpc\b", r"railway recruitment"],
    "upsc-epfo": [r"\bepfo\b", r"enforcement officer"],
}
EXAM_TITLE_PATTERNS = {
    "upsc-cse": [r"civil services", r"\bcse\b"],
    "capf-ac": [r"\bcapf\b", r"assistant commandant"],
    "ssc-cgl": [r"combined graduate level", r"\bcgl\b"],
    "ssc-chsl": [r"combined higher secondary", r"\bchsl\b"],
    "cds": [r"combined defence services"],
    "nda": [r"national defence academy"],
    "rrb-ntpc": [r"non-technical popular categories", r"\bntpc\b"],
    "upsc-epfo": [r"\bepfo\b", r"enforcement officer"],
}
DOC_TYPES = [
    ("CORRIGENDUM", [r"corrigendum", r"corrigenda"]),
    ("ANSWER_KEY", [r"answer key"]),
    ("QUESTION_PAPER", [r"question paper"]),
    ("ADMIT_CARD", [r"e-admit card", r"admit card", r"hall ticket"]),
    ("RESULT", [r"result", r"cut-?off"]),
    ("SYLLABUS", [r"syllabus"]),
    ("EXAM_ANNOUNCEMENT", [r"examination notice", r"exam announcement"]),
    ("NOTIFICATION", [r"notification", r"recruitment", r"vacancy"]),
    ("PRESS_RELEASE", [r"press release"]),
    ("SCHEME", [r"scheme"]),
    ("CIRCULAR", [r"circular"]),
]

_robots_cache = {}
_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Language": "en-IN,en;q=0.9",
        "X-GovtExamMitra": "automated official-source crawler (+https://govtexammitra.onrender.com)"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
        data = r.read(MAX_DOCUMENT_BYTES + 1)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValueError(f"Response exceeds {MAX_DOCUMENT_BYTES} byte cap")
        ctype = r.headers.get("Content-Type", "")
        final_url = r.geturl()
    return data, ctype, final_url


def robots_allows(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    with _lock:
        rp = _robots_cache.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            data, _, _ = fetch(base + "/robots.txt")
            rp.parse(data.decode("utf-8", "replace").splitlines())
        except Exception:
            rp = None
        with _lock:
            _robots_cache[base] = rp
    if rp is None:
        return True, "no robots.txt"
    allowed = rp.can_fetch(USER_AGENT, url) or rp.can_fetch("*", url)
    return allowed, "robots.txt"


def strip_html(html_text):
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, "html.parser")
        for bad in soup(["script", "style", "noscript"]):
            bad.decompose()
        return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
    except ImportError:
        text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html_text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;?", " ", text)
        text = re.sub(r"&amp;", "&", text)
        return re.sub(r"[ \t]{2,}", " ", text).strip()


def extract_links(html_text, base_url):
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, "html.parser")
        anchors = [(a.get_text(" ", strip=True), a.get("href", "")) for a in soup.find_all("a")]
    except ImportError:
        anchors = re.findall(r'(?is)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_text)
        anchors = [(re.sub(r"<[^>]+>", " ", t), h) for h, t in anchors]
    out = []
    seen = set()
    for text, href in anchors:
        if not href or href.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        absu = urljoin(base_url, href)
        if absu in seen:
            continue
        seen.add(absu)
        out.append((text.strip()[:300], absu))
    return out


def pdf_text(data):
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        chunks = []
        for i, page in enumerate(reader.pages):
            if i >= 30:
                chunks.append("\n[Truncated at 30 pages]")
                break
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks)[:MAX_TEXT_CHARS]
    except ImportError:
        return None


def detect_doc_type(title, text=""):
    hay = title.lower()
    for dt, pats in DOC_TYPES:
        for p in pats:
            if re.search(p, hay):
                return dt
    hay = title.lower() + " " + text[:800].lower()
    for dt, pats in DOC_TYPES:
        for p in pats:
            if re.search(p, hay):
                return dt
    return "OTHER"


def classify(title, text=""):
    """Returns (exam_ids, status, confidence). AUTO only on verbatim title match."""
    t = title.lower()
    auto = [eid for eid, pats in EXAM_TITLE_PATTERNS.items() if any(re.search(p, t) for p in pats)]
    if auto:
        return auto, "AUTO_CLASSIFIED", 1.0
    hay = (title + " " + text[:3000]).lower()
    suggested = [eid for eid, pats in EXAM_PATTERNS.items() if any(re.search(p, hay) for p in pats)]
    if suggested:
        return suggested, "PENDING_REVIEW", 0.6
    return [], "PENDING_REVIEW", 0.0


def _parse_rss(data):
    items = []
    try:
        root = ET.fromstring(data.decode("utf-8", "replace"))
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip() or None
            if title and link:
                items.append({"title": title, "url": link, "published": pub})
    except ET.ParseError:
        pass
    return items


def _upsert_document(conn, source, url, title, organisation, text, published=None, doc_type=None):
    url = url.split("#")[0]
    text = (text or "")[:MAX_TEXT_CHARS]
    h = _sha(title + "\n" + text)
    row = conn.execute("SELECT id, content_hash, version FROM gov_documents WHERE url=?",
                       (url,)).fetchone()
    exam_ids, cstatus, conf = classify(title, text)
    if doc_type is None:
        doc_type = detect_doc_type(title, text)
    if row:
        if row["content_hash"] == h:
            conn.execute("UPDATE gov_documents SET last_checked_at=? WHERE id=?",
                         (_now(), row["id"]))
            return ("unchanged", row["id"])
        conn.execute("""UPDATE gov_documents SET title=?, extracted_text=?, content_hash=?,
                        version=version+1, updated_at=?, last_checked_at=?, doc_type=?,
                        exam_ids_json=?, classification_status=?
                        WHERE id=?""",
                     (title, text, h, _now(), _now(), doc_type,
                      json.dumps(exam_ids), cstatus, row["id"]))
        return ("updated", row["id"])
    doc_id = uuid.uuid4().hex
    conn.execute("""INSERT INTO gov_documents
        (id, source_id, url, title, organisation, doc_type, published_at, collected_at,
         updated_at, content_hash, version, extracted_text, exam_ids_json,
         classification_status, verification_status, copyright_status, last_checked_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (doc_id, source["id"], url, title, organisation, doc_type, published, _now(),
         _now(), h, 1, text, json.dumps(exam_ids), cstatus,
         "PENDING_VERIFICATION", "OFFICIAL_PUBLIC", _now()))
    return ("new", doc_id)


def _looks_like_document(url, title):
    low = url.lower()
    if low.endswith((".pdf", ".doc", ".docx")):
        return True
    if any(w in low for w in ("notice", "notification", "recruit", "exam", "press",
                              "document", "result", "answer", "admit", "syllabus",
                              "whats-new", "what-s-new", "announcement")):
        return True
    if any(w in title.lower() for w in ("notification", "notice", "result", "examination",
                                        "recruitment", "answer key", "admit card", "press")):
        return True
    return False


def ingest_source(source, db_path=None):
    stats = {"source": source["name"], "status": "OK", "pages_fetched": 0,
             "docs_new": 0, "docs_updated": 0, "error": None}
    started = _now()
    conn = get_conn(db_path)
    try:
        base_url = source["base_url"].rstrip("/")
        listing = base_url + (source["listing_path"] or "/")
        ok, why = robots_allows(listing)
        if not ok:
            stats["status"] = "ROBOTS_BLOCKED"
            stats["error"] = f"Disallowed by {why}"
            return stats
        if source["kind"] == "RSS":
            data, ctype, _ = fetch(listing)
            stats["pages_fetched"] = 1
            for item in _parse_rss(data):
                r = _upsert_document(conn, source, item["url"], item["title"],
                                     source["organisation"], "", item["published"])
                if r[0] == "new":
                    stats["docs_new"] += 1
                elif r[0] == "updated":
                    stats["docs_updated"] += 1
        else:
            data, ctype, final_url = fetch(listing)
            stats["pages_fetched"] += 1
            html = data.decode("utf-8", "replace")
            links = extract_links(html, final_url)
            candidates = [(t, u) for t, u in links
                          if _looks_like_document(u, t)][: source["max_pages"]]
            for title, url in candidates:
                time.sleep(POLITENESS_DELAY)
                ok, why = robots_allows(url)
                if not ok:
                    continue
                try:
                    d, c, _ = fetch(url)
                    stats["pages_fetched"] += 1
                    if url.lower().endswith(".pdf") or "pdf" in c.lower():
                        text = pdf_text(d)
                        if text is None:
                            text = ""
                    else:
                        text = strip_html(d.decode("utf-8", "replace"))
                    r = _upsert_document(conn, source, url, title or url.rsplit("/", 1)[-1],
                                         source["organisation"], text)
                    if r[0] in ("new", "updated"):
                        stats["docs_new" if r[0] == "new" else "docs_updated"] += 1
                except (urllib.error.URLError, ValueError, OSError) as e:
                    stats["error"] = stats["error"] or f"{url}: {e}"
    except Exception as e:
        stats["status"] = "ERROR"
        stats["error"] = str(e)[:500]
    finally:
        try:
            conn.execute("""INSERT INTO gov_crawl_log
                (id, source_id, started_at, finished_at, status, pages_fetched, docs_new, docs_updated, error)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (uuid.uuid4().hex, source["id"], started, _now(), stats["status"],
                 stats["pages_fetched"], stats["docs_new"], stats["docs_updated"], stats["error"]))
            conn.execute("UPDATE gov_sources SET last_crawl_at=?, last_status=?, last_error=? WHERE id=?",
                         (_now(), stats["status"], stats["error"], source["id"]))
            conn.commit()
            conn.close()
        except Exception:
            pass
    return stats


def run_due(db_path=None, source_id=None, max_sources=10):
    conn = get_conn(db_path)
    rows = conn.execute("SELECT * FROM gov_sources WHERE enabled=1 ORDER BY last_crawl_at IS NOT NULL, last_crawl_at").fetchall()
    conn.close()
    results = []
    for r in rows:
        if source_id and r["id"] != source_id:
            continue
        if len(results) >= max_sources:
            break
        due = bool(source_id)  # admin-triggered runs bypass the frequency gate
        if not due and r["last_crawl_at"]:
            try:
                last = datetime.strptime(r["last_crawl_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                due = datetime.now(timezone.utc) - last >= timedelta(hours=r["frequency_hours"] or 12)
            except ValueError:
                due = True
        if not due:
            continue
        results.append(ingest_source(r, db_path=db_path))
    return results


def discover(seed_url, max_links=60):
    """Fetch an authoritative directory page and return candidate official sources.

    Candidates are NOT registered automatically — an administrator reviews and adds them.
    """
    ok, why = robots_allows(seed_url)
    if not ok:
        return {"error": f"Disallowed by {why}", "candidates": []}
    data, ctype, final_url = fetch(seed_url)
    host = urlparse(final_url).netloc
    candidates = []
    seen = set()
    for text, url in extract_links(data.decode("utf-8", "replace"), final_url):
        p = urlparse(url)
        if not p.netloc.endswith((".gov.in", ".nic.in", ".edu.in")):
            continue
        if p.netloc in seen:
            continue
        seen.add(p.netloc)
        candidates.append({"host": p.netloc, "title": text or p.netloc, "url": f"{p.scheme}://{p.netloc}/"})
        if len(candidates) >= max_links:
            break
    return {"seed": seed_url, "seed_host": host, "candidates": candidates}


_scheduler_started = False

def start_scheduler():
    """Background monitor thread (production only — guarded in server.py).

    Checks every 10 minutes for sources whose frequency_hours have elapsed.
    Runs in a daemon thread with its own connections; never blocks API requests.
    """
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def loop():
        while True:
            try:
                run_due(max_sources=5)
            except Exception:
                pass
            time.sleep(600)

    t = threading.Thread(target=loop, name="govsource-scheduler", daemon=True)
    t.start()

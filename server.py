"""GovtExamMitra API + application server.

REST contract: versioned under /api/v1 and documented via OpenAPI at /docs.
The frontend is a static SPA served from /static and consumes only /api/v1 —
the same contract a future React Native/Expo app would use.
"""
import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Body, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.db import get_conn, load_json_fields
from app import overlap as ov, progress as prog, planner as plan
from app import mocks as mockmod, revision as revmod, recommend as recmod, mains as mainmod
from app.seed import seed
from app.auth import resolve_user, authenticate, register as register_user, EMAIL_RE
from app.security import make_token
from app.ratelimit import RateLimitMiddleware
from app import mentor

# Production hard-fail: never boot a public deployment without a real secret.
# "Production" = DATABASE_URL (managed Postgres) set or a Render/managed environment.
if (os.environ.get("DATABASE_URL") or os.environ.get("RENDER")) and not os.environ.get("SECRET_KEY"):
    raise RuntimeError(
        "SECRET_KEY is not set. In production it is mandatory: tokens are signed with it and "
        "must stay valid across restarts. Refusing to start with an auto-generated secret.")

def current_user(request: Request) -> str | None:
    return resolve_user(request)

def require_user(user: str | None = Depends(current_user)) -> str:
    if not user:
        raise HTTPException(401, "Authentication required. Register or log in to use this feature.")
    return user

BASE = os.path.dirname(os.path.abspath(__file__))

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed()
    # Government source monitor: production only (scheduler threads must not run under tests).
    if (os.environ.get("DATABASE_URL") or os.environ.get("RENDER")) and os.environ.get("GOV_INGEST_SCHEDULER", "1") != "0":
        from app.govsource import start_scheduler
        start_scheduler()
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if admin_email and admin_password:
        conn = get_conn()
        if not conn.execute("SELECT 1 FROM users WHERE email=?", (admin_email.lower(),)).fetchone():
            register_user(conn, admin_email, admin_password)
            conn.execute("UPDATE users SET role='admin' WHERE email=?", (admin_email.lower(),))
            conn.commit()
        conn.close()
    yield

app = FastAPI(title="GovtExamMitra API", version="1.0.0",
              description="REST API for GovtExamMitra. Versioned under /api/v1.",
              lifespan=lifespan)
app.add_middleware(RateLimitMiddleware)

# CORS: same-origin SPA needs nothing; a separately hosted Next.js frontend adds its
# origin(s) via the CORS_ORIGINS env var (comma-separated).
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=_origins,
                       allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

api = API = None
from fastapi import APIRouter
api = APIRouter(prefix="/api/v1")

# ---------- auth ----------

class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=200)

@api.post("/auth/register", tags=["auth"])
def auth_register(payload: RegisterIn):
    conn = get_conn()
    try:
        user = register_user(conn, payload.email, payload.password)
        return {"token": make_token(user["id"], user["role"]), "user": user}
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()

@api.post("/auth/login", tags=["auth"])
def auth_login(payload: RegisterIn):
    conn = get_conn()
    try:
        user = authenticate(conn, payload.email, payload.password)
        if not user:
            raise HTTPException(401, "Invalid email or password")
        return {"token": make_token(user["id"], user["role"]), "user": user}
    finally:
        conn.close()

@api.get("/me", tags=["auth"])
def me(user: str | None = Depends(current_user)):
    if not user:
        return {"authenticated": False}
    conn = get_conn()
    row = conn.execute("SELECT id,email,role,created_at FROM users WHERE id=?", (user,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "Unknown user")
    return {"authenticated": True, **dict(row)}

@api.get("/admin/users", tags=["admin"])
def admin_users(user: str | None = Depends(current_user)):
    if not user:
        raise HTTPException(401, "Authentication required")
    conn = get_conn()
    row = conn.execute("SELECT role FROM users WHERE id=?", (user,)).fetchone()
    if not row or row["role"] != "admin":
        conn.close()
        raise HTTPException(403, "Administrator access required")
    rows = [dict(r) for r in conn.execute(
        "SELECT id,email,role,created_at FROM users ORDER BY created_at DESC").fetchall()]
    conn.close()
    return {"users": rows}

# ---------- exams ----------

@api.get("/exams", tags=["exams"])
def list_exams():
    conn = get_conn()
    rows = ov.list_exams(conn)
    conn.close()
    return [load_json_fields(r, ["stages_json", "papers_json", "marking_json", "official_links_json"]) for r in rows]

@api.get("/exams/{exam_id}", tags=["exams"])
def get_exam(exam_id: str):
    conn = get_conn()
    e = ov.get_exam(conn, exam_id)
    conn.close()
    if not e:
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    return load_json_fields(e, ["stages_json", "papers_json", "marking_json", "official_links_json"])

# ---------- exam overlap intelligence ----------

@api.get("/overlap/{exam_a}/{exam_b}", tags=["overlap"])
def overlap(exam_a: str, exam_b: str,
            classification: str | None = Query(None, description="EXACT_MATCH|PARTIAL_OVERLAP|RELATED_CONCEPT"),
            group: str | None = Query(None, description="subject group key"),
            q: str | None = Query(None, description="search text in topic names")):
    try:
        conn = get_conn()
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")
    try:
        result = ov.compare(conn, exam_a, exam_b)
        pairs = result["pairs"]
        if classification:
            if classification not in ov.CLASSIFICATIONS:
                raise HTTPException(422, f"classification must be one of {ov.CLASSIFICATIONS}")
            pairs = [p for p in pairs if p["classification"] == classification]
        if group:
            pairs = [p for p in pairs if p["group_key"] == group]
        if q:
            ql = q.lower()
            pairs = [p for p in pairs if ql in p["name_a"].lower() or ql in p["name_b"].lower()]
        if classification or group or q:
            result = ov.compare(conn, exam_a, exam_b)
            result["pairs"] = pairs
        stats = ov.stats(result["pairs"], result["specific_a"], result["specific_b"])
        return {"exam_a": exam_a, "exam_b": exam_b, "stats": stats,
                "groups": ov.group_by_subject(result["pairs"], result["specific_a"], result["specific_b"])}
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()

@api.get("/syllabus/{exam_id}", tags=["syllabus"])
def syllabus(exam_id: str):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    subjects = [dict(r) for r in conn.execute(
        "SELECT * FROM subjects WHERE exam_id=? ORDER BY ordering, name", (exam_id,)).fetchall()]
    micros = [dict(r) for r in conn.execute(
        "SELECT m.*, s.name subject_name, s.group_key FROM micro_topics m JOIN subjects s ON s.id=m.subject_id "
        "WHERE m.exam_id=? ORDER BY s.ordering, m.name", (exam_id,)).fetchall()]
    conn.close()
    return {"exam_id": exam_id, "subjects": subjects, "micro_topics": micros}

# ---------- progress ----------

class ProgressIn(BaseModel):
    micro_topic_id: int = Field(gt=0)
    status: str = Field(pattern="^(NOT_STARTED|IN_PROGRESS|COMPLETED)$")
    mastery: int = Field(default=0, ge=0, le=100)

@api.get("/progress", tags=["progress"])
def get_progress(exam_id: str | None = None, user: str = Depends(require_user)):
    conn = get_conn()
    rows = prog.get_progress(conn, user, exam_id)
    conn.close()
    return {"user": user, "progress": rows}

@api.post("/progress", tags=["progress"])
def set_progress(payload: ProgressIn, user: str = Depends(require_user)):
    conn = get_conn()
    try:
        applied = prog.propagate(conn, user, payload.micro_topic_id, payload.status, payload.mastery)
        conn.commit()
        return {"applied": applied,
                "propagation_rule": ("EXACT_MATCH: same status/mastery copied to the mapped exam. "
                                     "PARTIAL_OVERLAP: other exam set to IN_PROGRESS with mastery capped at 60. "
                                     "RELATED_CONCEPT and exam-specific: no propagation.")}
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()

@api.get("/progress/{exam_id}/coverage", tags=["progress"])
def coverage(exam_id: str, user: str = Depends(require_user)):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    data = prog.coverage(conn, user, exam_id)
    overall = prog.overall(conn, user, exam_id)
    weak = prog.weak_topics(conn, user, exam_id)
    conn.close()
    return {"exam_id": exam_id, "subjects": data, "overall": overall, "weak_topics": weak}

# ---------- combined plan & tasks ----------

@api.get("/plan/{exam_a}/{exam_b}", tags=["planner"])
def combined_plan(exam_a: str, exam_b: str, user: str = Depends(require_user)):
    conn = get_conn()
    try:
        items = plan.build_plan(conn, user, exam_a, exam_b)
        return {"exam_a": exam_a, "exam_b": exam_b, "items": items}
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()

@api.post("/plan/{exam_a}/{exam_b}/generate", tags=["planner"])
def generate_tasks(exam_a: str, exam_b: str, limit: int = Query(10, ge=1, le=25), user: str = Depends(require_user)):
    conn = get_conn()
    try:
        created = plan.create_tasks(conn, user, exam_a, exam_b, limit)
        return {"created": len(created), "tasks": created}
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()

@api.get("/tasks", tags=["planner"])
def tasks(user: str = Depends(require_user)):
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC", (user,)).fetchall()]
    conn.close()
    return {"tasks": [load_json_fields(r, ["micro_topic_ids_json", "exam_ids_json"]) for r in rows]}

@api.post("/tasks/{task_id}/complete", tags=["planner"])
def complete_task(task_id: int, user: str = Depends(require_user)):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Task not found")
    conn.execute("UPDATE tasks SET status='DONE' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return {"id": task_id, "status": "DONE"}

# ---------- practice ----------

@api.get("/questions", tags=["practice"])
def questions(exam_id: str, q_type: str | None = None, difficulty: str | None = None):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    sql = ("SELECT q.id, q.exam_id, q.q_type, q.year, q.paper, q.difficulty, q.question, q.options_json, "
           "m.name topic_name, s.name subject_name FROM questions q "
           "LEFT JOIN micro_topics m ON m.id=q.micro_topic_id LEFT JOIN subjects s ON s.id=q.subject_id "
           "WHERE q.exam_id=?")
    args = [exam_id]
    if q_type:
        sql += " AND q.q_type=?"
        args.append(q_type)
    if difficulty:
        sql += " AND q.difficulty=?"
        args.append(difficulty)
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    for r in rows:
        r["options"] = json.loads(r.pop("options_json") or "[]")
    return {"questions": rows, "note": "Answers are not included; submit through /questions/{id}/answer. All seeded questions are DEMONSTRATION type."}

@api.post("/questions/{question_id}/answer", tags=["practice"])
def answer_question(question_id: int, chosen: int = Body(ge=0, le=5, embed=True), user: str = Depends(require_user)):
    conn = get_conn()
    q = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    if not q:
        conn.close()
        raise HTTPException(404, "Question not found")
    correct = int(chosen == q["answer_index"])
    exam = ov.get_exam(conn, q["exam_id"])
    marking = (exam or {}).get("marking_json")
    score = 0.0
    if marking and isinstance(marking, str):
        try:
            marking = json.loads(marking)
        except ValueError:
            marking = None
    if correct:
        score = 1.0
    elif marking:
        neg = (marking.get("prelims_gs1") or marking.get("paper1") or {}).get("negative_fraction", "1/3")
        score = -1 / 3 if neg == "1/3" else 0.0
    cur = conn.execute("INSERT INTO attempts (user_id, question_id, chosen, correct, score) VALUES (?,?,?,?,?)",
                       (user, question_id, chosen, correct, score))
    conn.commit()
    attempt_id = cur.lastrowid
    conn.close()
    return {"attempt_id": attempt_id, "correct": bool(correct), "answer_index": q["answer_index"],
            "explanation": q["explanation"], "score": score,
            "question_type": q["q_type"]}

@api.get("/analytics", tags=["practice"])
def analytics(exam_id: str, user: str = Depends(require_user)):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    overall = prog.overall(conn, user, exam_id)
    weak = prog.weak_topics(conn, user, exam_id)
    agg = conn.execute("""SELECT COUNT(*) total, SUM(correct) correct, AVG(score) avg_score
                          FROM attempts a JOIN questions q ON q.id=a.question_id
                          WHERE a.user_id=? AND q.exam_id=?""", (user, exam_id)).fetchone()
    agg = dict(agg) if agg else {}
    if agg.get("avg_score") is not None:
        agg["avg_score"] = round(agg["avg_score"], 3)
    recent = [dict(r) for r in conn.execute("""
        SELECT a.id, q.question, a.chosen, a.correct, a.score, a.created_at
        FROM attempts a JOIN questions q ON q.id=a.question_id
        WHERE a.user_id=? AND q.exam_id=? ORDER BY a.id DESC LIMIT 10""", (user, exam_id)).fetchall()]
    conn.close()
    return {"exam_id": exam_id, "syllabus_progress": overall, "weak_topics": weak,
            "attempts": {"total": agg["total"] or 0, "correct": agg["correct"] or 0,
                         "avg_score": agg["avg_score"]}, "recent": recent}

# ---------- dashboard ----------

@api.get("/dashboard", tags=["dashboard"])
def dashboard(user: str = Depends(require_user)):
    conn = get_conn()
    exams = [e for e in ov.list_exams(conn) if e["supported"]]
    out = {"exams": [], "pending_tasks": []}
    for e in exams:
        data = {"id": e["id"], "name": e["name"], "authority": e["authority"],
                "progress": prog.overall(conn, user, e["id"])}
        out["exams"].append(data)
    out["pending_tasks"] = [dict(r) for r in conn.execute(
        "SELECT id,title,detail,due_date,status FROM tasks WHERE user_id=? AND status='PENDING' ORDER BY id LIMIT 8",
        (user,)).fetchall()]
    try:
        cmp_stats = ov.stats(*_overlap_parts(conn, "upsc-cse", "capf-ac"))
    except ValueError:
        cmp_stats = None
    out["overlap_summary"] = cmp_stats
    conn.close()
    return out

def _overlap_parts(conn, a, b):
    r = ov.compare(conn, a, b)
    return r["pairs"], r["specific_a"], r["specific_b"]

# ---------- AI mentor ----------

@api.post("/mentor", tags=["mentor"])
def mentor_question(payload: dict = Body(...)):
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(422, "Field 'question' is required")
    if len(question) > 2000:
        raise HTTPException(422, "Question too long (max 2000 chars)")
    result = mentor.ask(question, context=payload.get("context"))
    if result is None:
        raise HTTPException(503, "AI mentor is not configured. Set a provider API key in the server environment "
                                 "(see app/mentor.py). GovtExamMitra does not fake AI responses.")
    return result

# ---------- government information centre ----------

from app import govsource as gv
import threading as _threading
from urllib.parse import urlparse as _urlparse

_INGEST_LOCK = _threading.Lock()

OFFICIAL_HOST_SUFFIXES = (".gov.in", ".nic.in", "gov.in", "nic.in", ".edu.in", ".ac.in")

class SourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    organisation: str = Field(min_length=2, max_length=200)
    base_url: str = Field(min_length=8, max_length=500)
    kind: str = Field(default="HTML", pattern="^(HTML|RSS)$")
    listing_path: str | None = Field(default=None, max_length=300)
    frequency_hours: int = Field(default=12, ge=1, le=168)
    max_pages: int = Field(default=8, ge=1, le=30)

class SourcePatch(BaseModel):
    enabled: bool | None = None
    frequency_hours: int | None = Field(default=None, ge=1, le=168)
    max_pages: int | None = Field(default=None, ge=1, le=30)
    listing_path: str | None = Field(default=None, max_length=300)

class IngestIn(BaseModel):
    source_id: str | None = None

class DiscoverIn(BaseModel):
    seed_url: str = Field(min_length=8, max_length=500)

class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)

def _require_admin(user: str | None, conn) -> str:
    if not user:
        raise HTTPException(401, "Authentication required")
    row = conn.execute("SELECT role FROM users WHERE id=?", (user,)).fetchone()
    if not row or row["role"] != "admin":
        raise HTTPException(403, "Administrator access required")
    return user

def _audit(conn, admin_id, action, target, detail=None):
    conn.execute("INSERT INTO gov_audit_log (id, admin_id, action, target, detail, created_at) VALUES (?,?,?,?,?,?)",
                 (uuid.uuid4().hex, admin_id, action, target, detail, gv._now()))

@api.get("/gov/sources", tags=["govinfo"])
def gov_sources():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT id, name, organisation, base_url, kind, enabled, frequency_hours, max_pages, "
        "last_crawl_at, last_status FROM gov_sources ORDER BY organisation, name").fetchall()]
    conn.close()
    return {"sources": rows}

@api.get("/gov/documents", tags=["govinfo"])
def gov_documents(q: str | None = None, exam: str | None = None, doc_type: str | None = None,
                  organisation: str | None = None, days: int | None = Query(None, ge=1, le=365),
                  classification: str | None = None,
                  limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):
    conn = get_conn()
    sql = ("SELECT d.id, d.url, d.title, d.organisation, d.doc_type, d.published_at, d.collected_at, "
           "d.updated_at, d.version, d.exam_ids_json, d.classification_status, d.verification_status, "
           "d.last_checked_at, s.name AS source_name FROM gov_documents d "
           "JOIN gov_sources s ON s.id=d.source_id WHERE d.classification_status != 'REJECTED'")
    args: list = []
    if classification:
        sql += " AND d.classification_status=?"
        args.append(classification)
    if q:
        sql += " AND (d.title LIKE ? OR d.extracted_text LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if exam:
        sql += " AND d.exam_ids_json LIKE ?"
        args.append(f'%"{exam}"%')
    if doc_type:
        sql += " AND d.doc_type=?"
        args.append(doc_type)
    if organisation:
        sql += " AND d.organisation LIKE ?"
        args.append(f"%{organisation}%")
    if days:
        sql += " AND d.collected_at >= datetime('now', ?)"
        args.append(f"-{days} days")
    total = conn.execute("SELECT COUNT(*) c FROM (" + sql + ")", args).fetchone()["c"]
    rows = [dict(r) for r in conn.execute(sql + " ORDER BY COALESCE(d.published_at, d.collected_at) DESC LIMIT ? OFFSET ?",
                                          args + [limit, offset]).fetchall()]
    conn.close()
    for r in rows:
        r["exam_ids"] = json.loads(r.pop("exam_ids_json") or "[]")
    return {"total": total, "documents": rows}

@api.get("/gov/documents/{doc_id}", tags=["govinfo"])
def gov_document(doc_id: str):
    conn = get_conn()
    row = conn.execute("SELECT d.*, s.name AS source_name, s.base_url AS source_base FROM "
                       "gov_documents d JOIN gov_sources s ON s.id=d.source_id WHERE d.id=?",
                       (doc_id,)).fetchone()
    conn.close()
    if not row or row["classification_status"] == "REJECTED":
        raise HTTPException(404, "Document not found")
    out = dict(row)
    out["exam_ids"] = json.loads(out.pop("exam_ids_json") or "[]")
    return out

@api.get("/gov/stats", tags=["govinfo"])
def gov_stats():
    conn = get_conn()
    out = {
        "sources_total": conn.execute("SELECT COUNT(*) c FROM gov_sources").fetchone()["c"],
        "sources_enabled": conn.execute("SELECT COUNT(*) c FROM gov_sources WHERE enabled=1").fetchone()["c"],
        "documents": conn.execute("SELECT COUNT(*) c FROM gov_documents WHERE classification_status != 'REJECTED'").fetchone()["c"],
        "pending_review": conn.execute("SELECT COUNT(*) c FROM gov_documents WHERE classification_status='PENDING_REVIEW'").fetchone()["c"],
        "last_crawl": conn.execute("SELECT MAX(finished_at) m FROM gov_crawl_log WHERE status='OK'").fetchone()["m"],
    }
    conn.close()
    return out

@api.post("/gov/sources", tags=["govinfo"])
def gov_add_source(payload: SourceIn, user: str | None = Depends(current_user)):
    conn = get_conn()
    try:
        admin = _require_admin(user, conn)
        p = _urlparse(payload.base_url)
        local_ok = os.environ.get("GOV_INGEST_ALLOW_LOCAL") == "1" and p.netloc.startswith("localhost")
        if p.scheme not in ("http", "https") or not (p.netloc.endswith(OFFICIAL_HOST_SUFFIXES) or local_ok):
            raise HTTPException(422, "base_url must be an official government/education domain "
                                     "(.gov.in, .nic.in, .edu.in, .ac.in).")
        sid = uuid.uuid4().hex
        conn.execute("""INSERT INTO gov_sources (id, name, organisation, base_url, kind, listing_path,
                        enabled, frequency_hours, max_pages, added_by, created_at)
                        VALUES (?,?,?,?,?,?,1,?,?,?,?)""",
                     (sid, payload.name, payload.organisation, payload.base_url.rstrip("/"),
                      payload.kind, payload.listing_path, payload.frequency_hours, payload.max_pages,
                      admin, gv._now()))
        _audit(conn, admin, "ADD_SOURCE", sid, payload.base_url)
        conn.commit()
        return {"id": sid, "status": "registered"}
    finally:
        conn.close()

@api.patch("/gov/sources/{source_id}", tags=["govinfo"])
def gov_patch_source(source_id: str, payload: SourcePatch, user: str | None = Depends(current_user)):
    conn = get_conn()
    try:
        admin = _require_admin(user, conn)
        if not conn.execute("SELECT 1 FROM gov_sources WHERE id=?", (source_id,)).fetchone():
            raise HTTPException(404, "Source not found")
        for field in ("enabled", "frequency_hours", "max_pages", "listing_path"):
            v = getattr(payload, field)
            if v is not None:
                conn.execute(f"UPDATE gov_sources SET {field}=? WHERE id=?", (int(v) if isinstance(v, bool) else v, source_id))
        _audit(conn, admin, "UPDATE_SOURCE", source_id, payload.model_dump_json(exclude_none=True))
        conn.commit()
        return {"id": source_id, "status": "updated"}
    finally:
        conn.close()

@api.delete("/gov/sources/{source_id}", tags=["govinfo"])
def gov_delete_source(source_id: str, user: str | None = Depends(current_user)):
    conn = get_conn()
    try:
        admin = _require_admin(user, conn)
        if not conn.execute("SELECT 1 FROM gov_sources WHERE id=?", (source_id,)).fetchone():
            raise HTTPException(404, "Source not found")
        conn.execute("DELETE FROM gov_documents WHERE source_id=?", (source_id,))
        conn.execute("DELETE FROM gov_crawl_log WHERE source_id=?", (source_id,))
        conn.execute("DELETE FROM gov_sources WHERE id=?", (source_id,))
        _audit(conn, admin, "DELETE_SOURCE", source_id)
        conn.commit()
        return {"id": source_id, "status": "deleted"}
    finally:
        conn.close()

@api.post("/gov/ingest/run", tags=["govinfo"])
def gov_run_ingest(payload: IngestIn, user: str | None = Depends(current_user)):
    conn = get_conn()
    try:
        _require_admin(user, conn)
    finally:
        conn.close()
    if payload.source_id:
        conn = get_conn()
        ok = conn.execute("SELECT 1 FROM gov_sources WHERE id=?", (payload.source_id,)).fetchone()
        conn.close()
        if not ok:
            raise HTTPException(404, "Source not found")
    if not _INGEST_LOCK.acquire(blocking=False):
        raise HTTPException(409, "An ingestion run is already in progress")
    try:
        t = _threading.Thread(target=gv.run_due, kwargs={"source_id": payload.source_id, "max_sources": 10},
                              daemon=True, name="govsource-manual")
        t.start()
    finally:
        _INGEST_LOCK.release()
    return {"started": True, "note": "Ingestion runs in the background; check /gov/jobs for progress."}

@api.get("/gov/jobs", tags=["govinfo"])
def gov_jobs(limit: int = Query(30, ge=1, le=100), user: str | None = Depends(current_user)):
    conn = get_conn()
    _require_admin(user, conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT c.*, s.name AS source_name FROM gov_crawl_log c LEFT JOIN gov_sources s ON s.id=c.source_id "
        "ORDER BY c.started_at DESC LIMIT ?", (limit,)).fetchall()]
    stats = {"runs": conn.execute("SELECT COUNT(*) c FROM gov_crawl_log").fetchone()["c"],
             "failed": conn.execute("SELECT COUNT(*) c FROM gov_crawl_log WHERE status='ERROR'").fetchone()["c"]}
    conn.close()
    return {"jobs": rows, "stats": stats}

@api.post("/gov/discover", tags=["govinfo"])
def gov_discover(payload: DiscoverIn, user: str | None = Depends(current_user)):
    conn = get_conn()
    try:
        _require_admin(user, conn)
    finally:
        conn.close()
    p = _urlparse(payload.seed_url)
    if p.scheme not in ("http", "https") or not p.netloc.endswith(OFFICIAL_HOST_SUFFIXES):
        raise HTTPException(422, "seed_url must be an official government directory "
                                 "(.gov.in, .nic.in, .edu.in, .ac.in).")
    try:
        return gv.discover(payload.seed_url)
    except Exception as e:
        raise HTTPException(502, f"Discovery fetch failed: {e}")

@api.post("/gov/documents/{doc_id}/review", tags=["govinfo"])
def gov_review_document(doc_id: str, payload: ReviewIn, user: str | None = Depends(current_user)):
    conn = get_conn()
    try:
        admin = _require_admin(user, conn)
        if not conn.execute("SELECT 1 FROM gov_documents WHERE id=?", (doc_id,)).fetchone():
            raise HTTPException(404, "Document not found")
        status = "ADMIN_APPROVED" if payload.decision == "approve" else "REJECTED"
        conn.execute("UPDATE gov_documents SET classification_status=?, review_note=? WHERE id=?",
                     (status, payload.note, doc_id))
        _audit(conn, admin, f"DOCUMENT_{payload.decision.upper()}", doc_id, payload.note)
        conn.commit()
        return {"id": doc_id, "classification_status": status}
    finally:
        conn.close()

@api.get("/gov/audit", tags=["govinfo"])
def gov_audit(limit: int = Query(100, ge=1, le=200), user: str | None = Depends(current_user)):
    conn = get_conn()
    _require_admin(user, conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT a.*, u.email AS admin_email FROM gov_audit_log a LEFT JOIN users u ON u.id=a.admin_id "
        "ORDER BY a.created_at DESC LIMIT ?", (limit,)).fetchall()]
    conn.close()
    return {"audit": rows}

# ---------- guest-mode public helpers (no persistence; device mode stores locally) ----------

@api.post("/questions/{question_id}/check", tags=["practice"])
def check_question(question_id: int, chosen: int = Body(ge=0, le=5, embed=True)):
    """Public answer check for guest/device mode: same engine as the authenticated
    answer endpoint, minus the attempt record. The device store keeps the attempt locally."""
    conn = get_conn()
    q = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    if not q:
        conn.close()
        raise HTTPException(404, "Question not found")
    correct = int(chosen == q["answer_index"])
    exam = ov.get_exam(conn, q["exam_id"])
    marking = (exam or {}).get("marking_json")
    if marking and isinstance(marking, str):
        try:
            marking = json.loads(marking)
        except ValueError:
            marking = None
    score = 0.0
    if correct:
        score = 1.0
    elif marking:
        neg = (marking.get("prelims_gs1") or marking.get("paper1") or {}).get("negative_fraction", "1/3")
        score = -1 / 3 if neg == "1/3" else 0.0
    conn.close()
    return {"correct": bool(correct), "answer_index": q["answer_index"],
            "explanation": q["explanation"], "score": score, "question_type": q["q_type"]}

@api.post("/mocks/{exam_id}/submit-guest", tags=["mocks"])
def mock_submit_guest(exam_id: str, payload: dict = Body(...)):
    """Score a guest mock without persisting: identical engine, device store keeps the card."""
    conn = get_conn()
    try:
        answers = (payload or {}).get("answers")
        if not isinstance(answers, dict):
            raise HTTPException(422, "Field 'answers' must be an object {question_id: chosen_index or null}")
        paper = (payload or {}).get("paper") or "Mock"
        qids = (payload or {}).get("question_ids")
        if qids is not None and not isinstance(qids, list):
            raise HTTPException(422, "Field 'question_ids' must be a list of question ids")
        return mockmod.score(conn, "guest-device", exam_id, paper, answers, persist=False,
                             question_ids=qids)
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()

@api.get("/plan/{exam_a}/{exam_b}/preview", tags=["planner"])
def plan_preview(exam_a: str, exam_b: str):
    """Public combined-plan preview for guest exploration: the real planner engine,
    computed against no stored progress (everything NOT_STARTED), nothing persisted."""
    conn = get_conn()
    try:
        items = plan.build_plan(conn, "guest-device", exam_a, exam_b)
        return {"exam_a": exam_a, "exam_b": exam_b, "items": items,
                "note": "Preview mode: computed with no personal progress. Sign in to track progress and generate tasks."}
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()

app.include_router(api)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(BASE, "static", "index.html"))

# ---------- mock tests ----------

@api.get("/mocks/{exam_id}", tags=["mocks"])
def mock_paper(exam_id: str):
    conn = get_conn()
    try:
        paper = mockmod.assemble(conn, exam_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()
    if not paper:
        raise HTTPException(404, "No objective sections with questions exist for this exam yet.")
    paper["note"] = ("Assembled live from the GovtExamMitra question bank. All seeded questions are "
                     "DEMONSTRATION-labelled; sections are smaller than official papers until the bank grows.")
    return paper

@api.post("/mocks/{exam_id}/submit", tags=["mocks"])
def mock_submit(exam_id: str, payload: dict = Body(...), user: str = Depends(require_user)):
    conn = get_conn()
    try:
        answers = (payload or {}).get("answers")
        if not isinstance(answers, dict):
            raise HTTPException(422, "Field 'answers' must be an object {question_id: chosen_index or null}")
        paper = (payload or {}).get("paper") or "Mock"
        qids = (payload or {}).get("question_ids")
        if qids is not None and not isinstance(qids, list):
            raise HTTPException(422, "Field 'question_ids' must be a list of question ids")
        return mockmod.score(conn, user, exam_id, paper, answers, question_ids=qids)
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()

@api.get("/mocks/{exam_id}/history", tags=["mocks"])
def mock_history(exam_id: str, user: str = Depends(require_user)):
    conn = get_conn()
    rows = mockmod.history(conn, user, exam_id)
    conn.close()
    return {"exam_id": exam_id, "attempts": rows}

# ---------- revision centre ----------

@api.get("/revision/{exam_id}/queue", tags=["revision"])
def revision_queue(exam_id: str, user: str = Depends(require_user)):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    out = revmod.queue(conn, user, exam_id)
    conn.close()
    return out

@api.get("/revision/{exam_id}/session", tags=["revision"])
def revision_session(exam_id: str, limit: int = Query(10, ge=1, le=25), user: str = Depends(require_user)):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    out = revmod.session(conn, user, exam_id, limit)
    conn.close()
    return out

# ---------- flashcards ----------

@api.get("/flashcards/{exam_id}", tags=["revision"])
def flashcards(exam_id: str, limit: int = Query(30, ge=1, le=100), user: str | None = Depends(current_user)):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    due_ids = revmod.due_topic_ids(conn, user, exam_id) if user else None
    micros = [dict(r) for r in conn.execute("""
        SELECT m.id, m.name, m.depth_note, s.name subject_name, s.paper, s.stage, s.official_text
        FROM micro_topics m JOIN subjects s ON s.id=m.subject_id
        WHERE m.exam_id=? ORDER BY s.ordering, m.name""", (exam_id,)).fetchall()]
    conn.close()
    cards = []
    for m in micros:
        card = {
            "micro_topic_id": m["id"], "front": m["name"],
            "back": {"subject": m["subject_name"], "paper": m["paper"], "stage": m["stage"],
                     "depth_note": m["depth_note"],
                     "syllabus_context": m["official_text"]},
            "source": "Generated from the verified syllabus decomposition (subjects.official_text "
                      "is official UPSC notification wording; micro-topics are AI-derived).",
        }
        if due_ids is not None:
            card["due"] = m["id"] in due_ids
        cards.append(card)
    if due_ids:
        cards.sort(key=lambda c: not c["due"])
    return {"exam_id": exam_id, "cards": cards[:limit], "scheduled": bool(user)}

# ---------- mind maps ----------

@api.get("/mindmap/{exam_id}", tags=["revision"])
def mindmap(exam_id: str, user: str | None = Depends(current_user)):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    subjects = [dict(r) for r in conn.execute(
        "SELECT id, name, group_key, stage, paper FROM subjects WHERE exam_id=? ORDER BY ordering",
        (exam_id,)).fetchall()]
    pmap = {}
    if user:
        for p in prog.get_progress(conn, user, exam_id):
            pmap[p["micro_topic_id"]] = p
    micros = [dict(r) for r in conn.execute(
        "SELECT id, name, subject_id FROM micro_topics WHERE exam_id=? ORDER BY name",
        (exam_id,)).fetchall()]
    qn = {r["micro_topic_id"]: r["c"] for r in conn.execute(
        "SELECT micro_topic_id, COUNT(*) c FROM questions WHERE exam_id=? AND micro_topic_id IS NOT NULL GROUP BY micro_topic_id",
        (exam_id,)).fetchall()}
    conn.close()
    tree = []
    for s in subjects:
        children = []
        for m in micros:
            if m["subject_id"] != s["id"]:
                continue
            p = pmap.get(m["id"])
            children.append({"id": m["id"], "name": m["name"],
                             "status": p["status"] if p else "NOT_STARTED",
                             "mastery": p["mastery"] if p else 0,
                             "questions": qn.get(m["id"], 0)})
        done = sum(1 for c in children if c["status"] == "COMPLETED")
        tree.append({"id": s["id"], "name": s["name"], "group_key": s["group_key"],
                     "stage": s["stage"], "paper": s["paper"],
                     "completion_pct": round(100 * done / len(children), 1) if children else 0.0,
                     "children": children})
    return {"exam_id": exam_id, "subjects": tree,
            "note": "Rendered from the real database hierarchy. Node colour = your progress; "
                    "structure is the verified syllabus decomposition."}

# ---------- recommendations ----------

@api.get("/recommendations/{exam_id}", tags=["recommendations"])
def recommendations(exam_id: str, pair: str | None = Query(None, description="paired exam for overlap rules"),
                   user: str = Depends(require_user)):
    conn = get_conn()
    try:
        return recmod.recommend(conn, user, exam_id, pair)
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()

# ---------- mains answer writing ----------

@api.get("/mains/{exam_id}/prompts", tags=["mains"])
def mains_prompts(exam_id: str):
    conn = get_conn()
    try:
        return mainmod.prompts(conn, exam_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()

@api.post("/mains/attempts", tags=["mains"])
def mains_submit(payload: dict = Body(...), user: str = Depends(require_user)):
    conn = get_conn()
    try:
        exam_id = (payload or {}).get("exam_id")
        prompt_id = (payload or {}).get("prompt_id")
        if not exam_id or not prompt_id or not isinstance((payload or {}).get("body"), str):
            raise HTTPException(422, "Fields exam_id, prompt_id and body are required")
        return mainmod.submit(conn, user, payload)
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()

@api.get("/mains/attempts", tags=["mains"])
def mains_history(exam_id: str | None = None, user: str = Depends(require_user)):
    conn = get_conn()
    rows = mainmod.history(conn, user, exam_id)
    conn.close()
    return {"attempts": rows}

# ---------- AI answer evaluation (advisory; needs configured provider) ----------

EVAL_SYSTEM = ("You are the GovtExamMitra answer evaluator. Score the descriptive answer against the "
               "given rubric dimensions. Return: per-dimension scores with one-line justification, "
               "missing key points, and one improvement suggestion. You are advisory, not official.")

@api.post("/eval/answer", tags=["mains"])
def eval_answer(payload: dict = Body(...), user: str = Depends(require_user)):
    question = (payload or {}).get("question", "").strip()
    answer = (payload or {}).get("answer", "").strip()
    if not question or not answer:
        raise HTTPException(422, "Fields 'question' and 'answer' are required")
    if len(answer) > 8000:
        raise HTTPException(422, "Answer too long (max 8000 chars)")
    rubric_keys = [r["key"] for r in mainmod.RUBRIC]
    rubric_text = "; ".join(f"{r['label']} (0-{r['max']})" for r in mainmod.RUBRIC)
    result = mentor.ask(
        f"Question: {question}\n\nAnswer: {answer}\n\nRubric dimensions: {rubric_text}. "
        "Return per-dimension scores with justification, missing key points and one improvement.",
        context={"task": "answer_evaluation", "rubric": rubric_keys})
    if result is None:
        raise HTTPException(503, "AI answer evaluation is not configured. Set MENTOR_PROVIDER and "
                                 "MENTOR_API_KEY in the server environment. GovtExamMitra does not "
                                 "pretend to score answers without a real evaluation engine.")
    result["rubric"] = mainmod.RUBRIC
    return result

# ---------- PYQs ----------

@api.get("/pyqs/{exam_id}", tags=["pyqs"])
def pyqs(exam_id: str, topic: str | None = None):
    conn = get_conn()
    if not ov.get_exam(conn, exam_id):
        conn.close()
        raise HTTPException(404, f"Exam '{exam_id}' not found")
    sql = ("SELECT q.id, q.q_type, q.year, q.paper, q.question, q.options_json, q.difficulty, "
           "m.name topic_name FROM questions q "
           "LEFT JOIN micro_topics m ON m.id=q.micro_topic_id WHERE q.exam_id=? AND q.q_type='OFFICIAL_PYQ'")
    args: list = [exam_id]
    if topic:
        sql += " AND m.name LIKE ?"
        args.append(f"%{topic}%")
    rows = []
    papers = []
    notes_extra = ""
    try:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    except Exception as exc:  # never fail the whole page over one query
        import traceback
        print("[pyqs] questions query failed:", repr(exc), flush=True)
        traceback.print_exc()
        notes_extra = " Question listing is temporarily unavailable; past papers below are unaffected."
    try:
        papers = [dict(r) for r in conn.execute("""
            SELECT d.id, d.title, d.url, d.organisation, d.published_at, d.doc_type, s.name source_name
            FROM gov_documents d JOIN gov_sources s ON s.id=d.source_id
            WHERE d.classification_status != 'REJECTED' AND d.exam_ids_json LIKE ?
            AND (d.doc_type IN ('QUESTION_PAPER','PYQ') OR d.title LIKE '%question paper%')
            ORDER BY d.published_at DESC LIMIT 50""", (f'%"{exam_id}"%',)).fetchall()]
    except Exception as exc:
        import traceback
        print("[pyqs] papers query failed:", repr(exc), flush=True)
        traceback.print_exc()
        notes_extra += " Official paper listing is temporarily unavailable."
    conn.close()
    for r in rows:
        r["options"] = json.loads(r.pop("options_json") or "[]")
    return {"exam_id": exam_id, "questions": rows, "papers": papers,
            "note": ("Only questions traceable to an official paper appear as OFFICIAL_PYQ. "
                     "No official PYQs have been ingested yet — the pipeline accepts them via the "
                     "government-source engine and the admin review queue. "
                     "All currently attemptable questions are DEMONSTRATION-labelled.") + notes_extra}

# ---------- current affairs ----------

@api.get("/current-affairs", tags=["current-affairs"])
def current_affairs(exam: str | None = None, limit: int = Query(30, ge=1, le=100)):
    conn = get_conn()
    sql = ("SELECT d.id, d.url, d.title, d.organisation, d.doc_type, d.published_at, d.collected_at, "
           "d.exam_ids_json, s.name source_name, s.base_url source_base "
           "FROM gov_documents d JOIN gov_sources s ON s.id=d.source_id "
           "WHERE d.classification_status != 'REJECTED' "
           "AND d.doc_type IN ('NEWS','PIB_RELEASE','PRESS_RELEASE','OTHER')")
    args: list = []
    if exam:
        sql += " AND (d.exam_ids_json LIKE ? OR d.exam_ids_json='[]')"
        args.append(f'%"{exam}"%')
    rows = [dict(r) for r in conn.execute(
        sql + " ORDER BY COALESCE(d.published_at, d.collected_at) DESC LIMIT ?",
        args + [limit]).fetchall()]
    conn.close()
    for r in rows:
        r["exam_ids"] = json.loads(r.pop("exam_ids_json") or "[]")
    return {"items": rows,
            "note": "Every item links to its originating official release. Relevance mapping to "
                    "exam syllabus improves as documents are classified."}

# ---------- notes ----------

@api.get("/notes", tags=["notes"])
def notes_all(user: str = Depends(require_user)):
    conn = get_conn()
    rows = [dict(r) for r in conn.execute("""
        SELECT n.micro_topic_id, n.body, n.updated_at, m.name topic_name, m.exam_id
        FROM notes n JOIN micro_topics m ON m.id=n.micro_topic_id
        WHERE n.user_id=? ORDER BY n.updated_at DESC""", (user,)).fetchall()]
    conn.close()
    return {"notes": rows}

@api.get("/notes/{micro_topic_id}", tags=["notes"])
def note_get(micro_topic_id: int, user: str = Depends(require_user)):
    conn = get_conn()
    row = conn.execute("SELECT body, updated_at FROM notes WHERE user_id=? AND micro_topic_id=?",
                       (user, micro_topic_id)).fetchone()
    conn.close()
    return {"micro_topic_id": micro_topic_id, "body": row["body"] if row else "",
            "updated_at": row["updated_at"] if row else None}

@api.put("/notes/{micro_topic_id}", tags=["notes"])
def note_put(micro_topic_id: int, payload: dict = Body(...), user: str = Depends(require_user)):
    body = (payload or {}).get("body")
    if not isinstance(body, str) or len(body) > 20000:
        raise HTTPException(422, "Field 'body' (string, max 20000 chars) is required")
    conn = get_conn()
    try:
        m = conn.execute("SELECT exam_id FROM micro_topics WHERE id=?", (micro_topic_id,)).fetchone()
        if not m:
            raise HTTPException(404, "Unknown micro-topic")
        from datetime import datetime, timezone as _tz
        now = datetime.now(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""INSERT INTO notes (user_id, micro_topic_id, body, updated_at)
                        VALUES (?,?,?,?)
                        ON CONFLICT (user_id, micro_topic_id)
                        DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at""",
                     (user, micro_topic_id, body, now))
        conn.commit()
        return {"micro_topic_id": micro_topic_id, "saved": True, "updated_at": now}
    finally:
        conn.close()

@api.delete("/notes/{micro_topic_id}", tags=["notes"])
def note_delete(micro_topic_id: int, user: str = Depends(require_user)):
    conn = get_conn()
    cur = conn.execute("DELETE FROM notes WHERE user_id=? AND micro_topic_id=?",
                       (user, micro_topic_id))
    conn.commit()
    conn.close()
    return {"deleted": cur.rowcount}

# ---------- bookmarks ----------

VALID_BOOKMARK_KINDS = ("TOPIC", "QUESTION", "TASK")

@api.get("/bookmarks", tags=["bookmarks"])
def bookmarks_all(user: str = Depends(require_user)):
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT kind, ref_id, created_at FROM bookmarks WHERE user_id=? ORDER BY created_at DESC",
        (user,)).fetchall()]
    out = []
    for r in rows:
        label = detail = None
        if r["kind"] == "TOPIC":
            t = conn.execute("SELECT m.name, m.exam_id FROM micro_topics m WHERE m.id=?",
                             (r["ref_id"],)).fetchone()
            if t:
                label, detail = t["name"], t["exam_id"]
        elif r["kind"] == "QUESTION":
            try:
                q = conn.execute("SELECT question FROM questions WHERE id=?",
                                 (int(r["ref_id"]),)).fetchone()
            except ValueError:
                q = None
            if q:
                label, detail = q["question"][:120], None
        out.append({**r, "label": label, "detail": detail})
    conn.close()
    return {"bookmarks": out}

@api.post("/bookmarks", tags=["bookmarks"])
def bookmark_add(payload: dict = Body(...), user: str = Depends(require_user)):
    kind = (payload or {}).get("kind")
    ref_id = (payload or {}).get("ref_id")
    if kind not in VALID_BOOKMARK_KINDS:
        raise HTTPException(422, f"kind must be one of {VALID_BOOKMARK_KINDS}")
    if not ref_id:
        raise HTTPException(422, "ref_id is required")
    conn = get_conn()
    try:
        if kind == "TOPIC" and not conn.execute(
                "SELECT 1 FROM micro_topics WHERE id=?", (int(ref_id),)).fetchone():
            raise HTTPException(422, "Unknown micro-topic")
        if kind == "QUESTION" and not conn.execute(
                "SELECT 1 FROM questions WHERE id=?", (int(ref_id),)).fetchone():
            raise HTTPException(422, "Unknown question")
        conn.execute("INSERT INTO bookmarks (user_id, kind, ref_id) VALUES (?,?,?) "
                     "ON CONFLICT (user_id, kind, ref_id) DO NOTHING",
                     (user, kind, str(ref_id)))
        conn.commit()
        return {"bookmarked": True, "kind": kind, "ref_id": str(ref_id)}
    except ValueError:
        raise HTTPException(422, "ref_id must be an integer for TOPIC/QUESTION bookmarks")
    finally:
        conn.close()

@api.delete("/bookmarks/{kind}/{ref_id}", tags=["bookmarks"])
def bookmark_del(kind: str, ref_id: str, user: str = Depends(require_user)):
    conn = get_conn()
    cur = conn.execute("DELETE FROM bookmarks WHERE user_id=? AND kind=? AND ref_id=?",
                       (user, kind, ref_id))
    conn.commit()
    conn.close()
    return {"deleted": bool(cur.rowcount)}

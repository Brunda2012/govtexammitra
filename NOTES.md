# GovtExamMitra — API, Deployment & Production Notes

## Stack (current, deployed)
Python 3.12, FastAPI, SQLite (stdlib driver), dependency-free vanilla-JS SPA (no Node build).
Planned (hybrid path): Next.js + TypeScript + Tailwind frontend in a separate folder, consuming
the same /api/v1 API over CORS (`CORS_ORIGINS` env var). Do NOT migrate until the Next.js
build, API integration and tests are verified with a working Node install.

## Run locally
    python -m uvicorn server:app --host 127.0.0.1 --port 8000
Database auto-creates and seeds on startup (`govtexammitra.db` next to the project).

## Run via Docker (what the host will do)
    docker build -t govtexammitra . && docker run -p 8000:8000 -e SECRET_KEY=... -e ADMIN_EMAIL=... -e ADMIN_PASSWORD=... govtexammitra

## Production database (DONE, verified)
`DATABASE_URL` selects the engine: unset = SQLite file (local dev), set = PostgreSQL
(psycopg2). Verified against a real PostgreSQL 16.4 server:
- Full 10-test API suite passes on Postgres (register, login, progress, planner,
  analytics, practice, 401s, two-user isolation).
- User data survived a full Postgres server stop/start (login + progress + tasks intact).
- Seed is idempotent on Postgres: repeated reseeds produce exactly 8 exams / 62
  micro-topics / 23 mappings (UNIQUE constraints + ON CONFLICT).
- Versioned migrations (app/migrations.py, schema_migrations table) apply once each
  on fresh and existing databases; migration 2 dedupes overlap_mappings and adds a
  unique pair index. Portable SQL: dialect bugs found and fixed (named params,
  GROUP BY strictness, ROUND type, datetime('now'), last_insert_rowid).

## Hosting decision — Cloudflare audit (checked against current official limits)
Cloudflare Python Workers were audited and REJECTED for this backend today, honestly:
- Free plan: 10 ms CPU per request — our PBKDF2-SHA256 password hashing alone
  (200k iterations) needs far more; login/registration would fail or we'd have to
  weaken security (unacceptable).
- Python Workers run CPython via Pyodide: native C extensions like psycopg2 cannot
  load; Postgres access would require pure-Python/HTTP drivers (experimental) or a
  full JS rewrite of the backend — violating the preserve-working-code constraint.
- 128 MB memory, package/bundle size limits; background jobs unsupported.
- A real prototype cannot be built here anyway: wrangler CLI requires Node.js.
Verdict: Cloudflare stays an option for the future static frontend/edge (Pages) and
as a CDN in front of the API — NOT for the FastAPI backend.
Selected architecture: Render (Docker, free tier) for FastAPI + Neon (free) Postgres
+ GitHub auto-deploy. Re-evaluate Cloudflare for the Next.js frontend in Milestone 4.

# Zero-cost hosting comparison (verified against vendor docs, see chat history)
# Selected: Render free (FastAPI, no card, no auto-billing possible) + Neon free (Postgres,
# no card, manual-only upgrades). Contingency: Hugging Face Spaces (no card, ephemeral disk).
# Rejected: Cloud Run/Oracle (card required), Cloudflare Workers (10ms CPU, no psycopg2),
# D1 (Workers-only), Supabase (pauses after 1 week idle).

## Public deployment (Render + Neon) — exact steps for the account owner
1. Create a free GitHub account (if none) and push this project:
      cd govtexammitra
      git init (if needed) && git add . && git commit -m "GovtExamMitra"
      git remote add origin https://github.com/<you>/govtexammitra.git && git push -u origin main
2. Create a free Postgres at neon.com (no credit card): New Project → copy the
   connection string (postgresql://...neon.tech/db?sslmode=require). Free tier:
   0.5 GB storage, autosuspends after ~5 min idle (cold start ~1 s, data persists).
3. On render.com (free signup): New → Blueprint → select the repo (render.yaml
   included). Fill in: DATABASE_URL (from Neon), ADMIN_EMAIL, ADMIN_PASSWORD
   (choose strong), CORS_ORIGINS can stay empty while the SPA is same-origin.
4. Deploy. First boot runs migrations, seeds exam data, creates the admin account.
5. Verify: open https://<service>.onrender.com, register a user, log in, complete a
   topic, restart/redeploy the service from the Render dashboard and confirm the
   data is still there (it will be — Postgres is outside the container).
Free-tier caveats: the web service sleeps after ~15 min idle (first visit ~30-60 s);
data is durable because it lives in Neon, not on the Render container.

## API contract (versioned, /api/v1)
Interactive OpenAPI docs: `/docs`.

- GET  /exams · GET /exams/{id} — catalogue with verification status per exam
- GET  /overlap/{exam_a}/{exam_b} — flagship comparison. Query: classification, group, q
- GET  /syllabus/{exam_id} — subjects (official wording) + micro-topics (AI-derived)
- GET  /progress · POST /progress — explicit completion; cross-exam propagation rules apply
- GET  /progress/{exam_id}/coverage — per-subject completion, weak topics
- GET  /plan/{a}/{b} · POST /plan/{a}/{b}/generate — combined plan, task generation
- GET  /tasks · POST /tasks/{id}/complete
- GET  /questions?exam_id= · POST /questions/{id}/answer — negative marking applied
- GET  /analytics?exam_id=
- GET  /dashboard
- POST /mentor — 503 until MENTOR_* env vars are set; never fakes responses

### Authentication (implemented, multi-user)
- POST /auth/register → 422 on bad email / short password / duplicate.
- POST /auth/login → 401 on wrong credentials.
- All requests present `Authorization: Bearer <token>`; tokens are HS256 JWTs, 30-day expiry.
- Passwords: PBKDF2-HMAC-SHA256, 200k iterations, per-user salt.
- Roles: `user` / `admin`; GET /admin/users requires admin.
- Personal endpoints (progress, tasks, plan, answer, analytics, dashboard, mentor) return 401
  when unauthenticated. Two-user isolation is covered by an automated test.
- A fixed "local" principal exists only with GOVTEXAMMITRA_LOCAL=1 (dev convenience).

## Security
- Pydantic validation on writes; 404/422/429 handled explicitly.
- In-memory rate limiting: 120 req/min GET, 40 req/min writes (replace with a shared store
  e.g. Redis for multi-worker production).
- Secrets only via environment variables (MENTOR_API_KEY etc.). Nothing committed.
- CORS is not enabled (same-origin serving); enable explicitly with an allow-list when the
  frontend is hosted separately.

## Production requirements (external to this repo)
1. Hosting account able to run one Python process (Render/Railway/Fly free tier works).
2. PostgreSQL + migration tool (Alembic) when multi-user; SQLite is file-based until then.
3. Backups: SQLite file snapshot or managed Postgres backups.
4. Domain + HTTPS at the platform level.
5. MENTOR_* env vars for the AI mentor (optional; app is fully functional without).
6. For React Native later: install Node.js on the dev machine and build via Expo EAS.

## Data honesty rules (enforced in app/seed.py)
- Subject-level wording quoted from official UPSC notifications (source links + last-verified).
- Micro-topics are AI-derived decompositions: PENDING_VERIFICATION with confidence + rationale.
- Exam catalogue stubs carry PENDING_VERIFICATION / NOT_EXTRACTED; no invented dates or
  eligibility rules.
- All seeded questions are DEMONSTRATION type; official PYQ ingestion is a future milestone.

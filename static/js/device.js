// Device mode — guest-first foundations.
// When a visitor is not signed in, personal data lives in localStorage on this
// device and drives the SAME UI. The server never receives it. Every page shows
// the persistent honest banner while device mode is active.

const KEY = "gm.device.v1";

const blank = () => ({
  progress: {},        // micro_topic_id -> {status, mastery, updated_at, exam_id}
  attempts: [],        // {question_id, chosen, correct, score, exam_id, topic_name, created_at}
  tasks: [],           // planner tasks generated locally
  taskSeq: 1,
  notes: {},           // micro_topic_id -> {body, updated_at}
  bookmarks: [],       // {kind, ref_id, label, created_at}
  mains: [],           // {attempt_id, exam_id, prompt_id, body, word_count, self_scores, created_at}
  mainsSeq: 1,
  mocks: [],           // score cards from submit-guest
  checklistDone: [],   // onboarding steps
  checklistDismissed: false,
});

function load() {
  try {
    return { ...blank(), ...JSON.parse(localStorage.getItem(KEY) || "{}") };
  } catch {
    return blank();
  }
}

function save(state) {
  localStorage.setItem(KEY, JSON.stringify(state));
}

function now() {
  return new Date().toISOString().slice(0, 19).replace("T", " ");
}

export const device = {
  active() { return !localStorage.getItem("gm.token"); },
  reset() { localStorage.removeItem(KEY); },

  // ---- progress ----
  async progressList(examId) {
    const s = load();
    let rows = Object.entries(s.progress).map(([mid, p]) => ({
      micro_topic_id: Number(mid), ...p,
    }));
    if (examId) rows = rows.filter((r) => r.exam_id === examId);
    return { user: "device", progress: rows };
  },

  async setProgress(microId, status, mastery, examId) {
    const s = load();
    const applied = [this._applyProgress(s, microId, status, mastery, examId)];
    // Cross-exam propagation, same rules as the server engine (app/progress.py):
    // EXACT_MATCH copies status+mastery; PARTIAL_OVERLAP sets IN_PROGRESS capped at 60.
    try {
      const { api } = await import("./api.js");
      const pairExam = examId === "upsc-cse" ? "capf-ac" : "upsc-cse";
      const data = await api.get(`/overlap/${examId}/${pairExam}`).catch(() => null);
      const allPairs = data && data.groups ? data.groups.flatMap((g) => g.items || []) : [];
      const pair = allPairs.find((p) => p.id_a === microId || p.id_b === microId) || null;
      if (pair) {
        const other = pair.id_a === microId ? pair.id_b : pair.id_a;
        if (pair.classification === "EXACT_MATCH") {
          applied.push(this._applyProgress(s, other, status, mastery, pair.exam_a === examId ? pair.exam_b : pair.exam_a));
        } else if (pair.classification === "PARTIAL_OVERLAP" && status === "COMPLETED") {
          applied.push(this._applyProgress(s, other, "IN_PROGRESS", Math.min(60, mastery),
            pair.exam_a === examId ? pair.exam_b : pair.exam_a));
        }
      }
    } catch { /* propagation is best-effort in device mode */ }
    save(s);
    return { applied, propagation_rule: "Same rules as the server engine: exact → same mastery; partial → IN_PROGRESS capped at 60; related → none." };
  },

  _applyProgress(s, microId, status, mastery, examId) {
    mastery = Math.max(0, Math.min(100, Number(mastery) || 0));
    if (status === "COMPLETED") mastery = Math.max(mastery, 100);
    if (status === "NOT_STARTED") mastery = 0;
    s.progress[microId] = { status, mastery, updated_at: now(), exam_id: examId || s.progress[microId]?.exam_id };
    return { micro_topic_id: microId, exam_id: examId, status, mastery };
  },

  async coverage(examId) {
    const { api } = await import("./api.js");
    const syl = await api.get(`/syllabus/${examId}`);
    const s = load();
    const subjects = syl.subjects.map((sub) => {
      const micros = syl.micro_topics.filter((m) => m.subject_name === sub.name);
      let completed = 0, inProgress = 0;
      for (const m of micros) {
        const p = s.progress[m.id];
        if (p && p.status === "COMPLETED") completed++;
        else if (p && p.status === "IN_PROGRESS") inProgress++;
      }
      return { subject_name: sub.name, subject_id: sub.id, total: micros.length,
               completed, in_progress: inProgress,
               completion: micros.length ? Math.round(1000 * completed / micros.length) / 10 : 0.0 };
    });
    const total = subjects.reduce((a, x) => a + x.total, 0);
    const completed = subjects.reduce((a, x) => a + x.completed, 0);
    return { exam_id: examId, subjects,
      overall: { exam_id: examId, total, completed, in_progress: subjects.reduce((a, x) => a + x.in_progress, 0),
                 completion_pct: total ? Math.round(1000 * completed / total) / 10 : 0.0 } };
  },

  // ---- attempts / analytics ----
  async answer(questionId, chosen, hint) {
    const { api } = await import("./api.js");
    const res = await api.post(`/questions/${questionId}/check`, { chosen });
    const s = load();
    s.attempts.unshift({ question_id: questionId, chosen, correct: res.correct ? 1 : 0,
      score: res.score, exam_id: hint?.examId, topic_name: hint?.topicName, created_at: now() });
    s.attempts = s.attempts.slice(0, 500);
    save(s);
    return res;
  },

  async analytics(examId) {
    const { api } = await import("./api.js");
    const [cov, qs] = await Promise.all([
      this.coverage(examId), api.get(`/questions?exam_id=${examId}`),
    ]);
    const s = load();
    const atts = s.attempts.filter((a) => a.exam_id === examId);
    const correct = atts.filter((a) => a.correct).length;
    // weak topics: >= 2 attempts, accuracy < 60%
    const per = {};
    for (const a of atts) {
      const key = a.topic_name || "General";
      per[key] = per[key] || { attempts: 0, correct: 0 };
      per[key].attempts++; if (a.correct) per[key].correct++;
    }
    const qtext = {};
    for (const q of qs.questions) qtext[q.id] = q.question;
    const weak = Object.entries(per)
      .filter(([, v]) => v.attempts >= 2 && 100 * v.correct / v.attempts < 60)
      .map(([name, v]) => ({ topic_name: name, subject_name: null, attempts: v.attempts,
        accuracy: Math.round(100 * v.correct / v.attempts * 10) / 10 }));
    weak.sort((a, b) => a.accuracy - b.accuracy);
    return { exam_id: examId, syllabus_progress: cov.overall, weak_topics: weak,
      attempts: { total: atts.length, correct, avg_score: atts.length
        ? Math.round(atts.reduce((a, x) => a + x.score, 0) / atts.length * 1000) / 1000 : null },
      recent: atts.slice(0, 10).map((a) => ({ question: qtext[a.question_id] || "", chosen: a.chosen,
        correct: !!a.correct, score: a.score, created_at: a.created_at })) };
  },

  async dashboard() {
    const { api } = await import("./api.js");
    const exams = (await api.get("/exams")).filter((e) => e.supported);
    const out = { exams: [], pending_tasks: [] };
    for (const e of exams) {
      const cov = await this.coverage(e.id);
      out.exams.push({ id: e.id, name: e.name, authority: e.authority, progress: cov.overall });
    }
    out.pending_tasks = load().tasks.filter((t) => t.status === "PENDING").slice(0, 8)
      .map((t) => ({ id: t.id, title: t.title, detail: t.detail, status: t.status }));
    try {
      const r = await api.get("/overlap/upsc-cse/capf-ac");
      out.overlap_summary = r.stats;
    } catch { out.overlap_summary = null; }
    return out;
  },

  // ---- planner ----
  async plan(a, b) {
    const { api } = await import("./api.js");
    const [preview, prog] = await Promise.all([
      api.get(`/plan/${a}/${b}/preview`), this.progressList(),
    ]);
    const pmap = {};
    for (const p of prog.progress) pmap[p.micro_topic_id] = p;
    for (const it of preview.items) {
      const pa = pmap[it.id_a], pb = pmap[it.id_b];
      it.status_a = pa ? pa.status : "NOT_STARTED";
      it.status_b = pb ? pb.status : "NOT_STARTED";
      it.mastery_a = pa ? pa.mastery : 0;
      it.mastery_b = pb ? pb.mastery : 0;
    }
    return { exam_a: a, exam_b: b, items: preview.items };
  },

  async generateTasks(a, b, limit) {
    const p = await this.plan(a, b);
    const s = load();
    const created = [];
    for (const it of p.items.slice(0, limit)) {
      const done = it.status_a === "COMPLETED" && it.status_b === "COMPLETED";
      if (done) continue;
      const title = it.kind === "SHARED" ? `[${it.classification}] ${it.topic_a}` : `[${it.exam_a.toUpperCase()} only] ${it.topic_a || it.topic_b}`;
      const t = { id: s.taskSeq++, title, detail: it.rationale, status: "PENDING",
                  exam_ids: [a, b], created_at: now() };
      s.tasks.unshift(t);
      created.push(t);
    }
    save(s);
    return { created: created.length, tasks: created };
  },

  async tasks() {
    const s = load();
    return { tasks: s.tasks.map((t) => ({ ...t, micro_topic_ids_json: [], exam_ids_json: t.exam_ids })) };
  },

  async completeTask(id) {
    const s = load();
    const t = s.tasks.find((t) => t.id === id);
    if (t) t.status = "DONE";
    save(s);
    return { id, status: "DONE" };
  },

  // ---- revision (device-mode approximation of the same SM-2-style engine) ----
  async revisionQueue(examId) {
    const { api } = await import("./api.js");
    const syl = await api.get(`/syllabus/${examId}`);
    const s = load();
    const per = {};
    for (const a of s.attempts.filter((a) => a.exam_id === examId)) {
      const key = a.topic_name || "General";
      per[key] = per[key] || { attempts: 0, correct: 0 };
      per[key].attempts++; if (a.correct) per[key].correct++;
    }
    const due = [], scheduled = [], newItems = [];
    for (const m of syl.micro_topics) {
      const p = s.progress[m.id];
      const acc = per[m.name];
      const base = { id: m.id, name: m.name, subject_name: m.subject_name, group_key: m.group_key,
                     status: p ? p.status : "NOT_STARTED", mastery: p ? p.mastery : 0,
                     attempts: acc ? acc.attempts : 0,
                     accuracy: acc ? Math.round(100 * acc.correct / acc.attempts * 10) / 10 : null };
      if (acc && base.accuracy < 60) {
        base.urgency = 100 - base.accuracy;
        base.reason = `Weak topic: ${base.accuracy}% accuracy over ${acc.attempts} attempt(s). Revisit before anything else.`;
        due.push(base); continue;
      }
      if (!p || p.status === "NOT_STARTED") {
        base.urgency = 10;
        base.reason = "Not started yet.";
        newItems.push(base); continue;
      }
      const ease = base.accuracy == null ? 1.3 : 0.5 + 2.0 * (base.accuracy / 100);
      const reps = p.status === "COMPLETED" ? 4 : Math.min(3, (p.mastery || 0) / 25 | 0);
      const interval = (p.status === "COMPLETED" ? 7 : 2) * Math.pow(ease, reps);
      const days = Math.floor((Date.now() - new Date(p.updated_at.replace(" ", "T") + "Z").getTime()) / 86400000);
      if (days >= interval) {
        base.urgency = 40 + Math.min(40, (days - interval) * 2) + (p.mastery || 0) / 10;
        base.reason = `${p.status.toLowerCase().replace("_", " ")} ${days} day(s) ago — review cycle of ${Math.round(interval * 10) / 10} day(s) elapsed.`;
        due.push(base);
      } else {
        base.next_review_in_days = Math.round((interval - days) * 10) / 10;
        base.reason = `On schedule; next review in ${base.next_review_in_days} day(s).`;
        scheduled.push(base);
      }
    }
    due.sort((a, b) => b.urgency - a.urgency);
    return { exam_id: examId, due, scheduled: scheduled.slice(0, 15), new: newItems.slice(0, 15),
      method: "Device mode: same SM-2-style spacing computed locally from your on-device progress and attempts.",
      stored_on_server: false };
  },

  async revisionSession(examId, limit = 10) {
    const q = await this.revisionQueue(examId);
    const { api } = await import("./api.js");
    const ids = q.due.slice(0, limit).map((t) => t.id);
    if (!ids.length) return { exam_id: examId, topics: [], questions: [],
      note: "Nothing is due right now — mark topics done in the syllabus and answer practice questions to build the schedule." };
    const qs = await api.get(`/questions?exam_id=${examId}`);
    const topics = q.due.slice(0, limit).map((t) => t.name);
    const questions = qs.questions.filter((x) => ids.includes(x.micro_topic_id)
      || topics.includes(x.topic_name)).slice(0, 20);
    return { exam_id: examId, topics, questions };
  },

  async dueTopicIds(examId) {
    return (await this.revisionQueue(examId)).due.map((t) => t.id);
  },

  // ---- mocks ----
  async submitMock(examId, paper, answers, questionIds) {
    const { api } = await import("./api.js");
    const card = await api.post(`/mocks/${examId}/submit-guest`,
      { answers, paper, question_ids: questionIds });
    const s = load();
    s.mocks.unshift(card);
    s.mocks = s.mocks.slice(0, 20);
    save(s);
    return card;
  },

  async mockHistory(examId) {
    return { exam_id: examId, attempts: load().mocks.filter((m) => m.exam_id === examId) };
  },

  // ---- mains ----
  async saveMains(payload) {
    const s = load();
    const words = payload.body.trim().split(/\s+/).length;
    const rec = { attempt_id: s.mainsSeq++, exam_id: payload.exam_id, prompt_id: payload.prompt_id,
      body: payload.body, word_count: words,
      self_scores: payload.self_scores || {}, created_at: now() };
    s.mains.unshift(rec);
    save(s);
    return { attempt_id: rec.attempt_id, word_count: words, within_limit: words <= (payload.word_limit || 250),
      self_scores: rec.self_scores, rubric_note: "Self-evaluation only. GovtExamMitra does not generate a score for descriptive answers.",
      submitted_at: rec.created_at };
  },

  async mainsHistory(examId) {
    let rows = load().mains;
    if (examId) rows = rows.filter((r) => r.exam_id === examId);
    return { attempts: rows };
  },

  // ---- notes ----
  async notesAll() {
    const s = load();
    return { notes: Object.entries(s.notes).map(([mid, n]) => ({
      micro_topic_id: Number(mid), body: n.body, updated_at: n.updated_at,
      topic_name: n.topic_name, exam_id: n.exam_id })) };
  },

  async noteGet(mid) {
    const n = load().notes[mid];
    return { micro_topic_id: mid, body: n ? n.body : "", updated_at: n ? n.updated_at : null };
  },

  async notePut(mid, body, meta) {
    const s = load();
    s.notes[mid] = { body, updated_at: now(), topic_name: meta?.topicName, exam_id: meta?.examId };
    save(s);
    return { micro_topic_id: mid, saved: true, updated_at: s.notes[mid].updated_at };
  },

  async noteDelete(mid) {
    const s = load();
    const had = !!s.notes[mid];
    delete s.notes[mid];
    save(s);
    return { deleted: had ? 1 : 0 };
  },

  // ---- bookmarks ----
  async bookmarksAll() {
    return { bookmarks: load().bookmarks };
  },

  async bookmarkAdd(kind, refId, label) {
    const s = load();
    if (!s.bookmarks.some((b) => b.kind === kind && String(b.ref_id) === String(refId))) {
      s.bookmarks.unshift({ kind, ref_id: String(refId), label: label || null, created_at: now() });
      save(s);
    }
    return { bookmarked: true, kind, ref_id: String(refId) };
  },

  async bookmarkDelete(kind, refId) {
    const s = load();
    const before = s.bookmarks.length;
    s.bookmarks = s.bookmarks.filter((b) => !(b.kind === kind && String(b.ref_id) === String(refId)));
    save(s);
    return { deleted: before !== s.bookmarks.length };
  },

  // ---- recommendations (device-mode rules, same structure as the server engine) ----
  async recommendations(examId, pair) {
    const { api } = await import("./api.js");
    const [cov, an, prog] = await Promise.all([
      this.coverage(examId), this.analytics(examId), this.progressList(),
    ]);
    const recs = [];
    for (const w of an.weak_topics) {
      recs.push({ rule: "WEAK_TOPIC", priority: 1, title: `Revise ${w.topic_name}`,
        reason: `Accuracy ${w.accuracy}% over ${w.attempts} attempt(s) — below the 60% threshold.`,
        action: "practice", exam_id: examId });
    }
    for (const g of cov.subjects) {
      if (g.completion === 0 && g.total > 0) {
        recs.push({ rule: "COVERAGE_GAP", priority: 2, title: `Start ${g.subject_name}`,
          reason: `0 of ${g.total} micro-topics started in ${g.subject_name}.`,
          action: "syllabus", exam_id: examId });
      }
    }
    if (pair) {
      const pmap = {};
      for (const p of prog.progress) pmap[p.micro_topic_id] = p;
      try {
        const r = await api.get(`/overlap/${examId}/${pair}`);
        for (const p of r.pairs || []) {
          const pa = pmap[p.id_a], pb = pmap[p.id_b];
          const sa = pa ? pa.status : "NOT_STARTED", sb = pb ? pb.status : "NOT_STARTED";
          if (p.classification === "EXACT_MATCH" && sa === "COMPLETED" && sb !== "COMPLETED") {
            recs.push({ rule: "OVERLAP_LEVERAGE", priority: 3, title: `Claim ${p.name_b} on ${pair}`,
              reason: `Completed ${p.name_a} here; the exact-match topic carries the same content.`,
              action: "syllabus", exam_id: pair });
          }
        }
      } catch { /* pair may not exist */ }
    }
    const tasks = (await this.tasks()).tasks.filter((t) => t.status === "PENDING").slice(0, 5);
    for (const t of tasks) {
      recs.push({ rule: "PLANNER_NEXT", priority: 4, title: `Work on: ${t.title}`,
        reason: "Pending task in your planner.", action: "planner", exam_id: examId });
    }
    recs.sort((a, b) => a.priority - b.priority);
    return { exam_id: examId, recommendations: recs,
      note: recs.length ? null : "No data yet — answer a few practice questions and recommendations will sharpen.",
      stored_on_server: false };
  },

  // ---- onboarding ----
  checklist(steps) {
    const s = load();
    if (s.checklistDismissed) return null;
    return steps.map((st) => ({ ...st, done: s.checklistDone.includes(st.key) }));
  },
  checklistStep(key) {
    const s = load();
    if (!s.checklistDone.includes(key)) { s.checklistDone.push(key); save(s); }
  },
  checklistDismiss() {
    const s = load();
    s.checklistDismissed = true;
    save(s);
  },
};

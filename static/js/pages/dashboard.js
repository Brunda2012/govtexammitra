import { api } from "../api.js";
import { el, badge, loading, errorState, pageHead, progressbar } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Your preparation overview",
    "Progress recorded on this device (local user). Multi-user accounts arrive in the next milestone."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const d = await api.get("/dashboard");
    content.innerHTML = "";

    const hero = el("section", { class: "card" },
      el("h2", { style: "margin-top:0" }, "Exam Overlap Intelligence"),
      el("p", { class: "muted" }, "The flagship capability: know what to study once for multiple exams, and where extra depth is needed."),
      d.overlap_summary
        ? el("div", { class: "grid cols-4", style: "margin-top:12px" },
            miniStat(d.overlap_summary.compared_pairs, "mapped topic pairs"),
            miniStat(d.overlap_summary.exact_match, "exact overlaps"),
            miniStat(d.overlap_summary.partial_overlap, "partial overlaps"),
            miniStat(d.overlap_summary.related_concept, "related concepts"))
        : el("div", { class: "notice warn" }, "Overlap data not available yet."),
      el("a", { class: "btn accent", style: "margin-top:14px", href: "#/overlap" }, "Open comparison →"));
    content.append(hero);
    content.append(toolsGrid());

    for (const e of d.exams) {
      const p = e.progress;
      content.append(el("section", { class: "card" },
        el("h3", { style: "margin:0 0 4px" }, e.name),
        el("div", { class: "muted small" }, e.authority),
        el("div", { style: "margin:10px 0 6px" }, progressbar(p.completion_pct)),
        el("div", { class: "muted small" },
          `${p.completed}/${p.total} micro-topics completed · ${p.in_progress} in progress (${p.completion_pct}%)`),
        el("a", { href: `#/syllabus?exam=${e.id}`, class: "small" }, "Browse syllabus →")));
    }

    content.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Pending tasks"),
      d.pending_tasks.length
        ? el("ul", null, d.pending_tasks.map((t) => el("li", null, t.title)))
        : el("p", { class: "muted" }, "No pending tasks. Generate a combined study plan from the Planner."),
      el("a", { href: "#/planner", class: "btn ghost" }, "Open planner")));
  } catch (err) {
    content.innerHTML = "";
    if (err.status === 401) {
      content.append(el("section", { class: "card" },
        el("h3", { style: "margin-top:0" }, "Sign in to see your dashboard"),
        el("p", { class: "muted" }, "Your progress, plans and practice history are private to your account. Create a free account in seconds — no email verification needed."),
        el("a", { class: "btn accent", href: "#/account" }, "Create account / Log in")));
    } else {
      content.append(errorState(err, () => render(root)));
    }
  }
}

const TOOLS = [
  { t: "Government Information Centre", href: "#/govinfo", live: true, d: "Auto-ingested official notifications & documents" },
  { t: "Exam Overlap Intelligence", href: "#/overlap", live: true, d: "Micro-topic comparison across examinations" },
  { t: "Exam Explorer", href: "#/exams", live: true, d: "Verified examination catalogue" },
  { t: "Detailed Syllabus Explorer", href: "#/syllabus", live: true, d: "Official wording + AI-derived micro-topics" },
  { t: "MCQ Practice", href: "#/practice", live: true, d: "Attempt, score and learn with explanations" },
  { t: "Personalized Study Planner", href: "#/planner", live: true, d: "Combined, de-duplicated study sequence" },
  { t: "Performance Analytics", href: "#/analytics", live: true, d: "Coverage, accuracy and recent attempts" },
  { t: "Weakness Detection", href: "#/analytics", live: true, d: "Per-topic accuracy below the 60% threshold" },
  { t: "Profile & Settings", href: "#/account", live: true, d: "Your account and sessions" },
  { t: "AI Study Mentor", href: "#/mentor", key: true, d: "Doubt-solving via your own API key" },
  { t: "Previous-Year Questions", href: "#/pyqs", d: "Only officially sourced PYQs" },
  { t: "Full-Length Mock Tests", href: "#/mocks", d: "Official marking schemes" },
  { t: "Mains Answer Writing", href: "#/mains", d: "Timed practice with rubrics" },
  { t: "AI Answer Evaluation", href: "#/answer-eval", d: "Rubric-based advisory feedback" },
  { t: "Current Affairs", href: "#/current-affairs", d: "Sourced monthly compilations" },
  { t: "Smart Revision Centre", href: "#/revision", d: "Spaced repetition on weak topics" },
  { t: "Flashcards", href: "#/flashcards", d: "From verified micro-topics" },
  { t: "Mind Maps", href: "#/mindmaps", d: "Subject → topic hierarchies" },
  { t: "Topic-wise Notes", href: "#/notes", d: "Private notes per micro-topic" },
  { t: "Bookmarks", href: "#/bookmarks", d: "Save topics and questions" },
  { t: "Learning Recommendations", href: "#/recommendations", d: "What to study next, and why" },
];

function toolsGrid() {
  return el("section", { class: "card" },
    el("h3", { style: "margin:0 0 4px" }, "All learning tools"),
    el("p", { class: "muted small", style: "margin:0 0 12px" }, "Labelled honestly: LIVE means fully functional today; PLANNED pages describe exactly what they will do once their data engine exists."),
    el("div", { class: "tools-grid" },
      TOOLS.map((x) => el("a", { class: "tool-card" + (x.live ? " live" : ""), href: x.href },
        el("span", { class: "tool-status " + (x.live ? "live" : x.key ? "key" : "soon") },
          x.live ? "LIVE" : x.key ? "NEEDS KEY" : "PLANNED"),
        el("strong", null, x.t),
        el("span", { class: "muted small" }, x.d)))));
}

function miniStat(n, lbl) {
  return el("div", { class: "stat accent" }, el("div", { class: "num" }, n), el("div", { class: "lbl" }, lbl));
}

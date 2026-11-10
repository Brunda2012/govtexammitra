import { api } from "../api.js";
import { store } from "../store.js";
import { device } from "../device.js";
import { el, loading, errorState, pageHead, progressbar } from "../ui.js";

const STEPS = [
  { key: "pick", title: "Pick your exam", href: "#/exams", hint: "See which exams are ready today." },
  { key: "syllabus", title: "Learn the syllabus", href: "#/syllabus", hint: "Small topics you can tick off one by one." },
  { key: "overlap", title: "Compare two exams", href: "#/overlap", hint: "Optional: study shared topics once." },
  { key: "practice", title: "Practise questions", href: "#/practice", hint: "Real marking rules, with explanations." },
  { key: "plan", title: "Make a study plan", href: "#/planner", hint: "A day-by-day plan from your progress." },
  { key: "track", title: "Track your progress", href: "#/dashboard", hint: "You are here — this page." },
];

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("My progress",
    "One glance: what you have done, and the one thing to do next. Everything else lives in the menu."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const d = await store.get("/dashboard");
    content.innerHTML = "";

    // ---- next step ----
    const checklist = device.checklist(STEPS);
    const next = checklist.find((s) => !s.done);
    if (next) {
      content.append(el("section", { class: "card next-step-card" },
        el("div", { class: "muted small" }, "YOUR NEXT STEP"),
        el("h2", { style: "margin:6px 0" }, next.title),
        el("p", { class: "muted", style: "margin:0 0 14px" }, next.hint),
        el("a", { class: "btn accent big", href: next.href }, "Do it now →"),
        el("div", { class: "muted small", style: "margin-top:12px" },
          `${checklist.filter((s) => s.done).length} of ${STEPS.length} first steps done`)));
    } else {
      content.append(el("section", { class: "card next-step-card" },
        el("div", { class: "muted small" }, "KEEP GOING"),
        el("h2", { style: "margin:6px 0" }, "Revise your weak topics"),
        el("p", { class: "muted", style: "margin:0 0 14px" },
          "You have finished the first steps. The best use of your next 20 minutes is a short revision session — weak topics resurface until they stick."),
        el("a", { class: "btn accent big", href: "#/revision" }, "Start a revision session →")));
    }

    // ---- exam progress (simple) ----
    content.append(el("h2", { class: "home-h2" }, "How far along are you"));
    for (const e of d.exams) {
      const p = e.progress;
      content.append(el("section", { class: "card" },
        el("div", { style: "display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:baseline" },
          el("h3", { style: "margin:0" }, e.name),
          el("span", { class: "badge " + (p.completion_pct >= 50 ? "EXACT_MATCH" : "INFO") },
            `${p.completion_pct}% done`)),
        el("div", { style: "margin:12px 0 8px" }, progressbar(p.completion_pct)),
        el("div", { class: "muted small" },
          `${p.completed} of ${p.total} topics completed${p.in_progress ? ` · ${p.in_progress} in progress` : ""}`),
        el("div", { class: "hero-actions", style: "margin-top:10px" },
          el("a", { class: "btn ghost", href: `#/syllabus?exam=${e.id}` }, "Keep learning"),
          el("a", { class: "btn ghost", href: "#/practice" }, "Practise"))));
    }

    // ---- tasks ----
    content.append(el("h2", { class: "home-h2" }, "Today's plan"));
    content.append(el("section", { class: "card" },
      d.pending_tasks.length
        ? el("ul", { class: "task-list" }, d.pending_tasks.slice(0, 5).map((t) => el("li", null, t.title)))
        : el("p", { class: "muted" },
          "No tasks yet. Make a study plan and it will fill this list with what to do each day."),
      el("a", { class: "btn ghost", href: "#/planner" }, "Open my study plan")));

    // ---- everything else, tucked away ----
    content.append(el("details", { class: "card", style: "padding:0" },
      el("summary", { style: "padding:14px 18px;cursor:pointer" },
        el("strong", null, "All learning tools"),
        el("span", { class: "muted small", style: "margin-left:8px" }, "everything, if you want it")),
      el("div", { style: "padding:4px 18px 16px" }, toolsGrid())));
  } catch (err) {
    content.innerHTML = "";
    if (err.status === 401) {
      content.append(el("section", { class: "card" },
        el("h3", { style: "margin-top:0" }, "Your progress is saved on this device — and on your account"),
        el("p", { class: "muted" }, "You can study without an account. A free account keeps your progress on every device you use."),
        el("div", { class: "hero-actions", style: "margin-top:10px" },
          el("a", { class: "btn accent", href: "#/syllabus" }, "Just keep studying"),
          el("a", { class: "btn ghost", href: "#/account" }, "About accounts"))));
    } else {
      content.append(errorState(err, () => render(root)));
    }
  }
}

const TOOLS = [
  { t: "Choose your exam", href: "#/exams", d: "What we support today" },
  { t: "Syllabus", href: "#/syllabus", d: "Official wording, small topics" },
  { t: "Practice questions", href: "#/practice", d: "With explanations" },
  { t: "Mock tests", href: "#/mocks", d: "Timed, with a score card" },
  { t: "Mains writing", href: "#/mains", d: "Timed answers, honest self-scoring" },
  { t: "Flashcards", href: "#/flashcards", d: "Quick revision" },
  { t: "Topic map", href: "#/mindmaps", d: "Whole subject at a glance" },
  { t: "What to revise", href: "#/revision", d: "Weak topics first" },
  { t: "Study plan", href: "#/planner", d: "What to do each day" },
  { t: "Strengths & weaknesses", href: "#/analytics", d: "Per-topic accuracy" },
  { t: "Suggestions for you", href: "#/recommendations", d: "What to study next, and why" },
  { t: "Compare two exams", href: "#/overlap", d: "What overlaps, what doesn't" },
  { t: "Past papers", href: "#/pyqs", d: "Official papers with sources" },
  { t: "Current affairs", href: "#/current-affairs", d: "Official releases" },
  { t: "Government updates", href: "#/govinfo", d: "Notifications and documents" },
  { t: "My notes", href: "#/notes", d: "Saved topic by topic" },
  { t: "Saved items", href: "#/bookmarks", d: "Your bookmarks" },
  { t: "Ask a question", href: "#/mentor", d: "AI study help (needs server setup)" },
  { t: "AI answer evaluation", href: "#/answer-eval", d: "Advisory feedback (needs server setup)" },
  { t: "How this works", href: "#/methodology", d: "Our data, honestly explained" },
];

function toolsGrid() {
  return el("div", { class: "tools-grid" },
    TOOLS.map((x) => el("a", { class: "tool-card live", href: x.href },
      el("strong", null, x.t),
      el("span", { class: "muted small" }, x.d))));
}

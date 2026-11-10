// Smart Revision Centre — spaced repetition queue built on accuracy + completion data.
import { api } from "../api.js";
import { store } from "../store.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Smart Revision Centre",
    "A spaced-repetition queue computed from your own per-topic accuracy and completion dates. Weak topics are always due; completed topics resurface as their interval decays."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const exams = (await api.get("/exams")).filter((e) => e.supported);
    const sel = el("select", { "aria-label": "Choose examination" });
    for (const e of exams) sel.append(el("option", { value: e.id }, e.name));
    sel.value = selected;
    sel.addEventListener("change", () => { selected = sel.value; localStorage.setItem("gm.exam", selected); load(content); });
    root.append(el("div", { class: "compare-controls" }, el("label", null, "Examination", sel)));
    await load(content);
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

async function load(content) {
  content.innerHTML = "";
  content.append(loading());
  try {
    const q = await store.get(`/revision/${selected}/queue`);
    content.innerHTML = "";
    content.append(el("section", { class: "card" },
      el("div", { class: "meta-line" },
        el("span", { class: "badge INFO" }, `${q.due.length} due`),
        el("span", { class: "muted small" }, `${(q.scheduled || []).length} on schedule · ${(q.new || []).length} not started`)),
      el("p", { class: "muted small", style: "margin-top:8px" }, q.method)));
    if (!q.due.length) {
      content.append(el("div", { class: "state-box" },
        el("div", { class: "big" }, "Nothing due right now"),
        el("div", null, "Answer practice questions and mark syllabus topics — the queue builds from your data.")));
    }
    const sessBox = el("div");
    content.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, "One-click revision session"),
      el("p", { class: "muted small" }, "Pulls practice questions from your top due topics."),
      el("button", { class: "btn accent", onclick: async () => {
        const btn = sessBox.querySelector("button");
        if (btn) btn.disabled = true;
        const s = await store.get(`/revision/${selected}/session`);
        sessBox.innerHTML = "";
        if (!s.questions.length) {
          sessBox.append(el("p", { class: "muted" }, s.note || "Nothing due."));
        } else {
          sessBox.append(el("p", { class: "muted small" }, "Topics in this session: " + s.topics.join(", ")),
            el("a", { class: "btn ghost", href: "#/practice" },
              `Open Practice — ${s.questions.length} question(s) queued from your due topics`));
        }
      } }, "Start revision session"), sessBox));
    for (const t of q.due) content.append(topicCard(t, true));
    if ((q.scheduled || []).length) {
      content.append(el("h2", { class: "home-h2" }, "On schedule"));
      for (const t of q.scheduled) content.append(topicCard(t, false));
    }
    if ((q.new || []).length) {
      content.append(el("h2", { class: "home-h2" }, "Not started yet"));
      for (const t of q.new) content.append(topicCard(t, false));
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

function topicCard(t, urgent) {
  return el("section", { class: "card" + (urgent ? " due-card" : "") },
    el("div", { class: "meta-line" },
      el("strong", null, t.name),
      t.subject_name ? el("span", { class: "muted small" }, t.subject_name) : null,
      t.accuracy != null ? el("span", { class: "badge " + (t.accuracy < 60 ? "EXAM_SPECIFIC" : "EXACT_MATCH") },
        `${t.accuracy}% accuracy`) : null),
    el("p", { class: "muted", style: "margin:6px 0" }, t.reason),
    el("div", { class: "hero-actions" },
      el("a", { class: "btn ghost", href: "#/practice" }, "Practice this topic"),
      el("a", { class: "btn ghost", href: `#/notes?topic=${t.id}` }, "Open notes")));
}

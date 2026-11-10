import { api } from "../api.js";
import { store } from "../store.js";
import { el, loading, errorState, pageHead, progressbar } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Performance Analytics",
    "Syllabus coverage, practice accuracy and weak topics for your account. Weak-topic detection uses your per-topic accuracy: topics with at least 2 attempts below 60% are listed."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const exams = (await api.get("/exams")).filter((e) => e.supported);
    if (!exams.length) throw new Error("No supported examinations available yet.");
    const sel = el("select", { "aria-label": "Choose examination" });
    for (const e of exams) sel.append(el("option", { value: e.id }, e.name));
    if (!exams.some((e) => e.id === selected)) selected = exams[0].id;
    sel.value = selected;
    sel.addEventListener("change", () => { selected = sel.value; localStorage.setItem("gm.exam", selected); load(content, sel); });
    root.append(el("div", { class: "compare-controls" }, el("label", null, "Examination", sel)));
    await load(content, sel);
  } catch (err) {
    fail(content, root, err);
  }
}

async function load(content, sel) {
  content.innerHTML = "";
  content.append(loading());
  try {
    const a = await store.get("/analytics", { examId: selected });
    content.innerHTML = "";
    const sp = a.syllabus_progress || {};
    const at = a.attempts || {};
    const accuracy = at.total ? Math.round(((at.correct || 0) / at.total) * 100) : null;

    content.append(el("div", { class: "grid cols-4" },
      stat(`${sp.completed ?? 0}/${sp.total ?? 0}`, "Topics completed"),
      stat(`${sp.completion_pct ?? 0}%`, "Syllabus coverage", "accent"),
      stat(String(at.total ?? 0), "Questions attempted"),
      stat(accuracy === null ? "—" : accuracy + "%", "Accuracy")));

    content.append(el("section", { class: "card" },
      el("h3", { style: "margin:0 0 8px" }, "Syllabus coverage"),
      progressbar(sp.completion_pct ?? 0),
      el("div", { class: "muted small", style: "margin-top:6px" },
        `${sp.in_progress ?? 0} in progress · coverage is computed over the verified micro-topic decomposition of this examination.`)));

    const weak = a.weak_topics || [];
    const weakCard = el("section", { class: "card" }, el("h3", { style: "margin-top:0" }, "Weak topics"));
    if (weak.length) {
      const tbl = el("table", { class: "data" },
        el("thead", null, el("tr", null, el("th", null, "Topic"), el("th", null, "Subject"), el("th", null, "Attempts"), el("th", null, "Accuracy"))));
      const body = el("tbody");
      for (const w of weak) {
        body.append(el("tr", null,
          el("td", null, w.topic_name || "—"),
          el("td", { class: "small" }, w.subject_name || "—"),
          el("td", { class: "small" }, String(w.attempts)),
          el("td", null, el("span", { class: "badge EXAM_SPECIFIC" }, (w.accuracy ?? 0) + "%"))));
      }
      tbl.append(body);
      weakCard.append(el("p", { class: "muted small", style: "margin:6px 0 10px" },
        "These topics are below the 60% accuracy threshold. The Smart Revision Centre schedules them automatically."),
        el("a", { class: "btn ghost", style: "margin-bottom:10px", href: "#/revision" }, "Open Revision Centre →"), tbl);
    } else {
      weakCard.append(el("p", { class: "muted" },
        "No weak topics yet — weak-topic detection needs at least 2 attempts on a topic. Head to Practice to build the signal."));
    }
    content.append(weakCard);

    const recent = a.recent || [];
    const recentCard = el("section", { class: "card" }, el("h3", { style: "margin-top:0" }, "Recent attempts"));
    if (recent.length) {
      const tbl = el("table", { class: "data" },
        el("thead", null, el("tr", null, el("th", null, "Question"), el("th", null, "Result"), el("th", null, "Score"))));
      const body = el("tbody");
      for (const r of recent) {
        body.append(el("tr", null,
          el("td", { class: "small" }, (r.question || "").slice(0, 110) + ((r.question || "").length > 110 ? "…" : "")),
          el("td", null, el("span", { class: "badge " + (r.correct ? "EXACT_MATCH" : "EXAM_SPECIFIC") }, r.correct ? "CORRECT" : "INCORRECT")),
          el("td", { class: "small" }, String(r.score))));
      }
      tbl.append(body);
      recentCard.append(tbl);
    } else {
      recentCard.append(el("p", { class: "muted" }, "No attempts recorded yet for this examination."));
    }
    content.append(recentCard);
  } catch (err) {
    fail(content, root, err);
  }
}

function fail(content, root, err) {
  content.innerHTML = "";
  if (err.status === 401) {
    content.append(signInCard());
  } else {
    content.append(errorState(err, () => render(root)));
  }
}

export function signInCard() {
  return el("section", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Sign in to see your analytics"),
    el("p", { class: "muted" }, "Analytics are computed from your private attempt history. Create a free account in seconds — no email verification needed."),
    el("a", { class: "btn accent", href: "#/account" }, "Create account / Log in"));
}

function stat(num, lbl, cls = "") {
  return el("div", { class: `stat ${cls}` }, el("div", { class: "num" }, num), el("div", { class: "lbl" }, lbl));
}

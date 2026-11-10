import { api } from "../api.js";
import { store } from "../store.js";
import { el, badge, loading, errorState, pageHead, progressbar } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Syllabus browser",
    "Examination → stage → paper → subject → micro-topics. Subject-level wording is official; micro-topics are an AI-derived decomposition."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const exams = (await api.get("/exams")).filter((e) => e.supported);
    const sel = el("select", { "aria-label": "Choose examination" });
    for (const e of exams) sel.append(el("option", { value: e.id }, e.name));
    sel.value = selected;
    sel.addEventListener("change", () => { selected = sel.value; localStorage.setItem("gm.exam", selected); load(content); });
    root.append(el("div", { class: "compare-controls" }, el("label", null, "Examination", sel)));
    await load(content, sel);
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

async function load(content, sel) {
  content.innerHTML = "";
  content.append(loading());
  try {
    const [data, prog] = await Promise.all([
      api.get(`/syllabus/${selected}`),
      store.get(`/progress/${selected}/coverage`),
    ]);
    const covMap = {};
    for (const c of prog.subjects) covMap[c.subject_name] = c;
    content.innerHTML = "";
    const overall = prog.overall;
    content.append(el("section", { class: "card" },
      el("h3", { style: "margin:0 0 8px" }, "Overall progress"),
      el("div", { class: "muted small" }, `${overall.completed}/${overall.total} micro-topics completed (${overall.completion_pct}%)`),
      progressbar(overall.completion_pct)));

    for (const s of data.subjects) {
      const micros = data.micro_topics.filter((m) => m.subject_name === s.name);
      const cov = covMap[s.name];
      const details = el("details", { class: "card", style: "padding:0" },
        el("summary", { style: "padding:14px 18px;cursor:pointer;display:flex;gap:10px;align-items:center;flex-wrap:wrap" },
          el("strong", null, s.name),
          el("span", { class: "muted small" }, `${s.stage} · ${s.paper}`),
          cov ? el("span", { class: "muted small" }, `${cov.completed || 0}/${cov.total} done`) : null));
      const body = el("div", { style: "padding:0 18px 16px" });
      body.append(el("div", { class: "official-label" }, "Official syllabus wording"),
        el("div", { class: "official", style: "margin:6px 0 10px" }, `“${s.official_text}”`));
      if (micros.length) {
        const ul = el("ul", { style: "margin:0;padding-left:18px" });
        for (const m of micros) {
          ul.append(el("li", { style: "margin:3px 0" },
            m.name + " ",
            el("button", {
              class: "pill", style: "padding:2px 10px;font-size:0.72rem;margin-left:6px",
              onclick: () => markProgress(m, ul),
            }, "Mark done"),
            el("button", {
              class: "pill", style: "padding:2px 10px;font-size:0.72rem;margin-left:4px",
              onclick: () => bookmarkTopic(m, ul),
            }, "Bookmark"),
            el("a", { class: "pill", style: "padding:2px 10px;font-size:0.72rem;margin-left:4px",
              href: `#/notes?topic=${m.id}` }, "Note")));
        }
        body.append(el("div", { class: "muted small", style: "margin-top:8px" }, "Micro-topics (AI-derived decomposition — verify against the official notification):"), ul);
      }
      details.append(body);
      content.append(details);
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content, sel)));
  }
}

async function markProgress(m, ul) {
  try {
    const res = await store.post("/progress", { micro_topic_id: m.id, status: "COMPLETED", mastery: 100 });
    const note = el("div", { class: "notice", style: "margin-top:10px" },
      "Saved. " + (res.applied.length > 1
        ? `Propagated to ${res.applied.length - 1} mapped exam topic(s) per the overlap rules (exact → same mastery; partial → capped at 60%).`
        : "No cross-exam propagation for this topic."));
    ul.parentElement.insertBefore(note, ul);
    setTimeout(() => note.remove(), 8000);
  } catch (err) {
    alert("Could not save progress: " + err.message);
  }
}

async function bookmarkTopic(m, ul) {
  try {
    await store.post("/bookmarks", { kind: "TOPIC", ref_id: String(m.id) }, { label: m.name });
    const note = el("div", { class: "notice", style: "margin-top:10px" },
      `Bookmarked “${m.name}”. Find it under Bookmarks.`);
    ul.parentElement.insertBefore(note, ul);
    setTimeout(() => note.remove(), 6000);
  } catch (err) {
    alert("Could not bookmark: " + err.message);
  }
}

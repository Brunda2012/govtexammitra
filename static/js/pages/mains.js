// Mains Answer Writing — timed descriptive practice with word-limit guidance and
// honest rubric self-scoring. No generated scores.
import { api } from "../api.js";
import { store } from "../store.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";
let timer = null;
let secondsLeft = 0;

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Mains answer writing",
    "Timed descriptive answers against syllabus-derived prompts. GovtExamMitra does NOT generate a score for your writing — you self-score on the rubric, honestly."));
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
    const data = await api.get(`/mains/${selected}/prompts`);
    const history = await store.get("/mains/attempts", { examId: selected });
    content.innerHTML = "";
    content.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Self-evaluation rubric (applied by you)"),
      el("ul", { style: "margin:8px 0 0;padding-left:20px" },
        data.rubric.map((r) => el("li", { class: "muted small", style: "margin:3px 0" },
          `${r.label} (0–${r.max}): ${r.guide}`))),
      el("p", { class: "muted small", style: "margin-top:8px" }, data.rubric_note)));
    if (history.attempts.length) {
      content.append(el("section", { class: "card" },
        el("h3", { style: "margin-top:0" }, "Your previous answers"),
        el("table", { class: "data" },
          el("thead", null, el("tr", null, el("th", null, "When"), el("th", null, "Prompt"), el("th", null, "Words"), el("th", null, "Self-score"))),
          el("tbody", null, history.attempts.map((a) => el("tr", null,
            el("td", { class: "small" }, (a.created_at || "").slice(0, 16)),
            el("td", { class: "small" }, a.prompt_id),
            el("td", { class: "small" }, String(a.word_count)),
            el("td", { class: "small" },
              Object.entries(a.self_scores || {}).map(([k, v]) => `${k} ${v}`).join(", ") || "—")))))));
    }
    for (const p of data.prompts) content.append(promptCard(p));
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

function promptCard(p) {
  const ta = el("textarea", { class: "mains-input", rows: "10",
    placeholder: "Write your answer here. Structure: introduction, body with dimensions, conclusion." });
  const wc = el("span", { class: "muted small" }, "0 words");
  const timerLabel = el("span", { class: "badge INFO" }, "Timer ready");
  const rubricBox = el("div");
  const saved = el("div");
  ta.addEventListener("input", () => {
    const n = ta.value.trim() ? ta.value.trim().split(/\s+/).length : 0;
    wc.textContent = `${n} / ${p.word_limit} words` + (n > p.word_limit ? " — over the limit" : "");
    wc.className = "muted small" + (n > p.word_limit ? " over-limit" : "");
  });
  const startBtn = el("button", { class: "btn ghost", onclick: () => {
    secondsLeft = p.word_limit >= 500 ? 4 * 60 : 7 * 60;
    clearInterval(timer);
    timer = setInterval(tick, 1000);
    tick();
  } }, "Start timer");
  function tick() {
    const m = Math.floor(secondsLeft / 60), s = secondsLeft % 60;
    timerLabel.textContent = `⏱ ${m}:${String(s).padStart(2, "0")}`;
    if (secondsLeft <= 0) {
      clearInterval(timer);
      timerLabel.textContent = "Time's up — evaluate honestly now.";
      timerLabel.className = "badge EXAM_SPECIFIC";
    }
    secondsLeft--;
  }
  const submitBtn = el("button", { class: "btn accent", onclick: async () => {
    submitBtn.disabled = true;
    try {
      const selfScores = {};
      for (const inp of rubricBox.querySelectorAll("input[type=number]")) {
        if (inp.value !== "") selfScores[inp.dataset.key] = Number(inp.value);
      }
      const res = await store.post("/mains/attempts",
        { exam_id: p.exam_id, prompt_id: p.id, body: ta.value, self_scores: selfScores, word_limit: p.word_limit },
        { examId: p.exam_id });
      saved.innerHTML = "";
      saved.append(el("div", { class: "notice", style: "margin-top:10px" },
        `Saved (${res.word_count} words, ${res.within_limit ? "within" : "OVER"} the ${p.word_limit}-word limit). `
        + res.rubric_note));
    } catch (err) {
      saved.innerHTML = "";
      saved.append(el("div", { class: "notice bad", style: "margin-top:10px" }, err.message));
    }
    submitBtn.disabled = false;
  } }, "Save answer + self-scores");
  return el("section", { class: "card" },
    el("div", { class: "meta-line" },
      badge(p.paper.toUpperCase().replace(" ", "_")),
      el("span", { class: "muted small" }, `${p.subject_name}${p.topic_name ? " · " + p.topic_name : ""} · ${p.word_limit} words`)),
    el("div", { class: "q-text", style: "margin-top:8px" }, p.prompt),
    p.guidance ? el("p", { class: "muted small", style: "margin:6px 0" }, "Structure guidance: " + p.guidance) : null,
    el("div", { class: "hero-actions", style: "margin:8px 0" }, startBtn, timerLabel, wc),
    ta,
    el("div", { style: "margin-top:10px" },
      el("strong", { class: "small" }, "Self-score the rubric (optional):"),
      el("div", { class: "rubric-inputs" },
        [["content", "Content 0-5"], ["structure", "Structure 0-5"], ["analysis", "Analysis 0-5"],
         ["examples", "Examples 0-5"], ["presentation", "Presentation 0-5"]].map(([k, lbl]) =>
          el("label", { class: "small" }, lbl + " ",
            el("input", { type: "number", min: "0", max: "5", "data-key": k, style: "width:56px" }))))),
    el("div", { class: "hero-actions", style: "margin-top:10px" }, submitBtn),
    saved);
}

// Mock tests — timed section-wise tests assembled from the question bank,
// official negative marking from exams.marking_json, section-wise score cards.
import { api } from "../api.js";
import { store } from "../store.js";
import { el, badge, loading, errorState, pageHead, progressbar } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";
let timer = null;

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Full-length mock tests",
    "Sections assembled from the GovtExamMitra question bank per paper; negative marking comes from each exam's verified marking scheme. All questions are DEMONSTRATION-labelled."));
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
    const [paper, history] = await Promise.all([
      api.get(`/mocks/${selected}`),
      store.get(`/mocks/${selected}/history`),
    ]);
    content.innerHTML = "";
    if (history.attempts.length) content.append(historyCard(history.attempts));
    content.append(briefCard(paper));
    content.append(await testCard(paper));
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

function briefCard(paper) {
  return el("section", { class: "card" },
    el("h3", { style: "margin-top:0" }, `${paper.exam_name} — ${paper.total_questions} questions, ~${paper.total_time_minutes} min`),
    el("div", { class: "meta-line" },
      el("span", { class: "badge INFO" }, `+1 correct · ${paper.marking.negative ? `−1/3 wrong` : "no negative marking"}`),
      el("span", { class: "muted small" }, "scheme source: " + paper.marking.source)),
    el("p", { class: "muted small", style: "margin-top:8px" }, paper.note));
}

function historyCard(attempts) {
  return el("section", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Previous attempts"),
    el("table", { class: "data" },
      el("thead", null, el("tr", null, el("th", null, "When"), el("th", null, "Paper"), el("th", null, "Score"), el("th", null, "Accuracy"))),
      el("tbody", null, attempts.map((a) => el("tr", null,
        el("td", { class: "small" }, (a.created_at || "").slice(0, 16)),
        el("td", { class: "small" }, a.paper),
        el("td", null, `${a.total_score}/${a.max_score}`),
        el("td", { class: "small" },
          a.total
            ? (a.total.accuracy == null ? "—" : a.total.accuracy + "%")
            : (a.correct + a.wrong ? Math.round(100 * a.correct / (a.correct + a.wrong)) + "%" : "—")))))));

}

async function testCard(paper) {
  const answers = {};
  const card = el("section", { class: "card mock-run" });
  card.append(el("h3", { style: "margin-top:0" }, "Take the test"),
    el("p", { class: "muted small" },
      "Answer the questions below. Choose “Skip” for a question you would leave in the real exam — skipped questions count as unattempted."));
  let idx = 0;
  const flat = paper.sections.flatMap((s) => s.questions.map((q) => ({ ...q, section: s.subject })));
  const counter = el("div", { class: "muted small", style: "margin:8px 0" });
  const qBox = el("div");
  const submitBtn = el("button", { class: "btn accent", onclick: submit }, "Submit test");
  const resultBox = el("div");

  function show(i) {
    idx = i;
    const q = flat[i];
    counter.textContent = `Question ${i + 1} of ${flat.length} — section: ${q.section}`;
    qBox.innerHTML = "";
    qBox.append(el("div", { class: "q-text" }, q.question));
    q.options.forEach((opt, oi) => {
      qBox.append(el("button", { class: "opt", onclick: () => {
        answers[q.id] = oi;
        [...qBox.querySelectorAll(".opt")].forEach((b, bi) => b.classList.toggle("picked", bi === oi));
        nextBtn.disabled = false;
      } }, opt));
    });
    qBox.append(el("button", { class: "pill", style: "margin-top:8px", onclick: () => {
      delete answers[q.id];
      [...qBox.querySelectorAll(".opt")].forEach((b) => b.classList.remove("picked"));
      nextBtn.disabled = false;
    } }, "Skip (unattempted)"));
  }
  const prevBtn = el("button", { class: "btn ghost", onclick: () => show(Math.max(0, idx - 1)) }, "← Previous");
  const nextBtn = el("button", { class: "btn ghost", onclick: () => show(Math.min(flat.length - 1, idx + 1)) }, "Next →");
  nextBtn.disabled = true;
  card.append(counter, qBox,
    el("div", { class: "hero-actions", style: "margin-top:10px" }, prevBtn, nextBtn, submitBtn), resultBox);
  show(0);

  async function submit() {
    submitBtn.disabled = true;
    try {
      const res = await store.post(`/mocks/${selected}/submit`,
        { answers, paper: "Mock", question_ids: flat.map((q) => q.id) });
      showResult(res, resultBox, flat, answers);
      submitBtn.remove();
    } catch (err) {
      resultBox.append(el("div", { class: "notice bad", style: "margin-top:10px" }, err.message));
      submitBtn.disabled = false;
    }
  }
  return card;
}

function showResult(res, box, flat, answers) {
  box.innerHTML = "";
  const t = res.total;
  box.append(el("div", { class: "notice", style: "margin-top:12px" },
    el("strong", null, `Score: ${t.score} / ${t.max}`),
    ` — ${t.correct} correct, ${t.wrong} wrong, ${t.unattempted} unattempted. `,
    t.accuracy != null ? `Accuracy on attempted: ${t.accuracy}%. ` : "",
    `Negative marking applied: ${res.marking.negative_fraction || "none"} (source: ${res.marking.source}).`));
  const tbl = el("table", { class: "data", style: "margin-top:10px" },
    el("thead", null, el("tr", null, el("th", null, "Section"), el("th", null, "Correct"), el("th", null, "Wrong"), el("th", null, "Skipped"), el("th", null, "Score"), el("th", null, "Accuracy"))));
  const body = el("tbody");
  for (const s of res.sections) {
    body.append(el("tr", null,
      el("td", null, s.section),
      el("td", { class: "small" }, String(s.correct)),
      el("td", { class: "small" }, String(s.wrong)),
      el("td", { class: "small" }, String(s.unattempted)),
      el("td", { class: "small" }, String(s.score)),
      el("td", { class: "small" }, s.accuracy == null ? "—" : s.accuracy + "%")));
  }
  tbl.append(body);
  box.append(el("h3", { style: "margin:14px 0 6px" }, "Section-wise score card"), tbl);

  // review mode
  const qmap = {};
  for (const q of flat) qmap[q.id] = q;
  const review = el("details", { class: "card", style: "margin-top:12px;padding:0" },
    el("summary", { style: "padding:12px 16px;cursor:pointer" }, "Review every question (answers & explanations)"));
  const rbody = el("div", { style: "padding:0 16px 16px" });
  for (const s of res.sections) {
    for (const r of s.review) {
      const q = qmap[r.question_id];
      if (!q) continue;
      rbody.append(el("div", { style: "border-top:1px solid var(--line);padding:10px 0" },
        el("div", { class: "muted small" }, q.section),
        el("div", { class: "q-text" }, q.question),
        el("div", { class: "muted small" },
          `Your answer: ${r.chosen == null ? "skipped" : (q.options[r.chosen] || "—")} · Correct: ${q.options[r.answer_index]}`),
        r.explanation ? el("p", { class: "muted", style: "margin:6px 0 0" }, r.explanation) : null));
    }
  }
  review.append(rbody);
  box.append(review);
}

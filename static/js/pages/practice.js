import { api } from "../api.js";
import { el, badge, loading, emptyState, errorState, pageHead } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("MCQ practice",
    "Seeded questions are DEMONSTRATION items authored for GovtExamMitra — none are presented as official PYQs. " +
    "Official PYQ ingestion is a planned milestone. Scoring applies the exam's negative marking (1/3 where configured)."));
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
    const [data, analytics] = await Promise.all([
      api.get(`/questions?exam_id=${selected}`),
      api.get(`/analytics?exam_id=${selected}`),
    ]);
    content.innerHTML = "";

    content.append(el("section", { class: "card" },
      el("h3", { style: "margin:0 0 8px" }, "Your practice record"),
      analytics.attempts.total
        ? el("div", { class: "muted small" },
            `${analytics.attempts.total} attempts · ${analytics.attempts.correct} correct · avg score ${analytics.attempts.avg_score}`)
        : el("p", { class: "muted" }, "No attempts yet — answer a question below and your record appears here."),
      analytics.weak_topics.length
        ? el("div", { class: "notice warn", style: "margin-top:8px" },
            "Weak topics (accuracy < 60% over 2+ attempts): " + analytics.weak_topics.map((w) => w.topic_name).join(", "))
        : null));

    if (!data.questions.length) {
      content.append(emptyState("No questions for this exam yet", "The question bank is seeded lightly to stay within budget."));
      return;
    }
    let i = 0;
    for (const q of data.questions) {
      i++;
      content.append(questionCard(q, i));
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

function questionCard(q, n) {
  const card = el("section", { class: "card q-card" });
  card.append(el("div", { class: "meta-line" },
    badge(q.q_type), el("span", { class: "muted small" }, `Q${n} · ${q.topic_name || "General"} · ${q.difficulty}`)),
    el("div", { class: "q-text" }, q.question));
  let answered = false;
  q.options.forEach((opt, idx) => {
    const btn = el("button", { class: "opt", onclick: async () => {
      if (answered) return;
      answered = true;
      btn.disabled = true;
      try {
        const res = await api.post(`/questions/${q.id}/answer`, { chosen: idx });
        [...card.querySelectorAll(".opt")].forEach((b, i) => {
          b.classList.toggle("correct", i === res.answer_index);
          if (i === idx && !res.correct) b.classList.add("wrong");
        });
        card.append(el("div", { class: res.correct ? "notice" : "notice bad", style: "margin-top:10px" },
          (res.correct ? "Correct. " : "Incorrect. Score " + res.score + ". "),
          res.explanation));
      } catch (err) {
        card.append(el("div", { class: "notice bad" }, "Error: " + err.message));
      }
      } }, opt);
    card.append(btn);
  });
  return card;
}

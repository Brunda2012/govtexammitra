// AI Answer Evaluation — advisory feedback via the mentor provider abstraction.
// Honest "needs API key" state: the server returns 503 when no engine is configured.
import { api } from "../api.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("AI answer evaluation",
    "Rubric-based feedback on descriptive answers. Advisory only — the model, the rubric and the fact that this is not an official evaluation are always shown."));
  const content = el("div", null);
  root.append(content);

  let prompts = [];
  try {
    const data = await api.get(`/mains/upsc-cse/prompts`);
    prompts = data.prompts || [];
  } catch { /* prompts are optional context */ }

  const q = el("textarea", { rows: "3", placeholder: "The mains question (paste any mains question here)" });
  const a = el("textarea", { rows: "12", placeholder: "Your answer (max 8000 characters)" });
  const sel = el("select", { "aria-label": "Attach a syllabus prompt (optional)" });
  sel.append(el("option", { value: "" }, "— attach a syllabus prompt (optional) —"));
  for (const p of prompts) sel.append(el("option", { value: p.id }, `${p.paper}: ${p.prompt.slice(0, 60)}…`));
  sel.addEventListener("change", () => {
    const p = prompts.find((x) => x.id === sel.value);
    if (p) q.value = p.prompt;
  });
  const out = el("div");
  const btn = el("button", { class: "btn accent", onclick: async () => {
    btn.disabled = true;
    out.innerHTML = "";
    try {
      const res = await api.post("/eval/answer", { question: q.value, answer: a.value });
      out.append(el("div", { class: "notice warn" }, "Advisory AI feedback — not an official evaluation. " + (res.note || "")),
        el("section", { class: "card", style: "margin-top:12px" },
          el("h3", { style: "margin-top:0" }, "Feedback"),
          el("p", { style: "white-space:pre-wrap" }, res.answer)));
    } catch (err) {
      if (err.status === 503) {
        out.append(el("div", { class: "state-box" },
          el("div", { class: "big" }, "Evaluation engine not configured"),
          el("div", null, "AI answer evaluation needs a provider API key set in the server environment (MENTOR_PROVIDER + MENTOR_API_KEY). GovtExamMitra does not pretend to score answers without a real, verified engine — use the rubric self-scoring in Mains Answer Writing meanwhile."),
          el("a", { class: "btn ghost", style: "margin-top:12px", href: "#/mains" }, "Go to Mains Answer Writing →"),
          el("a", { class: "btn ghost", style: "margin-top:12px", href: "#/methodology" }, "Read why we refuse fake scores")));
      } else if (err.status === 401) {
        out.append(el("div", { class: "state-box" },
          el("div", { class: "big" }, "Sign in to use AI evaluation"),
          el("div", null, "AI answer evaluation runs against the server's configured engine and needs an account. You can self-score any answer right now with the rubric in Mains Answer Writing."),
          el("a", { class: "btn accent", style: "margin-top:12px", href: "#/account" }, "Create an account / log in"),
          el("a", { class: "btn ghost", style: "margin-top:12px", href: "#/mains" }, "Mains Answer Writing →")));
      } else {
        out.append(el("div", { class: "notice bad", style: "margin-top:10px" }, err.message));
      }
    }
    btn.disabled = false;
  } }, "Evaluate my answer");

  content.append(el("section", { class: "card" },
    el("div", { class: "compare-controls" }, el("label", null, "Syllabus prompt (optional)", sel)),
    el("label", { class: "small" }, "Question"), q,
    el("label", { class: "small", style: "display:block;margin-top:8px" }, "Your answer"), a,
    el("div", { class: "hero-actions", style: "margin-top:10px" }, btn),
    el("p", { class: "muted small", style: "margin-top:8px" },
      "Rubric dimensions: content, structure, analysis, examples, presentation — each scored with justification, plus missing key points and one improvement.")),
    out);
}

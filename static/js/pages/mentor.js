import { api } from "../api.js";
import { el, pageHead } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("AI Study Mentor",
    "Explanations and doubt-solving. The mentor is modular: it works with any OpenAI-compatible API and is disabled until you configure a key. GovtExamMitra never fakes AI responses."));
  const disabled = el("div", { class: "notice warn" },
    "AI mentor not configured. Set MENTOR_PROVIDER, MENTOR_API_KEY, MENTOR_BASE_URL and MENTOR_MODEL in the server environment, then restart. Answers will always be labelled advisory.");
  root.append(disabled);
  const box = el("section", { class: "card" });
  const ta = el("textarea", {
    rows: "4", style: "width:100%;background:var(--bg-soft);border:1px solid var(--line);color:var(--text);border-radius:9px;padding:12px;font-family:inherit",
    placeholder: "e.g. Explain the difference between exact and partial syllabus overlap with an example…",
  });
  const send = el("button", { class: "btn", style: "margin-top:10px", onclick: submit }, "Ask mentor");
  const out = el("div", { style: "margin-top:14px" });
  async function submit() {
    const q = ta.value.trim();
    if (!q) return;
    send.disabled = true;
    out.innerHTML = "";
    out.append(el("div", { class: "spinner" }));
    try {
      const res = await api.post("/mentor", { question: q });
      out.innerHTML = "";
      out.append(el("div", { class: "card" }, res.answer),
        el("p", { class: "muted small" }, res.note));
    } catch (err) {
      out.innerHTML = "";
      out.append(el("div", { class: "notice bad" }, err.message));
    }
    send.disabled = false;
  }
  box.append(ta, send, out);
  root.append(box);
}

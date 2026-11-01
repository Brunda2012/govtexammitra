import { api } from "../api.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Exam Explorer",
    "Central government examination catalogue. Details are stored only where sourced from official notifications; " +
    "everything else is explicitly marked pending verification."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const exams = await api.get("/exams");
    content.innerHTML = "";
    for (const e of exams) {
      const links = (e.official_links_json || []).map((l) =>
        el("a", { href: l.url, target: "_blank", rel: "noopener", class: "small", style: "margin-right:10px" }, l.title));
      content.append(el("section", { class: "card" },
        el("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" },
          el("h3", { style: "margin:0" }, e.name),
          badge(e.verification_status),
          e.supported ? el("span", { class: "badge INFO" }, "SYLLABUS MAPPED") : el("span", { class: "badge INFO" }, "CATALOGUE ENTRY")),
        el("div", { class: "muted small" }, `${e.authority} · ${e.category || "—"}`),
        e.description ? el("p", { class: "muted" }, e.description) : null,
        e.stages_json && e.stages_json.length
          ? el("p", { class: "small" }, el("strong", null, "Stages: "), e.stages_json.join(" → "))
          : el("p", { class: "muted small" }, "Stages, eligibility and dates: pending verification from official notification."),
        el("div", { class: "meta-line" },
          links.length ? links : el("span", { class: "muted small" }, "Official source: " + (e.notification_url || "—")),
          el("span", { class: "muted small" }, "Last verified: " + (e.last_verified || "—"))),
        el("div", { class: "meta-line" },
          e.supported ? el("a", { class: "btn ghost", href: `#/syllabus?exam=${e.id}` }, "Syllabus") : null,
          e.supported ? el("a", { class: "btn ghost", href: `#/overlap?exam=${e.id}` }, "Compare") : null,
          e.supported ? el("a", { class: "btn ghost", href: `#/practice?exam=${e.id}` }, "Practice") : null)));
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

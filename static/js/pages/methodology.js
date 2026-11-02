import { el, pageHead, badge } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Methodology & data quality",
    "How GovtExamMitra classifies overlap, what is verified, and what requires verification."));
  root.append(el("section", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Classification methodology"),
    el("ul", null,
      el("li", null, badge("EXACT_MATCH"), " — both examinations' official notifications name the same subject with materially identical wording (e.g. both list “Indian and World Geography”)."),
      el("li", null, badge("PARTIAL_OVERLAP"), " — the same general topic, but the official wording differs in scope or emphasis (e.g. UPSC pairs History with the Indian National Movement; CAPF lists only “History of India”)."),
      el("li", null, badge("RELATED_CONCEPT"), " — concepts connect but the syllabus requirements are not equivalent."),
      el("li", null, badge("EXAM_SPECIFIC"), " — established in one examination's official syllabus with no counterpart mapping in the other.")),
    el("h3", null, "Verification states"),
    el("ul", null,
      el("li", null, badge("VERIFIED_OFFICIAL"), " — wording quoted from an official UPSC notification, with source link and last-verified date."),
      el("li", null, badge("PENDING_VERIFICATION"), " — AI-derived micro-topic decomposition or mapping; includes confidence and rationale. Never treated as official."),
      el("li", null, badge("DEMONSTRATION"), " — sample questions authored for GovtExamMitra; never presented as official PYQs.")),
    el("h3", null, "What we never do"),
    el("ul", null,
      el("li", null, "Invent official syllabus wording, PYQs, notifications, dates or eligibility rules."),
      el("li", null, "Treat absence from a syllabus as proof a topic can never be asked."),
      el("li", null, "Present generated scores as official evaluations.")),
    el("h3", null, "API & production notes"),
    el("ul", null,
      el("li", null, "REST API versioned under /api/v1; interactive docs at /docs (OpenAPI)."),
      el("li", null, "Multi-user accounts with JWT sessions (30-day tokens); every personal endpoint enforces authentication and per-user data isolation — verified by automated tests."),
      el("li", null, "Rate limiting: 15 req/min on authentication, 120 req/min reads, 40 req/min writes (in-memory; use a shared store for multi-worker deployments)."),
      el("li", null, "Secrets live in environment variables only; nothing is committed."))));
}

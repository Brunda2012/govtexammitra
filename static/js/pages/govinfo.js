import { api } from "../api.js";
import { el, loading, errorState, pageHead, emptyState } from "../ui.js";

const DOC_TYPES = ["NOTIFICATION", "EXAM_ANNOUNCEMENT", "SYLLABUS", "QUESTION_PAPER", "ANSWER_KEY",
  "RESULT", "ADMIT_CARD", "CIRCULAR", "PRESS_RELEASE", "SCHEME", "CORRIGENDUM", "OTHER"];

const CLASS_LABEL = {
  AUTO_CLASSIFIED: "AI-classified · exam name found in official title",
  PENDING_REVIEW: "AI-suggested · awaiting admin review",
  ADMIN_APPROVED: "Admin verified",
};

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Government Information Centre",
    "Documents discovered automatically from registered official government sources. " +
    "Every record links to its original source; AI-extracted classifications are labelled until verified."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const [stats, exams] = await Promise.all([api.get("/gov/stats"), api.get("/exams")]);
    content.innerHTML = "";

    content.append(el("div", { class: "grid cols-4", style: "margin-bottom:16px" },
      stat(stats.sources_total, "registered official sources"),
      stat(stats.sources_enabled, "monitored"),
      stat(stats.documents, "documents ingested"),
      stat(stats.pending_review, "awaiting review")));

    const notice = el("div", { class: "notice warn small" },
      "Source attribution: every document links to the official government page it was collected from. ",
      "Publication dates appear only when the source provides them. ",
      "Extraction and exam-tagging are automated assistance — always confirm against the official document.");
    content.append(notice);
    content.append(el("div", { class: "hero-actions", style: "margin:10px 0 4px" },
      el("a", { class: "btn ghost", href: "#/current-affairs" }, "Current Affairs (from ingested releases) →"),
      el("a", { class: "btn ghost", href: "#/pyqs" }, "Previous-year questions →")));

    const listWrap = el("div", null, loading());
    content.append(listWrap);

    const state = { q: "", exam: "", doc_type: "", days: "" };
    async function refresh() {
      listWrap.innerHTML = "";
      listWrap.append(loading());
      try {
        const params = new URLSearchParams();
        if (state.q) params.set("q", state.q);
        if (state.exam) params.set("exam", state.exam);
        if (state.doc_type) params.set("doc_type", state.doc_type);
        if (state.days) params.set("days", state.days);
        params.set("limit", "25");
        const d = await api.get("/gov/documents?" + params.toString());
        listWrap.innerHTML = "";
        listWrap.append(el("div", { class: "muted small", style: "margin:4px 0 8px" },
          `${d.total} document${d.total === 1 ? "" : "s"} found`));
        if (!d.documents.length) {
          listWrap.append(emptyState("No documents match",
            "Adjust the filters, or check back after the next ingestion run."));
          return;
        }
        for (const doc of d.documents) listWrap.append(docCard(doc));
      } catch (err) {
        listWrap.innerHTML = "";
        listWrap.append(errorState(err, refresh));
      }
    }

    content.append(el("section", { class: "card" },
      el("div", { class: "filters", style: "display:flex;flex-wrap:wrap;gap:8px" },
        searchBox((v) => { state.q = v; refresh(); }),
        select("All exams", [{ v: "", t: "All exams" }].concat(
          exams.map((e) => ({ v: e.id, t: e.name }))), (v) => { state.exam = v; refresh(); }),
        select("All types", [{ v: "", t: "All document types" }].concat(
          DOC_TYPES.map((t) => ({ v: t, t: t.replaceAll("_", " ") }))), (v) => { state.doc_type = v; refresh(); }),
        select("Any time", [{ v: "", t: "Any time" }, { v: "7", t: "Last 7 days" },
          { v: "30", t: "Last 30 days" }, { v: "90", t: "Last 90 days" }], (v) => { state.days = v; refresh(); }))));

    await refresh();
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

function stat(n, lbl) {
  return el("div", { class: "stat accent" }, el("div", { class: "num" }, n), el("div", { class: "lbl" }, lbl));
}

function searchBox(onInput) {
  const inp = el("input", { type: "search", placeholder: "Search documents…",
    style: "flex:1;min-width:180px;padding:8px 12px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg-soft);color:var(--text)" });
  let t = null;
  inp.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(() => onInput(inp.value.trim()), 400);
  });
  return inp;
}

function select(def, opts, onChange) {
  const s = el("select", {
    style: "padding:8px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg-soft);color:var(--text)",
    onchange: () => onChange(s.value),
  }, opts.map((o) => el("option", { value: o.v }, o.t)));
  return s;
}

function docCard(doc) {
  const cls = CLASS_LABEL[doc.classification_status] || doc.classification_status;
  const card = el("section", { class: "card" },
    el("div", { style: "display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap" },
      el("h3", { style: "margin:0;font-size:1.02rem" }, doc.title),
      el("span", { class: "soon-tag" }, doc.doc_type.replaceAll("_", " "))),
    el("div", { class: "muted small", style: "margin:6px 0" },
      doc.organisation, " · via ", doc.source_name),
    el("div", { class: "muted small" },
      "Published: ", doc.published_at || "not stated by source",
      " · Collected: ", (doc.collected_at || "").slice(0, 10),
      doc.version > 1 ? ` · v${doc.version} (updated)` : ""),
    doc.exam_ids.length
      ? el("div", { style: "margin:8px 0" }, doc.exam_ids.map((x) =>
          el("span", { class: "badge", style: "margin-right:6px" }, x.toUpperCase())))
      : null,
    el("div", { class: "muted small", style: "margin:4px 0" }, "⚠ ", cls));
  const detailBtn = el("button", { class: "btn ghost small", style: "margin-top:8px" }, "Extracted text");
  detailBtn.addEventListener("click", async () => {
    if (card.querySelector(".gov-extract")) {
      card.querySelector(".gov-extract").remove();
      return;
    }
    detailBtn.textContent = "Loading…";
    try {
      const d = await api.get(`/gov/documents/${doc.id}`);
      const pre = el("div", { class: "gov-extract notice", style: "margin-top:10px;max-height:260px;overflow:auto;white-space:pre-wrap;font-size:0.8rem" },
        d.extracted_text ? d.extracted_text.slice(0, 6000) : "(No text extracted — open the original source.)");
      card.append(pre);
    } catch (err) {
      card.append(el("div", { class: "gov-extract notice warn", style: "margin-top:10px" }, String(err.message || err)));
    }
    detailBtn.textContent = "Extracted text";
  });
  card.append(el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;align-items:center" },
    detailBtn,
    el("a", { class: "btn accent small", href: doc.url, target: "_blank", rel: "noopener noreferrer" },
      "Official source ↗")));
  return card;
}

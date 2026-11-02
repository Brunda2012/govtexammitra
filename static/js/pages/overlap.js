import { api } from "../api.js";
import { el, badge, loading, emptyState, errorState, pageHead } from "../ui.js";

const EXAMS = [
  { id: "upsc-cse", label: "UPSC Civil Services" },
  { id: "capf-ac", label: "CAPF Assistant Commandant" },
  { id: "ssc-cgl", label: "SSC CGL" },
  { id: "cds", label: "CDS" },
  { id: "nda", label: "NDA" },
];
const CLASSES = ["EXACT_MATCH", "PARTIAL_OVERLAP", "RELATED_CONCEPT"];

const state = { a: "upsc-cse", b: "capf-ac", cls: null, group: null, q: "", data: null };

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Exam Overlap Intelligence",
    "Compare examinations at subject, topic and micro-topic level. Official syllabus wording is quoted from UPSC notifications; " +
    "micro-topic mappings are AI-derived, confidence-scored and labelled for verification."));

  const controls = el("div", { class: "compare-controls" });
  const selA = examSelect("selA", state.a);
  const selB = examSelect("selB", state.b);
  const search = el("input", { type: "search", placeholder: "Search topics…", value: state.q, "aria-label": "Search topics" });
  const swapBtn = el("button", { class: "btn ghost", onclick: () => { [state.a, state.b] = [state.b, state.a]; render(root); } }, "⇄ Swap");
  controls.append(el("label", null, "Examination A", selA),
    swapBtn,
    el("label", null, "Examination B", selB),
    el("label", { style: "flex:1;min-width:180px" }, "Search", search));
  root.append(controls);

  const content = el("div", null, loading());
  root.append(content);

  async function load() {
    if (state.a === state.b) {
      content.innerHTML = "";
      content.append(emptyState("Pick two different examinations", "Select two exams to compare."));
      return;
    }
    content.innerHTML = "";
    content.append(loading());
    try {
      const params = new URLSearchParams();
      if (state.cls) params.set("classification", state.cls);
      if (state.group) params.set("group", state.group);
      if (state.q) params.set("q", state.q);
      state.data = await api.get(`/overlap/${state.a}/${state.b}?` + params.toString());
      draw();
    } catch (err) {
      content.innerHTML = "";
      content.append(errorState(err, load));
    }
  }

  function draw() {
    const d = state.data;
    const s = d.stats;
    content.innerHTML = "";

    content.append(el("div", { class: "grid cols-4" },
      stat(s.compared_pairs, "Mapped pairs"),
      stat(s.exact_match, "Exact overlap", "accent"),
      stat(s.partial_overlap, "Partial overlap"),
      stat(s.related_concept, "Related concepts"),
      stat(s.exam_a_specific, `${shortName(state.a)}-specific`),
      stat(s.exam_b_specific, `${shortName(state.b)}-specific`)));

    const pills = el("div", { class: "pillbar", role: "group", "aria-label": "Filter by classification" });
    pills.append(pill("All", null, !state.cls && !state.group, () => { state.cls = null; state.group = null; load(); }));
    for (const c of CLASSES) pills.append(pill(c.replaceAll("_", " "), c, state.cls === c, () => { state.cls = state.cls === c ? null : c; state.group = null; load(); }));
    for (const g of (state.data.groups || [])) {
      pills.append(pill("Subject: " + g.group_key.replaceAll("_", " "), g.group_key, state.group === g.group_key, () => { state.group = state.group === g.group_key ? null : g.group_key; state.cls = null; load(); }));
    }
    content.append(pills);
    content.append(el("div", { class: "notice" },
      "How to read this: ", badge("EXACT MATCH"), " — same official coverage, study once. ",
      badge("PARTIAL OVERLAP"), " — same topic, different depth: check the depth notes for each exam. ",
      badge("RELATED CONCEPT"), " / ", badge("EXAM SPECIFIC"), " — prepare separately. Absence from a syllabus is not proof a topic can never be asked."));

    if (!d.groups.length) {
      content.append(emptyState("No matching topics", "Try clearing filters or the search box."));
      return;
    }
    for (const g of d.groups) {
      const wrap = el("section", { class: "subject-group" }, el("h3", null, g.group_key.replaceAll("_", " ")));
      for (const p of g.items) wrap.append(pairRow(p));
      for (const sp of g.specific_a) wrap.append(specificRow(sp, state.a));
      for (const sp of g.specific_b) wrap.append(specificRow(sp, state.b));
      content.append(wrap);
    }
  }

  function pairRow(p) {
    const detail = el("div", { class: "pair-detail" },
      el("div", { class: "vs-grid" },
        el("div", { class: "vs-col" },
          el("h4", null, `${p.stage_a} · ${p.paper_a} — ${p.subject_a}`),
          el("div", { class: "official-label" }, "Official syllabus wording"),
          el("div", { class: "official" }, `“${p.official_a}”`),
          el("div", { class: "muted" }, `Topic: ${p.name_a}`),
          p.map_note_a || p.note_a ? el("div", { class: "muted small" }, `Depth note: ${p.map_note_a || p.note_a}`) : null),
        el("div", { class: "vs-col" },
          el("h4", null, `${p.stage_b} · ${p.paper_b} — ${p.subject_b}`),
          el("div", { class: "official-label" }, "Official syllabus wording"),
          el("div", { class: "official" }, `“${p.official_b}”`),
          el("div", { class: "muted" }, `Topic: ${p.name_b}`),
          p.map_note_b || p.note_b ? el("div", { class: "muted small" }, `Depth note: ${p.map_note_b || p.note_b}`) : null)),
      el("div", { class: "meta-line" },
        badge(p.verification_status),
        el("span", { class: "muted small" }, `AI-mapped confidence ${(p.confidence * 100).toFixed(0)}%`),
        p.source_url ? el("a", { href: p.source_url, target: "_blank", rel: "noopener", class: "small" }, "Official source") : null,
        el("span", { class: "muted small" }, `Last verified: ${p.last_verified || "—"}`)),
      el("p", { class: "muted small", style: "margin:8px 0 0" }, p.rationale));
    const row = el("div", { class: "pair-row" });
    const head = el("button", { class: "pair-summary", "aria-expanded": "false",
      onclick: () => { row.classList.toggle("open"); head.setAttribute("aria-expanded", row.classList.contains("open")); } },
      badge(p.classification),
      el("span", { class: "topic" }, `${p.name_a} ⟷ ${p.name_b}`),
      el("span", { class: "arrow" }, "▸"));
    row.append(head, detail);
    return row;
  }

  function specificRow(sp, examId) {
    const row = el("div", { class: "pair-row" });
    const head = el("button", { class: "pair-summary", "aria-expanded": "false",
      onclick: () => { row.classList.toggle("open"); head.setAttribute("aria-expanded", row.classList.contains("open")); } },
      badge(sp.classification),
      el("span", { class: "topic" }, `${sp.name} — ${examId === state.a ? "exam A only" : "exam B only"}`),
      el("span", { class: "arrow" }, "▸"));
    row.append(head, el("div", { class: "pair-detail" },
      el("div", { class: "notice" }, `Mapped to ${sp.stage} · ${sp.paper} under subject “${sp.subject_name}”. ` +
        "Not established in the other examination's syllabus; absence of a reference is not proof it can never be asked."),
      el("div", { class: "meta-line" }, badge("PENDING_VERIFICATION"))));
    return row;
  }

  function stat(num, lbl, cls = "") {
    return el("div", { class: `stat ${cls}` }, el("div", { class: "num" }, num), el("div", { class: "lbl" }, lbl));
  }
  function pill(label, key, active, onclick) {
    return el("button", { class: "pill" + (active ? " active" : ""), onclick }, label);
  }

  selA.addEventListener("change", () => { state.a = selA.value; load(); });
  selB.addEventListener("change", () => { state.b = selB.value; load(); });
  let t;
  search.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(() => { state.q = search.value.trim(); load(); }, 300);
  });

  await load();
}

function examSelect(id, value) {
  const s = el("select", { id, "aria-label": id });
  for (const e of EXAMS) s.append(el("option", { value: e.id }, e.label));
  s.value = value;
  return s;
}

function shortName(id) {
  const e = EXAMS.find((x) => x.id === id);
  return e ? e.label.split(" ")[0] : id;
}

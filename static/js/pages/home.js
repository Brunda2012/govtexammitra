// Homepage — what this platform is, who it is for, and how to start.
// First-time visitors land here instead of an app dashboard.
import { api } from "../api.js";
import { store } from "../store.js";
import { device } from "../device.js";
import { el, badge, loading, errorState, progressbar } from "../ui.js";

const STEPS = [
  { key: "pick", n: 1, title: "Pick your examination", href: "#/exams", hint: "UPSC CSE and CAPF AC are fully supported today; more are catalogued." },
  { key: "syllabus", n: 2, title: "Read the real syllabus", href: "#/syllabus", hint: "Official wording per subject, decomposed into trackable micro-topics." },
  { key: "overlap", n: 3, title: "Compare overlapping exams", href: "#/overlap", hint: "Study once for both — see exactly what transfers and what needs extra depth." },
  { key: "practice", n: 4, title: "Answer practice questions", href: "#/practice", hint: "Negative marking applied exactly as per the verified scheme." },
  { key: "plan", n: 5, title: "Generate your study plan", href: "#/planner", hint: "Shared topics first, exam-specific depth second." },
  { key: "track", n: 6, title: "Track progress & revise", href: "#/dashboard", hint: "Analytics, weak-topic detection and the revision queue." },
];

export async function render(root) {
  root.innerHTML = "";
  root.append(el("div", { class: "home-hero" },
    el("div", { class: "hero-inner" },
      el("span", { class: "badge VERIFIED_OFFICIAL" }, "BUILT ON OFFICIAL DATA"),
      el("h1", null, "One platform. Multiple exams. Smarter preparation."),
      el("p", { class: "hero-sub" },
        "GovtExamMitra prepares you for India's central government examinations using only official syllabus data — ",
        "and tells you honestly what is verified, what is AI-derived, and what is not ready yet."),
      el("div", { class: "hero-actions" },
        el("a", { class: "btn accent", href: "#/syllabus" }, "Start your preparation →"),
        el("a", { class: "btn ghost", href: "#/overlap" }, "See Overlap Intelligence")))));

  // what it is / who it is for
  root.append(el("div", { class: "grid cols-3" },
    feature("Built on official notifications",
      "Subject wording comes from UPSC notifications, marked VERIFIED_OFFICIAL with the source and date attached. Nothing invented, nothing paraphrased into fake officialdom."),
    feature("Micro-topic precision",
      "Each syllabus line is decomposed into micro-topics so progress, weakness and overlap are tracked at the exact granularity you study at."),
    feature("Data honesty as a feature",
      "Every screen labels its data source. AI-derived items are labelled, unverified items are labelled, and un-built features say PLANNED instead of pretending.")));

  // supported exams
  const content = el("div", null, loading());
  root.append(el("h2", { class: "home-h2" }, "Supported examinations"), content);
  try {
    const exams = await api.get("/exams");
    const supported = exams.filter((e) => e.supported);
    const planned = exams.filter((e) => !e.supported);
    content.innerHTML = "";
    for (const e of supported) {
      content.append(el("section", { class: "card exam-card" },
        el("div", { class: "meta-line" }, badge(e.verification_status),
          el("span", { class: "muted small" }, e.authority)),
        el("h3", { style: "margin:6px 0 2px" }, e.name),
        el("p", { class: "muted", style: "margin:4px 0 10px" }, e.description || ""),
        el("div", { class: "muted small" },
          `Stages: ${(e.stages_json || []).join(" · ") || "—"}`),
        el("div", { class: "hero-actions", style: "margin-top:12px" },
          el("a", { class: "btn accent", href: `#/syllabus?exam=${e.id}` }, "Open syllabus"),
          e.id === "upsc-cse" ? el("a", { class: "btn ghost", href: "#/overlap" }, "Compare with CAPF AC") : null)));
    }
    if (planned.length) {
      content.append(el("section", { class: "card" },
        el("h3", { style: "margin-top:0" }, "Catalogued for the future"),
        el("p", { class: "muted" },
          "Tracked with honest PENDING_VERIFICATION status until their official syllabus is extracted and verified: "
          + planned.map((e) => e.name).join("; ") + ".")));
    }

    // onboarding checklist
    const checklist = buildChecklist();
    if (checklist) {
      const box = el("section", { class: "card onboarding" },
        el("div", { class: "onboard-head" },
          el("h3", { style: "margin:0" }, "Getting started — 6 steps"),
          el("button", { class: "pill", onclick: () => { device.checklistDismiss(); box.remove(); } }, "Dismiss")),
        el("ol", { class: "onboard-steps" },
          checklist.map((st) => el("li", { class: st.done ? "done" : "" },
            el("a", { href: st.href, onclick: () => device.checklistStep(st.key) }, `${st.n}. ${st.title}`),
            el("div", { class: "muted small" }, st.hint),
            st.done ? el("span", { class: "badge EXACT_MATCH" }, "DONE") : null))));
      root.prepend(box);
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

function buildChecklist() {
  const steps = device.checklist(STEPS);
  return steps;
}

function feature(title, text) {
  return el("section", { class: "card" }, el("h3", { style: "margin-top:0" }, title),
    el("p", { class: "muted" }, text));
}

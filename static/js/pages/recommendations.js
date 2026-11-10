// Learning Recommendations — rules over coverage, weak topics, overlap propagation
// and the planner. Every suggestion shows its reason.
import { api } from "../api.js";
import { store } from "../store.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";
const RULE_BADGE = { WEAK_TOPIC: "EXAM_SPECIFIC", COVERAGE_GAP: "INFO", OVERLAP_LEVERAGE: "EXACT_MATCH",
                     PLANNER_NEXT: "PENDING_VERIFICATION", KEEP_STREAK: "SECONDARY_SOURCE" };
const ACTION = { practice: ["#/practice", "Open practice"], syllabus: ["#/syllabus", "Open syllabus"],
                 planner: ["#/planner", "Open planner"] };

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Learning Recommendations",
    "What to study next, computed from your own progress, weak topics, overlap mappings and planner. The reason for every recommendation is shown — nothing is ranked by vibes."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const exams = (await api.get("/exams")).filter((e) => e.supported);
    const sel = el("select", { "aria-label": "Choose examination" });
    for (const e of exams) sel.append(el("option", { value: e.id }, e.name));
    sel.value = selected;
    sel.addEventListener("change", () => { selected = sel.value; localStorage.setItem("gm.exam", selected); load(content); });
    const pairSel = el("select", { "aria-label": "Paired examination" });
    for (const e of exams) pairSel.append(el("option", { value: e.id }, e.name));
    if (pairSel.querySelector(`option[value="capf-ac"]`)) pairSel.value = "capf-ac";
    root.append(el("div", { class: "compare-controls" },
      el("label", null, "Examination", sel),
      el("label", null, "Paired exam (overlap rules)", pairSel)));
    pairSel.addEventListener("change", () => load(content));
    await load(content, pairSel.value);
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

async function load(content, pair) {
  content.innerHTML = "";
  content.append(loading());
  try {
    const data = await store.get(`/recommendations/${selected}`, { pair });
    content.innerHTML = "";
    if (data.note) content.append(el("div", { class: "notice", style: "margin-bottom:12px" }, data.note));
    if (!data.recommendations.length) {
      content.append(el("div", { class: "state-box" },
        el("div", { class: "big" }, "No recommendations yet"),
        el("div", null, "Answer practice questions and mark syllabus topics — recommendations build from your data.")));
    }
    for (const r of data.recommendations) {
      const [href, label] = ACTION[r.action] || ["#/dashboard", "Open"];
      content.append(el("section", { class: "card" },
        el("div", { class: "meta-line" },
          el("span", { class: "badge " + (RULE_BADGE[r.rule] || "INFO") }, r.rule.replaceAll("_", " ")),
          el("span", { class: "muted small" }, `priority ${r.priority}`)),
        el("h3", { style: "margin:6px 0 4px" }, r.title),
        el("p", { class: "muted", style: "margin:4px 0 10px" }, "Why: " + r.reason),
        el("a", { class: "btn accent", href }, label)));
    }
    if (data.stored_on_server === false) {
      content.append(el("p", { class: "muted small" },
        "Device mode: these rules ran against data saved on this device only."));
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content, pair)));
  }
}

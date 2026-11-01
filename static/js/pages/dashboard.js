import { api } from "../api.js";
import { el, badge, loading, errorState, pageHead, progressbar } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Your preparation overview",
    "Progress recorded on this device (local user). Multi-user accounts arrive in the next milestone."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const d = await api.get("/dashboard");
    content.innerHTML = "";

    const hero = el("section", { class: "card" },
      el("h2", { style: "margin-top:0" }, "Exam Overlap Intelligence"),
      el("p", { class: "muted" }, "The flagship capability: know what to study once for multiple exams, and where extra depth is needed."),
      d.overlap_summary
        ? el("div", { class: "grid cols-4", style: "margin-top:12px" },
            miniStat(d.overlap_summary.compared_pairs, "mapped topic pairs"),
            miniStat(d.overlap_summary.exact_match, "exact overlaps"),
            miniStat(d.overlap_summary.partial_overlap, "partial overlaps"),
            miniStat(d.overlap_summary.related_concept, "related concepts"))
        : el("div", { class: "notice warn" }, "Overlap data not available yet."),
      el("a", { class: "btn accent", style: "margin-top:14px", href: "#/overlap" }, "Open comparison →"));
    content.append(hero);

    for (const e of d.exams) {
      const p = e.progress;
      content.append(el("section", { class: "card" },
        el("h3", { style: "margin:0 0 4px" }, e.name),
        el("div", { class: "muted small" }, e.authority),
        el("div", { style: "margin:10px 0 6px" }, progressbar(p.completion_pct)),
        el("div", { class: "muted small" },
          `${p.completed}/${p.total} micro-topics completed · ${p.in_progress} in progress (${p.completion_pct}%)`),
        el("a", { href: `#/syllabus?exam=${e.id}`, class: "small" }, "Browse syllabus →")));
    }

    content.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Pending tasks"),
      d.pending_tasks.length
        ? el("ul", null, d.pending_tasks.map((t) => el("li", null, t.title)))
        : el("p", { class: "muted" }, "No pending tasks. Generate a combined study plan from the Planner."),
      el("a", { href: "#/planner", class: "btn ghost" }, "Open planner")));
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

function miniStat(n, lbl) {
  return el("div", { class: "stat accent" }, el("div", { class: "num" }, n), el("div", { class: "lbl" }, lbl));
}

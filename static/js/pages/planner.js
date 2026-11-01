import { api } from "../api.js";
import { el, badge, loading, emptyState, errorState, pageHead } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Combined preparation planner",
    "A merged, de-duplicated sequence across two exams: shared topics first (exact overlaps before partials), then exam-specific topics. " +
    "Generating tasks creates planner entries; nothing is auto-marked complete."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const plan = await api.get("/plan/upsc-cse/capf-ac");
    content.innerHTML = "";
    const genBtn = el("button", { class: "btn accent", onclick: async () => {
      genBtn.disabled = true;
      try {
        const res = await api.post("/plan/upsc-cse/capf-ac/generate", {});
        note.innerHTML = "";
        note.append(el("div", { class: "notice" }, `${res.created} tasks created. Open the task list below.`));
        loadTasks();
      } catch (err) {
        note.innerHTML = "";
        note.append(el("div", { class: "notice bad" }, err.message));
      }
      genBtn.disabled = false;
    } }, "Generate study tasks from top pending topics");
    const note = el("div", null);
    content.append(el("div", { class: "card" }, genBtn, note));

    if (!plan.items.length) {
      content.append(emptyState("No plan items", "Add overlap mappings to build a plan."));
      return;
    }
    for (const it of plan.items) content.append(planCard(it));
    const tasksBox = el("section", { class: "card" }, el("h3", { style: "margin-top:0" }, "Your tasks"));
    content.append(tasksBox);
    loadTasks(tasksBox);
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

function planCard(it) {
  const shared = it.kind === "SHARED";
  const statusLine = shared
    ? `UPSC: ${it.status_a} (${it.mastery_a}%) · CAPF: ${it.status_b} (${it.mastery_b}%)`
    : `${(it.topic_a || it.topic_b)} — ${it.status_a === "COMPLETED" || it.status_b === "COMPLETED" ? "COMPLETED" : "NOT_STARTED"}`;
  return el("section", { class: "card" },
    el("div", { class: "meta-line" },
      badge(it.classification),
      shared ? el("span", { class: "badge INFO" }, "STUDY ONCE") : null,
      el("span", { class: "muted small" }, it.question_count + " linked question(s)"),
      it.confidence != null ? el("span", { class: "muted small" }, `confidence ${(it.confidence * 100).toFixed(0)}%`) : null),
    el("h3", { style: "margin:8px 0 2px" }, shared ? `${it.topic_a}` : (it.topic_a || it.topic_b)),
    shared ? el("div", { class: "muted small" }, `${it.exam_a} (${it.stage_a} · ${it.paper_a}) ⟷ ${it.exam_b} (${it.stage_b} · ${it.paper_b})`) : null,
    el("p", { class: "muted", style: "margin:8px 0" }, it.rationale),
    it.extra_depth_a || it.extra_depth_b
      ? el("div", { class: "notice warn small" },
          it.extra_depth_a ? `Extra depth for exam A: ${it.extra_depth_a}. ` : "",
          it.extra_depth_b ? `Extra depth for exam B: ${it.extra_depth_b}.` : "")
      : null,
    el("div", { class: "muted small" }, statusLine));
}

async function loadTasks(box) {
  try {
    const data = await api.get("/tasks");
    box.innerHTML = "";
    box.append(el("h3", { style: "margin-top:0" }, "Your tasks"));
    if (!data.tasks.length) {
      box.append(el("p", { class: "muted" }, "No tasks yet. Use the generate button above."));
      return;
    }
    const tbl = el("table", { class: "data" },
      el("thead", null, el("tr", null, el("th", null, "Task"), el("th", null, "Exams"), el("th", null, "Status"), el("th", null, ""))));
    const body = el("tbody");
    for (const t of data.tasks) {
      const tr = el("tr", null,
        el("td", null, el("strong", null, t.title), el("div", { class: "muted small" }, t.detail || "")),
        el("td", { class: "small" }, (t.exam_ids_json || []).join(", ")),
        el("td", null, el("span", { class: "badge " + (t.status === "DONE" ? "VERIFIED_OFFICIAL" : "INFO") }, t.status)));
      if (t.status === "PENDING") {
        tr.append(el("td", null, el("button", { class: "btn ghost", onclick: async () => {
          await api.post(`/tasks/${t.id}/complete`);
          loadTasks(box);
        } }, "Mark done")));
      } else tr.append(el("td"));
      body.append(tr);
    }
    tbl.append(body);
    box.append(tbl);
  } catch (err) {
    box.append(el("div", { class: "notice bad" }, "Could not load tasks: " + err.message));
  }
}

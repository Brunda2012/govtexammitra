// Mind Maps — subject → micro-topic hierarchy rendered from the real database,
// progress-coloured when you're signed in (or via device-mode progress).
import { api } from "../api.js";
import { store } from "../store.js";
import { device } from "../device.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";

const STATUS_COLOR = { COMPLETED: "var(--ok, #2e7d32)", IN_PROGRESS: "#c98a00", NOT_STARTED: "var(--line, #c9d2e0)" };

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Mind Maps",
    "The real subject → micro-topic hierarchy from the database. Node colour shows your progress: green completed, amber in progress, grey not started."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const exams = (await api.get("/exams")).filter((e) => e.supported);
    const sel = el("select", { "aria-label": "Choose examination" });
    for (const e of exams) sel.append(el("option", { value: e.id }, e.name));
    sel.value = selected;
    sel.addEventListener("change", () => { selected = sel.value; localStorage.setItem("gm.exam", selected); load(content); });
    root.append(el("div", { class: "compare-controls" }, el("label", null, "Examination", sel)));
    await load(content);
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

async function load(content) {
  content.innerHTML = "";
  content.append(loading());
  try {
    const data = await api.get(`/mindmap/${selected}`);
    // merge device-mode progress when signed out
    let local = {};
    if (device.active()) {
      const pl = (await store.get("/progress")).progress;
      local = Object.fromEntries(pl.map((p) => [p.micro_topic_id, p]));
    }
    content.innerHTML = "";
    for (const s of data.subjects) {
      const bar = el("div", { class: "progressbar", role: "progressbar", "aria-valuenow": s.completion_pct },
        el("div", { style: `width:${s.completion_pct}%` }));
      const details = el("details", { class: "card mindmap-card" },
        el("summary", { style: "cursor:pointer;display:flex;gap:10px;align-items:center;flex-wrap:wrap" },
          el("strong", null, s.name),
          el("span", { class: "muted small" }, `${s.stage} · ${s.paper}`),
          el("span", { class: "muted small" }, `${s.completion_pct}% complete`)),
        el("div", { style: "padding:0 16px 14px" },
          bar,
          el("div", { class: "mm-children", style: "margin-top:12px" },
            s.children.map((m) => {
              const st = local[m.id]?.status || m.status;
              const col = STATUS_COLOR[st] || STATUS_COLOR.NOT_STARTED;
              return el("div", { class: "mm-node" },
                el("span", { class: "mm-dot", style: `background:${col}` }),
                el("a", { href: `#/notes?topic=${m.id}` }, m.name),
                el("span", { class: "muted small" },
                  `${st.replace("_", " ").toLowerCase()} · mastery ${local[m.id]?.mastery ?? m.mastery}%`
                  + (m.questions ? ` · ${m.questions} q(s)` : "")));
            }))));
      content.append(details);
    }
    content.append(el("p", { class: "muted small" }, data.note));
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

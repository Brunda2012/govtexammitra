// Current Affairs — sourced items from ingested official releases (PIB etc.),
// every item linked to its origin, filtered by exam relevance.
import { api } from "../api.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

let selected = "";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Current affairs",
    "Items come from ingested official releases. Every item links to its originating document; nothing is presented as important without a reason tied to a source."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const exams = (await api.get("/exams")).filter((e) => e.supported);
    const sel = el("select", { "aria-label": "Filter by examination" });
    sel.append(el("option", { value: "" }, "All examinations"));
    for (const e of exams) sel.append(el("option", { value: e.id }, e.name));
    sel.value = selected;
    sel.addEventListener("change", () => { selected = sel.value; load(content); });
    root.append(el("div", { class: "compare-controls" }, el("label", null, "Relevant to", sel)));
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
    const data = await api.get(`/current-affairs${selected ? `?exam=${selected}` : ""}`);
    content.innerHTML = "";
    content.append(el("p", { class: "muted small" }, data.note));
    if (!data.items.length) {
      content.append(el("div", { class: "state-box" },
        el("div", { class: "big" }, "No sourced items yet"),
        el("div", null, "Add official news sources (e.g. PIB) in the Government Information Centre — ingested releases appear here with full attribution."),
        el("a", { class: "btn ghost", style: "margin-top:12px", href: "#/govinfo" }, "Open Government Information Centre")));
      return;
    }
    for (const it of data.items) {
      content.append(el("section", { class: "card" },
        el("div", { class: "meta-line" },
          badge(it.doc_type),
          el("span", { class: "muted small" }, `${it.organisation} · ${it.published_at || it.collected_at || "date not stated"}`)),
        el("h3", { style: "margin:6px 0 2px" },
          el("a", { href: it.url, target: "_blank", rel: "noopener" }, it.title)),
        el("div", { class: "muted small" },
          `Source: ${it.source_name}${it.exam_ids.length ? " · relevant to: " + it.exam_ids.join(", ") : ""}`)));
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

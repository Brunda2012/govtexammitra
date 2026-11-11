// Bookmarks — saved topics, questions and planner tasks. One-click save from
// syllabus / practice / planner; device mode stores locally.
import { store } from "../store.js";
import { el, emptyState, errorState, pageHead, loading } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Bookmarks",
    "References to real entities — topics, questions, planner tasks. Nothing orphaned: if the underlying entity disappears, the bookmark is cleaned up."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const data = await store.get("/bookmarks");
    content.innerHTML = "";
    if (!data.bookmarks.length) {
      content.append(emptyState("No bookmarks yet",
        "Use the Bookmark button in the syllabus, or save questions from practice."));
      return;
    }
    const KIND_LABEL = { TOPIC: "Micro-topic", QUESTION: "Question", TASK: "Planner task" };
    const tbl = el("table", { class: "data" },
      el("thead", null, el("tr", null, el("th", null, "Item"), el("th", null, "Type"), el("th", null, "Saved"), el("th", null, ""))));
    const body = el("tbody");
    for (const b of data.bookmarks) {
      const tr = el("tr", null,
        el("td", null, b.label || b.ref_id),
        el("td", { class: "small" }, KIND_LABEL[b.kind] || b.kind),
        el("td", { class: "small" }, (b.created_at || "").slice(0, 16)));
      tr.append(el("td", null, el("button", { class: "btn ghost", onclick: async () => {
        await store.del(`/bookmarks/${b.kind}/${encodeURIComponent(b.ref_id)}`);
        render(root);
      } }, "Remove")));
      body.append(tr);
    }
    tbl.append(body);
    content.append(el("section", { class: "card" }, tbl));
    if (localStorage.getItem("gm.token") === null) {
      content.append(el("p", { class: "muted small" },
        "Device mode: bookmarks are saved on this device only. Create an account to carry them across devices."));
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

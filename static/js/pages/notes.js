// Notes — per micro-topic notes, attached to the real topic ID so they surface
// wherever the topic appears. Device mode stores locally; accounts store server-side.
import { api } from "../api.js";
import { store } from "../store.js";
import { el, loading, errorState, pageHead } from "../ui.js";

export async function render(root, query) {
  root.innerHTML = "";
  root.append(pageHead("Topic-wise notes",
    "Notes are attached to the exact micro-topic, so they appear wherever that topic appears — syllabus, revision, mind maps. Private to you (or to this device in testing mode)."));
  const content = el("div", null, loading());
  root.append(content);
  const focus = query && query.get ? query.get("topic") : null;
  try {
    const [all, exams] = await Promise.all([
      store.get("/notes"),
      api.get("/exams"),
    ]);
    const supported = exams.filter((e) => e.supported);
    content.innerHTML = "";

    const sel = el("select", { "aria-label": "Choose examination for a new note" });
    for (const e of supported) sel.append(el("option", { value: e.id }, e.name));

    // new / edit note picker
    const topicSel = el("select", { "aria-label": "Micro-topic" });
    async function fillTopics() {
      const syl = await api.get(`/syllabus/${sel.value}`);
      topicSel.innerHTML = "";
      for (const m of syl.micro_topics) topicSel.append(el("option", { value: m.id }, m.name));
      if (focus && syl.micro_topics.some((m) => String(m.id) === focus)) topicSel.value = focus;
      loadEditor();
    }
    sel.addEventListener("change", () => fillTopics());

    const ta = el("textarea", { class: "mains-input", rows: "8", placeholder: "Write your note for this micro-topic…" });
    const status = el("div");
    const saveBtn = el("button", { class: "btn accent", onclick: async () => {
      const mid = topicSel.value;
      if (!mid) { status.innerHTML = ""; status.append(el("div", { class: "notice bad" }, "Choose a micro-topic first.")); return; }
      try {
        await store.put(`/notes/${mid}`, { body: ta.value }, { topicName: topicSel.selectedOptions[0].textContent });
        status.innerHTML = "";
        status.append(el("div", { class: "notice" }, "Note saved. Saved on " + (localStorage.getItem("gm.token") ? "your account." : "this device only (testing mode).")));
        await renderList(listBox);
      } catch (err) {
        status.innerHTML = "";
        status.append(el("div", { class: "notice bad" }, err.message));
      }
    } }, "Save note");
    const delBtn = el("button", { class: "btn ghost", onclick: async () => {
      const mid = topicSel.value;
      if (!mid) return;
      await store.del(`/notes/${mid}`);
      ta.value = "";
      status.innerHTML = "";
      status.append(el("div", { class: "notice" }, "Note deleted."));
      await renderList(listBox);
    } }, "Delete note");

    async function loadEditor() {
      const mid = topicSel.value;
      if (!mid) return;
      try {
        const n = await store.get(`/notes/${mid}`);
        ta.value = n.body || "";
      } catch { ta.value = ""; }
    }
    topicSel.addEventListener("change", loadEditor);

    content.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, focus ? "Write / edit note" : "Write a note"),
      el("div", { class: "compare-controls" },
        el("label", null, "Examination", sel),
        el("label", null, "Micro-topic", topicSel)),
      ta, status,
      el("div", { class: "hero-actions", style: "margin-top:10px" }, saveBtn, delBtn)));

    const listBox = el("div");
    content.append(el("h2", { class: "home-h2" }, "All your notes"), listBox);
    await renderList(listBox);

    await fillTopics();
    if (focus) await loadEditor();
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root, query)));
  }
}

async function renderList(box) {
  box.innerHTML = "";
  const data = await store.get("/notes");
  if (!data.notes.length) {
    box.append(el("p", { class: "muted" }, "No notes yet. Pick a micro-topic above and start writing."));
    return;
  }
  for (const n of data.notes) {
    box.append(el("section", { class: "card" },
      el("div", { class: "meta-line" },
        el("strong", null, n.topic_name || ("Topic #" + n.micro_topic_id)),
        el("span", { class: "muted small" }, `${n.exam_id || ""} · updated ${n.updated_at}`)),
      el("p", { style: "white-space:pre-wrap;margin:6px 0 0" }, n.body)));
  }
}

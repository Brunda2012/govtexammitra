// Flashcards — two-sided cards generated from the verified syllabus decomposition.
// Review scheduling shares the Revision Centre's due computation.
import { api } from "../api.js";
import { store } from "../store.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Flashcards",
    "Auto-generated from the same verified syllabus decomposition used everywhere — subject wording official, micro-topics AI-derived. Scheduling shares the Revision Centre queue."));
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
    const data = await api.get(`/flashcards/${selected}`);
    const dueIds = await deviceDue();
    content.innerHTML = "";
    content.append(el("p", { class: "muted small" }, `${data.cards.length} cards. ${data.scheduled ? "Cards due in your revision queue appear first." : "Sign in to schedule reviews — or just flip through."}`));
    const box = el("div", { class: "flash-wrap" });
    content.append(box);
    let i = 0;
    const cards = data.cards.slice();
    if (dueIds) cards.sort((a, b) => (dueIds.has(b.micro_topic_id) ? 1 : 0) - (dueIds.has(a.micro_topic_id) ? 1 : 0));
    const cardBox = el("div");
    const nav = el("div", { class: "hero-actions" });
    box.append(el("p", { class: "muted small", id: "fc-counter" }), cardBox, nav);
    function show(n) {
      i = (n + cards.length) % cards.length;
      const c = cards[i];
      box.querySelector("#fc-counter").textContent = `Card ${i + 1} of ${cards.length}` + (dueIds && dueIds.has(c.micro_topic_id) ? " — DUE in your revision queue" : "");
      cardBox.innerHTML = "";
      const front = el("div", { class: "flashcard", tabindex: "0", role: "button",
        "aria-label": "Flashcard — activate to flip", onclick: () => flip() },
        el("div", { class: "fc-side fc-front" },
          el("div", { class: "muted small" }, c.back.subject + " · " + c.back.paper),
          el("div", { class: "fc-title" }, c.front),
          el("div", { class: "muted small", style: "margin-top:auto" }, "Click to flip →")));
      const back = el("div", { class: "flashcard flipped", tabindex: "0", role: "button",
        onclick: () => unflip() },
        el("div", { class: "fc-side fc-back" },
          el("div", { class: "muted small" }, "Syllabus context"),
          el("p", { class: "muted", style: "font-size:0.9rem" }, c.back.syllabus_context || "—"),
          c.back.depth_note ? el("div", { class: "notice warn small" }, "Depth: " + c.back.depth_note) : null,
          el("div", { class: "muted small", style: "margin-top:auto" }, c.source)));
      cardBox.append(front, back);
      const flip = () => { front.style.display = "none"; back.style.display = "flex"; };
      const unflip = () => { back.style.display = "none"; front.style.display = "flex"; };
      nav.innerHTML = "";
      nav.append(
        el("button", { class: "btn ghost", onclick: () => show(i - 1) }, "← Previous"),
        el("button", { class: "btn accent", onclick: () => flip() }, "Flip"),
        el("button", { class: "btn ghost", onclick: () => show(i + 1) }, "Next →"),
        el("a", { class: "btn ghost", href: `#/notes?topic=${c.micro_topic_id}` }, "Note on this topic"));
    }
    show(0);
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

async function deviceDue() {
  try {
    const { device } = await import("../device.js");
    if (!device.active()) return null;
    return new Set(await device.dueTopicIds(selected));
  } catch { return null; }
}

// PYQs — two layers: (a) browse official papers ingested by the gov engine with
// source attribution; (b) OFFICIAL_PYQ-labelled questions only, never invented ones.
import { api } from "../api.js";
import { el, badge, loading, errorState, pageHead } from "../ui.js";

let selected = localStorage.getItem("gm.exam") || "upsc-cse";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Previous-year questions",
    "Only questions traceable to an official examination paper appear here, with year, paper and source attached. Where a question cannot be sourced, it is not published."));
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
    const data = await api.get(`/pyqs/${selected}`);
    content.innerHTML = "";

    content.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Official question papers (ingested)"),
      data.papers.length
        ? el("ul", { style: "margin:8px 0 0;padding-left:20px" },
            data.papers.map((p) => el("li", { style: "margin:5px 0" },
              el("a", { href: p.url, target: "_blank", rel: "noopener" }, p.title),
              el("div", { class: "muted small" },
                `${p.organisation} · ${p.published_at || "date not stated"} · source: ${p.source_name}`))))
        : el("p", { class: "muted" },
            "No official papers ingested yet. The government-source engine ingests official portals (robots-respecting, deduped, versioned) — add sources from the Government Information Centre and approved papers appear here."),
      el("p", { class: "muted small", style: "margin-top:8px" }, data.note)));

    if (data.questions.length) {
      content.append(el("h2", { class: "home-h2" }, "PYQ-tagged questions"));
      for (const q of data.questions) {
        content.append(el("section", { class: "card" },
          el("div", { class: "meta-line" },
            badge(q.q_type),
            el("span", { class: "muted small" },
              `${q.year || "year not stated"} · ${q.paper || ""} · ${q.topic_name || ""}`)),
          el("div", { class: "q-text" }, q.question)));
      }
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => load(content)));
  }
}

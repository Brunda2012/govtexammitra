// Homepage — written for a first-time student: what is this, and what do I do first?
// Three plain steps, one button each. Everything else stays discoverable in the menu.
import { api } from "../api.js";
import { store } from "../store.js";
import { device } from "../device.js";
import { el, loading, errorState, progressbar } from "../ui.js";

const STEPS = [
  { key: "pick", n: 1, title: "Pick your exam", href: "#/exams", hint: "See which exams are ready today." },
  { key: "syllabus", n: 2, title: "Learn the syllabus", href: "#/syllabus", hint: "The official syllabus, broken into small topics you can tick off." },
  { key: "practice", n: 3, title: "Practise questions", href: "#/practice", hint: "Real marking rules — including negative marking." },
  { key: "overlap", n: 4, title: "Compare two exams (optional)", href: "#/overlap", hint: "Preparing for more than one exam? Study the shared topics once." },
  { key: "plan", n: 5, title: "Make a study plan", href: "#/planner", hint: "A day-by-day plan from your own progress." },
  { key: "track", n: 6, title: "Watch your progress", href: "#/dashboard", hint: "See what is done and what to revise next." },
];

export async function render(root) {
  root.innerHTML = "";
  let myExam = localStorage.getItem("gm.exam") || "upsc-cse";
  let examName = "UPSC Civil Services Examination";

  // onboarding (if you've started) goes right at the top
  try {
    const progress = await store.get("/progress");
    const done = (progress.progress || []).filter((p) => p.status === "COMPLETED").length;
    const checklist = device.checklist(STEPS);
    const doneSteps = checklist.filter((s) => s.done).length;
    if (done > 0 || doneSteps > 0) {
      root.append(el("section", { class: "card onboarding" },
        el("div", { class: "onboard-head" },
          el("h3", { style: "margin:0" }, `Welcome back — ${doneSteps} of ${STEPS.length} first steps done`),
          el("button", { class: "pill", onclick: () => { device.checklistDismiss(); root.querySelector(".onboarding").remove(); } }, "Hide")),
        progressbar(Math.round(100 * doneSteps / STEPS.length)),
        el("ol", { class: "onboard-steps" },
          checklist.map((st) => el("li", { class: st.done ? "done" : "" },
            el("a", { href: st.href, onclick: () => device.checklistStep(st.key) }, st.done ? `✓ ${st.title}` : `${st.n}. ${st.title}`),
            st.done ? null : el("div", { class: "muted small" }, st.hint)))),
        el("a", { class: "btn accent", style: "margin-top:14px", href: "#/dashboard" }, "Continue studying →")));
      return; // returning visitors get a clean, single focus
    }
  } catch { /* guest with no data yet — fall through to the welcome page */ }

  // ---------- first-time welcome ----------
  root.append(el("div", { class: "home-hero" },
    el("div", { class: "hero-inner" },
      el("span", { class: "badge VERIFIED_OFFICIAL" }, "FREE · BUILT ON THE OFFICIAL SYLLABUS"),
      el("h1", null, "Prepare for government exams — without the confusion."),
      el("p", { class: "hero-sub" },
        "Learn one small topic at a time, practise with the real marking rules, and always know what to study next. ",
        "No sign-up needed to try it."),
      el("div", { class: "hero-actions" },
        el("a", { class: "btn accent big", href: "#/exams" }, "Choose your exam →"),
        el("a", { class: "btn ghost", href: "#/practice" }, "Just try some questions")))));

  // how it works — three steps, one action each
  root.append(el("h2", { class: "home-h2" }, "How it works"));
  root.append(el("div", { class: "grid cols-3" },
    stepCard("1", "Pick your exam",
      "UPSC Civil Services and CAPF Assistant Commandant are ready today. More exams are coming.",
      "#/exams", "See the exams"),
    stepCard("2", "Learn topic by topic",
      "The official syllabus, split into small topics. Tick them off as you learn — your progress saves itself on this device.",
      `#/syllabus?exam=${myExam}`, "Open the syllabus"),
    stepCard("3", "Practise and improve",
      "Answer questions, take a timed mock test, and get simple suggestions on what to revise next.",
      "#/practice", "Practise now")));

  // two quiet extras, phrased in plain language
  root.append(el("h2", { class: "home-h2" }, "Helpful extras"));
  root.append(el("div", { class: "grid cols-3" },
    stepCard("★", "Studying for two exams?",
      "Many topics are shared between exams. We show you what overlaps so you study once, plus what needs extra depth.",
      "#/overlap", "Compare exams"),
    stepCard("✎", "Writing practice for Mains",
      "Timed answer writing with a simple self-scoring rubric — because nobody should trust a machine to grade their essay.",
      "#/mains", "Try answer writing"),
    stepCard("📰", "Official updates, no noise",
      "Notifications, past papers and current affairs — collected from official government sources, always linked to where they came from.",
      "#/govinfo", "See official updates")));

  // supported exams — simple cards
  const content = el("div", null, loading());
  root.append(el("h2", { class: "home-h2" }, "Exams ready today"), content);
  try {
    const exams = await api.get("/exams");
    const supported = exams.filter((e) => e.supported);
    const planned = exams.filter((e) => !e.supported);
    content.innerHTML = "";
    content.className = "grid cols-2";
    for (const e of supported) {
      content.append(el("section", { class: "card exam-card" },
        el("h3", { style: "margin:0 0 4px" }, e.name),
        el("p", { class: "muted", style: "margin:0 0 12px" }, e.description || ""),
        el("div", { class: "hero-actions" },
          el("a", { class: "btn accent", href: `#/syllabus?exam=${e.id}` }, "Start this exam →"))));
    }
    if (planned.length) {
      content.append(el("p", { class: "muted small", style: "max-width:900px;margin:18px auto 0" },
        `More exams on the way (added only after we verify their official syllabus): ${planned.map((e) => e.name).join(", ")}.`));
    }
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

function stepCard(n, title, text, href, label) {
  return el("section", { class: "card step-card" },
    el("div", { class: "step-num" }, n),
    el("h3", { style: "margin:10px 0 6px" }, title),
    el("p", { class: "muted", style: "margin:0 0 14px" }, text),
    el("a", { class: "btn ghost", href }, label + " →"));
}

import { el, pageHead } from "../ui.js";

export const PLANNED = {
 "/pyqs": {
   title: "Previous-Year Questions",
   tagline: "Real PYQs, traceable to official papers — never invented.",
   honesty: "We will only publish questions we can trace to an official examination paper, with the year and paper name attached. Where a question cannot be sourced, it will not appear here.",
   points: [
     "Year- and paper-wise PYQ browsing for supported examinations.",
     "Tagging of every PYQ to the micro-topics used by Overlap Intelligence.",
     "Your attempt history and accuracy per PYQ topic.",
     "Official answer keys cited; disputed keys labelled as such.",
   ],
 },
 "/mocks": {
   title: "Full-Length Mock Tests",
   tagline: "Timed, full-length tests with official marking schemes.",
   honesty: "Mocks will replicate the verified paper pattern (questions, marks, negative marking) of each examination. Papers whose pattern is not yet verified will be labelled explicitly.",
   points: [
     "Timed sections matching the official paper structure.",
     "Negative marking exactly as per the verified scheme (e.g. 1/3 for UPSC Prelims).",
     "Score cards with section-wise breakdown and attempted-vs-correct analysis.",
     "Rank-free, pressure-free review mode with explanations.",
   ],
 },
 "/mains": {
   title: "Mains Answer Writing",
   tagline: "Timed descriptive answer practice with structured rubrics.",
   honesty: "Mains evaluation is genuinely hard to automate. Answer evaluation will only go live when the rubric engine produces feedback we consider trustworthy — until then this page offers structured practice, not fake scores.",
   points: [
     "Timed answer writing against real syllabus topics.",
     "Word-limit and structure guidance per question type.",
     "Self-evaluation rubrics aligned to UPSC marking dimensions.",
     "Optional AI feedback once an evaluation engine is configured and verified.",
   ],
 },
 "/answer-eval": {
   title: "AI Answer Evaluation",
   tagline: "Rubric-based feedback on descriptive answers.",
   honesty: "No pretend scoring: this will be clearly labelled advisory, will require an explicitly configured evaluation engine, and will always show the rubric used.",
   points: [
     "Rubric-based scoring: content, structure, examples, conclusion.",
     "Comparison against the key points expected for the question.",
     "Advisory-only labelling with the model and rubric shown.",
   ],
 },
 "/current-affairs": {
   title: "Current Affairs",
   tagline: "Sourced monthly compilations mapped to your syllabus.",
   honesty: "Current-affairs content will cite its source for every item. Nothing will be presented as 'important' without a reason tied to the syllabus or previous papers.",
   points: [
     "Monthly compilations with source links.",
     "Mapping of news items to the micro-topics you are tracking.",
     "Practice questions derived from cited events.",
   ],
 },
 "/revision": {
   title: "Smart Revision Centre",
   tagline: "Spaced repetition over the topics you actually get wrong.",
   honesty: "The weakness engine already exists (Performance Analytics tracks per-topic accuracy). Revision scheduling will build directly on that data.",
   points: [
     "Spaced-repetition queue driven by your weak topics.",
     "Decay-based resurfacing of completed micro-topics.",
     "One-click revision sessions from your planner tasks.",
   ],
 },
 "/flashcards": {
   title: "Flashcards",
   tagline: "Two-sided recall cards generated from verified micro-topics.",
   honesty: "Cards will be generated from the same verified syllabus decomposition used everywhere else — never from invented content.",
   points: [
     "Auto-generated cards per micro-topic, editable by you.",
     "Review scheduling integrated with the Revision Centre.",
   ],
 },
 "/mindmaps": {
   title: "Mind Maps",
   tagline: "Visual subject → topic → micro-topic hierarchies.",
   honesty: "Maps will render the real syllabus hierarchy stored in the database, with your progress colour-coded on each node.",
   points: [
     "Interactive hierarchy per examination.",
     "Progress and overlap classification shown on nodes.",
   ],
 },
 "/notes": {
   title: "Topic-wise Notes",
   tagline: "Your notes, attached to the exact micro-topic.",
   honesty: "Notes are private to your account and attached to real micro-topic IDs, so they appear wherever that topic appears — syllabus, overlap, planner, revision.",
   points: [
     "Rich-text notes per micro-topic.",
     "Search across all your notes.",
   ],
 },
 "/bookmarks": {
   title: "Bookmarks",
   tagline: "Save any topic, question or plan item for quick access.",
   honesty: "Bookmarks will reference real entities (topics, questions, tasks) — no orphan links.",
   points: [
     "One-click bookmark from syllabus, practice and planner.",
     "Bookmarked PYQs and topics surface in revision.",
   ],
 },
 "/recommendations": {
   title: "Learning Recommendations",
   tagline: "What to study next, computed from your own data.",
   honesty: "Recommendations will be derived from your progress, weak topics and plan — with the reason for every recommendation shown.",
   points: [
     "Next-best-topic suggestions from coverage and accuracy.",
     "Planner-aware sequencing (shared topics before exam-specific).",
   ],
 },
};

export function has(path) {
  return Object.prototype.hasOwnProperty.call(PLANNED, path);
}

export async function render(root, path) {
  const f = PLANNED[path] || {
    title: "Planned feature",
    tagline: "This capability is on the GovtExamMitra roadmap.",
    honesty: "It will go live only when its data engine is real and verified.",
    points: [],
  };
  root.innerHTML = "";
  root.append(pageHead(f.title, f.tagline));
  root.append(el("section", { class: "card planned-card" },
    el("div", { class: "planned-banner" },
      el("span", { class: "badge PENDING_VERIFICATION" }, "PLANNED — NOT YET OPERATIONAL")),
    el("p", { class: "muted" }, f.honesty),
    f.points.length ? el("ul", { class: "planned-list" }, f.points.map((p) => el("li", null, p))) : null,
    el("div", { class: "meta-line" },
      el("a", { class: "btn ghost", href: "#/" }, "Back to dashboard"),
      el("a", { class: "btn ghost", href: "#/methodology" }, "Our data-honesty rules")),
    el("p", { class: "muted small", style: "margin-top:12px" },
      "GovtExamMitra does not ship decorative screens: a page switches from Planned to Live only when the underlying data and engine are real, tested and verified.")));
}

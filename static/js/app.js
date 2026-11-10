import { render as home } from "./pages/home.js";
import { render as dashboard } from "./pages/dashboard.js";
import { render as overlap } from "./pages/overlap.js";
import { render as exams } from "./pages/exams.js";
import { render as syllabus } from "./pages/syllabus.js";
import { render as practice } from "./pages/practice.js";
import { render as planner } from "./pages/planner.js";
import { render as mentor } from "./pages/mentor.js";
import { render as methodology } from "./pages/methodology.js";
import { render as account } from "./pages/account.js";
import { render as analytics } from "./pages/analytics.js";
import { render as govinfo } from "./pages/govinfo.js";
import { render as govadmin } from "./pages/govadmin.js";
import { render as mocks } from "./pages/mocks.js";
import { render as revision } from "./pages/revision.js";
import { render as flashcards } from "./pages/flashcards.js";
import { render as mindmaps } from "./pages/mindmaps.js";
import { render as recommendations } from "./pages/recommendations.js";
import { render as mains } from "./pages/mains.js";
import { render as answereval } from "./pages/answereval.js";
import { render as pyqs } from "./pages/pyqs.js";
import { render as currentaffairs } from "./pages/currentaffairs.js";
import { render as notes } from "./pages/notes.js";
import { render as bookmarks } from "./pages/bookmarks.js";
import { render as planned, has as plannedHas } from "./pages/planned.js";
import { emptyState } from "./ui.js";

const routes = {
 "/": home,
 "/dashboard": dashboard,
 "/overlap": overlap,
 "/exams": exams,
 "/syllabus": syllabus,
 "/practice": practice,
 "/planner": planner,
 "/mentor": mentor,
 "/methodology": methodology,
 "/account": account,
 "/analytics": analytics,
 "/govinfo": govinfo,
 "/govadmin": govadmin,
 "/mocks": mocks,
 "/revision": revision,
 "/flashcards": flashcards,
 "/mindmaps": mindmaps,
 "/recommendations": recommendations,
 "/mains": mains,
 "/answer-eval": answereval,
 "/pyqs": pyqs,
 "/current-affairs": currentaffairs,
 "/notes": notes,
 "/bookmarks": bookmarks,
};

const app = document.getElementById("app");
const nav = document.getElementById("mainNav");

document.getElementById("menuBtn").addEventListener("click", () => nav.classList.toggle("open"));

document.querySelectorAll(".nav-drop").forEach((drop) => {
  const dropBtn = drop.querySelector(".nav-drop-btn");
  dropBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = drop.classList.toggle("open");
    dropBtn.setAttribute("aria-expanded", String(open));
    document.querySelectorAll(".nav-drop").forEach((d) => {
      if (d !== drop) { d.classList.remove("open"); d.querySelector(".nav-drop-btn").setAttribute("aria-expanded", "false"); }
    });
  });
  document.addEventListener("click", (e) => {
    if (!drop.contains(e.target)) {
      drop.classList.remove("open");
      dropBtn.setAttribute("aria-expanded", "false");
    }
  });
});

async function router() {
  const raw = (location.hash.replace(/^#/, "") || "/").split("?");
  const path = raw[0] || "/";
  const query = new URLSearchParams(raw[1] || "");
  const page = routes[path];
  nav.querySelectorAll("a").forEach((a) => a.classList.toggle("active", a.dataset.route === path));
  nav.classList.remove("open");
  document.querySelectorAll(".nav-drop").forEach((d) => d.classList.remove("open"));
  window.scrollTo(0, 0);
  if (typeof window.__gmRefreshBanner === "function") window.__gmRefreshBanner();
  if (!page) {
    if (plannedHas(path)) {
      await planned(app, path);
    } else {
      app.innerHTML = "";
      app.append(emptyState("Page not found", "Use the navigation above to get back on track."));
    }
    return;
  }
  await page(app, query);
}

window.addEventListener("hashchange", router);
router();

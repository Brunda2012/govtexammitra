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
import { render as planned, has as plannedHas } from "./pages/planned.js";
import { emptyState } from "./ui.js";

const routes = {
 "/": dashboard,
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
};

const app = document.getElementById("app");
const nav = document.getElementById("mainNav");

document.getElementById("menuBtn").addEventListener("click", () => nav.classList.toggle("open"));

const drop = nav.querySelector(".nav-drop");
if (drop) {
  const dropBtn = drop.querySelector(".nav-drop-btn");
  dropBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = drop.classList.toggle("open");
    dropBtn.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => {
    if (!drop.contains(e.target)) {
      drop.classList.remove("open");
      dropBtn.setAttribute("aria-expanded", "false");
    }
  });
}

async function router() {
  const path = (location.hash.replace(/^#/, "") || "/").split("?")[0];
  const page = routes[path];
  nav.querySelectorAll("a").forEach((a) => a.classList.toggle("active", a.dataset.route === path));
  nav.classList.remove("open");
  if (drop) drop.classList.remove("open");
  window.scrollTo(0, 0);
  if (!page) {
    if (plannedHas(path)) {
      await planned(app, path);
    } else {
      app.innerHTML = "";
      app.append(emptyState("Page not found", "Use the navigation above to get back on track."));
    }
    return;
  }
  await page(app);
}

window.addEventListener("hashchange", router);
router();

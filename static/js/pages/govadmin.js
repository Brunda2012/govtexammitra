import { api } from "../api.js";
import { el, loading, errorState, pageHead, emptyState } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Government Source Management",
    "Admin-only console: register sources, run ingestion, review AI classifications and monitor crawl health."));
  const content = el("div", null, loading());
  root.append(content);
  try {
    const me = await api.get("/me");
    if (!me.authenticated || me.role !== "admin") {
      content.innerHTML = "";
      content.append(emptyState("Administrator access required",
        "This console manages the government source registry. Log in with an administrator account."));
      return;
    }

    const runMsg = el("span", { class: "muted small" });
    const runBtn = el("button", {
      class: "btn accent",
      onclick: async () => {
        runBtn.disabled = true;
        runMsg.textContent = "Starting…";
        try {
          await api.post("/gov/ingest/run", {});
          runMsg.textContent = "Ingestion started in the background — job results appear below once done.";
          setTimeout(loadJobs, 4000);
        } catch (err) {
          runMsg.textContent = String(err.message || err);
        }
        runBtn.disabled = false;
      },
    }, "Run ingestion now (due sources)");

    content.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Ingestion"),
      el("p", { class: "muted small", style: "margin:0 0 10px" },
        "A scheduler also checks sources automatically every 10 minutes in production. Manual runs bypass the frequency gate for the sources you pick."),
      el("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" }, runBtn, runMsg)));

    const sourcesCard = el("section", { class: "card" }, el("h3", { style: "margin-top:0" }, "Registered sources"));
    content.append(sourcesCard);
    content.append(addSourceCard());
    content.append(discoverCard());
    const reviewCard = el("section", { class: "card" }, el("h3", { style: "margin-top:0" }, "Review queue"));
    const jobsCard = el("section", { class: "card" }, el("h3", { style: "margin-top:0" }, "Recent crawl jobs"));
    content.append(reviewCard, jobsCard);

    async function loadSources() {
      sourcesCard.querySelectorAll("table, p.muted, .state-box").forEach((n) => n.remove());
      try {
        const d = await api.get("/gov/sources");
        if (!d.sources.length) {
          sourcesCard.append(el("p", { class: "muted" }, "No sources registered yet."));
          return;
        }
        sourcesCard.append(el("table", null,
          el("thead", null, el("tr", null, ["Source", "Kind", "Every", "Last crawl", "Status", ""].map(
            (h) => el("th", null, h)))),
          el("tbody", null, d.sources.map((s) => el("tr", null,
            el("td", null, el("strong", null, s.name), el("div", { class: "muted small" }, s.organisation, " · ", s.base_url)),
            el("td", null, s.kind),
            el("td", null, `${s.frequency_hours}h`),
            el("td", { class: "muted small" }, s.last_crawl_at || "never"),
            el("td", null, el("span", { class: "badge" }, s.last_status || (s.enabled ? "ENABLED" : "DISABLED"))),
            el("td", null,
              el("button", { class: "btn ghost small", onclick: () => toggle(s) }, s.enabled ? "Disable" : "Enable"),
              " ",
              el("button", {
                class: "btn ghost small",
                onclick: async () => {
                  if (!confirm(`Remove source "${s.name}" and its collected documents?`)) return;
                  await api.del(`/gov/sources/${s.id}`);
                  loadSources();
                },
              }, "Delete")))))));
      } catch (err) {
        sourcesCard.append(errorState(err, loadSources));
      }
    }

    async function toggle(s) {
      await api.patch(`/gov/sources/${s.id}`, { enabled: !s.enabled });
      loadSources();
    }

    async function loadJobs() {
      jobsCard.querySelectorAll("table, p.muted, .state-box").forEach((n) => n.remove());
      try {
        const d = await api.get("/gov/jobs?limit=20");
        jobsCard.append(el("p", { class: "muted small", style: "margin:0 0 8px" },
          `${d.stats.runs} total runs · ${d.stats.failed} failed`));
        if (!d.jobs.length) {
          jobsCard.append(el("p", { class: "muted" }, "No ingestion runs yet."));
          return;
        }
        jobsCard.append(el("table", null,
          el("thead", null, el("tr", null, ["When", "Source", "Pages", "New", "Updated", "Status"].map(
            (h) => el("th", null, h)))),
          el("tbody", null, d.jobs.map((j) => el("tr", null,
            el("td", { class: "muted small" }, j.finished_at || j.started_at),
            el("td", null, j.source_name || j.source_id),
            el("td", null, String(j.pages_fetched)),
            el("td", null, String(j.docs_new)),
            el("td", null, String(j.docs_updated)),
            el("td", null, el("span", { class: "badge" }, j.status || "—")))))));
      } catch (err) {
        jobsCard.append(errorState(err, loadJobs));
      }
    }

    async function loadReview() {
      reviewCard.querySelectorAll("div.doc-review, p.muted, .state-box").forEach((n) => n.remove());
      try {
        const d = await api.get("/gov/documents?classification=PENDING_REVIEW&limit=25");
        if (!d.documents.length) {
          reviewCard.append(el("p", { class: "muted" }, "Review queue is empty — every document is classified or approved."));
          return;
        }
        reviewCard.append(el("p", { class: "muted small", style: "margin:0 0 8px" },
          "Documents whose exam associations were AI-suggested at low confidence. Approve to confirm, reject to hide."));
        for (const doc of d.documents) {
          const row = el("div", { class: "doc-review", style: "border-top:1px solid var(--line);padding:10px 0" },
            el("strong", { style: "font-size:0.92rem" }, doc.title),
            el("div", { class: "muted small" }, doc.organisation, " · suggested: ",
              doc.exam_ids.join(", ") || "no exam match"),
            el("div", { style: "margin-top:6px;display:flex;gap:8px" },
              el("button", {
                class: "btn accent small",
                onclick: async () => {
                  await api.post(`/gov/documents/${doc.id}/review`, { decision: "approve", note: "Approved in admin console" });
                  loadReview();
                },
              }, "Approve"),
              el("button", {
                class: "btn ghost small",
                onclick: async () => {
                  await api.post(`/gov/documents/${doc.id}/review`, { decision: "reject", note: "Rejected in admin console" });
                  loadReview();
                },
              }, "Reject")));
          reviewCard.append(row);
        }
      } catch (err) {
        reviewCard.append(errorState(err, loadReview));
      }
    }

    await Promise.all([loadSources(), loadJobs(), loadReview()]);
  } catch (err) {
    content.innerHTML = "";
    content.append(errorState(err, () => render(root)));
  }
}

function addSourceCard() {
  const msg = el("div", { class: "muted small", style: "margin-top:8px" });
  const f = (placeholder, key, type = "text") => {
    const inp = el("input", { placeholder, type, style: "width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg-soft);color:var(--text);box-sizing:border-box" });
    inp.dataset.key = key;
    return inp;
  };
  const name = f("Source name (e.g. UPSC What's New)", "name");
  const org = f("Organisation (e.g. Union Public Service Commission)", "organisation");
  const base = f("Base URL — official .gov.in / .nic.in domain only", "base_url");
  const path = f("Listing path (optional, e.g. /whats-new.php)", "listing_path");
  const kind = el("select", { style: "padding:8px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg-soft);color:var(--text)" },
    el("option", { value: "HTML" }, "HTML listing page"),
    el("option", { value: "RSS" }, "RSS feed"));
  const submit = el("button", { class: "btn accent" }, "Register source");
  submit.addEventListener("click", async () => {
    msg.textContent = "";
    const payload = { name: name.value.trim(), organisation: org.value.trim(), base_url: base.value.trim(),
      kind: kind.value, listing_path: path.value.trim() || null };
    if (!payload.name || !payload.organisation || !payload.base_url) {
      msg.textContent = "Name, organisation and base URL are required.";
      return;
    }
    submit.disabled = true;
    try {
      await api.post("/gov/sources", payload);
      msg.textContent = "Registered. It will be crawled on the next ingestion run.";
      name.value = org.value = base.value = path.value = "";
      window.dispatchEvent(new CustomEvent("govsource-added"));
    } catch (err) {
      msg.textContent = String(err.message || err);
    }
    submit.disabled = false;
  });
  return el("section", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Add a source"),
    el("p", { class: "muted small", style: "margin:0 0 10px" },
      "Only official government and education domains (.gov.in, .nic.in, .edu.in, .ac.in) are accepted."),
    name, el("div", { style: "height:8px" }), org, el("div", { style: "height:8px" }),
    base, el("div", { style: "height:8px" }),
    el("div", { style: "display:flex;gap:8px" }, kind, path),
    el("div", { style: "margin-top:10px" }, submit), msg);
}

function discoverCard() {
  const msg = el("div", { class: "muted small", style: "margin-top:8px" });
  const inp = el("input", { placeholder: "Directory URL, e.g. https://www.india.gov.in",
    style: "width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg-soft);color:var(--text);box-sizing:border-box" });
  const results = el("div", { style: "margin-top:10px" });
  const btn = el("button", { class: "btn ghost" }, "Discover official websites");
  btn.addEventListener("click", async () => {
    results.innerHTML = "";
    msg.textContent = "Fetching directory…";
    try {
      const d = await api.post("/gov/discover", { seed_url: inp.value.trim() });
      msg.textContent = `${(d.candidates || []).length} official domains found on ${d.seed_host || "directory"} — none are registered automatically: review and add them above.`;
      for (const c of (d.candidates || []).slice(0, 30)) {
        results.append(el("div", { style: "display:flex;justify-content:space-between;gap:10px;border-top:1px solid var(--line);padding:6px 0;align-items:center" },
          el("div", { class: "small" }, el("strong", null, c.host), el("div", { class: "muted small" }, c.title || "")),
          el("a", { href: c.url, target: "_blank", rel: "noopener noreferrer", class: "small" }, "open ↗")));
      }
    } catch (err) {
      msg.textContent = String(err.message || err);
    }
  });
  return el("section", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Source discovery"),
    el("p", { class: "muted small", style: "margin:0 0 10px" },
      "Fetch an authoritative directory (india.gov.in, IGOD) and list the official .gov.in domains linked from it."),
    inp, el("div", { style: "margin-top:10px" }, btn), msg, results);
}

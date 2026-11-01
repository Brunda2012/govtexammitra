export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined) continue;
    node.append(c.nodeType ? c : document.createTextNode(c));
  }
  return node;
}

export function badge(text) {
  const cls = text.startsWith("EXAM_SPECIFIC") ? "EXAM_SPECIFIC" : text;
  return el("span", { class: `badge ${cls}` }, text.replaceAll("_", " "));
}

export function progressbar(pct) {
  return el("div", { class: "progressbar", role: "progressbar", "aria-valuenow": Math.round(pct) },
    el("div", { style: `width:${Math.max(0, Math.min(100, pct))}%` }));
}

export function loading() {
  return el("div", { class: "spinner", role: "status", "aria-label": "Loading" });
}

export function emptyState(title, hint) {
  return el("div", { class: "state-box" },
    el("div", { class: "big" }, title),
    el("div", null, hint));
}

export function errorState(err, retry) {
  const box = el("div", { class: "state-box" },
    el("div", { class: "big" }, "Something went wrong"),
    el("div", null, String(err.message || err)));
  if (retry) box.append(el("button", { class: "btn ghost", style: "margin-top:14px", onclick: retry }, "Retry"));
  return box;
}

export function pageHead(title, subtitle) {
  return el("div", { class: "page-head" }, el("h1", null, title), subtitle ? el("p", null, subtitle) : null);
}

export function fmtDate(iso) {
  if (!iso) return "—";
  return iso;
}

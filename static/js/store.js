// store.js — one API surface for pages. Signed-in users hit the server exactly as
// before (no auth changes); guests are routed to the device store (localStorage),
// and the same UI keeps working with the honest "saved on this device" banner.
import { api } from "./api.js";
import { device } from "./device.js";

// [method, regex, handler(matchGroups, data, hint)]
const GUEST_ROUTES = [
  ["GET", /^\/progress$/, (g, d, h) => device.progressList(h?.examId)],
  ["GET", /^\/progress\/([^/]+)\/coverage$/, (g) => device.coverage(g[0])],
  ["POST", /^\/progress$/, (g, d) => device.setProgress(d.micro_topic_id, d.status, d.mastery)],
  ["GET", /^\/analytics$/, (g, d, h) => device.analytics(h?.examId)],
  ["GET", /^\/dashboard$/, () => device.dashboard()],
  ["GET", /^\/plan\/([^/]+)\/([^/]+)$/, (g) => device.plan(g[0], g[1])],
  ["POST", /^\/plan\/([^/]+)\/([^/]+)\/generate$/, (g) => device.generateTasks(g[0], g[1], 10)],
  ["GET", /^\/tasks$/, () => device.tasks()],
  ["POST", /^\/tasks\/(\d+)\/complete$/, (g) => device.completeTask(Number(g[0]))],
  ["POST", /^\/questions\/(\d+)\/answer$/, (g, d, h) => device.answer(Number(g[0]), d.chosen, h)],
  ["GET", /^\/revision\/([^/]+)\/queue$/, (g) => device.revisionQueue(g[0])],
  ["GET", /^\/revision\/([^/]+)\/session$/, (g) => device.revisionSession(g[0])],
  ["GET", /^\/mocks\/([^/]+)\/history$/, (g) => device.mockHistory(g[0])],
  ["POST", /^\/mocks\/([^/]+)\/submit$/, (g, d) => device.submitMock(g[0], d.paper || "Mock", d.answers, d.question_ids)],
  ["GET", /^\/mains\/attempts$/, (g, d, h) => device.mainsHistory(h?.examId)],
  ["POST", /^\/mains\/attempts$/, (g, d) => device.saveMains(d)],
  ["GET", /^\/notes$/, () => device.notesAll()],
  ["GET", /^\/notes\/(\d+)$/, (g) => device.noteGet(Number(g[0]))],
  ["PUT", /^\/notes\/(\d+)$/, (g, d, h) => device.notePut(Number(g[0]), d.body, h)],
  ["DELETE", /^\/notes\/(\d+)$/, (g) => device.noteDelete(Number(g[0]))],
  ["GET", /^\/bookmarks$/, () => device.bookmarksAll()],
  ["POST", /^\/bookmarks$/, (g, d, h) => device.bookmarkAdd(d.kind, d.ref_id, h?.label)],
  ["DELETE", /^\/bookmarks\/([^/]+)\/(.+)$/, (g) => device.bookmarkDelete(g[0], g[1])],
  ["GET", /^\/recommendations\/([^/]+)$/, (g, d, h) => device.recommendations(g[0], h?.pair)],
];

function match(method, path) {
  const clean = path.split("?")[0];
  for (const [m, re, fn] of GUEST_ROUTES) {
    if (m !== method) continue;
    const hit = clean.match(re);
    if (hit) return { fn, groups: hit.slice(1) };
  }
  return null;
}

async function put(path, data) {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("gm.token");
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch("/api/v1" + path, { method: "PUT", headers, body: JSON.stringify(data ?? {}) });
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    throw Object.assign(new Error(body && body.detail ? body.detail : `Request failed (${res.status})`),
      { status: res.status });
  }
  return body;
}

export const store = {
  async get(path, hint) {
    if (device.active()) {
      const hit = match("GET", path);
      if (hit) return hit.fn(hit.groups, null, hint);
    }
    return api.get(path);
  },
  async post(path, data, hint) {
    if (device.active()) {
      const hit = match("POST", path);
      if (hit) return hit.fn(hit.groups, data, hint);
    }
    return api.post(path, data);
  },
  async put(path, data, hint) {
    if (device.active()) {
      const hit = match("PUT", path);
      if (hit) return hit.fn(hit.groups, data, hint);
    }
    return put(path, data);
  },
  async del(path, hint) {
    if (device.active()) {
      const hit = match("DELETE", path);
      if (hit) return hit.fn(hit.groups, null, hint);
    }
    return api.del(path);
  },
};

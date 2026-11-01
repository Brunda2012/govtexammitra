import { api, setToken } from "../api.js";
import { el, pageHead } from "../ui.js";

export async function render(root) {
  root.innerHTML = "";
  root.append(pageHead("Your account",
    "Register once, then log in on any device. Your progress, plans and practice history are private to your account."));
  const me = await api.get("/me").catch(() => ({ authenticated: false }));

  if (me.authenticated) {
    root.append(el("section", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Signed in"),
      el("p", null, me.email + " · " + me.role),
      el("button", { class: "btn ghost", onclick: () => { setToken(null); location.hash = "#/"; location.reload(); } }, "Log out")));
    return;
  }

  const box = el("div", { class: "grid cols-2" });
  box.append(authCard("Create an account", "Register", async (email, password) => {
    const res = await api.post("/auth/register", { email, password });
    setToken(res.token); location.hash = "#/"; location.reload();
  }));
  box.append(authCard("Log in", "Log in", async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    setToken(res.token); location.hash = "#/"; location.reload();
  }));
  root.append(box);
  root.append(el("p", { class: "muted small", style: "margin-top:14px" },
    "Passwords are stored salted + hashed (PBKDF2-SHA256). Sessions use signed tokens; log out clears them from this device."));
}

function authCard(title, action, submit) {
  const email = el("input", { type: "text", placeholder: "you@example.com", "aria-label": "Email" });
  const password = el("input", { type: "password", placeholder: "Password (min 8 characters)", "aria-label": "Password" });
  const msg = el("div", null);
  const btn = el("button", { class: "btn", onclick: async () => {
    msg.innerHTML = "";
    btn.disabled = true;
    try {
      await submit(email.value.trim(), password.value);
    } catch (err) {
      msg.append(el("div", { class: "notice bad", style: "margin-top:10px" }, err.message));
      btn.disabled = false;
    }
  } }, action);
  return el("section", { class: "card" },
    el("h3", { style: "margin-top:0" }, title),
    el("label", { style: "display:block;margin:8px 0" }, el("span", { class: "muted small" }, "Email"), email),
    el("label", { style: "display:block;margin:8px 0" }, el("span", { class: "muted small" }, "Password"), password),
    btn, msg);
}

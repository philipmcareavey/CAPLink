import { api, state, setSession, clearSession } from "./api.js";
import { el, toast } from "./dom.js";
import { BANDS } from "./constants.js";
import { renderStudent, STUDENT_TABS } from "./student.js";
import { renderBusiness, BUSINESS_TABS } from "./business.js";
import { renderAdmin, ADMIN_TABS } from "./university-admin.js";

const ROLE_TABS = {
  student: STUDENT_TABS,
  business: BUSINESS_TABS,
  university_admin: ADMIN_TABS,
};

function logout() {
  clearSession();
  render();
}

async function quickLogin(email, password) {
  try {
    const tokens = await api("/auth/login", { method: "POST", body: { email, password }, auth: false });
    setSession(tokens);
    toast("Logged in as " + email, "success");
    render();
  } catch (e) { toast("Login failed: " + e.message, "error"); }
}

function render() {
  const who = document.getElementById("who");
  const roleTabs = document.getElementById("role-tabs");
  const app = document.getElementById("app");

  if (!state.token) {
    who.innerHTML = "";
    roleTabs.innerHTML = "";
    app.innerHTML = "";
    app.appendChild(renderLogin());
    return;
  }

  who.innerHTML = `<span class="role-tag">${state.role.replace(/_/g, " ")}</span><button class="logout" data-action="logout">Log out</button>`;
  who.querySelector('[data-action="logout"]').addEventListener("click", logout);

  const tabs = ROLE_TABS[state.role];
  if (tabs) {
    if (!state.activeTab || !tabs.find(t => t.key === state.activeTab)) state.activeTab = tabs[0].key;
    roleTabs.setAttribute("role", "tablist");
    roleTabs.setAttribute("aria-label", "Sections");
    roleTabs.innerHTML = tabs.map(t => `
      <button role="tab" id="tab-${t.key}" aria-selected="${state.activeTab === t.key}" aria-controls="app"
        data-tab="${t.key}" class="${state.activeTab === t.key ? "active" : ""}">${t.label}</button>
    `).join("");
    roleTabs.querySelectorAll("[data-tab]").forEach(btn => btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      state.openThreadId = null;
      render();
    }));
  } else {
    roleTabs.removeAttribute("role");
    roleTabs.innerHTML = "";
  }

  app.innerHTML = "";
  // Technical Implementation Plan 5.e.iii — <main> already carries a real,
  // valid "main" landmark role implicitly; overriding it to role="tabpanel"
  // (an earlier version of this fix did exactly that) is invalid per the
  // ARIA spec — "tabpanel" isn't an allowed role for <main> — and axe-core
  // correctly flagged it as both an aria-allowed-role violation and a lost
  // main landmark. Labelling it by whichever tab is active, without
  // touching its role, gets the same "announce which section this is"
  // benefit without either problem.
  if (state.activeTab) app.setAttribute("aria-labelledby", `tab-${state.activeTab}`);
  else app.removeAttribute("aria-labelledby");
  if (state.role === "student") renderStudent(app);
  else if (state.role === "business") renderBusiness(app);
  else if (state.role === "university_admin") renderAdmin(app);
  else app.appendChild(el(`<div class="card">No screen built for role "${state.role}" yet — try <a href="/docs">/docs</a> instead.</div>`));
}

// Technical Implementation Plan 2.c.iii — the site key is fetched once from
// the backend (see auth.py::get_captcha_site_key) rather than hardcoded here,
// so swapping in a real hCaptcha account later is a pure config change, not
// a frontend edit. Cached for the page's lifetime since it never changes
// mid-session.
let cachedCaptchaSiteKey = null;
async function getCaptchaSiteKey() {
  if (cachedCaptchaSiteKey) return cachedCaptchaSiteKey;
  const { site_key } = await api("/auth/captcha-site-key", { auth: false });
  cachedCaptchaSiteKey = site_key;
  return site_key;
}

// index.html defines window.onHcaptchaLoaded itself (in a plain classic
// script, not here — see its comment for why: this module script is
// deferred and can lose a race against the async hCaptcha script trying to
// call it). window.__hcaptchaReady covers the case where hCaptcha already
// finished loading before this module ran at all; the event covers the
// more common case where it hasn't yet.
const hcaptchaReady = window.__hcaptchaReady
  ? Promise.resolve()
  : new Promise(resolve => document.addEventListener("hcaptcha-ready", resolve, { once: true }));

// Widget ids returned by hcaptcha.render(), keyed by holder element id — a
// re-render (switching back to a registration tab a second time in the same
// session) needs the specific widget id to read its response back out;
// hcaptcha.getResponse() with no argument only ever reads the *first*
// widget ever rendered on the page, which breaks the moment a second form
// (student vs. business) has also been rendered once.
const captchaWidgetIds = {};

async function mountCaptcha(holderId) {
  try {
    const siteKey = await getCaptchaSiteKey();
    await hcaptchaReady;
    const holder = document.getElementById(holderId);
    if (!holder) return; // the user already navigated away before this resolved
    captchaWidgetIds[holderId] = hcaptcha.render(holder, { sitekey: siteKey });
  } catch (e) { /* registration still works without it if this ever fails — the backend fails open with no key configured */ }
}
function getCaptchaToken(holderId) {
  const widgetId = captchaWidgetIds[holderId];
  return widgetId !== undefined ? hcaptcha.getResponse(widgetId) : "";
}
function resetCaptcha(holderId) {
  const widgetId = captchaWidgetIds[holderId];
  if (widgetId !== undefined) { try { hcaptcha.reset(widgetId); } catch (e) { /* already gone */ } }
}

function renderLogin() {
  const wrap = el(`
    <div class="login-wrap">
      <div class="eyebrow">Sign in</div>
      <div class="tabs" id="login-tabs" role="tablist" aria-label="Sign in or register">
        <button role="tab" id="tab-login" aria-selected="${state.registerTab === "login"}" aria-controls="login-body"
          data-tab="login" class="${state.registerTab === "login" ? "active" : ""}">Log in</button>
        <button role="tab" id="tab-register-student" aria-selected="${state.registerTab === "register-student"}" aria-controls="login-body"
          data-tab="register-student" class="${state.registerTab === "register-student" ? "active" : "ghost"}">New student</button>
        <button role="tab" id="tab-register-business" aria-selected="${state.registerTab === "register-business"}" aria-controls="login-body"
          data-tab="register-business" class="${state.registerTab === "register-business" ? "active" : "ghost"}">New business</button>
      </div>
      <div id="login-body" role="tabpanel" aria-labelledby="tab-${state.registerTab}"></div>
    </div>
  `);
  wrap.getElementById("login-tabs").addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-tab]");
    if (!btn) return;
    state.registerTab = btn.dataset.tab;
    render();
  });
  const body = wrap.getElementById("login-body");

  if (state.registerTab === "login") {
    body.appendChild(el(`
      <div class="card">
        <h4 class="section">Seeded demo accounts</h4>
        <div class="quick-login">
          <button data-quick="aisha.rahman@manchester.ac.uk|ChangeMe123!">Student — Aisha Rahman<small>aisha.rahman@manchester.ac.uk</small></button>
          <button data-quick="hello@datacraft-analytics.com|ChangeMe123!">Business — DataCraft Analytics<small>hello@datacraft-analytics.com</small></button>
          <button data-quick="admin@manchester.ac.uk|ChangeMe123!">University admin — Manchester<small>admin@manchester.ac.uk</small></button>
        </div>
        <div class="divider">or sign in manually</div>
        <div class="field"><label for="li-email">Email</label><input id="li-email"></div>
        <div class="field pw-field"><label for="li-pass">Password</label><input id="li-pass" type="password"><button type="button" class="pw-toggle" data-toggle="li-pass">Show</button></div>
        <button data-action="manual-login" style="width:100%; justify-content:center">Log in</button>
        <p class="muted" style="margin-top:12px">All seeded passwords are <code class="idval">ChangeMe123!</code>. Run <code class="idval">python -m scripts.seed_demo_data</code> first if these don't work.</p>
      </div>
    `));
    body.querySelector('[data-action="manual-login"]').addEventListener("click", () => {
      quickLogin(document.getElementById("li-email").value, document.getElementById("li-pass").value);
    });
    body.querySelectorAll("[data-quick]").forEach(b => b.addEventListener("click", () => {
      const [email, pass] = b.dataset.quick.split("|");
      quickLogin(email, pass);
    }));
  } else if (state.registerTab === "register-student") {
    body.appendChild(el(`
      <div class="card">
        <h4 class="section">Register a student</h4>
        <p class="muted">Email must end in the university's domain (seeded demo university is <code class="idval">manchester</code>, domain <code class="idval">manchester.ac.uk</code>).</p>
        <div class="field"><label for="rs-email">Email</label><input id="rs-email" placeholder="you@manchester.ac.uk"></div>
        <div class="field pw-field"><label for="rs-pass">Password</label><input id="rs-pass" type="password" value="ChangeMe123!"><button type="button" class="pw-toggle" data-toggle="rs-pass">Show</button></div>
        <div class="field"><label for="rs-name">Full name</label><input id="rs-name"></div>
        <div class="field"><label for="rs-slug">University slug</label><input id="rs-slug" value="manchester"></div>
        <div class="field"><label for="rs-degree">Degree title</label><input id="rs-degree" value="BSc Computer Science"></div>
        <div class="field"><label for="rs-band">Band</label><select id="rs-band">${BANDS.map(b => `<option value="${b}">${b.replace(/_/g, " ")}</option>`).join("")}</select></div>
        <label class="row" style="align-items:flex-start; gap:8px; margin:10px 0">
          <input type="checkbox" id="rs-consent" style="margin-top:3px">
          <span class="muted" style="font-size:13px">I consent to CAPLink sharing my project engagement and outcome data with my university's careers team for reporting purposes.</span>
        </label>
        <div class="field"><div id="rs-captcha"></div></div>
        <button data-action="register-student" style="width:100%; justify-content:center">Register</button>
      </div>
    `));
    mountCaptcha("rs-captcha");
    body.querySelector('[data-action="register-student"]').addEventListener("click", async () => {
      try {
        if (!document.getElementById("rs-consent").checked) {
          toast("You must consent to data sharing with your university to register", "error");
          return;
        }
        const result = await api("/auth/register/student", { method: "POST", auth: false, body: {
          email: document.getElementById("rs-email").value,
          password: document.getElementById("rs-pass").value,
          full_name: document.getElementById("rs-name").value,
          university_slug: document.getElementById("rs-slug").value,
          degree_title: document.getElementById("rs-degree").value,
          band: document.getElementById("rs-band").value,
          data_sharing_consent: true,
          captcha_token: getCaptchaToken("rs-captcha"),
        }});
        // Local dev auto-verifies and logs straight in; staging/production
        // require a real clicked verification link instead (no ESP is wired
        // up yet, so that link only ever appears in the server's logs).
        if (result.access_token) {
          setSession(result);
          toast("Registered and logged in", "success");
          render();
        } else {
          toast(result.message || "Registered — check your email to verify.", "success");
          state.registerTab = "login";
          render();
        }
      } catch (e) { toast("Registration failed: " + e.message, "error"); resetCaptcha("rs-captcha"); }
    });
  } else if (state.registerTab === "register-business") {
    body.appendChild(el(`
      <div class="card">
        <h4 class="section">Register a business</h4>
        <p class="muted">A brand-new business has <strong>zero</strong> visibility of any student until a university approves it — try posting a project right after registering to see it get rejected.</p>
        <div class="field"><label for="rb-email">Email</label><input id="rb-email"></div>
        <div class="field pw-field"><label for="rb-pass">Password</label><input id="rb-pass" type="password" value="ChangeMe123!"><button type="button" class="pw-toggle" data-toggle="rb-pass">Show</button></div>
        <div class="field"><label for="rb-name">Contact full name</label><input id="rb-name"></div>
        <div class="field"><label for="rb-company">Company name</label><input id="rb-company"></div>
        <div class="field"><div id="rb-captcha"></div></div>
        <button data-action="register-business" style="width:100%; justify-content:center">Register</button>
      </div>
    `));
    mountCaptcha("rb-captcha");
    body.querySelector('[data-action="register-business"]').addEventListener("click", async () => {
      try {
        const result = await api("/auth/register/business", { method: "POST", auth: false, body: {
          email: document.getElementById("rb-email").value,
          password: document.getElementById("rb-pass").value,
          full_name: document.getElementById("rb-name").value,
          company_name: document.getElementById("rb-company").value,
          captcha_token: getCaptchaToken("rb-captcha"),
        }});
        if (result.access_token) {
          setSession(result);
          toast("Registered and logged in", "success");
          render();
        } else {
          toast(result.message || "Registered — check your email to verify.", "success");
          state.registerTab = "login";
          render();
        }
      } catch (e) { toast("Registration failed: " + e.message, "error"); resetCaptcha("rb-captcha"); }
    });
  }
  wirePasswordToggles(wrap);
  return wrap;
}

// A real usability fix that came out of the 2026-09-09 visual reskin, not
// just decoration: none of the three password fields on this page had a
// way to check what you'd typed before submitting. `.pw-toggle` sits next
// to whichever input it targets (`data-toggle` holds that input's id).
function wirePasswordToggles(root) {
  root.querySelectorAll(".pw-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.toggle);
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.textContent = showing ? "Show" : "Hide";
    });
  });
}

// Technical Implementation Plan 2.b — a successful university SSO login
// (app/api/v1/endpoints/saml.py::saml_acs) redirects the browser back here
// with fresh tokens in the URL *fragment* (never the query string or a log
// line, so they never end up in server access logs or browser history in
// a readable form), or an sso_error reason if it failed. This is the other
// half of that handoff that actually reads it back out — referenced by
// saml.py's own docstring, but never actually built until now.
function consumeSsoHandoff() {
  const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (!hash) return false;
  const params = new URLSearchParams(hash);
  const ssoError = params.get("sso_error");
  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");

  if (ssoError) {
    history.replaceState(null, "", window.location.pathname);
    toast("University sign-in failed: " + ssoError.replace(/_/g, " "), "error");
    return false;
  }
  if (accessToken && refreshToken) {
    history.replaceState(null, "", window.location.pathname);
    setSession({ access_token: accessToken, refresh_token: refreshToken });
    toast("Signed in via your university", "success");
    return true;
  }
  return false;
}

window.__caplinkRerender = render; // lets role modules trigger a full re-render after tab-affecting actions
consumeSsoHandoff();
render();

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
    roleTabs.innerHTML = tabs.map(t => `<button data-tab="${t.key}" class="${state.activeTab === t.key ? "active" : ""}">${t.label}</button>`).join("");
    roleTabs.querySelectorAll("[data-tab]").forEach(btn => btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      state.openThreadId = null;
      render();
    }));
  } else {
    roleTabs.innerHTML = "";
  }

  app.innerHTML = "";
  if (state.role === "student") renderStudent(app);
  else if (state.role === "business") renderBusiness(app);
  else if (state.role === "university_admin") renderAdmin(app);
  else app.appendChild(el(`<div class="card">No screen built for role "${state.role}" yet — try <a href="/docs">/docs</a> instead.</div>`));
}

function renderLogin() {
  const wrap = el(`
    <div class="login-wrap">
      <div class="eyebrow">Sign in</div>
      <div class="tabs" id="login-tabs">
        <button data-tab="login" class="${state.registerTab === "login" ? "active" : ""}">Log in</button>
        <button data-tab="register-student" class="${state.registerTab === "register-student" ? "active" : "ghost"}">New student</button>
        <button data-tab="register-business" class="${state.registerTab === "register-business" ? "active" : "ghost"}">New business</button>
      </div>
      <div id="login-body"></div>
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
        <div class="field"><label>Email</label><input id="li-email"></div>
        <div class="field"><label>Password</label><input id="li-pass" type="password"></div>
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
        <div class="field"><label>Email</label><input id="rs-email" placeholder="you@manchester.ac.uk"></div>
        <div class="field"><label>Password</label><input id="rs-pass" type="password" value="ChangeMe123!"></div>
        <div class="field"><label>Full name</label><input id="rs-name"></div>
        <div class="field"><label>University slug</label><input id="rs-slug" value="manchester"></div>
        <div class="field"><label>Degree title</label><input id="rs-degree" value="BSc Computer Science"></div>
        <div class="field"><label>Band</label><select id="rs-band">${BANDS.map(b => `<option value="${b}">${b.replace(/_/g, " ")}</option>`).join("")}</select></div>
        <button data-action="register-student" style="width:100%; justify-content:center">Register</button>
      </div>
    `));
    body.querySelector('[data-action="register-student"]').addEventListener("click", async () => {
      try {
        const tokens = await api("/auth/register/student", { method: "POST", auth: false, body: {
          email: document.getElementById("rs-email").value,
          password: document.getElementById("rs-pass").value,
          full_name: document.getElementById("rs-name").value,
          university_slug: document.getElementById("rs-slug").value,
          degree_title: document.getElementById("rs-degree").value,
          band: document.getElementById("rs-band").value,
        }});
        setSession(tokens);
        toast("Registered and logged in", "success");
        render();
      } catch (e) { toast("Registration failed: " + e.message, "error"); }
    });
  } else if (state.registerTab === "register-business") {
    body.appendChild(el(`
      <div class="card">
        <h4 class="section">Register a business</h4>
        <p class="muted">A brand-new business has <strong>zero</strong> visibility of any student until a university approves it — try posting a project right after registering to see it get rejected.</p>
        <div class="field"><label>Email</label><input id="rb-email"></div>
        <div class="field"><label>Password</label><input id="rb-pass" type="password" value="ChangeMe123!"></div>
        <div class="field"><label>Contact full name</label><input id="rb-name"></div>
        <div class="field"><label>Company name</label><input id="rb-company"></div>
        <button data-action="register-business" style="width:100%; justify-content:center">Register</button>
      </div>
    `));
    body.querySelector('[data-action="register-business"]').addEventListener("click", async () => {
      try {
        const tokens = await api("/auth/register/business", { method: "POST", auth: false, body: {
          email: document.getElementById("rb-email").value,
          password: document.getElementById("rb-pass").value,
          full_name: document.getElementById("rb-name").value,
          company_name: document.getElementById("rb-company").value,
        }});
        setSession(tokens);
        toast("Registered and logged in", "success");
        render();
      } catch (e) { toast("Registration failed: " + e.message, "error"); }
    });
  }
  return wrap;
}

window.__caplinkRerender = render; // lets role modules trigger a full re-render after tab-affecting actions
render();

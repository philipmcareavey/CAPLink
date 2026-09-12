// Technical Implementation Plan 8.a.ii — main.js is the shell: the
// logged-out login/register screen, the logged-in role-tab chrome, the
// password show/hide toggle (a real usability fix from the 2026-09-09
// reskin), and the SSO handoff (consumeSsoHandoff()) that reads tokens
// out of the URL fragment after a university SSO redirect. Runs its own
// render() at module-import time (see main.js's own final lines), so
// every test here re-imports it fresh against a DOM shell shaped like
// index.html's real markup (#who/#role-tabs/#app/#toasts) rather than
// calling an exported function directly.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function makeToken(payload) {
  const b64url = (obj) => btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${b64url({ alg: "HS256", typ: "JWT" })}.${b64url(payload)}.fakesignature`;
}

function setupDomShell() {
  document.body.innerHTML = `
    <div id="who"></div>
    <nav id="role-tabs"></nav>
    <main id="app"></main>
    <div id="toasts"></div>
  `;
}

async function flushPromises() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

async function freshImport() {
  vi.resetModules();
  return import("./main.js");
}

describe("main.js — logged-out login/register screen", () => {
  beforeEach(() => {
    setupDomShell();
    window.location.hash = "";
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the sign-in tabs and the three seeded quick-login buttons by default", async () => {
    await freshImport();
    expect(document.getElementById("login-tabs")).toBeTruthy();
    expect(document.querySelectorAll("[data-quick]").length).toBe(3);
    expect(document.getElementById("app").textContent).not.toContain("No screen built");
  });

  it("switches to the student registration form when that tab is clicked", async () => {
    await freshImport();
    document.querySelector('[data-tab="register-student"]').click();
    expect(document.getElementById("rs-email")).toBeTruthy();
    expect(document.getElementById("rs-consent")).toBeTruthy();
  });

  it("switches to the business registration form when that tab is clicked", async () => {
    await freshImport();
    document.querySelector('[data-tab="register-business"]').click();
    expect(document.getElementById("rb-company")).toBeTruthy();
  });

  it("logging in via the manual form renders the logged-in role chrome afterward", async () => {
    const token = makeToken({ sub: "u1", role: "student", university_id: "uni-1" });
    fetch.mockResolvedValue({ ok: true, json: async () => ({ access_token: token, refresh_token: "r1" }) });

    await freshImport();
    document.getElementById("li-email").value = "aisha@manchester.ac.uk";
    document.getElementById("li-pass").value = "ChangeMe123!";
    document.querySelector('[data-action="manual-login"]').click();
    await flushPromises();

    expect(document.querySelector(".role-tag").textContent).toBe("student");
    expect(document.querySelectorAll('[role="tab"][data-tab]').length).toBeGreaterThan(0);
  });

  it("shows an error toast and stays on the login screen when login fails", async () => {
    fetch.mockResolvedValue({ ok: false, status: 401, statusText: "Unauthorized", json: async () => ({ detail: "Bad credentials" }) });
    await freshImport();
    document.getElementById("li-email").value = "wrong@manchester.ac.uk";
    document.getElementById("li-pass").value = "wrong";
    document.querySelector('[data-action="manual-login"]').click();
    await flushPromises();

    expect(document.getElementById("login-tabs")).toBeTruthy();
    expect(document.querySelector("#toasts .toast.error").textContent).toContain("Login failed");
  });

  it("the password show/hide toggle flips both the input type and its own label", async () => {
    await freshImport();
    const input = document.getElementById("li-pass");
    const button = document.querySelector('[data-toggle="li-pass"]');
    expect(input.type).toBe("password");
    expect(button.textContent).toBe("Show");

    button.click();
    expect(input.type).toBe("text");
    expect(button.textContent).toBe("Hide");

    button.click();
    expect(input.type).toBe("password");
    expect(button.textContent).toBe("Show");
  });
});

describe("main.js — logging out", () => {
  beforeEach(() => {
    setupDomShell();
    window.location.hash = "";
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("clicking log out clears the session and returns to the login screen", async () => {
    const token = makeToken({ sub: "u1", role: "business", university_id: null });
    fetch.mockResolvedValue({ ok: true, json: async () => ({ access_token: token, refresh_token: "r1" }) });

    await freshImport();
    document.getElementById("li-email").value = "hello@datacraft-analytics.com";
    document.getElementById("li-pass").value = "ChangeMe123!";
    document.querySelector('[data-action="manual-login"]').click();
    await flushPromises();
    expect(document.querySelector(".role-tag")).toBeTruthy();

    document.querySelector('[data-action="logout"]').click();
    expect(document.getElementById("login-tabs")).toBeTruthy();
    expect(document.querySelector(".role-tag")).toBeNull();
  });
});

describe("main.js — consumeSsoHandoff()", () => {
  beforeEach(() => {
    setupDomShell();
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    window.location.hash = "";
  });

  it("logs a student in from a real access_token/refresh_token URL fragment", async () => {
    const token = makeToken({ sub: "u9", role: "student", university_id: "uni-9" });
    window.location.hash = `#access_token=${token}&refresh_token=r9`;

    await freshImport();

    expect(document.querySelector(".role-tag").textContent).toBe("student");
    expect(document.querySelector("#toasts .toast.success").textContent).toContain("Signed in via your university");
  });

  it("shows a readable error toast and stays logged out for an sso_error fragment", async () => {
    window.location.hash = "#sso_error=admin_account_not_provisioned";

    await freshImport();

    expect(document.getElementById("login-tabs")).toBeTruthy();
    expect(document.querySelector("#toasts .toast.error").textContent).toContain("admin account not provisioned");
  });

  it("does nothing when the URL has no fragment at all", async () => {
    window.location.hash = "";
    await freshImport();
    expect(document.getElementById("login-tabs")).toBeTruthy();
    expect(document.querySelector("#toasts .toast")).toBeNull();
  });
});

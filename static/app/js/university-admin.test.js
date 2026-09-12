// Technical Implementation Plan 8.a.ii — university-admin.js's four tabs:
// business partnership agreements (the safeguarding gate's actual
// control-panel action), campus location, SSO configuration (2.b.iv), and
// the employability report (5.d.iii).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { state, clearSession } from "./api.js";
import { renderAdmin } from "./university-admin.js";

function routeFetch(routes) {
  return vi.fn(async (url, opts) => {
    for (const [matcher, respond] of routes) {
      const matches = typeof matcher === "string" ? url === matcher : matcher.test(url);
      if (matches) {
        if (respond instanceof Error) throw respond;
        return { ok: true, json: async () => (typeof respond === "function" ? respond(url, opts) : respond) };
      }
    }
    throw new Error("Unmocked fetch call: " + url);
  });
}

async function flushPromises() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function setupApp() {
  document.body.innerHTML = `<div id="toasts"></div><main id="app"></main>`;
  return document.getElementById("app");
}

describe("university-admin.js — Partnerships (agreements) tab", () => {
  beforeEach(() => {
    state.activeTab = "agreements";
    state.universityId = "uni-1";
    window.__caplinkRerender = vi.fn();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    delete window.__caplinkRerender;
    state.activeTab = null;
  });

  const AGREEMENT = {
    id: "agreement-1", business_id: "biz-1", status: "pending",
    allowed_bands: ["year_3"], allowed_categories: ["software_engineering"],
  };

  it("lists agreements with each band's permitted/not-permitted state", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1/business-agreements", [AGREEMENT]]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    const card = document.getElementById("agreement-agreement-1");
    expect(card).toBeTruthy();
    expect(card.textContent).toContain("biz-1");
    expect(card.textContent).toContain("pending");
  });

  it("shows an empty state when no business has requested access yet", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1/business-agreements", []]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    expect(document.getElementById("admin-agreements").textContent).toContain("No agreements yet");
  });

  it("approving an agreement PATCHes the chosen status/bands/categories and reloads", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/universities/uni-1/business-agreements", [AGREEMENT]],
      [/business-agreements\/agreement-1$/, { ...AGREEMENT, status: "approved" }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    const card = document.getElementById("agreement-agreement-1");
    card.querySelector(".ag-status").value = "approved";
    card.querySelector('[data-save-agreement="agreement-1"]').click();
    await flushPromises();

    const patchCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/universities/uni-1/business-agreements/agreement-1" && opts.method === "PATCH");
    expect(patchCall).toBeTruthy();
    const body = JSON.parse(patchCall[1].body);
    expect(body.status).toBe("approved");
    expect(body.allowed_bands).toEqual(["year_3"]);
    expect(document.querySelector("#toasts .toast.success").textContent).toContain("Agreement updated");
  });
});

describe("university-admin.js — Campus Location tab", () => {
  beforeEach(() => {
    state.activeTab = "location";
    state.universityId = "uni-1";
    window.__caplinkRerender = vi.fn();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    delete window.__caplinkRerender;
    state.activeTab = null;
  });

  it("shows the current campus location when one is already set", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1", { postcode: "M13 9PL", latitude: 53.46, longitude: -2.23 }]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    expect(document.getElementById("location-current").textContent).toContain("M13 9PL");
  });

  it("shows 'not set' when no campus location exists yet", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1", { postcode: null }]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    expect(document.getElementById("location-current").textContent).toContain("No campus location set yet");
  });

  it("saving a postcode PATCHes the location and triggers a rerender", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/universities/uni-1", { postcode: null }],
      ["/api/v1/universities/uni-1/location", { id: "uni-1", postcode: "M13 9PL" }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    document.getElementById("loc-postcode").value = "M13 9PL";
    document.querySelector('[data-action="save-location"]').click();
    await flushPromises();

    const patchCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/universities/uni-1/location" && opts.method === "PATCH");
    expect(JSON.parse(patchCall[1].body)).toEqual({ postcode: "M13 9PL" });
    expect(window.__caplinkRerender).toHaveBeenCalled();
  });
});

describe("university-admin.js — Single Sign-On tab", () => {
  beforeEach(() => {
    state.activeTab = "sso";
    state.universityId = "uni-1";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    state.activeTab = null;
  });

  it("shows SSO as not configured when saml_enabled is false", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1/saml-config", { saml_enabled: false }]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    expect(document.getElementById("sso-current").textContent).toContain("SSO not configured");
  });

  it("shows the current entity ID/SSO URL when already enabled", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1/saml-config", {
      saml_enabled: true, saml_idp_entity_id: "https://idp.example.ac.uk/entity", saml_idp_sso_url: "https://idp.example.ac.uk/sso",
    }]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    expect(document.getElementById("sso-current").textContent).toContain("https://idp.example.ac.uk/entity");
  });

  it("uploading IdP metadata XML posts it and reloads the current config", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/universities/uni-1/saml-config", { saml_enabled: false }],
      ["/api/v1/universities/uni-1/saml-idp-metadata", { saml_enabled: true, saml_idp_entity_id: "e", saml_idp_sso_url: "u" }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    document.getElementById("sso-metadata-xml").value = "<EntityDescriptor>...</EntityDescriptor>";
    document.querySelector('[data-action="upload-metadata"]').click();
    await flushPromises();

    const uploadCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/universities/uni-1/saml-idp-metadata" && opts.method === "POST");
    expect(uploadCall).toBeTruthy();
    expect(document.querySelector("#toasts .toast.success").textContent).toContain("SSO configured from metadata");
  });

  it("refuses to upload empty metadata without ever calling the API", async () => {
    const fetchMock = routeFetch([["/api/v1/universities/uni-1/saml-config", { saml_enabled: false }]]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    document.querySelector('[data-action="upload-metadata"]').click();
    await flushPromises();

    expect(fetchMock.mock.calls.some(([url]) => url === "/api/v1/universities/uni-1/saml-idp-metadata")).toBe(false);
    expect(document.querySelector("#toasts .toast.error").textContent).toContain("Paste or upload");
  });

  it("saving manual entry requires all three fields before calling the API", async () => {
    const fetchMock = routeFetch([["/api/v1/universities/uni-1/saml-config", { saml_enabled: false }]]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    document.getElementById("sso-entity-id").value = "https://idp.example.ac.uk/entity";
    document.querySelector('[data-action="save-manual"]').click();
    await flushPromises();

    expect(fetchMock.mock.calls.some(([url, opts]) => url === "/api/v1/universities/uni-1/saml-config" && opts?.method === "PATCH")).toBe(false);
    expect(document.querySelector("#toasts .toast.error").textContent).toContain("All three fields are required");
  });

  it("saving a complete manual entry PATCHes the SAML config", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/universities/uni-1/saml-config", { saml_enabled: false }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    document.getElementById("sso-entity-id").value = "https://idp.example.ac.uk/entity";
    document.getElementById("sso-sso-url").value = "https://idp.example.ac.uk/sso";
    document.getElementById("sso-cert").value = "MIIDpDCC...";
    document.querySelector('[data-action="save-manual"]').click();
    await flushPromises();

    const patchCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/universities/uni-1/saml-config" && opts.method === "PATCH");
    expect(patchCall).toBeTruthy();
    const body = JSON.parse(patchCall[1].body);
    expect(body).toEqual({
      saml_enabled: true,
      saml_idp_entity_id: "https://idp.example.ac.uk/entity",
      saml_idp_sso_url: "https://idp.example.ac.uk/sso",
      saml_idp_x509_cert: "MIIDpDCC...",
    });
  });
});

describe("university-admin.js — Employability Report tab", () => {
  beforeEach(() => {
    state.activeTab = "report";
    state.universityId = "uni-1";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    state.activeTab = null;
  });

  it("shows a clear message when there are no students registered yet", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1/employability-report", { total_students: 0 }]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    expect(document.getElementById("report-body").textContent).toContain("No students registered");
  });

  it("renders the KPI tiles and band breakdown for a populated report", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/universities/uni-1/employability-report", {
      total_students: 10, applied_students: 6, hired_students: 3, completed_students: 2,
      total_earnings_gbp: 450, average_student_rating: 4.6, rated_engagements: 2,
      band_breakdown: [{ band: "year_3", total_students: 10, applied_students: 6, hired_students: 3, completed_students: 2, earnings_gbp: 450 }],
    }]]));
    const app = setupApp();
    await renderAdmin(app);
    await flushPromises();

    const body = document.getElementById("report-body");
    expect(body.textContent).toContain("Total students");
    expect(body.textContent).toContain("★ 4.6");
    expect(body.textContent).toContain("year 3");
  });
});

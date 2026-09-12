// Technical Implementation Plan 8.a.ii — business.js's page flows: the
// business profile card + postcode save, posting a project, requesting
// university access, listing "my projects", viewing/deciding applicants,
// creating a contract, and the shortlist + match-explanation drill-down
// (5.c.ii). shared/contracts.js and shared/messaging.js (the other two
// tabs renderBusiness() can delegate to) aren't covered here.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { state, clearSession } from "./api.js";
import { renderBusiness } from "./business.js";

const BUSINESS_PROFILE = {
  company_name: "DataCraft Analytics",
  industry: "Data & analytics",
  global_trust_tier: "standard",
  average_rating: 4.2,
  completed_projects_count: 3,
  postcode: null,
};

const MY_PROJECT = {
  id: "proj-1",
  title: "Build a landing page",
  status: "open",
  category: "software_engineering",
  hourly_rate_gbp: 20,
  duration_label: "1 week",
};

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

const BASE_ROUTES = [
  ["/api/v1/businesses/me", BUSINESS_PROFILE],
  ["/api/v1/payments/setup-status", { ready: true }],
  ["/api/v1/projects/mine", [MY_PROJECT]],
];

describe("business.js — projects tab", () => {
  beforeEach(() => {
    window.__caplinkRerender = vi.fn();
    state.activeTab = null;
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    delete window.__caplinkRerender;
  });

  it("renders the business profile card and the project list", async () => {
    vi.stubGlobal("fetch", routeFetch(BASE_ROUTES));
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    expect(app.textContent).toContain("DataCraft Analytics");
    expect(app.textContent).toContain("not set (won't appear in local business search)");
    expect(app.textContent).toContain("Build a landing page");
  });

  it("saving a postcode PATCHes the profile and triggers a rerender", async () => {
    const fetchMock = routeFetch(BASE_ROUTES);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    document.getElementById("bp-postcode").value = "M1 1AE";
    document.querySelector('[data-action="save-postcode"]').click();
    await flushPromises();

    const patchCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/businesses/me" && opts.method === "PATCH");
    expect(patchCall).toBeTruthy();
    expect(JSON.parse(patchCall[1].body)).toEqual({ postcode: "M1 1AE" });
    expect(window.__caplinkRerender).toHaveBeenCalled();
  });

  it("completes Stripe payment setup automatically when not yet ready", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/businesses/me", BUSINESS_PROFILE],
      ["/api/v1/payments/setup-status", { ready: false }],
      ["/api/v1/payments/setup-intent", { client_secret: "secret", customer_id: "cus_1", simulated: true }],
      ["/api/v1/projects/mine", []],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    expect(fetchMock.mock.calls.some(([url, opts]) => url === "/api/v1/payments/setup-intent" && opts.method === "POST")).toBe(true);
  });

  it("posting a project looks up the target university then posts and reloads the list", async () => {
    const fetchMock = routeFetch([
      ...BASE_ROUTES,
      ["/api/v1/universities/manchester/public", { id: "uni-1", name: "University of Manchester" }],
      ["/api/v1/projects", { id: "proj-new", title: "Landing page copy review", status: "open" }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    document.querySelector(".pp-band").click(); // select the first band checkbox
    document.querySelector('[data-action="post-project"]').click();
    await flushPromises();

    const postCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/projects" && opts.method === "POST");
    expect(postCall).toBeTruthy();
    const posted = JSON.parse(postCall[1].body);
    expect(posted.target_university_ids).toEqual(["uni-1"]);
    expect(document.querySelector("#toasts .toast.success").textContent).toContain("Project posted");
  });

  it("shows the safeguarding rejection reason right on the form when posting is refused", async () => {
    const forbidden = new Error("No approved agreement covers this band/category");
    forbidden.status = 403;
    const fetchMock = routeFetch([
      ...BASE_ROUTES,
      ["/api/v1/universities/manchester/public", { id: "uni-1", name: "University of Manchester" }],
      ["/api/v1/projects", forbidden],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    document.querySelector('[data-action="post-project"]').click();
    await flushPromises();

    expect(document.querySelector("#toasts .toast.error").textContent).toContain("No approved agreement covers this band/category");
  });

  it("requesting university access posts a pending agreement", async () => {
    const fetchMock = routeFetch([
      ...BASE_ROUTES,
      ["/api/v1/universities/manchester/public", { id: "uni-1", name: "University of Manchester" }],
      [/business-agreements$/, { id: "agreement-1", status: "pending" }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    document.querySelector('[data-action="request-access"]').click();
    await flushPromises();

    expect(document.querySelector("#toasts .toast.success").textContent).toContain('agreement agreement-1 is now "pending"');
  });

  it("viewing applicants, changing status, and messaging all wire up correctly", async () => {
    const applicant = {
      application_id: "app-1", full_name: "Aisha Rahman", degree_title: "BSc CS",
      status: "submitted", match_score_at_application: 0.8, proposed_rate_gbp: 18,
      cover_note: "Keen.", student_user_id: "student-user-1",
    };
    const fetchMock = routeFetch([
      ...BASE_ROUTES,
      ["/api/v1/projects/proj-1/applications", [applicant]],
      [/\/api\/v1\/applications\/app-1$/, { ...applicant, status: "shortlisted" }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    document.querySelector('[data-view-applicants="proj-1"]').click();
    await flushPromises();
    expect(document.getElementById("applicants-proj-1").textContent).toContain("Aisha Rahman");

    const select = document.querySelector('.app-status-select[data-app="app-1"]');
    select.value = "shortlisted";
    document.querySelector('[data-set-status="app-1"]').click();
    await flushPromises();

    const patchCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/applications/app-1" && opts.method === "PATCH");
    expect(JSON.parse(patchCall[1].body)).toEqual({ status: "shortlisted" });

    document.querySelector('[data-message-applicant="student-user-1"]').click();
    expect(state.activeTab).toBe("messages");
  });

  it("creating a contract from an applicant submits both milestones", async () => {
    const applicant = {
      application_id: "app-1", full_name: "Aisha Rahman", degree_title: "BSc CS",
      status: "shortlisted", match_score_at_application: 0.8, proposed_rate_gbp: 18,
      cover_note: "Keen.", student_user_id: "student-user-1",
    };
    const fetchMock = routeFetch([
      ...BASE_ROUTES,
      ["/api/v1/projects/proj-1/applications", [applicant]],
      ["/api/v1/contracts", { id: "contract-1" }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    document.querySelector('[data-view-applicants="proj-1"]').click();
    await flushPromises();
    document.querySelector('[data-create-contract="app-1"]').click();
    document.querySelector('[data-action="submit-contract"]').click();
    await flushPromises();

    const contractCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/contracts" && opts.method === "POST");
    expect(contractCall).toBeTruthy();
    const body = JSON.parse(contractCall[1].body);
    expect(body.application_id).toBe("app-1");
    expect(body.milestones).toHaveLength(2);
    expect(document.querySelector("#toasts .toast.success").textContent).toContain("Contract created: contract-1");
  });

  it("viewing the shortlist and drilling into a match explanation toggles it open and closed", async () => {
    const candidate = {
      student_id: "student-1", full_name: "Priya Patel", degree_title: "BSc Data Science",
      university_name: "Manchester", average_rating: 4.7, completed_projects_count: 1,
      match_score: 0.9, match_reasons: ["Python match"],
    };
    const explanation = { score: 0.9, breakdown: [{ name: "skills", detail: "Python", raw_score: 0.95, weight: 0.5, contribution: 0.475 }] };
    const fetchMock = routeFetch([
      ...BASE_ROUTES,
      ["/api/v1/projects/proj-1/shortlist", [candidate]],
      ["/api/v1/projects/proj-1/shortlist/student-1/explanation", explanation],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderBusiness(app);
    await flushPromises();

    document.querySelector('[data-view-shortlist="proj-1"]').click();
    await flushPromises();
    expect(document.getElementById("shortlist-proj-1").textContent).toContain("Priya Patel");

    document.querySelector('[data-explain="student-1"]').click();
    await flushPromises();
    expect(document.getElementById("explain-student-1").textContent).toContain("90% overall");

    document.querySelector('[data-explain="student-1"]').click();
    expect(document.getElementById("explain-student-1")).toBeNull();
  });
});

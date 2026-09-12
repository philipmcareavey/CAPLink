// Technical Implementation Plan 8.a.ii — student.js's page flows: the feed
// tab (profile card, suggested projects, applying, employer suggestions),
// the edit-profile modal, local business search, and ratings history.
// shared/contracts.js and shared/messaging.js (the other two tabs
// renderStudent() can delegate to) have their own separate concerns and
// aren't covered here — this file focuses on what student.js itself owns.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { state, clearSession } from "./api.js";
import { renderStudent } from "./student.js";

const PROFILE = {
  degree_title: "BSc Computer Science",
  band: "year_3",
  average_rating: 4.5,
  completed_projects_count: 2,
  on_time_rate: 0.9,
  skills: ["Python", "SQL"],
  hourly_rate_expectation_gbp: 20,
  weekly_hours_available: 10,
};

const FEED_PROJECT = {
  id: "proj-1",
  title: "Build a landing page",
  description: "Static marketing page.",
  category: "software_engineering",
  hourly_rate_gbp: 20,
  duration_label: "1 week",
  is_remote: true,
  status: "open",
  match_score: 0.8,
  match_reasons: ["Python match"],
};

function routeFetch(routes) {
  return vi.fn(async (url) => {
    for (const [matcher, respond] of routes) {
      const matches = typeof matcher === "string" ? url === matcher : matcher.test(url);
      if (matches) {
        if (respond instanceof Error) throw respond;
        return { ok: true, json: async () => (typeof respond === "function" ? respond(url) : respond) };
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

describe("student.js — feed tab", () => {
  beforeEach(() => {
    window.__caplinkRerender = vi.fn();
    state.activeTab = null;
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    delete window.__caplinkRerender;
  });

  it("renders the profile card, the matched feed, and employer suggestions", async () => {
    vi.stubGlobal("fetch", routeFetch([
      ["/api/v1/students/me", PROFILE],
      ["/api/v1/payments/connect/status", { onboarded: true }],
      [/\/api\/v1\/projects\/feed/, [FEED_PROJECT]],
      ["/api/v1/recommendations/employer-suggestions", [{ employer_type: "Analytics consultancies", reason: "Great fit" }]],
    ]));
    const app = setupApp();

    await renderStudent(app);
    await flushPromises();

    expect(app.textContent).toContain("BSc Computer Science");
    expect(app.textContent).toContain("Build a landing page");
    expect(app.textContent).toContain("Analytics consultancies");
    expect(document.querySelector("[data-apply]")).toBeTruthy();
  });

  it("shows a friendly empty state when no projects are visible yet", async () => {
    vi.stubGlobal("fetch", routeFetch([
      ["/api/v1/students/me", PROFILE],
      ["/api/v1/payments/connect/status", { onboarded: true }],
      [/\/api\/v1\/projects\/feed/, []],
      ["/api/v1/recommendations/employer-suggestions", []],
    ]));
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    expect(document.getElementById("student-feed").textContent).toContain("No open projects visible");
  });

  it("applying prompts for a cover note and posts the application", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/students/me", PROFILE],
      ["/api/v1/payments/connect/status", { onboarded: true }],
      [/\/api\/v1\/projects\/feed/, [FEED_PROJECT]],
      ["/api/v1/recommendations/employer-suggestions", []],
      ["/api/v1/applications", { id: "app-1", match_score_at_application: 0.75 }],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("prompt", vi.fn(() => "Keen to help."));
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    document.querySelector("[data-apply]").click();
    await flushPromises();

    expect(window.prompt).toHaveBeenCalled();
    const applicationCall = fetchMock.mock.calls.find(([url]) => url === "/api/v1/applications");
    expect(applicationCall).toBeTruthy();
    expect(JSON.parse(applicationCall[1].body)).toEqual({ project_id: "proj-1", cover_note: "Keen to help." });
    expect(document.querySelector("#toasts .toast.success").textContent).toContain("Applied!");
  });

  it("does not apply at all when the cover-note prompt is cancelled", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/students/me", PROFILE],
      ["/api/v1/payments/connect/status", { onboarded: true }],
      [/\/api\/v1\/projects\/feed/, [FEED_PROJECT]],
      ["/api/v1/recommendations/employer-suggestions", []],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("prompt", vi.fn(() => null));
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    document.querySelector("[data-apply]").click();
    await flushPromises();

    expect(fetchMock.mock.calls.some(([url]) => url === "/api/v1/applications")).toBe(false);
  });

  it("kicks off Stripe Connect onboarding when the student hasn't completed it yet", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/students/me", PROFILE],
      ["/api/v1/payments/connect/status", { onboarded: false }],
      ["/api/v1/payments/connect/onboarding-link", { onboarding_url: "https://connect.stripe.com/x" }],
      [/\/api\/v1\/projects\/feed/, []],
      ["/api/v1/recommendations/employer-suggestions", []],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    expect(fetchMock.mock.calls.some(([url, opts]) => url === "/api/v1/payments/connect/onboarding-link" && opts.method === "POST")).toBe(true);
  });

  it("editing the profile saves the updated skills/rate and triggers a rerender", async () => {
    const fetchMock = routeFetch([
      ["/api/v1/students/me", PROFILE],
      ["/api/v1/payments/connect/status", { onboarded: true }],
      [/\/api\/v1\/projects\/feed/, []],
      ["/api/v1/recommendations/employer-suggestions", []],
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    document.getElementById("edit-skills-btn").click();
    document.getElementById("em-skills").value = "Python, React";
    document.getElementById("em-rate").value = "25";
    document.getElementById("em-hours").value = "15";
    document.querySelector('[data-action="save-profile"]').click();
    await flushPromises();

    const patchCall = fetchMock.mock.calls.find(([url, opts]) => url === "/api/v1/students/me" && opts.method === "PATCH");
    expect(patchCall).toBeTruthy();
    expect(JSON.parse(patchCall[1].body)).toEqual({
      skills: ["Python", "React"],
      hourly_rate_expectation_gbp: 25,
      weekly_hours_available: 15,
    });
    expect(window.__caplinkRerender).toHaveBeenCalled();
  });
});

describe("student.js — local search tab", () => {
  beforeEach(() => {
    state.activeTab = "local";
    state.universityId = "uni-1";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    state.activeTab = null;
  });

  it("runs an initial search on render and lists nearby businesses", async () => {
    vi.stubGlobal("fetch", routeFetch([
      [/local-businesses\/meta/, { total_results: 1, radius_miles: 10, campus_name: "Manchester", campus_postcode: "M1 1AA" }],
      [/local-businesses\?/, [{ company_name: "DataCraft Analytics", industry: "Analytics", distance_miles: 2.1, average_rating: 4.2, completed_projects_count: 3, degree_relevance_label: "High", degree_relevance_score: 0.9 }]],
    ]));
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    expect(document.getElementById("ls-results").textContent).toContain("DataCraft Analytics");
    expect(document.getElementById("ls-results").textContent).toContain("1 result(s)");
  });

  it("shows a clear message when the university has no campus location set", async () => {
    const error = new Error("Campus location not set");
    error.status = 400;
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw error;
    }));
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    expect(document.getElementById("ls-results").textContent).toContain("campus location hasn't been set yet");
  });
});

describe("student.js — ratings history tab", () => {
  beforeEach(() => {
    state.activeTab = "ratings";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
    state.activeTab = null;
  });

  it("shows a hidden placeholder for a given-but-not-yet-released rating, and reveals a released one", async () => {
    vi.stubGlobal("fetch", routeFetch([
      ["/api/v1/ratings/mine", [
        { id: "r1", direction: "given", is_released: false, overall_score: null, visibility: "public" },
        { id: "r2", direction: "received", is_released: true, overall_score: 4.5, visibility: "public" },
      ]],
    ]));
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    const text = document.getElementById("ratings-list").textContent;
    expect(text).toContain("Hidden until they rate you too");
    expect(text).toContain("4.5");
  });

  it("shows an empty state when there's no rating history yet", async () => {
    vi.stubGlobal("fetch", routeFetch([["/api/v1/ratings/mine", []]]));
    const app = setupApp();
    await renderStudent(app);
    await flushPromises();

    expect(document.getElementById("ratings-list").textContent).toContain("No ratings yet");
  });
});

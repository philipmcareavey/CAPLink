// Technical Implementation Plan 8.a.ii. Session state and the fetch wrapper
// every page module goes through for every API call — worth testing
// directly rather than only indirectly through whichever page happens to
// call it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, clearSession, decodeJwt, setSession, state } from "./api.js";

// A real, structurally valid JWT (header.payload.signature) with a payload
// this test controls — signature is never verified client-side (that's the
// server's job), so any base64url string works for the third segment.
function makeToken(payload) {
  const b64url = (obj) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${b64url({ alg: "HS256", typ: "JWT" })}.${b64url(payload)}.fakesignature`;
}

describe("decodeJwt", () => {
  it("decodes a real base64url-encoded JWT payload back to the original object", () => {
    const token = makeToken({ sub: "user-123", role: "student", exp: 1234567890 });
    expect(decodeJwt(token)).toEqual({ sub: "user-123", role: "student", exp: 1234567890 });
  });

  it("handles base64url's - and _ characters correctly, not just plain base64", () => {
    // A payload whose base64 encoding is likely to contain +/ in standard
    // base64 (which JWT's base64url replaces with -/_) — a naive atob()
    // without the -> + and _ -> / translation would corrupt this.
    const token = makeToken({ university_id: "a>>>b???c" });
    expect(decodeJwt(token).university_id).toBe("a>>>b???c");
  });
});

describe("setSession / clearSession", () => {
  afterEach(() => clearSession());

  it("populates state from a real token pair's decoded claims", () => {
    const access_token = makeToken({ sub: "u1", role: "business", university_id: null });
    setSession({ access_token, refresh_token: "refresh-abc" });

    expect(state.token).toBe(access_token);
    expect(state.refreshToken).toBe("refresh-abc");
    expect(state.role).toBe("business");
    expect(state.userId).toBe("u1");
    expect(state.universityId).toBeNull();
  });

  it("reads university_id from the token when present, for a student/admin", () => {
    const access_token = makeToken({ sub: "u2", role: "student", university_id: "uni-42" });
    setSession({ access_token, refresh_token: "r" });
    expect(state.universityId).toBe("uni-42");
  });

  it("resets activeTab and openThreadId on a fresh login, not carrying over stale UI state", () => {
    state.activeTab = "messages";
    state.openThreadId = "thread-1";
    const access_token = makeToken({ sub: "u3", role: "student", university_id: "x" });
    setSession({ access_token, refresh_token: "r" });
    expect(state.activeTab).toBeNull();
    expect(state.openThreadId).toBeNull();
  });

  it("clearSession resets every session field back to its logged-out default", () => {
    const access_token = makeToken({ sub: "u4", role: "student", university_id: "x" });
    setSession({ access_token, refresh_token: "r" });
    clearSession();
    expect(state.token).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.role).toBeNull();
    expect(state.userId).toBeNull();
    expect(state.universityId).toBeNull();
  });
});

describe("api()", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    clearSession();
  });

  it("sends an Authorization header when a session token exists and auth isn't disabled", async () => {
    state.token = "abc123";
    fetch.mockResolvedValue({ ok: true, json: async () => ({ result: "ok" }) });

    await api("/projects/feed");

    const [, options] = fetch.mock.calls[0];
    expect(options.headers.Authorization).toBe("Bearer abc123");
  });

  it("omits the Authorization header entirely when auth: false is passed", async () => {
    state.token = "abc123";
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    await api("/auth/login", { auth: false });

    const [, options] = fetch.mock.calls[0];
    expect(options.headers.Authorization).toBeUndefined();
  });

  it("JSON-encodes a request body and sets the method", async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    await api("/applications", { method: "POST", body: { project_id: "p1" } });

    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/api/v1/applications");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ project_id: "p1" });
  });

  it("throws an Error carrying the server's detail message and status on a non-OK response", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ detail: "Not your contract" }),
    });

    await expect(api("/contracts/123/accept-terms", { method: "POST" })).rejects.toMatchObject({
      message: "Not your contract",
      status: 403,
    });
  });

  it("stringifies a structured FastAPI validation error rather than showing '[object Object]'", async () => {
    const validationError = [{ loc: ["body", "email"], msg: "field required" }];
    fetch.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: async () => ({ detail: validationError }),
    });

    await expect(api("/auth/register/student", { method: "POST" })).rejects.toMatchObject({
      message: JSON.stringify(validationError),
      status: 422,
    });
  });

  it("falls back to the HTTP status text when a non-OK response has no JSON body at all", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("no body");
      },
    });

    await expect(api("/projects/feed")).rejects.toMatchObject({
      message: "Internal Server Error",
      status: 500,
    });
  });
});

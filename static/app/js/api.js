export const API = "/api/v1";

export const state = {
  token: null, refreshToken: null, role: null, userId: null, universityId: null,
  registerTab: "login",
  activeTab: null,       // which sub-section of the current role view is showing
  openThreadId: null,    // which message thread is currently open, if any
};

export function decodeJwt(token) {
  const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  const json = decodeURIComponent(atob(b64).split("").map(c => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")).join(""));
  return JSON.parse(json);
}

export async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) {
    const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText;
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return data;
}

export function setSession(tokens) {
  state.token = tokens.access_token;
  state.refreshToken = tokens.refresh_token;
  const claims = decodeJwt(tokens.access_token);
  state.role = claims.role;
  state.userId = claims.sub;
  state.universityId = claims.university_id || null;
  state.activeTab = null;
  state.openThreadId = null;
}

export function clearSession() {
  Object.assign(state, {
    token: null, refreshToken: null, role: null, userId: null, universityId: null,
    activeTab: null, openThreadId: null,
  });
}

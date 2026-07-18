import { api, state } from "./api.js";
import { el, toast, badgeClass, pct, gbp, esc, titleCase } from "./dom.js";
import { renderContractsSection } from "./shared/contracts.js";
import { renderMessagesSection, startThread } from "./shared/messaging.js";

export const STUDENT_TABS = [
  { key: "feed", label: "Feed" },
  { key: "contracts", label: "Contracts" },
  { key: "messages", label: "Messages" },
  { key: "local", label: "Local Search" },
  { key: "ratings", label: "My Ratings" },
];

export async function renderStudent(app) {
  if (state.activeTab === "contracts") {
    return renderContractsSection(app, "student", (otherUserId, projectId) => {
      state.activeTab = "messages";
      startThread(otherUserId, projectId).then(() => window.__caplinkRerender());
    });
  }
  if (state.activeTab === "messages") return renderMessagesSection(app);
  if (state.activeTab === "local") return renderLocalSearch(app);
  if (state.activeTab === "ratings") return renderRatingsHistory(app);
  return renderFeed(app);
}

// ---------- Feed tab: profile, suggested projects, apply, employer suggestions ----------

async function renderFeed(app) {
  app.appendChild(el(`<div class="card" id="student-profile">Loading profile…</div>`));
  app.appendChild(el(`<div class="card"><h4 class="section">Suggested projects</h4><div id="student-feed">Loading feed…</div></div>`));
  app.appendChild(el(`<div class="card"><h4 class="section">Career suggestions</h4><div id="employer-suggestions">Loading…</div></div>`));

  try {
    const profile = await api("/students/me");
    document.getElementById("student-profile").outerHTML = renderStudentProfileCard(profile);
    document.getElementById("edit-skills-btn").addEventListener("click", () => openEditProfile(profile));
  } catch (e) { toast("Couldn't load profile: " + e.message, "error"); }

  try {
    const feed = await api("/projects/feed?page=1&page_size=20");
    document.getElementById("student-feed").innerHTML = feed.length
      ? feed.map(renderProjectMatchCard).join("")
      : `<p class="muted">No open projects visible to you right now — check your university/band with an admin.</p>`;
    document.querySelectorAll("[data-apply]").forEach(btn => btn.addEventListener("click", () => applyToProject(btn.dataset.apply, btn.dataset.title)));
  } catch (e) { document.getElementById("student-feed").innerHTML = `<p class="muted">Couldn't load feed: ${e.message}</p>`; }

  try {
    const suggestions = await api("/recommendations/employer-suggestions");
    document.getElementById("employer-suggestions").innerHTML = suggestions.length
      ? suggestions.map(s => `<p style="margin:0 0 10px"><span class="chip reason">${esc(s.employer_type)}</span> <span class="muted">${esc(s.reason)}</span></p>`).join("")
      : `<p class="muted">No suggestions yet — add more skills to your profile.</p>`;
  } catch (e) { document.getElementById("employer-suggestions").innerHTML = `<p class="muted">Couldn't load suggestions: ${e.message}</p>`; }
}

function renderStudentProfileCard(p) {
  return `
    <div class="card">
      <div class="eyebrow">Your profile</div>
      <h3 class="title">${esc(p.degree_title)}</h3>
      <p class="muted">${titleCase(p.band)} · ★ ${p.average_rating.toFixed(1)} (${p.completed_projects_count} completed) · on-time ${(p.on_time_rate * 100).toFixed(0)}%</p>
      <div style="margin:10px 0">${p.skills.map(s => `<span class="chip">${esc(s)}</span>`).join("")}</div>
      <p class="muted">Rate expectation: ${gbp(p.hourly_rate_expectation_gbp)}/hr · ${p.weekly_hours_available ?? "—"}h/week available</p>
      <button class="ghost small" id="edit-skills-btn" style="margin-top:10px">Edit skills / rate</button>
    </div>
  `;
}

function openEditProfile(profile) {
  const app = document.getElementById("app");
  const modal = el(`
    <div class="card" id="edit-modal">
      <h4 class="section">Edit profile</h4>
      <div class="field"><label>Skills (comma separated)</label><input id="em-skills" value="${esc(profile.skills.join(", "))}"></div>
      <div class="field"><label>Hourly rate expectation (£)</label><input id="em-rate" type="number" value="${profile.hourly_rate_expectation_gbp ?? ""}"></div>
      <div class="field"><label>Weekly hours available</label><input id="em-hours" type="number" value="${profile.weekly_hours_available ?? ""}"></div>
      <div class="row">
        <button data-action="save-profile">Save &amp; refresh feed</button>
        <button class="ghost" data-action="cancel-edit">Cancel</button>
      </div>
    </div>
  `);
  app.insertBefore(modal, app.children[1]);
  document.querySelector('[data-action="cancel-edit"]').addEventListener("click", () => document.getElementById("edit-modal").remove());
  document.querySelector('[data-action="save-profile"]').addEventListener("click", async () => {
    try {
      await api("/students/me", { method: "PATCH", body: {
        skills: document.getElementById("em-skills").value.split(",").map(s => s.trim()).filter(Boolean),
        hourly_rate_expectation_gbp: Number(document.getElementById("em-rate").value) || null,
        weekly_hours_available: Number(document.getElementById("em-hours").value) || null,
      }});
      toast("Profile updated — match scores will reflect this now", "success");
      window.__caplinkRerender();
    } catch (e) { toast("Update failed: " + e.message, "error"); }
  });
}

function renderProjectMatchCard(p) {
  return `
    <div class="item-card">
      <h4>${esc(p.title)} <span class="badge ${badgeClass(p.status)}">${titleCase(p.status)}</span></h4>
      <p class="muted">${titleCase(p.category)} · ${gbp(p.hourly_rate_gbp)}/hr · ${esc(p.duration_label)} · ${p.is_remote ? "remote" : (p.location_label || "on-site")}</p>
      <p style="font-size:13px">${esc(p.description)}</p>
      <div class="score-track"><div style="width:${pct(p.match_score)}"></div></div>
      <p class="muted" style="margin:2px 0 8px">${pct(p.match_score)} match</p>
      <div>${p.match_reasons.map(r => `<span class="chip reason">${esc(r)}</span>`).join("")}</div>
      <div style="margin-top:12px"><button class="small" data-apply="${p.id}" data-title="${esc(p.title)}">Apply</button></div>
    </div>
  `;
}

async function applyToProject(projectId, title) {
  const coverNote = prompt(`Cover note for "${title}" (optional):`, "Happy to get started right away.");
  if (coverNote === null) return;
  try {
    const application = await api("/applications", { method: "POST", body: { project_id: projectId, cover_note: coverNote } });
    toast(`Applied! Match score ${pct(application.match_score_at_application)}. Application id: ${application.id}`, "success");
  } catch (e) { toast("Application failed: " + e.message, "error"); }
}

// ---------- Local Search tab ----------

async function renderLocalSearch(app) {
  app.appendChild(el(`
    <div class="card">
      <h4 class="section">Local business search</h4>
      <p class="muted">Degree-relevant businesses near your campus — only businesses your university has approved for your band show up at all.</p>
      <div class="grid">
        <div class="field"><label>Radius (miles)</label><input id="ls-radius" type="number" value="10" min="0.5" max="100"></div>
        <div class="field"><label>Min degree-relevance (0-1)</label><input id="ls-relevance" type="number" value="0" min="0" max="1" step="0.1"></div>
      </div>
      <button data-action="run-search">Search</button>
      <div id="ls-results" style="margin-top:16px"></div>
    </div>
  `));
  document.querySelector('[data-action="run-search"]').addEventListener("click", runLocalSearch);
  runLocalSearch();
}

async function runLocalSearch() {
  const resultsEl = document.getElementById("ls-results");
  const radius = document.getElementById("ls-radius").value || 10;
  const relevance = document.getElementById("ls-relevance").value || 0;
  resultsEl.innerHTML = "Searching…";
  try {
    const meta = await api(`/universities/${state.universityId}/local-businesses/meta?radius_miles=${radius}`);
    const results = await api(`/universities/${state.universityId}/local-businesses?radius_miles=${radius}&min_degree_relevance=${relevance}`);
    resultsEl.innerHTML = `<p class="muted">${meta.total_results} result(s) within ${meta.radius_miles} miles of ${esc(meta.campus_name)} (${meta.campus_postcode || "no postcode set"})</p>`
      + (results.length
        ? results.map(r => `
          <div class="item-card">
            <h4>${esc(r.company_name)}</h4>
            <p class="muted">${esc(r.industry || "—")} · ${r.distance_miles} mi away · ★ ${r.average_rating.toFixed(1)} (${r.completed_projects_count} completed)</p>
            <span class="chip reason">${esc(r.degree_relevance_label)} — ${pct(r.degree_relevance_score)}</span>
          </div>
        `).join("")
        : `<div class="empty-state">No businesses found in range yet.</div>`);
  } catch (e) {
    if (e.status === 400) {
      resultsEl.innerHTML = `<div class="empty-state">Your university's campus location hasn't been set yet — ask a university admin to add a campus postcode (Partnerships tab &gt; Campus Location).</div>`;
    } else {
      resultsEl.innerHTML = `<p class="muted">Search failed: ${esc(e.message)}</p>`;
    }
  }
}

// ---------- My Ratings tab ----------

async function renderRatingsHistory(app) {
  app.appendChild(el(`<div class="card"><h4 class="section">My ratings</h4><div id="ratings-list">Loading…</div></div>`));
  const listEl = document.getElementById("ratings-list");
  try {
    const ratings = await api("/ratings/mine");
    listEl.innerHTML = ratings.length
      ? ratings.map(r => `
        <div class="item-card">
          <h4><span class="badge ${r.direction === "given" ? "warn" : "good"}">${r.direction}</span> ${r.overall_score != null ? "★ " + r.overall_score.toFixed(1) : ""}</h4>
          ${r.overall_score == null
            ? `<p class="muted">Hidden until they rate you too (blind-until-both-submit).</p>`
            : `<p class="muted">${r.is_released ? "Released" : "Given, not yet released"} · visibility: ${titleCase(r.visibility)}</p>`}
        </div>
      `).join("")
      : `<div class="empty-state">No ratings yet — these appear once a contract's milestones are underway.</div>`;
  } catch (e) { listEl.innerHTML = `<p class="muted">Couldn't load ratings: ${e.message}</p>`; }
}

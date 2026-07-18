import { api, state } from "./api.js";
import { el, toast, badgeClass, pct, gbp, esc, titleCase } from "./dom.js";
import { BANDS, CATEGORIES, APPLICATION_STATUSES } from "./constants.js";
import { renderContractsSection } from "./shared/contracts.js";
import { renderMessagesSection, startThread } from "./shared/messaging.js";

export const BUSINESS_TABS = [
  { key: "projects", label: "My Projects" },
  { key: "contracts", label: "Contracts" },
  { key: "messages", label: "Messages" },
];

function goToMessages(otherUserId, projectId) {
  state.activeTab = "messages";
  startThread(otherUserId, projectId).then(() => window.__caplinkRerender());
}

export async function renderBusiness(app) {
  if (state.activeTab === "contracts") return renderContractsSection(app, "business", goToMessages);
  if (state.activeTab === "messages") return renderMessagesSection(app);
  return renderProjectsTab(app);
}

async function renderProjectsTab(app) {
  app.appendChild(el(`<div class="card" id="business-profile">Loading profile…</div>`));
  app.appendChild(renderPostProjectForm());
  app.appendChild(renderRequestAccessForm());
  app.appendChild(el(`<div class="card"><h4 class="section">My projects</h4><div id="business-projects">Loading…</div></div>`));

  try {
    const profile = await api("/businesses/me");
    document.getElementById("business-profile").outerHTML = `
      <div class="card">
        <div class="eyebrow">Your profile</div>
        <h3 class="title">${esc(profile.company_name)}</h3>
        <p class="muted">${esc(profile.industry || "—")} · trust tier: ${titleCase(profile.global_trust_tier)} · ★ ${profile.average_rating.toFixed(1)} (${profile.completed_projects_count} completed)</p>
        <p class="muted">Postcode: ${profile.postcode ? esc(profile.postcode) : "not set (won't appear in local business search)"}</p>
        <div class="row" style="margin-top:10px">
          <input id="bp-postcode" placeholder="e.g. M1 1AE" style="max-width:200px">
          <button class="ghost small" data-action="save-postcode">Save postcode</button>
        </div>
      </div>`;
    document.querySelector('[data-action="save-postcode"]').addEventListener("click", async () => {
      try {
        await api("/businesses/me", { method: "PATCH", body: { postcode: document.getElementById("bp-postcode").value } });
        toast("Postcode saved — geocoded automatically", "success");
        window.__caplinkRerender();
      } catch (e) { toast("Couldn't save postcode: " + e.message, "error"); }
    });
  } catch (e) { toast("Couldn't load profile: " + e.message, "error"); }

  await loadMyProjects();
}

function renderPostProjectForm() {
  return el(`
    <div class="card">
      <h4 class="section">Post a new project</h4>
      <p class="muted">Requires an <strong>approved</strong> agreement with the target university covering this category and every selected band — otherwise you'll see the safeguarding rejection reason right here.</p>
      <div class="grid">
        <div class="field"><label>Title</label><input id="pp-title" value="Landing page copy review"></div>
        <div class="field"><label>Category</label><select id="pp-category">${CATEGORIES.map(c => `<option value="${c}">${titleCase(c)}</option>`).join("")}</select></div>
        <div class="field"><label>Duration label</label><input id="pp-duration" value="1 week"></div>
        <div class="field"><label>Hourly rate (£)</label><input id="pp-rate" type="number" value="18"></div>
        <div class="field"><label>Required skills (comma separated)</label><input id="pp-skills" value="Python, SQL"></div>
        <div class="field"><label>Target university slug</label><input id="pp-slug" value="manchester"></div>
      </div>
      <div class="field"><label>Description</label><textarea id="pp-desc">Short paid project, remote, flexible hours.</textarea></div>
      <div class="field"><label>Target bands</label><div class="band-checks">${BANDS.map(b => `<label class="band-check"><input type="checkbox" class="pp-band" value="${b}"> ${titleCase(b)}</label>`).join("")}</div></div>
      <button data-action="post-project">Post project</button>
    </div>
  `);
}

async function wirePostProjectForm() {
  const btn = document.querySelector('[data-action="post-project"]');
  if (!btn) return;
  btn.addEventListener("click", async () => {
    try {
      const slug = document.getElementById("pp-slug").value.trim();
      const uni = await api(`/universities/${slug}/public`, { auth: false });
      const bands = Array.from(document.querySelectorAll(".pp-band:checked")).map(cb => cb.value);
      const project = await api("/projects", { method: "POST", body: {
        title: document.getElementById("pp-title").value,
        description: document.getElementById("pp-desc").value,
        category: document.getElementById("pp-category").value,
        required_skills: document.getElementById("pp-skills").value.split(",").map(s => s.trim()).filter(Boolean),
        duration_label: document.getElementById("pp-duration").value,
        hourly_rate_gbp: Number(document.getElementById("pp-rate").value),
        target_university_ids: [uni.id],
        target_bands: bands,
      }});
      toast(`Project posted: "${project.title}" (status: ${project.status})`, "success");
      await loadMyProjects();
    } catch (e) { toast("Couldn't post project: " + e.message, "error"); }
  });
}

function renderRequestAccessForm() {
  return el(`
    <div class="card">
      <h4 class="section">Request access to a university</h4>
      <p class="muted">A brand-new business needs this before it can post anything. Starts <span class="badge warn">pending</span> until a university admin reviews and approves it.</p>
      <div class="row">
        <input id="ra-slug" placeholder="university slug, e.g. manchester" value="manchester" style="max-width:260px">
        <button class="ghost" data-action="request-access">Request access</button>
      </div>
    </div>
  `);
}

async function wireRequestAccessForm() {
  const btn = document.querySelector('[data-action="request-access"]');
  if (!btn) return;
  btn.addEventListener("click", async () => {
    try {
      const slug = document.getElementById("ra-slug").value.trim();
      const uni = await api(`/universities/${slug}/public`, { auth: false });
      const me = await api("/businesses/me");
      const agreement = await api(`/universities/${uni.id}/business-agreements`, { method: "POST", body: { business_id: me.id } });
      toast(`Access requested — agreement ${agreement.id} is now "${agreement.status}". A university admin needs to approve it.`, "success");
    } catch (e) { toast("Request failed: " + e.message, "error"); }
  });
}

async function loadMyProjects() {
  const container = document.getElementById("business-projects");
  try {
    const projects = await api("/projects/mine");
    container.innerHTML = projects.length
      ? projects.map(p => `
        <div class="item-card">
          <h4>${esc(p.title)} <span class="badge ${badgeClass(p.status)}">${titleCase(p.status)}</span></h4>
          <p class="muted">${titleCase(p.category)} · ${gbp(p.hourly_rate_gbp)}/hr · ${esc(p.duration_label)}</p>
          <p class="muted">id: <code class="idval">${p.id}</code></p>
          <button class="small ghost" data-view-applicants="${p.id}">View applicants</button>
          <div class="applicants" id="applicants-${p.id}"></div>
        </div>
      `).join("")
      : `<p class="muted">No projects yet — post one above.</p>`;
    container.querySelectorAll("[data-view-applicants]").forEach(b => b.addEventListener("click", () => loadApplicants(b.dataset.viewApplicants)));
  } catch (e) {
    container.innerHTML = `<p class="muted">Couldn't load projects: ${e.message}</p>`;
  }
  wirePostProjectForm();
  wireRequestAccessForm();
}

async function loadApplicants(projectId) {
  const container = document.getElementById("applicants-" + projectId);
  container.innerHTML = "<p class='muted'>Loading applicants…</p>";
  try {
    const applicants = await api(`/projects/${projectId}/applications`);
    container.innerHTML = applicants.length
      ? applicants.map(a => `
        <div class="item-card">
          <h4>${esc(a.full_name)} <span class="badge ${badgeClass(a.status)}">${a.status}</span></h4>
          <p class="muted">${esc(a.degree_title)} · match ${a.match_score_at_application != null ? pct(a.match_score_at_application) : "—"} · proposed ${gbp(a.proposed_rate_gbp)}/hr</p>
          <p style="font-size:13px">${esc(a.cover_note || "")}</p>
          <p class="muted">application id: <code class="idval">${a.application_id}</code></p>
          <div class="row">
            <select class="app-status-select" data-app="${a.application_id}">
              ${APPLICATION_STATUSES.map(s => `<option value="${s}" ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}
            </select>
            <button class="small ghost" data-set-status="${a.application_id}">Update status</button>
            <button class="small ghost" data-message-applicant="${a.student_user_id}">Message</button>
            <button class="small" data-create-contract="${a.application_id}">Create contract</button>
          </div>
        </div>
      `).join("")
      : `<p class="muted">No one has applied to this project yet.</p>`;
    container.querySelectorAll("[data-set-status]").forEach(b => b.addEventListener("click", async () => {
      const select = container.querySelector(`.app-status-select[data-app="${b.dataset.setStatus}"]`);
      try {
        await api(`/applications/${b.dataset.setStatus}`, { method: "PATCH", body: { status: select.value } });
        toast("Application status updated to " + select.value, "success");
        loadApplicants(projectId);
      } catch (e) { toast("Update failed: " + e.message, "error"); }
    }));
    container.querySelectorAll("[data-message-applicant]").forEach(b => b.addEventListener("click", () => {
      goToMessages(b.dataset.messageApplicant, projectId);
    }));
    container.querySelectorAll("[data-create-contract]").forEach(b => b.addEventListener("click", () => openContractForm(b.dataset.createContract, projectId)));
  } catch (e) {
    container.innerHTML = `<p class="muted">Couldn't load applicants: ${e.message}</p>`;
  }
}

function openContractForm(applicationId, projectId) {
  const container = document.getElementById("applicants-" + projectId);
  const form = el(`
    <div class="card" style="background:var(--paper)">
      <h4 class="section">New contract for application ${applicationId}</h4>
      <div class="grid">
        <div class="field"><label>Milestone 1 description</label><input class="cf-m1-desc" value="First half of the work"></div>
        <div class="field"><label>Milestone 1 payment (£)</label><input class="cf-m1-amt" type="number" value="80"></div>
        <div class="field"><label>Milestone 2 description</label><input class="cf-m2-desc" value="Final delivery"></div>
        <div class="field"><label>Milestone 2 payment (£)</label><input class="cf-m2-amt" type="number" value="120"></div>
      </div>
      <button data-action="submit-contract">Create contract</button>
    </div>
  `);
  container.appendChild(form);
  container.querySelector('[data-action="submit-contract"]').addEventListener("click", async () => {
    try {
      const contract = await api("/contracts", { method: "POST", body: {
        application_id: applicationId,
        milestones: [
          { description: container.querySelector(".cf-m1-desc").value, payment_amount_gbp: Number(container.querySelector(".cf-m1-amt").value) },
          { description: container.querySelector(".cf-m2-desc").value, payment_amount_gbp: Number(container.querySelector(".cf-m2-amt").value) },
        ],
      }});
      toast(`Contract created: ${contract.id} — see it under the Contracts tab.`, "success");
      loadApplicants(projectId);
    } catch (e) { toast("Contract creation failed: " + e.message, "error"); }
  });
}

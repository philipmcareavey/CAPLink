import { api, state } from "./api.js";
import { el, toast, badgeClass, esc, titleCase, gbp } from "./dom.js";
import { BANDS, CATEGORIES, AGREEMENT_STATUSES } from "./constants.js";

export const ADMIN_TABS = [
  { key: "agreements", label: "Partnerships" },
  { key: "location", label: "Campus Location" },
  { key: "sso", label: "Single Sign-On" },
  { key: "report", label: "Employability Report" },
];

export async function renderAdmin(app) {
  if (state.activeTab === "location") return renderLocationTab(app);
  if (state.activeTab === "sso") return renderSsoTab(app);
  if (state.activeTab === "report") return renderReportTab(app);
  return renderAgreementsTab(app);
}

// ---------- Partnerships (business agreements) ----------

async function renderAgreementsTab(app) {
  app.appendChild(el(`<div class="card"><h4 class="section">Business partnership agreements</h4><p class="muted">University id (from your login): <code class="idval">${state.universityId}</code></p><div id="admin-agreements">Loading…</div></div>`));
  await loadAgreements();
}

async function loadAgreements() {
  const container = document.getElementById("admin-agreements");
  try {
    const agreements = await api(`/universities/${state.universityId}/business-agreements`);
    container.innerHTML = agreements.length
      ? agreements.map(renderAgreementCard).join("")
      : `<p class="muted">No agreements yet — have a business request access first.</p>`;
    agreements.forEach(a => wireAgreementForm(a));
  } catch (e) { container.innerHTML = `<p class="muted">Couldn't load agreements: ${e.message}</p>`; }
}

function renderAgreementCard(a) {
  const bandRows = BANDS.map(b => `
    <div class="lc-row"><span>${titleCase(b)}</span>
      <span class="permit-pill ${a.allowed_bands.includes(b) ? "allow" : ""}">${a.allowed_bands.includes(b) ? "Permitted" : "Not permitted"}</span>
    </div>`).join("");
  return `
    <div class="ledger-card" id="agreement-${a.id}">
      <div class="lc-head">
        <span class="lc-title">Business <code class="idval">${a.business_id}</code></span>
        <span class="badge ${badgeClass(a.status)}">${a.status}</span>
      </div>
      ${bandRows}
      <div class="lc-row"><span>Category access</span><span class="permit-track">${
        a.allowed_categories.length
          ? a.allowed_categories.map(c => `<span class="permit-pill allow">${titleCase(c)}</span>`).join("")
          : `<span class="permit-pill">None yet</span>`
      }</span></div>
      <details>
        <summary>Manage this agreement</summary>
        <div class="field"><label for="ag-status-${a.id}">Status</label><select id="ag-status-${a.id}" class="ag-status">${AGREEMENT_STATUSES.map(s => `<option value="${s}" ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select></div>
        <div class="field"><span class="field-label" id="ag-bands-label-${a.id}">Allowed bands</span><div class="band-checks" role="group" aria-labelledby="ag-bands-label-${a.id}">${BANDS.map(b => `<label class="band-check"><input type="checkbox" class="ag-band" value="${b}" ${a.allowed_bands.includes(b) ? "checked" : ""}> ${titleCase(b)}</label>`).join("")}</div></div>
        <div class="field"><span class="field-label" id="ag-categories-label-${a.id}">Allowed categories</span><div class="band-checks" role="group" aria-labelledby="ag-categories-label-${a.id}">${CATEGORIES.map(c => `<label class="band-check"><input type="checkbox" class="ag-category" value="${c}" ${a.allowed_categories.includes(c) ? "checked" : ""}> ${titleCase(c)}</label>`).join("")}</div></div>
        <button class="small" data-save-agreement="${a.id}">Save decision</button>
      </details>
    </div>
  `;
}

function wireAgreementForm(a) {
  const cardEl = document.getElementById("agreement-" + a.id);
  const btn = cardEl.querySelector(`[data-save-agreement="${a.id}"]`);
  btn.addEventListener("click", async () => {
    try {
      const status = cardEl.querySelector(".ag-status").value;
      const allowed_bands = Array.from(cardEl.querySelectorAll(".ag-band:checked")).map(cb => cb.value);
      const allowed_categories = Array.from(cardEl.querySelectorAll(".ag-category:checked")).map(cb => cb.value);
      await api(`/universities/${state.universityId}/business-agreements/${a.id}`, {
        method: "PATCH", body: { status, allowed_bands, allowed_categories },
      });
      toast("Agreement updated", "success");
      loadAgreements();
    } catch (e) { toast("Save failed: " + e.message, "error"); }
  });
}

// ---------- Campus Location ----------

async function renderLocationTab(app) {
  app.appendChild(el(`
    <div class="card">
      <h4 class="section">Campus location</h4>
      <p class="muted">Setting this is what unlocks "local business search" for your students — it's the centre point every radius search is measured from. Requires internet access (geocodes via postcodes.io).</p>
      <div id="location-current" class="muted" style="margin-bottom:12px">Loading…</div>
      <div class="row">
        <input id="loc-postcode" placeholder="e.g. M13 9PL" style="max-width:220px">
        <button data-action="save-location">Save &amp; geocode</button>
      </div>
    </div>
  `));
  try {
    const uni = await api(`/universities/${state.universityId}`);
    document.getElementById("location-current").textContent = uni.postcode
      ? `Current: ${uni.postcode} (${uni.latitude}, ${uni.longitude})`
      : "No campus location set yet.";
  } catch (e) { /* GET /universities/{id} has no auth requirement in the API, but keep this non-fatal either way */ }

  document.querySelector('[data-action="save-location"]').addEventListener("click", async () => {
    try {
      await api(`/universities/${state.universityId}/location`, {
        method: "PATCH", body: { postcode: document.getElementById("loc-postcode").value },
      });
      toast("Campus location saved", "success");
      window.__caplinkRerender();
    } catch (e) { toast("Couldn't save location: " + esc(e.message), "error"); }
  });
}

// ---------- Single Sign-On (Technical Implementation Plan 2.b.iv) ----------
// The backend (PATCH .../saml-config for manual entry, POST
// .../saml-idp-metadata for an XML upload, and GET .../saml-config to read
// current state — the last of these didn't exist until now, added
// specifically so this screen has something to show before an admin
// overwrites it blind) has been real since Epic 2.b (2026-09-06); this is
// just the first UI in front of it.

async function renderSsoTab(app) {
  app.appendChild(el(`
    <div class="card">
      <h4 class="section">University single sign-on</h4>
      <p class="muted">Let your students and staff sign in with your institution's own identity
        provider instead of a CAPLink password. Email/password sign-in keeps working either way —
        this is additive, never a replacement.</p>
      <div id="sso-current" class="muted" style="margin-bottom:16px">Loading current configuration…</div>

      <h4 class="section">Option 1 — upload your IdP's metadata file</h4>
      <p class="muted">The fastest, least error-prone path: export the metadata XML from your IdP
        (e.g. your Entra ID / Okta / Shibboleth admin console) and upload it here. The entity ID, SSO
        URL, and signing certificate are all extracted automatically.</p>
      <div class="field"><label for="sso-metadata-xml">IdP metadata XML</label>
        <textarea id="sso-metadata-xml" rows="6" placeholder="<EntityDescriptor ...>...</EntityDescriptor>"></textarea>
      </div>
      <button data-action="upload-metadata">Upload &amp; save</button>

      <h4 class="section" style="margin-top:24px">Option 2 — enter details manually</h4>
      <p class="muted">If you already have these three values to hand.</p>
      <div class="field"><label for="sso-entity-id">IdP entity ID</label><input id="sso-entity-id" placeholder="https://idp.youruniversity.ac.uk/adfs/services/trust"></div>
      <div class="field"><label for="sso-sso-url">IdP SSO URL</label><input id="sso-sso-url" placeholder="https://idp.youruniversity.ac.uk/adfs/ls"></div>
      <div class="field"><label for="sso-cert">IdP signing certificate (PEM or base64, no headers needed)</label>
        <textarea id="sso-cert" rows="6" placeholder="MIIDpDCCAoygAwIBAgIG..."></textarea>
      </div>
      <button data-action="save-manual">Save</button>
    </div>
  `));

  await loadSsoConfig();

  document.querySelector('[data-action="upload-metadata"]').addEventListener("click", async () => {
    try {
      const metadata_xml = document.getElementById("sso-metadata-xml").value.trim();
      if (!metadata_xml) { toast("Paste or upload the IdP's metadata XML first", "error"); return; }
      await api(`/universities/${state.universityId}/saml-idp-metadata`, {
        method: "POST", body: { metadata_xml, saml_enabled: true },
      });
      toast("SSO configured from metadata", "success");
      loadSsoConfig();
    } catch (e) { toast("Couldn't save metadata: " + esc(e.message), "error"); }
  });

  document.querySelector('[data-action="save-manual"]').addEventListener("click", async () => {
    try {
      const saml_idp_entity_id = document.getElementById("sso-entity-id").value.trim();
      const saml_idp_sso_url = document.getElementById("sso-sso-url").value.trim();
      const saml_idp_x509_cert = document.getElementById("sso-cert").value.trim();
      if (!saml_idp_entity_id || !saml_idp_sso_url || !saml_idp_x509_cert) {
        toast("All three fields are required", "error");
        return;
      }
      await api(`/universities/${state.universityId}/saml-config`, {
        method: "PATCH", body: { saml_enabled: true, saml_idp_entity_id, saml_idp_sso_url, saml_idp_x509_cert },
      });
      toast("SSO configured", "success");
      loadSsoConfig();
    } catch (e) { toast("Couldn't save SSO config: " + esc(e.message), "error"); }
  });
}

async function loadSsoConfig() {
  const box = document.getElementById("sso-current");
  try {
    const cfg = await api(`/universities/${state.universityId}/saml-config`);
    box.innerHTML = cfg.saml_enabled
      ? `<span class="badge good">SSO enabled</span> — entity ID <code class="idval">${esc(cfg.saml_idp_entity_id)}</code>, SSO URL <code class="idval">${esc(cfg.saml_idp_sso_url)}</code>`
      : `<span class="badge">SSO not configured</span> — students and staff sign in with email/password only.`;
  } catch (e) { box.textContent = "Couldn't load current SSO configuration: " + e.message; }
}

// ---------- Employability Report (Technical Implementation Plan 5.d.iii) ----------

async function renderReportTab(app) {
  app.appendChild(el(`
    <div class="card">
      <h4 class="section">Employability outcomes</h4>
      <p class="muted">How many of your students engaged with the platform, got hired, actually completed
        their work, and what they earned — computed live from applications, contracts and milestones, not a
        stored snapshot.</p>
      <div id="report-body">Loading…</div>
    </div>
  `));

  const body = document.getElementById("report-body");
  try {
    const r = await api(`/universities/${state.universityId}/employability-report`);
    if (r.total_students === 0) {
      body.innerHTML = `<p class="muted">No students registered at your university yet.</p>`;
      return;
    }
    body.innerHTML = `
      <div class="stat-grid">
        <div class="stat-tile"><div class="stat-value">${r.total_students}</div><div class="stat-label">Total students</div></div>
        <div class="stat-tile"><div class="stat-value">${r.hired_students}</div><div class="stat-label">Hired (of ${r.applied_students} applied)</div></div>
        <div class="stat-tile"><div class="stat-value">${r.completed_students}</div><div class="stat-label">Completed a paid contract</div></div>
        <div class="stat-tile"><div class="stat-value">${gbp(r.total_earnings_gbp)}</div><div class="stat-label">Total student earnings</div></div>
      </div>
      <p class="muted" style="margin:16px 0 0">
        ${r.average_student_rating != null
          ? `Average business rating of students: <strong>★ ${r.average_student_rating.toFixed(1)}</strong> (from ${r.rated_engagements} released rating${r.rated_engagements === 1 ? "" : "s"})`
          : "No released ratings of your students yet."}
      </p>
      <h4 class="section" style="margin-top:24px">By band</h4>
      ${r.band_breakdown.map(b => `
        <div class="ledger-card">
          <div class="lc-head"><span class="lc-title">${titleCase(b.band)}</span><span class="badge">${b.total_students} student${b.total_students === 1 ? "" : "s"}</span></div>
          <div class="lc-row"><span>Applied</span><span>${b.applied_students}</span></div>
          <div class="lc-row"><span>Hired</span><span>${b.hired_students}</span></div>
          <div class="lc-row"><span>Completed a paid contract</span><span>${b.completed_students}</span></div>
          <div class="lc-row"><span>Earnings</span><span>${gbp(b.earnings_gbp)}</span></div>
        </div>
      `).join("")}
    `;
  } catch (e) { body.innerHTML = `<p class="muted">Couldn't load the report: ${esc(e.message)}</p>`; }
}

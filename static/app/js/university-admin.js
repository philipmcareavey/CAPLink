import { api, state } from "./api.js";
import { el, toast, badgeClass, esc, titleCase } from "./dom.js";
import { BANDS, CATEGORIES, AGREEMENT_STATUSES } from "./constants.js";

export const ADMIN_TABS = [
  { key: "agreements", label: "Partnerships" },
  { key: "location", label: "Campus Location" },
];

export async function renderAdmin(app) {
  if (state.activeTab === "location") return renderLocationTab(app);
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
        <div class="field"><label>Status</label><select class="ag-status">${AGREEMENT_STATUSES.map(s => `<option value="${s}" ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select></div>
        <div class="field"><label>Allowed bands</label><div class="band-checks">${BANDS.map(b => `<label class="band-check"><input type="checkbox" class="ag-band" value="${b}" ${a.allowed_bands.includes(b) ? "checked" : ""}> ${titleCase(b)}</label>`).join("")}</div></div>
        <div class="field"><label>Allowed categories</label><div class="band-checks">${CATEGORIES.map(c => `<label class="band-check"><input type="checkbox" class="ag-category" value="${c}" ${a.allowed_categories.includes(c) ? "checked" : ""}> ${titleCase(c)}</label>`).join("")}</div></div>
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

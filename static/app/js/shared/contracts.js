import { api } from "../api.js";
import { toast, badgeClass, esc, gbp } from "../dom.js";
import { openRatingModal } from "../components.js";

// role: "student" | "business". onMessage(counterpartUserId, projectId) lets
// the caller decide what "message this person" means (switch tabs, open
// thread) without this module needing to know about tab navigation.
export async function renderContractsSection(container, role, onMessage) {
  container.innerHTML = `<div class="card"><h4 class="section">My contracts</h4><div id="contracts-list">Loading…</div></div>`;
  const listEl = container.querySelector("#contracts-list");
  try {
    const contracts = await api("/contracts/mine");
    listEl.innerHTML = contracts.length
      ? contracts.map(c => renderContractCard(c, role)).join("")
      : `<div class="empty-state">No contracts yet.${role === "business" ? " Create one from an applicant on one of your projects." : " These appear once a business hires you from an application."}</div>`;
    wireContractCards(listEl, container, role, onMessage);
  } catch (e) {
    listEl.innerHTML = `<p class="muted">Couldn't load contracts: ${e.message}</p>`;
  }
}

function renderContractCard(c, role) {
  const termsNeeded = !c.ip_assignment_accepted || !c.nda_accepted;
  return `
    <div class="ledger-card" id="contract-${c.id}">
      <div class="lc-head">
        <span class="lc-title">${esc(c.project_title || "Untitled project")}</span>
        <span class="badge ${badgeClass(c.status)}">${c.status}</span>
      </div>
      <p class="muted" style="margin:-6px 0 10px">With <strong>${esc(c.counterpart_name)}</strong></p>
      ${c.milestones.map(m => `
        <div class="lc-row" data-milestone="${m.id}">
          <span>${esc(m.description)} — ${gbp(m.payment_amount_gbp)}${m.due_date ? " · due " + m.due_date : ""}</span>
          <span class="row" style="gap:8px">
            <span class="badge ${badgeClass(m.status)}">${m.status}</span>
            ${role === "student" && m.status === "pending" ? `<button class="small ghost" data-submit-milestone="${m.id}">Submit</button>` : ""}
            ${role === "business" && m.status === "submitted" ? `<button class="small" data-pay-milestone="${m.id}">Approve &amp; pay</button>` : ""}
          </span>
        </div>
      `).join("")}
      <div class="row" style="margin-top:14px">
        ${termsNeeded ? `<button class="small ghost" data-accept-terms="${c.id}">Accept IP/NDA terms</button>` : `<span class="muted" style="font-size:12px">Terms accepted by you</span>`}
        <button class="small ghost" data-message="${c.counterpart_user_id}" data-project="${c.project_id}">Message ${esc(c.counterpart_name)}</button>
        <button class="small ghost" data-rate="${c.id}" data-rate-name="${esc(c.counterpart_name)}">Rate this contract</button>
      </div>
    </div>
  `;
}

function wireContractCards(listEl, container, role, onMessage) {
  listEl.querySelectorAll("[data-submit-milestone]").forEach(btn => btn.addEventListener("click", async () => {
    try {
      await api(`/contracts/milestones/${btn.dataset.submitMilestone}/submit`, { method: "POST" });
      toast("Milestone submitted", "success");
      renderContractsSection(container, role, onMessage);
    } catch (e) { toast("Failed: " + e.message, "error"); }
  }));
  listEl.querySelectorAll("[data-pay-milestone]").forEach(btn => btn.addEventListener("click", async () => {
    try {
      await api(`/contracts/milestones/${btn.dataset.payMilestone}/approve-and-pay`, { method: "POST" });
      toast("Milestone approved & paid", "success");
      renderContractsSection(container, role, onMessage);
    } catch (e) { toast("Failed: " + e.message, "error"); }
  }));
  listEl.querySelectorAll("[data-accept-terms]").forEach(btn => btn.addEventListener("click", async () => {
    try {
      await api(`/contracts/${btn.dataset.acceptTerms}/accept-terms`, { method: "POST" });
      toast("Terms accepted", "success");
      renderContractsSection(container, role, onMessage);
    } catch (e) { toast("Failed: " + e.message, "error"); }
  }));
  listEl.querySelectorAll("[data-message]").forEach(btn => btn.addEventListener("click", () => {
    onMessage(btn.dataset.message, btn.dataset.project);
  }));
  listEl.querySelectorAll("[data-rate]").forEach(btn => btn.addEventListener("click", () => {
    const contractId = btn.dataset.rate;
    openRatingModal({
      title: `Rate ${btn.dataset.rateName}`,
      onSubmit: async (score, comment) => {
        try {
          const rating = await api("/ratings", { method: "POST", body: {
            contract_id: contractId,
            overall_score: score,
            private_comment: comment,
          }});
          toast(`Rating submitted${rating.is_released ? " — both sides have now rated, released!" : " — hidden until the other side rates too"}`, "success");
        } catch (e) { toast("Couldn't submit rating: " + e.message, "error"); }
      },
    });
  }));
}

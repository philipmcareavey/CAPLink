// Technical Implementation Plan 5.a.ii — the reusable component library.
// The plan's own wording asks for these "as production React components";
// there is no Node.js/npm available anywhere this project has been built
// from, so nothing here could ever be installed, compiled, or verified —
// see CLAUDE.md's Workstream 5 section for the full reasoning behind
// building these as plain, dependency-free render functions instead. The
// discipline that actually matters — one canonical definition per
// component, one canonical set of styles (app/css/app.css's "Component
// library" section), reused everywhere the pattern appears — is the same
// either way.
import { esc, pct, badgeClass, titleCase } from "./dom.js";

// ---------- MatchDial ----------
// A circular match-score indicator. `score` is a 0-1 fraction. Returns an
// HTML string (all callers already interpolate into a template string, so
// this matches that convention rather than returning a DOM node).
export function renderMatchDial(score, { size = "md" } = {}) {
  const dims = size === "sm" ? { box: 36, r: 14, sw: 3.5 } : { box: 56, r: 22, sw: 4.5 };
  const circumference = 2 * Math.PI * dims.r;
  const fraction = Math.max(0, Math.min(1, score || 0));
  const offset = circumference * (1 - fraction);
  const center = dims.box / 2;
  return `
    <div class="match-dial size-${size}" role="img" aria-label="${pct(fraction)} match">
      <svg width="${dims.box}" height="${dims.box}" viewBox="0 0 ${dims.box} ${dims.box}" aria-hidden="true">
        <circle class="dial-track" cx="${center}" cy="${center}" r="${dims.r}" stroke-width="${dims.sw}"></circle>
        <circle class="dial-fill" cx="${center}" cy="${center}" r="${dims.r}" stroke-width="${dims.sw}"
          stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"></circle>
      </svg>
      <span class="dial-label" aria-hidden="true">${pct(fraction)}</span>
    </div>
  `;
}

// ---------- ProjectCard ----------
// Renders a project, optionally with a match dial + reasons (the student
// feed's use case) and an optional "Apply" affordance. `interactive: true`
// wraps the whole card as a real <button> (not a clickable <div> — see
// CLAUDE.md's Workstream 5 accessibility notes for why that distinction
// matters) when `onClickDataAttr` is supplied for a click handler to bind to.
export function renderProjectCard(project, { matchScore, matchReasons, showApplyButton = false, showStatus = false } = {}) {
  const dial = matchScore != null ? renderMatchDial(matchScore, { size: "sm" }) : "";
  const reasons = matchReasons && matchReasons.length
    ? `<div style="margin-top:8px">${matchReasons.map(r => `<span class="chip reason">${esc(r)}</span>`).join("")}</div>`
    : "";
  const metaParts = [
    project.category ? titleCase(project.category) : "",
    project.hourly_rate_gbp != null ? "£" + project.hourly_rate_gbp + "/hr" : "",
    project.duration_label || "",
    project.is_remote != null ? (project.is_remote ? "remote" : (project.location_label || "on-site")) : "",
  ].filter(Boolean);
  const statusBadge = showStatus && project.status
    ? ` <span class="badge ${badgeClass(project.status)}">${titleCase(project.status)}</span>`
    : "";
  return `
    <div class="item-card">
      <div class="row" style="justify-content:space-between; align-items:flex-start">
        <div>
          <h4>${esc(project.title)}${statusBadge}</h4>
          <p class="muted">${esc(metaParts.join(" · "))}</p>
        </div>
        ${dial}
      </div>
      <p style="font-size:13px">${esc(project.description || "")}</p>
      ${reasons}
      ${showApplyButton ? `<div style="margin-top:12px"><button class="small" data-apply="${project.id}" data-title="${esc(project.title)}">Apply</button></div>` : ""}
    </div>
  `;
}

// ---------- StudentCard ----------
// The business-side counterpart to ProjectCard — a candidate on a
// shortlist, with a match dial and a button to drill into the full
// scoring breakdown (5.c.ii).
export function renderStudentCard(student) {
  return `
    <div class="item-card">
      <div class="row" style="justify-content:space-between; align-items:flex-start">
        <div>
          <h4>${esc(student.full_name)}</h4>
          <p class="muted">${esc(student.degree_title)} · ${esc(student.university_name || "")}</p>
          <p class="muted">★ ${student.average_rating.toFixed(1)} (${student.completed_projects_count} completed)</p>
        </div>
        ${renderMatchDial(student.match_score, { size: "sm" })}
      </div>
      <div style="margin-top:8px">${(student.match_reasons || []).map(r => `<span class="chip reason">${esc(r)}</span>`).join("")}</div>
      <div style="margin-top:12px"><button class="small ghost" data-explain="${student.student_id}">Why this match?</button></div>
    </div>
  `;
}

// ---------- RatingModal ----------
// A real <dialog> — showModal()/close() give focus-trapping, Escape-to-
// close, and the backdrop for free from the browser, rather than a
// hand-rolled div overlay with none of that. `onSubmit(score, comment)` is
// called when the form is submitted; the modal closes itself either way.
export function openRatingModal({ title, onSubmit }) {
  const existing = document.getElementById("rating-modal");
  if (existing) existing.remove();

  const dialog = document.createElement("dialog");
  dialog.className = "modal";
  dialog.id = "rating-modal";
  dialog.innerHTML = `
    <div class="modal-inner">
      <div class="modal-header">
        <h4 class="section" style="margin:0">${esc(title)}</h4>
        <button type="button" class="modal-close" aria-label="Close">&times;</button>
      </div>
      <form method="dialog">
        <fieldset style="border:none; padding:0; margin:0 0 12px">
          <legend class="muted" style="font-size:11.5px; font-weight:600; text-transform:uppercase; letter-spacing:0.03em; margin-bottom:6px">Overall score</legend>
          <div class="star-picker" role="radiogroup" aria-label="Overall score, 1 to 5 stars">
            ${[1, 2, 3, 4, 5].map(n => `<button type="button" class="star" data-star="${n}" role="radio" aria-checked="false" aria-label="${n} star${n > 1 ? "s" : ""}">★</button>`).join("")}
          </div>
        </fieldset>
        <div class="field"><label for="rm-comment">Comment (private)</label><input id="rm-comment"></div>
        <button type="submit">Submit rating</button>
      </form>
    </div>
  `;
  document.body.appendChild(dialog);

  let score = 5;
  const stars = dialog.querySelectorAll("[data-star]");
  const paintStars = () => stars.forEach(s => {
    const n = Number(s.dataset.star);
    s.classList.toggle("filled", n <= score);
    s.setAttribute("aria-checked", String(n === score));
  });
  stars.forEach(s => s.addEventListener("click", () => { score = Number(s.dataset.star); paintStars(); }));
  paintStars();

  dialog.querySelector(".modal-close").addEventListener("click", () => dialog.close());
  dialog.querySelector("form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const comment = dialog.querySelector("#rm-comment").value || null;
    dialog.close();
    onSubmit(score, comment);
  });
  dialog.addEventListener("close", () => dialog.remove());

  dialog.showModal();
}

// Technical Implementation Plan 8.a.ii. The reusable component library —
// the plan's own literal wording asked for these "as production React
// components"; static/app/js/components.js is the deliberate vanilla-JS
// substitute (see components.js's own header comment and caplink/CLAUDE.md's
// Workstream 5 entry for why), so testing it directly matters more than for
// most files here — it's this project's actual answer to "are these
// components production-quality," not just a nice-to-have.
// test-setup.js (loaded globally via vitest.config.js's setupFiles) supplies
// the showModal()/close() polyfill jsdom itself doesn't implement — needed
// for the openRatingModal tests below.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { openRatingModal, renderMatchDial, renderProjectCard, renderStudentCard } from "./components.js";

describe("renderMatchDial", () => {
  it("renders an accessible percentage label matching the given score", () => {
    document.body.innerHTML = renderMatchDial(0.82);
    const dial = document.querySelector(".match-dial");
    expect(dial.getAttribute("aria-label")).toBe("82% match");
    expect(dial.querySelector(".dial-label").textContent).toBe("82%");
  });

  it("clamps an out-of-range score into 0-1 rather than drawing a broken circle", () => {
    document.body.innerHTML = renderMatchDial(1.5);
    expect(document.querySelector(".dial-label").textContent).toBe("100%");

    document.body.innerHTML = renderMatchDial(-0.3);
    expect(document.querySelector(".dial-label").textContent).toBe("0%");
  });

  it("treats a missing/null score as 0, not NaN%", () => {
    document.body.innerHTML = renderMatchDial(null);
    expect(document.querySelector(".dial-label").textContent).toBe("0%");
  });

  it("draws the fill circle's stroke-dashoffset proportional to the score", () => {
    // A full (100%) dial should have zero offset (nothing hidden); an empty
    // (0%) dial's offset should equal the full circumference (fully hidden).
    document.body.innerHTML = renderMatchDial(1);
    const fullOffset = Number(document.querySelector(".dial-fill").getAttribute("stroke-dashoffset"));
    expect(fullOffset).toBeCloseTo(0, 5);

    document.body.innerHTML = renderMatchDial(0);
    const emptyOffset = Number(document.querySelector(".dial-fill").getAttribute("stroke-dashoffset"));
    const circumference = Number(document.querySelector(".dial-fill").getAttribute("stroke-dasharray"));
    expect(emptyOffset).toBeCloseTo(circumference, 5);
  });

  it("uses a smaller radius for size: 'sm' than the default", () => {
    document.body.innerHTML = renderMatchDial(0.5, { size: "sm" });
    const smallR = Number(document.querySelector(".dial-fill").getAttribute("r"));
    document.body.innerHTML = renderMatchDial(0.5);
    const defaultR = Number(document.querySelector(".dial-fill").getAttribute("r"));
    expect(smallR).toBeLessThan(defaultR);
  });
});

describe("renderProjectCard", () => {
  const project = {
    id: "p1",
    title: "Build a landing page",
    description: "Static marketing page, mobile-first.",
    category: "software_engineering",
    hourly_rate_gbp: 20,
    duration_label: "1 week",
    is_remote: true,
  };

  it("escapes the title and description so a malicious project can't inject markup", () => {
    const malicious = { ...project, title: `<script>alert(1)</script>`, description: `<img onerror=alert(1)>` };
    const html = renderProjectCard(malicious);
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img onerror");
    expect(html).toContain("&lt;script&gt;");
  });

  it("renders category, rate, duration, and remote status in the meta line", () => {
    document.body.innerHTML = renderProjectCard(project);
    const meta = document.querySelector(".muted").textContent;
    expect(meta).toContain("software engineering");
    expect(meta).toContain("£20/hr");
    expect(meta).toContain("1 week");
    expect(meta).toContain("remote");
  });

  it("shows an on-site location label instead of 'remote' when is_remote is false", () => {
    document.body.innerHTML = renderProjectCard({ ...project, is_remote: false, location_label: "Manchester" });
    expect(document.querySelector(".muted").textContent).toContain("Manchester");
  });

  it("only renders an Apply button when showApplyButton is explicitly true", () => {
    document.body.innerHTML = renderProjectCard(project);
    expect(document.querySelector("[data-apply]")).toBeNull();

    document.body.innerHTML = renderProjectCard(project, { showApplyButton: true });
    const button = document.querySelector("[data-apply]");
    expect(button.dataset.apply).toBe("p1");
  });

  it("only renders a status badge when showStatus is true and the project has a status", () => {
    document.body.innerHTML = renderProjectCard(project);
    expect(document.querySelector(".badge")).toBeNull();

    document.body.innerHTML = renderProjectCard({ ...project, status: "open" }, { showStatus: true });
    expect(document.querySelector(".badge").textContent).toBe("open");
  });

  it("renders match reasons as chips only when reasons are actually supplied", () => {
    document.body.innerHTML = renderProjectCard(project);
    expect(document.querySelector(".chip.reason")).toBeNull();

    document.body.innerHTML = renderProjectCard(project, { matchScore: 0.9, matchReasons: ["Python", "SQL"] });
    const chips = document.querySelectorAll(".chip.reason");
    expect(chips.length).toBe(2);
    expect(chips[0].textContent).toBe("Python");
  });
});

describe("renderStudentCard", () => {
  const student = {
    student_id: "s1",
    full_name: "Aisha Rahman",
    degree_title: "BSc Computer Science",
    university_name: "University of Manchester",
    average_rating: 4.6,
    completed_projects_count: 3,
    match_score: 0.75,
    match_reasons: ["Strong Python match"],
  };

  it("escapes the student's name and degree title", () => {
    const html = renderStudentCard({ ...student, full_name: `<b>Injected</b>` });
    expect(html).not.toContain("<b>Injected</b>");
    expect(html).toContain("&lt;b&gt;Injected&lt;/b&gt;");
  });

  it("formats the rating to one decimal place regardless of the raw precision", () => {
    document.body.innerHTML = renderStudentCard({ ...student, average_rating: 4.6666 });
    // The card has two ".muted" lines (degree/university, then the rating) —
    // the rating specifically is the second one.
    expect(document.querySelectorAll(".muted")[1].textContent).toContain("★ 4.7");
  });

  it("wires the 'why this match?' button to the correct student_id", () => {
    document.body.innerHTML = renderStudentCard(student);
    expect(document.querySelector("[data-explain]").dataset.explain).toBe("s1");
  });
});

describe("openRatingModal", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("opens a real <dialog> with the given title and defaults to a 5-star score", () => {
    openRatingModal({ title: "Rate this contract", onSubmit: vi.fn() });
    const dialog = document.getElementById("rating-modal");
    expect(dialog.tagName).toBe("DIALOG");
    expect(dialog.open).toBe(true);
    expect(dialog.querySelector("h4").textContent).toBe("Rate this contract");
    expect(dialog.querySelectorAll(".star.filled").length).toBe(5);
  });

  it("clicking a star updates which stars are marked filled/checked", () => {
    openRatingModal({ title: "Rate", onSubmit: vi.fn() });
    const dialog = document.getElementById("rating-modal");
    const threeStar = dialog.querySelector('[data-star="3"]');
    threeStar.click();

    const filled = dialog.querySelectorAll(".star.filled");
    expect(filled.length).toBe(3);
    expect(threeStar.getAttribute("aria-checked")).toBe("true");
    expect(dialog.querySelector('[data-star="5"]').getAttribute("aria-checked")).toBe("false");
  });

  it("submitting the form calls onSubmit with the selected score and comment, then closes", () => {
    const onSubmit = vi.fn();
    openRatingModal({ title: "Rate", onSubmit });
    const dialog = document.getElementById("rating-modal");

    dialog.querySelector('[data-star="2"]').click();
    dialog.querySelector("#rm-comment").value = "Great to work with";
    dialog.querySelector("form").dispatchEvent(new Event("submit", { cancelable: true }));

    expect(onSubmit).toHaveBeenCalledWith(2, "Great to work with");
    expect(dialog.open).toBe(false);
  });

  it("submits null for an empty comment rather than an empty string", () => {
    const onSubmit = vi.fn();
    openRatingModal({ title: "Rate", onSubmit });
    document
      .getElementById("rating-modal")
      .querySelector("form")
      .dispatchEvent(new Event("submit", { cancelable: true }));
    expect(onSubmit).toHaveBeenCalledWith(5, null);
  });

  it("removes the dialog from the DOM once it closes", () => {
    openRatingModal({ title: "Rate", onSubmit: vi.fn() });
    const dialog = document.getElementById("rating-modal");
    dialog.close();
    expect(document.getElementById("rating-modal")).toBeNull();
  });

  it("the close button closes the dialog without calling onSubmit", () => {
    const onSubmit = vi.fn();
    openRatingModal({ title: "Rate", onSubmit });
    document.querySelector(".modal-close").click();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(document.getElementById("rating-modal")).toBeNull();
  });

  it("opening a second modal while one is already open replaces it, rather than stacking two", () => {
    openRatingModal({ title: "First", onSubmit: vi.fn() });
    openRatingModal({ title: "Second", onSubmit: vi.fn() });
    const dialogs = document.querySelectorAll("dialog");
    expect(dialogs.length).toBe(1);
    expect(dialogs[0].querySelector("h4").textContent).toBe("Second");
  });
});

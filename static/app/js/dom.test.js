// Technical Implementation Plan 8.a.ii. Real coverage priority: esc() is
// this app's only defence against stored XSS in every render*() function and
// every page module — a real stored-XSS bug shipped once in this codebase
// (shared/contracts.js, Epic 2.c.ii) specifically because one file forgot to
// call esc() at all. Testing esc() directly guards the function every other
// file trusts, rather than re-testing "did this page call esc()" over and
// over in every page's own tests.
import { describe, expect, it, vi } from "vitest";
import { badgeClass, el, esc, formatDateTime, gbp, pct, titleCase, toast } from "./dom.js";

describe("esc", () => {
  it("escapes all five HTML-significant characters", () => {
    expect(esc(`<img src=x onerror="alert(1)">&'`)).toBe(
      "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#39;"
    );
  });

  it("neutralises the exact stored-XSS payload found in the real 2.c.ii bug", () => {
    // The real payload used to verify the contracts.js fix, reproduced here
    // as a permanent regression test for esc() itself. The security
    // property is that no literal "<" or ">" survives (nothing can become
    // a real tag/attribute again once inserted via innerHTML) — the inert
    // text "onerror=alert" surviving as plain text is fine and expected.
    const payload = `<img src=x onerror=alert('pwned')>`;
    const escaped = esc(payload);
    expect(escaped).not.toContain("<");
    expect(escaped).not.toContain(">");
    expect(escaped).toBe("&lt;img src=x onerror=alert(&#39;pwned&#39;)&gt;");
  });

  it("treats null and undefined as empty strings, not the literal words", () => {
    expect(esc(null)).toBe("");
    expect(esc(undefined)).toBe("");
  });

  it("passes through a plain string with nothing to escape unchanged", () => {
    expect(esc("Just a normal project title")).toBe("Just a normal project title");
  });

  it("coerces non-string input the same way string interpolation would", () => {
    expect(esc(42)).toBe("42");
  });
});

describe("badgeClass", () => {
  it.each([
    ["open", "good"],
    ["approved", "good"],
    ["paid", "good"],
    ["completed", "good"],
  ])("maps %s to good", (status, expected) => {
    expect(badgeClass(status)).toBe(expected);
  });

  it.each([
    ["rejected", "bad"],
    ["declined", "bad"],
    ["disputed", "bad"],
    ["cancelled", "bad"],
  ])("maps %s to bad", (status, expected) => {
    expect(badgeClass(status)).toBe(expected);
  });

  it("falls back to warn for anything not explicitly good or bad", () => {
    expect(badgeClass("pending")).toBe("warn");
    expect(badgeClass("shortlisted")).toBe("warn");
    expect(badgeClass("some-status-nobody-has-seen-yet")).toBe("warn");
  });
});

describe("titleCase", () => {
  it("replaces underscores with spaces without touching capitalisation", () => {
    expect(titleCase("software_engineering")).toBe("software engineering");
    expect(titleCase("year_3")).toBe("year 3");
  });

  it("handles null/undefined the same way esc does", () => {
    expect(titleCase(null)).toBe("");
    expect(titleCase(undefined)).toBe("");
  });
});

describe("pct", () => {
  it("converts a 0-1 fraction to a rounded whole-number percentage string", () => {
    expect(pct(0.5)).toBe("50%");
    expect(pct(0.876)).toBe("88%");
    expect(pct(1)).toBe("100%");
  });

  it("treats a falsy fraction (0, null, undefined) as 0%, not NaN%", () => {
    expect(pct(0)).toBe("0%");
    expect(pct(null)).toBe("0%");
    expect(pct(undefined)).toBe("0%");
  });
});

describe("gbp", () => {
  it("prefixes a real amount with a pound sign", () => {
    expect(gbp(25)).toBe("£25");
    expect(gbp(0)).toBe("£0");
  });

  it("renders an em dash for a genuinely absent amount, not '£null'", () => {
    expect(gbp(null)).toBe("—");
    expect(gbp(undefined)).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("returns an empty string for a falsy input rather than 'Invalid Date'", () => {
    expect(formatDateTime(null)).toBe("");
    expect(formatDateTime(undefined)).toBe("");
    expect(formatDateTime("")).toBe("");
  });

  it("formats a real ISO timestamp into a compact date and time, deliberately without a year", () => {
    const result = formatDateTime("2026-03-15T14:30:00Z");
    // Deliberately not asserting an exact string — toLocaleDateString/
    // toLocaleTimeString are timezone-dependent by design (that's the
    // whole point of using them over a fixed UTC format). Assert on the
    // parts that must be true regardless of the runner's local timezone.
    // No year assertion: the real options passed (month/day, hour/minute)
    // never request one — this is a compact "recent activity" label, not
    // a full timestamp, and that's a deliberate choice, not an oversight.
    expect(result).toMatch(/Mar/);
    expect(result).toMatch(/15/);
    expect(result).not.toMatch(/2026/);
  });
});

describe("el", () => {
  it("parses an HTML string into a real DocumentFragment with matching content", () => {
    const fragment = el("<div class='card'>Hello</div>");
    expect(fragment.children.length).toBe(1);
    expect(fragment.children[0].className).toBe("card");
    expect(fragment.children[0].textContent).toBe("Hello");
  });

  it("trims surrounding whitespace before parsing, same as a hand-written template literal", () => {
    const fragment = el("   <p>trimmed</p>   ");
    expect(fragment.children[0].tagName).toBe("P");
  });
});

describe("toast", () => {
  it("appends a toast node to #toasts and auto-removes it after a delay", () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div id="toasts"></div>';

    toast("Saved successfully", "success");

    const wrap = document.getElementById("toasts");
    expect(wrap.children.length).toBe(1);
    expect(wrap.children[0].textContent).toBe("Saved successfully");
    expect(wrap.children[0].className).toBe("toast success");

    vi.advanceTimersByTime(5000);
    expect(wrap.children.length).toBe(0);

    vi.useRealTimers();
  });

  it("omits the type class entirely when none is given, rather than appending 'toast undefined'", () => {
    document.body.innerHTML = '<div id="toasts"></div>';
    toast("Plain message");
    expect(document.getElementById("toasts").children[0].className).toBe("toast");
  });
});

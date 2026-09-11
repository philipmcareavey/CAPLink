import { defineConfig } from "vitest/config";

// Technical Implementation Plan 8.a.ii. jsdom, not node, since static/app/js/
// is browser code (document, fetch, HTMLDialogElement) with no build step —
// this runs the exact same files the browser loads, unmodified.
export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["static/app/js/**/*.test.js"],
    setupFiles: ["static/app/js/test-setup.js"],
  },
});

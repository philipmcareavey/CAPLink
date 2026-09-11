// jsdom (as of v26, used by this project's vitest config) doesn't implement
// <dialog>'s showModal()/close() at all — see the "Verified test infrastructure"
// note in caplink/CLAUDE.md's 8.a.ii entry for the exact check that confirmed
// this. openRatingModal() (components.js) relies on real showModal()/close()
// behaviour (open flag + a "close" event other code listens for), so a
// minimal polyfill is needed for its tests to run at all — not a workaround
// for a bug in our own code, a real gap in jsdom's own spec coverage.
if (typeof HTMLDialogElement !== "undefined" && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
}

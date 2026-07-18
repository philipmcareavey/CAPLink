export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content;
}

export function toast(message, type) {
  const wrap = document.getElementById("toasts");
  const node = document.createElement("div");
  node.className = "toast" + (type ? " " + type : "");
  node.textContent = message;
  wrap.appendChild(node);
  setTimeout(() => node.remove(), 5000);
}

export function badgeClass(status) {
  if (["open", "approved", "accepted", "paid", "active", "good", "completed"].includes(status)) return "good";
  if (["rejected", "declined", "suspended", "disputed", "cancelled"].includes(status)) return "bad";
  return "warn"; // pending, submitted, pending_review, offered, shortlisted, interviewing
}

export function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function titleCase(value) {
  return String(value ?? "").replace(/_/g, " ");
}

export function pct(fraction) {
  return Math.round((fraction || 0) * 100) + "%";
}

export function gbp(amount) {
  return amount == null ? "—" : "£" + amount;
}

export function formatDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " "
    + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

import { api, state } from "../api.js";
import { el, toast, esc, formatDateTime } from "../dom.js";

// Renders a full "Messages" section into `container`: either the thread
// list, or (if state.openThreadId is set) one open thread. Threads are only
// ever started in context (see startThread below) — there's no generic
// "compose to anyone" form, matching how MessageThread actually requires a
// known counterpart.
export async function renderMessagesSection(container) {
  if (state.openThreadId) {
    await renderThreadView(container, state.openThreadId);
    return;
  }
  container.innerHTML = `<div class="card"><h4 class="section">Messages</h4><div id="thread-list">Loading…</div></div>`;
  const listEl = container.querySelector("#thread-list");
  try {
    const threads = await api("/messages/threads");
    listEl.innerHTML = threads.length
      ? threads.map(t => `
        <div class="item-card clickable" data-open-thread="${t.thread_id}">
          <h4>${esc(t.counterpart_name)} ${t.unread_count ? `<span class="badge warn">${t.unread_count} unread</span>` : ""}</h4>
          <p class="muted">${esc(t.last_message_preview || "No messages yet")} ${t.last_message_at ? "· " + formatDateTime(t.last_message_at) : ""}</p>
        </div>
      `).join("")
      : `<div class="empty-state">No conversations yet — start one from an applicant or a contract card.</div>`;
    listEl.querySelectorAll("[data-open-thread]").forEach(node => node.addEventListener("click", () => {
      state.openThreadId = node.dataset.openThread;
      renderMessagesSection(container);
    }));
  } catch (e) {
    listEl.innerHTML = `<p class="muted">Couldn't load conversations: ${esc(e.message)}</p>`;
  }
}

async function renderThreadView(container, threadId) {
  container.innerHTML = `
    <div class="card">
      <div class="row" style="justify-content:space-between; margin-bottom:14px">
        <h4 class="section" style="margin:0">Conversation</h4>
        <button class="ghost small" data-action="back-to-threads">&larr; All conversations</button>
      </div>
      <div class="thread-view" id="thread-messages">Loading…</div>
      <div class="compose-row">
        <textarea id="compose-input" placeholder="Type a message…"></textarea>
        <button data-action="send-message">Send</button>
      </div>
    </div>
  `;
  container.querySelector('[data-action="back-to-threads"]').addEventListener("click", () => {
    state.openThreadId = null;
    renderMessagesSection(container);
  });

  const messagesEl = container.querySelector("#thread-messages");
  try {
    const messages = await api(`/messages/threads/${threadId}`);
    messagesEl.innerHTML = messages.length
      ? messages.map(m => `
        <div class="msg-bubble ${m.sender_user_id === state.userId ? "mine" : ""} ${m.is_flagged ? "flagged" : ""}">
          ${esc(m.content)}
          <span class="msg-meta">${formatDateTime(m.created_at)}${m.is_flagged ? " · flagged: " + esc(m.flagged_reason || "possible off-platform contact") : ""}</span>
        </div>
      `).join("")
      : `<p class="muted">No messages yet — say hello.</p>`;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  } catch (e) {
    messagesEl.innerHTML = `<p class="muted">Couldn't load messages: ${esc(e.message)}</p>`;
  }

  container.querySelector('[data-action="send-message"]').addEventListener("click", async () => {
    const input = container.querySelector("#compose-input");
    const content = input.value.trim();
    if (!content) return;
    try {
      await api("/messages", { method: "POST", body: { thread_id: threadId, content } });
      input.value = "";
      await renderThreadView(container, threadId);
    } catch (e) { toast("Couldn't send: " + e.message, "error"); }
  });
}

// Called from a contract/applicant card's "Message" button. Creates a fresh
// thread every time (no "find existing thread with this person" lookup —
// the backend has no such endpoint, and a business/student pair is
// realistically tied to one project at a time in this demo dataset). The
// caller is expected to switch state.activeTab to "messages" and trigger a
// full re-render immediately after this resolves.
export async function startThread(otherUserId, projectId) {
  try {
    const { thread_id } = await api("/messages/threads", { method: "POST", body: { other_user_id: otherUserId, project_id: projectId || null } });
    state.openThreadId = thread_id;
  } catch (e) { toast("Couldn't start conversation: " + e.message, "error"); }
}

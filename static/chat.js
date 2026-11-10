// Private chat between the ride sharer and a passenger.
// Polls the server every 2 seconds for new messages (simple and good enough for a demo;
// swap for WebSockets later for instant delivery).
(function () {
  const box = document.getElementById("messages");
  if (!box) return;
  const url = box.dataset.url;
  const me = Number(box.dataset.me);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const statusBadge = document.getElementById("chat-status");
  const openArea = document.getElementById("chat-open");
  const closedArea = document.getElementById("chat-closed");
  const seen = new Set();
  let lastId = 0;
  let firstLoad = true;

  function render(m) {
    if (seen.has(m.id)) return;
    seen.add(m.id);
    lastId = Math.max(lastId, m.id);
    const kind = m.sender_id === null ? "bot" : m.sender_id === me ? "mine" : "theirs";
    const row = document.createElement("div");
    row.className = "msg " + kind;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = (kind === "bot" ? "🌸 " : "") + m.body; // textContent: no HTML injection
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = (kind === "mine" ? "You" : m.sender_name) + " · " + m.time;
    row.append(bubble, meta);
    box.append(row);
  }

  function nearBottom() {
    return box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  }

  function setStatus(status, chatOpen) {
    statusBadge.className = "badge " + status;
    statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    openArea.hidden = !chatOpen;
    closedArea.hidden = chatOpen;
  }

  async function poll() {
    try {
      const res = await fetch(url + "?after=" + lastId, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const data = await res.json();
      const stick = firstLoad || nearBottom();
      data.messages.forEach(render);
      if (data.messages.length && stick) box.scrollTop = box.scrollHeight;
      setStatus(data.status, data.chat_open);
      firstLoad = false;
    } catch (_) { /* offline: try again on the next tick */ }
  }

  async function send(text) {
    text = text.trim();
    if (!text) return;
    input.value = "";
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ body: text }),
      });
      const data = await res.json();
      if (!res.ok) { alert(data.error || "Message not sent."); input.value = text; return; }
      render(data.message);
      box.scrollTop = box.scrollHeight;
    } catch (_) {
      alert("Network error: message not sent.");
      input.value = text;
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  document.querySelectorAll("[data-quick]").forEach((chip) =>
    chip.addEventListener("click", () => send(chip.textContent)));

  poll();
  setInterval(poll, 2000);
  input.focus();
})();

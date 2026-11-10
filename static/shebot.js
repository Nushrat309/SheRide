// SheBot: floating help assistant available on every page.
(function () {
  const fab = document.getElementById("bot-fab");
  if (!fab) return;
  const panel = document.getElementById("bot-panel");
  const log = document.getElementById("bot-log");
  const chips = document.getElementById("bot-chips");
  const form = document.getElementById("bot-form");
  const input = document.getElementById("bot-input");
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let started = false;

  function add(text, who) {
    const row = document.createElement("div");
    row.className = "msg " + (who === "me" ? "mine" : "theirs");
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    row.append(bubble);
    log.append(row);
    log.scrollTop = log.scrollHeight;
  }

  function setChips(list) {
    chips.replaceChildren();
    (list || []).forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = s;
      b.addEventListener("click", () => ask(s));
      chips.append(b);
    });
  }

  async function ask(text) {
    text = text.trim();
    if (!text) return;
    add(text, "me");
    input.value = "";
    try {
      const res = await fetch("/api/shebot", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      add(data.reply, "bot");
      setChips(data.suggestions);
    } catch (_) {
      add("Sorry, I can't connect right now. In an emergency, call 999.", "bot");
    }
  }

  function toggle(open) {
    panel.classList.toggle("open", open);
    fab.textContent = open ? "✕" : "💬";
    if (open && !started) {
      started = true;
      add("Hi! 🌸 I'm SheBot. How can I help you today?", "bot");
      setChips(["How do I book a ride?", "How do I offer a ride?", "Safety tips", "Emergency"]);
    }
    if (open) input.focus();
  }

  fab.addEventListener("click", () => toggle(!panel.classList.contains("open")));
  document.getElementById("bot-close").addEventListener("click", () => toggle(false));
  form.addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
})();

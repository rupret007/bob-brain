"use strict";
const $ = (id) => document.getElementById(id);

if ($("login-form")) {
  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("button");
    button.disabled = true;
    $("login-error").textContent = "";
    try {
      const response = await fetch("/login", { method: "POST", body: new URLSearchParams(new FormData(event.target)), credentials: "same-origin" });
      if (response.ok) location.assign("/");
      else $("login-error").textContent = (await response.json()).error || "Login failed.";
    } catch (_) { $("login-error").textContent = "Cannot reach Bob. Please try again."; }
    finally { button.disabled = false; }
  });
} else {
  let csrf = "", current = "", busy = false, sending = false, revision = "", polling = false, draftRequest = null;
  const providers = { codex: "Codex", cursor: "Cursor", gemini: "Gemini", minimax: "MiniMax", claude: "Claude" };
  function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function speechText(text) {
    return text.replace(/```[\s\S]*?```/g, " ").replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/[#>*_-]/g, " ").replace(/\s+/g, " ").trim();
  }
  function renderMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre class="code-block"><code>${code.trim()}</code></pre>`);
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" rel="noopener noreferrer" target="_blank">$1</a>');
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/(?:^|\n)([-*] .+(?:\n[-*] .+)*)/g, (block) => {
      const items = block.trim().split("\n").map((line) => `<li>${line.replace(/^[-*]\s+/, "")}</li>`).join("");
      return `<ul>${items}</ul>`;
    });
    html = html.replace(/\n/g, "<br>");
    return html;
  }
  const stored = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  async function api(path, data) {
    const response = await fetch(path, { credentials: "same-origin", cache: "no-store",
      ...(data === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(data) }) });
    if (response.status === 401) { location.assign("/login"); throw new Error("Please log in."); }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed.");
    return result;
  }
  function composerState() {
    $("send").disabled = busy || sending || !current;
    $("stop").hidden = !busy;
    $("message").disabled = !current;
  }
  function render(conversation) {
    if (conversation.id !== current) return;
    const nextRevision = JSON.stringify(conversation);
    busy = conversation.messages.some((message) => ["running", "queued", "waiting"].includes(message.status));
    composerState();
    if (nextRevision === revision) return;
    revision = nextRevision;
    const last = conversation.messages.at(-1);
    if (last?.status === "error" && last.role === "assistant") {
      $("notice").textContent = last.content || "Reply failed. Edit your message and send again.";
    } else if (last?.status === "cancelled" && last.role === "assistant" && !sending) {
      $("notice").textContent = "Reply stopped. Send again when ready.";
    }
    const panel = $("messages"), nearBottom = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 100;
    const fragment = document.createDocumentFragment();
    if (!conversation.messages.length) {
      const welcome = document.createElement("div"); welcome.className = "welcome";
      const title = document.createElement("h2"); title.textContent = "What’s on your mind?";
      const text = document.createElement("p"); text.textContent = "Ask a question, work on a draft, or catch up on what’s running.";
      welcome.append(title, text); fragment.append(welcome);
    }
    for (const message of conversation.messages) {
      const pending = ["queued", "running"].includes(message.status);
      const article = document.createElement("article");
      article.className = `message ${message.role} ${pending ? "pending" : ""} ${message.status === "error" ? "error" : ""}`;
      const meta = document.createElement("div"); meta.className = "meta";
      meta.textContent = `${message.role === "user" ? "You" : "Bob"}${message.provider ? " · " + providers[message.provider] : ""} · ${new Date(message.created_at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
      const body = document.createElement("div"); body.className = "body";
      if (pending) body.textContent = message.provider ? `Thinking via ${providers[message.provider]}…` : "One moment…";
      else if (message.role === "assistant") body.innerHTML = renderMarkdown(message.content || "");
      else body.textContent = message.content;
      article.append(meta, body);
      if (message.status === "waiting" && message.retry_at) {
        const retry = document.createElement("div"); retry.className = "attempt";
        retry.textContent = `Queued · retry after ${new Date(message.retry_at * 1000).toLocaleTimeString()}`;
        article.append(retry);
      }
      if (message.action_card) {
        const card = document.createElement("div"); card.className = "action-card";
        const suffix = message.action_card.state === "queued" ? "Queued for scheduler" : message.action_card.state === "confirm" ? "Awaiting your yes" : "No action executed";
        card.textContent = `${message.action_card.reason} · ${suffix}`;
        article.append(card);
      }
      if (message.attempts?.length) {
        const detail = document.createElement("div"); detail.className = "attempt";
        detail.textContent = message.attempts.map((a) => a.message || `${providers[a.provider]}: ${a.error}${a.skipped ? " (cooldown or busy)" : ""}`).join(" · ");
        article.append(detail);
      }
      fragment.append(article);
    }
    panel.replaceChildren(fragment);
    if (nearBottom || sending) panel.scrollTop = panel.scrollHeight;
  }
  async function refreshList() {
    const data = await api("/api/conversations");
    const options = data.conversations.map((conversation) => {
      const option = document.createElement("option"); option.value = conversation.id; option.textContent = conversation.title; return option;
    });
    $("conversations").replaceChildren(...options);
    if (!current || !data.conversations.some((conversation) => conversation.id === current)) current = data.active_conversation || data.conversations[0]?.id;
    $("conversations").value = current;
    remember("bob.conversation", current);
  }
  async function poll() {
    if (!current || polling) return;
    polling = true;
    try {
      render(await api(`/api/conversations/${current}`));
      $("connection").textContent = "Your chat on the mini";
      if (!busy && $("notice").textContent === "Stopping this reply…") $("notice").textContent = "";
    } catch (error) { $("connection").textContent = "Reconnecting…"; $("notice").textContent = error.message; }
    finally { polling = false; }
  }
  $("composer").addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = $("message").value.trim();
    if (!message || busy || sending) return;
    const provider = $("provider-choice").value;
    if (!draftRequest || draftRequest.message !== message || draftRequest.conversation_id !== current || draftRequest.provider !== provider) {
      draftRequest = { conversation_id: current, message, provider, request_id: crypto.randomUUID() };
    }
    sending = true; composerState(); $("notice").textContent = "";
    try {
      const conversation = await api("/api/messages", draftRequest);
      const submitted = draftRequest;
      if (submitted.conversation_id === current && submitted.message === $("message").value.trim()) {
        $("message").value = "";
        $("message").style.height = "auto";
        draftRequest = null;
      }
      render(conversation); await refreshList();
    } catch (error) { $("notice").textContent = error.message; }
    finally { sending = false; composerState(); $("message").focus(); }
  });
  $("message").addEventListener("input", () => {
    $("message").style.height = "auto";
    $("message").style.height = Math.min($("message").scrollHeight, 180) + "px";
  });
  $("message").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !matchMedia("(pointer: coarse)").matches) {
      event.preventDefault(); $("composer").requestSubmit();
    }
  });
  $("conversations").addEventListener("change", async () => {
    current = $("conversations").value; remember("bob.conversation", current); revision = ""; busy = false;
    await poll(); $("messages").scrollTop = $("messages").scrollHeight;
  });
  $("new-chat").addEventListener("click", async () => {
    try { const conversation = await api("/api/conversations", {}); current = conversation.id; revision = ""; await refreshList(); render(conversation); $("message").focus(); }
    catch (error) { $("notice").textContent = error.message; }
  });
  let micRecognition = null;
  $("mic").addEventListener("click", () => {
    const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Speech) { $("notice").textContent = "Voice input is not supported in this browser."; return; }
    if (micRecognition) {
      micRecognition.stop();
      micRecognition = null;
      $("mic").classList.remove("mic-active");
      $("mic").setAttribute("aria-pressed", "false");
      $("notice").textContent = "";
      return;
    }
    const rec = new Speech();
    micRecognition = rec;
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    $("mic").classList.add("mic-active");
    $("mic").setAttribute("aria-pressed", "true");
    $("notice").textContent = "Listening… tap mic again to stop.";
    rec.onresult = (event) => {
      const transcript = Array.from(event.results).map((row) => row[0].transcript).join(" ").trim();
      $("message").value = ($("message").value + " " + transcript).trim();
      $("message").dispatchEvent(new Event("input"));
    };
    rec.onend = () => {
      micRecognition = null;
      $("mic").classList.remove("mic-active");
      $("mic").setAttribute("aria-pressed", "false");
      $("notice").textContent = "";
    };
    rec.onerror = () => { $("notice").textContent = "Could not capture voice. Try typing."; };
    rec.start();
  });
  $("speak").addEventListener("click", async () => {
    if (!("speechSynthesis" in window)) { $("notice").textContent = "Read-aloud is not supported here."; return; }
    try {
      const conversation = await api(`/api/conversations/${current}`);
      const last = conversation.messages.filter((m) => m.role === "assistant" && m.status === "done").at(-1);
      if (!last?.content) { $("notice").textContent = "No finished reply to read."; return; }
      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(speechText(last.content).slice(0, 4000));
      utter.rate = 1.02;
      speechSynthesis.speak(utter);
    } catch (error) { $("notice").textContent = error.message; }
  });
  $("stop").addEventListener("click", async () => {
    try { await api("/api/cancel", { conversation_id: current }); $("notice").textContent = "Stopping this reply…"; }
    catch (error) { $("notice").textContent = error.message; }
  });
  $("logout").addEventListener("click", async () => {
    try { await api("/api/logout", {}); location.assign("/login"); }
    catch (error) { $("notice").textContent = error.message; }
  });
  for (const button of document.querySelectorAll("[data-report]")) button.addEventListener("click", async () => {
    $("report-title").textContent = button.textContent;
    $("report-body").textContent = "Loading…"; $("report-date").textContent = ""; $("report").showModal();
    try {
      const data = await api(`/api/${button.dataset.report}`);
      $("report-date").textContent = data.modified_at ? `File updated ${new Date(data.modified_at * 1000).toLocaleString()} · saved report, not a new check` : `Read ${new Date(data.read_at * 1000).toLocaleString()}`;
      $("report-body").textContent = button.dataset.report === "jobs" ?
        `${data.maintenance ? "Scheduling paused: " + data.maintenance + "\n\n" : ""}SCREENS\n${data.screens}\n\nQUEUE${data.queue.modified_at ? " · updated " + new Date(data.queue.modified_at * 1000).toLocaleString() : ""}\n${data.queue.text}` :
        data.text + (data.truncated ? "\n\n[Display truncated]" : "");
    } catch (error) { $("report-body").textContent = error.message; }
  });
  $("close-report").addEventListener("click", () => $("report").close());
  let songProjectId = stored("bob.songProject") || "";
  async function loadSong() {
    try {
      const list = await api("/api/song-projects");
      const row = list.projects.find((p) => p.id === songProjectId) || list.projects[0];
      if (!row) { $("song-summary").textContent = "new"; return; }
      songProjectId = row.id; remember("bob.songProject", songProjectId);
      const project = await api(`/api/song-projects/${songProjectId}`);
      $("song-title").value = project.title || "";
      $("song-lyrics").value = project.lyrics || "";
      $("song-chords").value = project.chords || "";
      $("song-notes").value = project.notes || "";
      $("song-summary").textContent = project.title || "saved";
    } catch (_) { $("song-summary").textContent = "offline"; }
  }
  $("song-save").addEventListener("click", async () => {
    $("song-notice").textContent = "Saving…";
    try {
      const project = await api("/api/song-projects", {
        id: songProjectId || undefined,
        title: $("song-title").value,
        lyrics: $("song-lyrics").value,
        chords: $("song-chords").value,
        notes: $("song-notes").value,
        version_note: "saved from phone",
      });
      songProjectId = project.id; remember("bob.songProject", songProjectId);
      $("song-notice").textContent = "Saved " + new Date().toLocaleTimeString();
      $("song-summary").textContent = project.title;
    } catch (error) { $("song-notice").textContent = error.message; }
  });
  $("song-demo").addEventListener("click", async () => {
    const lyrics = $("song-lyrics").value.trim();
    if (!lyrics) { $("song-notice").textContent = "Add lyrics first."; return; }
    let receipt = "";
    try {
      const quote = await api("/api/music/demo", { lyrics, style: $("song-notes").value || "acoustic songwriter" });
      if (quote.needs_confirm) {
        receipt = quote.receipt || "";
        if (!quote.can_afford_demo) { $("song-notice").textContent = quote.message || "Cap too low for a demo."; return; }
        if (!window.confirm(quote.message || "Generate MiniMax demo?")) return;
      }
    } catch (error) { $("song-notice").textContent = error.message; return; }
    $("song-notice").textContent = "Generating demo…";
    try {
      const demo = await api("/api/music/demo", {
        lyrics, style: $("song-notes").value || "acoustic songwriter", confirm: true, receipt,
      });
      if (demo.audio_id) {
        const player = $("song-player");
        player.hidden = false;
        player.src = `/api/audio/${demo.audio_id}`;
        $("song-notice").textContent = `Demo ready · ~$${demo.cost_usd.toFixed(2)} · ${demo.bytes} bytes`;
      } else $("song-notice").textContent = demo.message || "Demo queued.";
    } catch (error) { $("song-notice").textContent = error.message; }
  });
  $("song-upload").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    $("song-notice").textContent = "Uploading…";
    try {
      const buffer = await file.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      let binary = "";
      for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
      const stored = await api("/api/audio/upload", { filename: file.name, data_base64: btoa(binary) });
      const player = $("song-player");
      player.hidden = false;
      player.src = `/api/audio/${stored.audio_id}`;
      $("song-notice").textContent = `Uploaded ${file.name}`;
    } catch (error) { $("song-notice").textContent = error.message; }
    event.target.value = "";
  });
  async function refreshPanel() {
    try {
      const data = await api("/api/panel");
      const state = data.handback?.bob_state?.text || "";
      $("handback-chip").textContent = state ? state.split("\n").find((line) => line.trim() && !line.startsWith("#"))?.slice(0, 140) || state.slice(0, 140) : "Handback: no BOB-STATE yet";
      const dash = data.dashboard_modified_at ? new Date(data.dashboard_modified_at * 1000).toLocaleString() : "unknown";
      const results = (data.recent_results || []).map((r) => r.name).join(", ") || "none";
      $("status-summary").textContent = `dashboard ${dash}`;
      const lines = [
        `Dashboard fresh: ${dash}`,
        `Recent RESULT files: ${results}`,
        `Screens: ${(data.jobs.screens || "").split("\n")[0] || "n/a"}`,
        "",
        (data.handback?.bob_state?.text || "").slice(0, 1200),
      ];
      $("status-body").textContent = lines.join("\n");
    } catch (_) {
      $("status-summary").textContent = "unavailable";
    }
  }
  async function refreshLanes() {
    try {
      const data = await api("/api/lanes" + (current ? "?conversation_id=" + encodeURIComponent(current) : ""));
      const entries = Object.entries(data.providers);
      $("lanes-summary").textContent = entries.filter(([, lane]) => lane.state === "cooldown").length + " cooling down";
      $("lanes").replaceChildren(...entries.map(([name, lane]) => {
        const row = document.createElement("div"); row.className = "lane";
        const title = document.createElement("strong");
        title.textContent = `${providers[name]} · ${lane.state.replace("_", " ")}${lane.automatic ? "" : " · explicit choice only"}`;
        const detail = document.createElement("span");
        const spend = lane.spend;
        detail.textContent = lane.detail + (lane.retry_at > Date.now() / 1000 ? ` · retry ${new Date(lane.retry_at * 1000).toLocaleTimeString()}` : "") +
          (spend.committed_usd !== undefined && ["gemini", "minimax"].includes(name) ? ` · $${spend.committed_usd.toFixed(4)} committed${spend.cap_usd ? " / $" + spend.cap_usd : ""} (includes reservations)` : ` · ${spend.billing}`) +
          (lane.probed_at ? ` · probe ${lane.probe}, ${new Date(lane.probed_at * 1000).toLocaleTimeString()} (login/configuration/network only)` : "");
        row.append(title, detail); return row;
      }));
    } catch (_) { $("lanes-summary").textContent = "Health unavailable"; }
  }
  async function init() {
    try {
      csrf = (await api("/api/session")).csrf; current = stored("bob.conversation");
      await refreshList(); await poll(); $("messages").scrollTop = $("messages").scrollHeight;
      await refreshPanel(); await refreshLanes(); await loadSong();
      setInterval(refreshPanel, 8000);
      setInterval(refreshLanes, 5000);
      setInterval(poll, 1200);
    } catch (error) { $("notice").textContent = error.message; }
  }
  composerState(); init();
}

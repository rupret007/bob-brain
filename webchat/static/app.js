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
  let csrf = "", current = "", busy = false, sending = false, revision = "", polling = false, draftRequest = null, pollFailures = 0;
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
    const dot = $("status-dot");
    if (dot) dot.classList.toggle("busy", busy || sending);
  }
  const conductorPrompts = {
    round: "start a job: Web Bob ready round (draft only, no merge)",
    council: "run council on: score Web Bob iPhone tab UI and handback failover",
    status: "From BOB-STATE and handback: what's running and what needs my yes?",
    stop: "stop the current screen job if it's safe (draft only)",
  };
  document.querySelector(".app")?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-conductor]");
    if (!btn) return;
    const text = conductorPrompts[btn.dataset.conductor];
    if (!text) return;
    setBottomTab("chat");
    const field = $("message");
    field.value = text;
    field.focus();
    field.dispatchEvent(new Event("input"));
  });
  let activeBottomTab = "chat";
  function setBottomTab(name) {
    activeBottomTab = name;
    for (const btn of document.querySelectorAll(".bottom-tab")) {
      const on = btn.dataset.bottom === name;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-current", on ? "page" : "false");
    }
    for (const view of document.querySelectorAll(".main-view")) {
      const on = view.dataset.view === name;
      view.hidden = !on;
      view.classList.toggle("active", on);
    }
  }
  for (const btn of document.querySelectorAll(".bottom-tab")) {
    btn.addEventListener("click", () => setBottomTab(btn.dataset.bottom));
  }
  $("open-chats")?.addEventListener("click", () => {
    syncConversationDialog();
    $("chats-dialog")?.showModal();
  });
  $("close-chats")?.addEventListener("click", () => $("chats-dialog")?.close());
  function syncConversationDialog() {
    const main = $("conversations");
    const dialog = $("conversations-dialog");
    if (!main || !dialog) return;
    dialog.replaceChildren(...Array.from(main.options).map((opt) => {
      const clone = document.createElement("option");
      clone.value = opt.value;
      clone.textContent = opt.textContent;
      return clone;
    }));
    dialog.value = main.value;
  }
  $("conversations-dialog")?.addEventListener("change", async () => {
    $("conversations").value = $("conversations-dialog").value;
    $("conversations").dispatchEvent(new Event("change"));
    $("chats-dialog")?.close();
  });
  $("new-chat-dialog")?.addEventListener("click", () => { $("new-chat")?.click(); $("chats-dialog")?.close(); });
  const chipActions = {
    status: "From BOB-STATE and handback: what's running and what needs my yes?",
    round: "start a job: Web Bob ready round (draft only, no merge)",
    council: "run council on: score Web Bob mobile UX after bottom tab bar",
    song: "",
  };
  $("quick-chips")?.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-chip]");
    if (!chip) return;
    const key = chip.dataset.chip;
    if (key === "song") {
      setBottomTab("song");
      $("song-title")?.focus();
      return;
    }
    const text = chipActions[key];
    if (!text) return;
    setBottomTab("chat");
    const field = $("message");
    field.value = text;
    field.focus();
    field.dispatchEvent(new Event("input"));
  });
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
      pollFailures = 0;
      $("connection").textContent = "On the mini";
      $("status-dot")?.classList.remove("warn");
      if (!busy && $("notice").textContent === "Stopping this reply…") $("notice").textContent = "";
    } catch (error) {
      pollFailures += 1;
      $("connection").textContent = pollFailures >= 3 ? "Offline — check the mini" : "Reconnecting…";
      if (pollFailures >= 2) $("status-dot")?.classList.add("warn");
      if (pollFailures < 3) $("notice").textContent = error.message;
    }
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
  let speakingUtterance = null;
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
    rec.continuous = matchMedia("(pointer: coarse)").matches;
    rec.maxAlternatives = 1;
    $("mic").classList.add("mic-active");
    $("mic").setAttribute("aria-pressed", "true");
    $("notice").textContent = rec.continuous
      ? "Listening… tap mic again to stop (iPhone: allow mic when prompted)."
      : "Listening… tap mic again to stop.";
    rec.onresult = (event) => {
      const transcript = Array.from(event.results).map((row) => row[0].transcript).join(" ").trim();
      $("message").value = ($("message").value + " " + transcript).trim();
      $("message").dispatchEvent(new Event("input"));
    };
    rec.onend = () => {
      micRecognition = null;
      $("mic").classList.remove("mic-active");
      $("mic").setAttribute("aria-pressed", "false");
      if (!$("notice").textContent.startsWith("Could not")) $("notice").textContent = "";
    };
    rec.onerror = () => { $("notice").textContent = "Could not capture voice. Try typing or keyboard dictation."; };
    rec.start();
  });
  $("speak").addEventListener("click", async () => {
    if (!("speechSynthesis" in window)) { $("notice").textContent = "Read-aloud is not supported here."; return; }
    if (micRecognition) {
      micRecognition.stop();
      micRecognition = null;
      $("mic").classList.remove("mic-active");
      $("mic").setAttribute("aria-pressed", "false");
    }
    if (speakingUtterance) {
      speechSynthesis.cancel();
      speakingUtterance = null;
      $("speak").classList.remove("mic-active");
      $("speak").setAttribute("aria-pressed", "false");
      return;
    }
    try {
      const conversation = await api(`/api/conversations/${current}`);
      const last = conversation.messages.filter((m) => m.role === "assistant" && m.status === "done").at(-1);
      if (!last?.content) { $("notice").textContent = "No finished reply to read."; return; }
      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(speechText(last.content).slice(0, 4000));
      utter.rate = 1.02;
      const voices = speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en"));
      if (voices.length) utter.voice = voices.find((v) => /samantha|daniel|english/i.test(v.name)) || voices[0];
      utter.onend = utter.onerror = () => {
        speakingUtterance = null;
        $("speak").classList.remove("mic-active");
        $("speak").setAttribute("aria-pressed", "false");
      };
      speakingUtterance = utter;
      $("speak").classList.add("mic-active");
      $("speak").setAttribute("aria-pressed", "true");
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
  $("close-report")?.addEventListener("click", () => $("report")?.close());
  let songProjectId = stored("bob.songProject") || "";
  async function loadSongList(selectId) {
    const list = await api("/api/song-projects");
    const picker = $(selectId || "song-picker");
    if (!picker) return list;
    picker.replaceChildren(...list.projects.map((p) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.title || "Untitled";
      return opt;
    }));
    if (!list.projects.length) {
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "No songs yet — tap New song";
      picker.append(empty);
    }
    return list;
  }
  async function loadSong(id) {
    try {
      const list = await loadSongList("song-picker");
      const row = list.projects.find((p) => p.id === (id || songProjectId)) || list.projects[0];
      if (!row) return;
      songProjectId = row.id;
      remember("bob.songProject", songProjectId);
      $("song-picker").value = songProjectId;
      const project = await api(`/api/song-projects/${songProjectId}`);
      $("song-title").value = project.title || "";
      $("song-lyrics").value = project.lyrics || "";
      $("song-chords").value = project.chords || "";
      $("song-notes").value = project.notes || "";
    } catch (_) { $("song-notice").textContent = "Offline — edits stay on device until you save."; }
  }
  $("song-picker")?.addEventListener("change", () => loadSong($("song-picker").value));
  $("song-new")?.addEventListener("click", () => {
    songProjectId = "";
    $("song-picker").value = "";
    $("song-title").value = "";
    $("song-lyrics").value = "";
    $("song-chords").value = "";
    $("song-notes").value = "";
    $("song-title").focus();
  });
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
      await loadSongList("song-picker");
      $("song-picker").value = project.id;
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
        if (!window.confirm(quote.message || "Generate local sketch demo ($0)?")) return;
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
        $("song-notice").textContent = `Demo ready · ${demo.engine || "local-sketch"} · ${demo.bytes} bytes`;
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
  function renderLiveJobs(jobs) {
    const host = $("live-jobs");
    if (!host) return;
    host.replaceChildren(...(jobs || []).slice(0, 6).map((job) => {
      const card = document.createElement("article");
      card.className = "live-job";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = `${job.engine || "job"} · R${job.round || "?"}`;
      const stall = document.createElement("span");
      stall.className = `stall ${job.stall_state === "stalled" ? "stalled" : "running"}`;
      stall.textContent = job.stall_state || "unknown";
      const elapsed = document.createElement("span");
      const mins = Math.round((job.elapsed_seconds || 0) / 60);
      elapsed.textContent = `${mins}m elapsed${job.started_at ? " · " + job.started_at.replace("T", " ").slice(0, 16) : ""}`;
      header.append(title, stall, elapsed);
      const now = document.createElement("p");
      const events = (job.events || []).filter((e) => e && (e.text || e.sha));
      if (events.length) {
        now.textContent = events.find((e) => e.kind === "status")?.text || job.plain_now || "Working…";
      } else {
        now.textContent = job.plain_now || "Working…";
      }
      const tail = document.createElement("pre");
      tail.className = "log-tail";
      const lines = events.length
        ? events.filter((e) => e.kind === "log").map((e) => e.text).slice(-3)
        : (job.log_tail || []).slice(-3);
      tail.textContent = lines.length ? lines.join("\n") : "";
      const commit = document.createElement("p");
      if (job.last_commit?.sha) {
        commit.textContent = `${job.last_commit.sha}${job.last_commit.message ? " — " + job.last_commit.message : ""}`;
      }
      card.append(header, now, tail, commit);
      return card;
    }));
  }
  async function refreshPanel() {
    try {
      const data = await api("/api/panel");
      const meta = data.live_ops_meta || {};
      const ops = data.live_ops || {};
      const spend = ops.minimax_spend || {};
      const roles = ops.roles || {};
      const jobs = ops.running_jobs || [];
      const committed = spend.committed_usd;
      const cap = spend.cap_usd || 59;
      const spendText = committed === undefined || committed === null ? "budget unknown" : `$${committed.toFixed(2)} of $${cap}`;
      const freshness = meta.stale ? "Refreshing dashboard…" : "Live";
      const liveCards = jobs.filter((j) => j.live_screen && j.stall_state === "running");
      const jobLead = liveCards.length
        ? `${liveCards.length} job${liveCards.length === 1 ? "" : "s"} running on screen`
        : (jobs.length ? `${jobs.length} tracked — none on screen right now` : "Nothing running on screen");
      $("status-summary").textContent = `${freshness} · ${jobLead} · MiniMax ${spendText} · round ${ops.webchat_round || "?"}`;
      renderLiveJobs(jobs);
      const c = data.conductor || {};
      $("conductor-summary").textContent = `Draft work on ${c.draft_branch || "unknown branch"}`;
      const autopilot = liveCards.length
        ? `Busy — ${liveCards.length} live job${liveCards.length === 1 ? "" : "s"}`
        : (c.pass_schedule?.state === "finished" && liveCards.length === 0
          ? `Idle${c.pass_schedule.next_due ? " · next pass " + new Date(c.pass_schedule.next_due * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : ""}`
          : (c.pass_schedule?.state ? `Autopilot ${c.pass_schedule.state}` : "Autopilot idle"));
      $("conductor-status").textContent = [
        autopilot,
        c.maintenance ? "Scheduling paused" : "Scheduler on",
        `Builder: ${roles.building || "none"} · Reviews: ${roles.reviewing || "idle"}`,
        (c.head_sha || "").slice(0, 7) ? `Latest commit ${(c.head_sha || "").slice(0, 7)}` : "",
      ].filter(Boolean).join(" · ");
      const summary = data.handback?.summary?.text || "";
      const plainHandback = summary.split("\n")
        .map((l) => l.replace(/^#+\s*/, "").replace(/\*\*/g, "").trim())
        .filter((l) => l && !l.startsWith("---"))
        .slice(0, 5)
        .join(" ");
      $("handback-plain").textContent = plainHandback || "Handback will appear after your next chat turn.";
      const si = data.self_improve || {};
      $("self-improve-status").textContent = si.summary || "Self-improve tick runs on the mini (launchd).";
    } catch (_) {
      $("status-summary").textContent = "Jobs panel unavailable";
    }
  }
  async function refreshLanes() {
    try {
      const data = await api("/api/lanes" + (current ? "?conversation_id=" + encodeURIComponent(current) : ""));
      const entries = Object.entries(data.providers);
      const cooling = entries.filter(([, lane]) => lane.state === "cooldown").length;
      $("lanes-summary").textContent = cooling ? `${cooling} model${cooling === 1 ? "" : "s"} cooling down` : "All models ready to help";
      $("lanes").replaceChildren(...entries.map(([name, lane]) => {
        const card = document.createElement("article");
        card.className = "lane-card";
        const dot = document.createElement("span");
        dot.className = `lane-dot ${lane.state === "ready" ? "ok" : lane.state === "cooldown" ? "warn" : "busy"}`;
        dot.setAttribute("aria-hidden", "true");
        const title = document.createElement("h3");
        title.textContent = providers[name];
        const state = document.createElement("p");
        state.className = "lane-state";
        state.textContent = lane.state.replace(/_/g, " ");
        const detail = document.createElement("p");
        detail.className = "lane-detail muted";
        const spend = lane.spend;
        const cost = spend.committed_usd !== undefined && ["gemini", "minimax"].includes(name)
          ? `$${spend.committed_usd.toFixed(2)}${spend.cap_usd ? ` / $${spend.cap_usd} cap` : ""}`
          : spend.billing;
        detail.textContent = [lane.detail, cost, lane.retry_at > Date.now() / 1000 ? `Retry ${new Date(lane.retry_at * 1000).toLocaleTimeString()}` : ""].filter(Boolean).join(" · ");
        card.append(dot, title, state, detail);
        return card;
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

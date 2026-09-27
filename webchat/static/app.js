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
  function minimaxCapUsd(spend) {
    const cap = spend?.cap_usd;
    return cap === undefined || cap === null ? 59 : cap;
  }
  function isQuietHoursCt() {
    try {
      const parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", hour: "numeric", hour12: false }).formatToParts(new Date());
      const hour = Number(parts.find((p) => p.type === "hour")?.value ?? 12);
      return hour >= 23 || hour < 7;
    } catch (_) {
      return true;
    }
  }
  function speechText(text) {
    return text.replace(/```[\s\S]*?```/g, " ").replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/[#>*_-]/g, " ").replace(/\s+/g, " ").trim();
  }
  function renderMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/```([\s\S]*?)```/g, (_, code) => {
      const inner = code.trim();
      return `<pre class="code-block" tabindex="0"><button type="button" class="copy-code" aria-label="Copy code">Copy</button><code>${inner}</code></pre>`;
    });
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" rel="noopener noreferrer" target="_blank">$1</a>');
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/^### (.+)$/gm, "<h4 class=\"md-h\">$1</h4>");
    html = html.replace(/^## (.+)$/gm, "<h3 class=\"md-h\">$1</h3>");
    html = html.replace(/(?:^|\n)(\d+\. .+(?:\n\d+\. .+)*)/g, (block) => {
      const items = block.trim().split("\n").map((line) => `<li>${line.replace(/^\d+\.\s+/, "")}</li>`).join("");
      return `<ol>${items}</ol>`;
    });
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
    status: "status",
    stop: "stop current job (draft only)",
  };
  async function submitChatText(text, { confirmStop = false, confirmMessage } = {}) {
    if (!text || !current) return;
    if (confirmStop && !window.confirm(confirmMessage || "Stop this job?")) return;
    if ((busy || sending) && !confirmStop) {
      $("notice").textContent = "Wait for the current reply to finish, then try again.";
      setBottomTab("chat");
      return;
    }
    setBottomTab("chat");
    const provider = $("provider-choice").value;
    if (!draftRequest || draftRequest.message !== text || draftRequest.conversation_id !== current) {
      draftRequest = { conversation_id: current, message: text, provider, request_id: crypto.randomUUID() };
    }
    const payload = draftRequest;
    sending = true;
    composerState();
    $("notice").textContent = "";
    try {
      const conversation = await api("/api/messages", payload);
      if (payload === draftRequest) draftRequest = null;
      render(conversation);
      await refreshList();
    } catch (error) {
      $("notice").textContent = error.message;
    } finally {
      sending = false;
      composerState();
    }
  }
  document.querySelector(".app")?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-conductor]");
    if (!btn) return;
    const key = btn.dataset.conductor;
    const text = conductorPrompts[key];
    if (!text) return;
    if (key === "round" || key === "council" || key === "status") {
      setBottomTab("chat");
    }
    submitChatText(text, { confirmStop: key === "stop" });
  });
  let activeBottomTab = "chat";
  let songSnapshot = "";
  function songFieldsText() {
    return ["song-title", "song-lyrics", "song-chords", "song-notes"]
      .map((id) => $(id)?.value || "").join("\x1e");
  }
  function markSongClean() { songSnapshot = songFieldsText(); }
  async function confirmLeaveSongEdits() {
    if (songFieldsText() === songSnapshot) return true;
    return window.confirm("You have unsaved song edits. Continue without saving?");
  }
  function setBottomTab(name) {
    if (activeBottomTab === "song" && name !== "song" && songFieldsText() !== songSnapshot) {
      if (!window.confirm("You have unsaved song edits. Leave this tab anyway?")) return false;
    }
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
    return true;
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
    status: "status",
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
    if (key === "round" || key === "council" || key === "status") {
      submitChatText(text);
      return;
    }
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
      if (message.role === "user") article.setAttribute("aria-label", "You");
      else article.setAttribute("aria-label", message.provider ? `Assistant, ${providers[message.provider]}` : "Assistant");
      const body = document.createElement("div"); body.className = "body";
      if (pending) body.textContent = message.provider ? `Thinking via ${providers[message.provider]}…` : "One moment…";
      else if (message.role === "assistant") body.innerHTML = renderMarkdown(message.content || "");
      else body.textContent = message.content;
      article.append(body);
      {
        const raw = (message.content || "").trim();
        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "msg-copy quiet";
        copyBtn.setAttribute("aria-label", "Copy message");
        copyBtn.textContent = "Copy";
        copyBtn.disabled = pending || !raw;
        if (!copyBtn.disabled) {
          copyBtn.addEventListener("click", async () => {
            try {
              await navigator.clipboard.writeText(raw);
              copyBtn.textContent = "Copied";
              setTimeout(() => { copyBtn.textContent = "Copy"; }, 1200);
            } catch (_) {
              $("notice").textContent = "Could not copy — long-press the message instead.";
            }
          });
        }
        article.append(copyBtn);
      }
      if (message.role === "assistant" && message.provider && !pending) {
        const hint = document.createElement("div");
        hint.className = "provider-hint";
        hint.textContent = providers[message.provider];
        article.append(hint);
      }
      if (message.status === "waiting" && message.retry_at) {
        const retry = document.createElement("div"); retry.className = "attempt";
        retry.textContent = `Queued · retry after ${new Date(message.retry_at * 1000).toLocaleTimeString()}`;
        article.append(retry);
      }
      if (message.action_card) {
        const card = document.createElement("div"); card.className = "action-card";
        const title = document.createElement("div"); title.className = "action-card-title";
        title.textContent = message.action_card.reason || "Action";
        card.append(title);
        const suffix = message.action_card.state === "queued" ? "Queued for scheduler"
          : message.action_card.state === "confirm" ? "Tap approve to continue (draft only)"
          : message.action_card.state === "refused" ? "Blocked by safety rules"
          : "No action executed";
        const hint = document.createElement("div"); hint.className = "action-card-hint"; hint.textContent = suffix;
        card.append(hint);
        if (message.action_card.state === "confirm" && message.action_card.executable) {
          const actions = document.createElement("div"); actions.className = "action-card-actions";
          const council = /council/i.test(message.action_card.reason || "");
          const proposalId = message.action_card.proposal_id || message.action_card.id || "";
          const approve = document.createElement("button");
          approve.type = "button"; approve.className = "action-approve";
          approve.textContent = council ? "Yes, run council" : "Yes, start job";
          approve.addEventListener("click", () => {
            const suffix = proposalId ? ` proposal ${proposalId}` : "";
            $("message").value = council ? `yes, run council${suffix}` : `yes, start job${suffix}`;
            $("message").dispatchEvent(new Event("input"));
            $("composer").requestSubmit();
          });
          const deny = document.createElement("button");
          deny.type = "button"; deny.className = "action-deny";
          deny.textContent = council ? "Dismiss" : "Not now";
          deny.addEventListener("click", () => {
            $("message").value = council ? "never mind council" : "never mind";
            $("message").dispatchEvent(new Event("input"));
            $("composer").requestSubmit();
          });
          actions.append(approve, deny);
          card.append(actions);
        }
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
  async function waitForReply(conversationId, requestId, { timeoutMs = 120000 } = {}) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const value = await api(`/api/conversations/${conversationId}`);
      const assistant = requestId
        ? value.messages.find((m) => m.role === "assistant" && m.request_id === requestId)
        : value.messages.filter((m) => m.role === "assistant").at(-1);
      if (assistant && !["queued", "running"].includes(assistant.status)) return value;
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
    throw new Error("Reply timed out — check chat.");
  }
  async function poll() {
    if (!current || polling) return;
    polling = true;
    try {
      render(await api(`/api/conversations/${current}`));
      pollFailures = 0;
      $("connection").textContent = "On the mini";
      const dot = $("status-dot");
      if (dot) {
        dot.classList.remove("warn");
        dot.setAttribute("aria-label", "Connected");
      }
      $("offline-banner")?.setAttribute("hidden", "");
      if (!busy && $("notice").textContent === "Stopping this reply…") $("notice").textContent = "";
    } catch (error) {
      pollFailures += 1;
      const offline = pollFailures >= 3;
      $("connection").textContent = offline ? "Offline — check the mini" : "Reconnecting…";
      const dot = $("status-dot");
      if (dot) {
        if (pollFailures >= 2) dot.classList.add("warn");
        dot.setAttribute("aria-label", offline ? "Offline" : "Reconnecting");
      }
      if (pollFailures >= 2) $("offline-banner")?.removeAttribute("hidden");
      if (pollFailures < 3) $("notice").textContent = error.message;
    }
    finally { polling = false; }
  }
  $("messages")?.addEventListener("contextmenu", (event) => {
    const article = event.target.closest(".message");
    if (!article || article.classList.contains("pending")) return;
    event.preventDefault();
    const body = article.querySelector(".body");
    const text = body?.innerText?.trim();
    if (!text) return;
    const menu = document.createElement("div");
    menu.className = "msg-menu";
    menu.innerHTML = '<button type="button" data-act="copy">Copy</button><button type="button" data-act="speak">Read aloud</button>';
    const close = () => { menu.remove(); document.removeEventListener("click", close, true); };
    menu.addEventListener("click", async (ev) => {
      const act = ev.target.closest("[data-act]")?.dataset.act;
      if (act === "copy") {
        try { await navigator.clipboard.writeText(text); $("notice").textContent = "Copied."; } catch (_) {}
      }
      if (act === "speak" && "speechSynthesis" in window) {
        await ensureSpeechVoices();
        speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(speechText(text).slice(0, 4000));
        utter.rate = 1.02;
        speechSynthesis.speak(utter);
      }
      close();
    });
    article.append(menu);
    setTimeout(() => document.addEventListener("click", close, true), 0);
  });
  $("messages")?.addEventListener("click", async (event) => {
    const btn = event.target.closest(".copy-code");
    if (!btn) return;
    const code = btn.parentElement?.querySelector("code")?.textContent || "";
    try {
      await navigator.clipboard.writeText(code);
      btn.textContent = "Copied";
      setTimeout(() => { btn.textContent = "Copy"; }, 1200);
    } catch (_) { $("notice").textContent = "Could not copy — select the code manually."; }
  });
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
  let micErrorActive = false;
  let speechVoicesReady = false;
  function primeSpeechVoices() {
    if (!("speechSynthesis" in window)) return;
    const voices = speechSynthesis.getVoices();
    if (voices.length) speechVoicesReady = true;
    speechSynthesis.onvoiceschanged = () => {
      if (speechSynthesis.getVoices().length) speechVoicesReady = true;
    };
  }
  function ensureSpeechVoices(timeoutMs = 600) {
    primeSpeechVoices();
    if (speechVoicesReady) return Promise.resolve();
    return new Promise((resolve) => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        if (speechSynthesis.getVoices().length) speechVoicesReady = true;
        resolve();
      };
      speechSynthesis.onvoiceschanged = finish;
      setTimeout(finish, timeoutMs);
    });
  }
  let speakingUtterance = null;
  $("mic").addEventListener("click", () => {
    const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Speech) { $("notice").textContent = "Voice input needs Safari on iPhone or Chrome on desktop. Keyboard dictation always works."; return; }
    if (micRecognition) {
      micRecognition.stop();
      micRecognition = null;
      $("mic").classList.remove("mic-active");
      $("mic").setAttribute("aria-pressed", "false");
      micErrorActive = false;
      $("notice").textContent = "";
      return;
    }
    micErrorActive = false;
    const micBase = ($("message").value || "").trim();
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
      if (micRecognition !== rec) return;
      const dictated = Array.from(event.results).map((row) => row[0].transcript).join(" ").trim();
      $("message").value = [micBase, dictated].filter(Boolean).join(" ").trim();
      $("message").dispatchEvent(new Event("input"));
    };
    rec.onend = () => {
      if (micRecognition !== rec) return;
      micRecognition = null;
      $("mic").classList.remove("mic-active");
      $("mic").setAttribute("aria-pressed", "false");
      if (!micErrorActive) $("notice").textContent = "";
    };
    rec.onerror = (event) => {
      if (micRecognition !== rec) return;
      micErrorActive = true;
      const reason = event?.error || "unknown";
      const hint = reason === "not-allowed"
        ? "Microphone blocked — allow mic in Safari settings or use keyboard dictation."
        : "Could not capture voice. Try typing or keyboard dictation.";
      $("notice").textContent = hint;
    };
    try {
      rec.start();
    } catch (_) {
      micErrorActive = true;
      micRecognition = null;
      $("mic").classList.remove("mic-active");
      $("mic").setAttribute("aria-pressed", "false");
      $("notice").textContent = "Could not start voice input. Try keyboard dictation.";
    }
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
      await ensureSpeechVoices();
      if (isQuietHoursCt()) {
        $("notice").textContent = "Quiet hours (11 PM–7 AM CT) — read-aloud is off. Live call still works.";
        return;
      }
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
  let callSession = null;
  async function drainCallQueue(session) {
    if (!session || session.drainRunning || callSession !== session) return;
    session.drainRunning = true;
    try {
      while (callSession === session && session.queue.length) {
        const { transcript, heardAt } = session.queue.shift();
        if (heardAt !== session.lastHeardAt) continue;
        await handleCallUtterance(transcript, session.id);
      }
    } finally {
      if (session === callSession) session.drainRunning = false;
    }
  }
  function enqueueCallUtterance(transcript, session) {
    if (!session || callSession !== session) return;
    const norm = transcript.trim().toLowerCase();
    if (norm.length < 3) return;
    const last = session.queue.at(-1);
    if (last && last.transcript.trim().toLowerCase() === norm) return;
    const heardAt = Date.now();
    session.lastHeardAt = heardAt;
    session.queue.push({ transcript: transcript.trim(), heardAt });
    drainCallQueue(session);
  }
  function appendCallLine(role, text) {
    const host = $("call-transcript");
    if (!host || !text) return;
    const row = document.createElement("p");
    row.className = role === "you" ? "call-you" : "call-bob";
    row.textContent = (role === "you" ? "You: " : "Bob: ") + text.trim();
    host.append(row);
    host.scrollTop = host.scrollHeight;
  }
  async function speakCallReply(text) {
    if (!("speechSynthesis" in window) || !text) return;
    await ensureSpeechVoices();
    return new Promise((resolve) => {
      const utter = new SpeechSynthesisUtterance(speechText(text).slice(0, 2000));
      utter.rate = 1.05;
      const voices = speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en"));
      if (voices.length) utter.voice = voices.find((v) => /samantha|daniel|english/i.test(v.name)) || voices[0];
      utter.onend = utter.onerror = () => resolve();
      if (callSession) callSession.speaking = utter;
      speechSynthesis.speak(utter);
    });
  }
  function stopLiveCall() {
    if (callSession?.recognition) {
      try { callSession.recognition.stop(); } catch (_) { /* ignore */ }
    }
    speechSynthesis.cancel();
    callSession = null;
    $("live-call")?.classList.remove("call-active");
    $("call-dialog")?.close();
    $("call-status").textContent = "";
    $("call-transcript").replaceChildren();
  }
  async function handleCallUtterance(transcript, sessionId) {
    if (!callSession || callSession.id !== sessionId || !transcript.trim()) return;
    if (callSession.busy) return;
    callSession.busy = true;
    appendCallLine("you", transcript);
    const thinkStarted = performance.now();
    $("call-status").textContent = "Bob is thinking…";
    speechSynthesis.cancel();
    try {
      const requestId = crypto.randomUUID();
      const convId = callSession.convId || current;
      const payload = {
        conversation_id: convId,
        message: transcript,
        provider: $("provider-choice").value,
        request_id: requestId,
      };
      await api("/api/messages", payload);
      const value = await waitForReply(convId, requestId);
      if (!callSession || callSession.id !== sessionId) return;
      const msg = value.messages.find((m) => m.role === "assistant" && m.request_id === requestId);
      const body = msg?.content || "No reply yet.";
      appendCallLine("bob", body);
      const thinkMs = Math.round(performance.now() - thinkStarted);
      $("call-status").textContent = `Listening… (${thinkMs}ms to reply · speak anytime, tap End to stop)`;
      await speakCallReply(body);
    } catch (error) {
      $("call-status").textContent = error.message || "Call error";
    } finally {
      if (callSession?.id === sessionId) callSession.busy = false;
    }
  }
  $("live-call")?.addEventListener("click", () => {
    if (callSession) { stopLiveCall(); return; }
    const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Speech) {
      $("notice").textContent = "Live call needs Safari on iPhone (HTTPS) or Chrome. Use the mic for dictation.";
      return;
    }
    const rec = new Speech();
    callSession = {
      id: crypto.randomUUID(),
      convId: current,
      recognition: rec,
      speaking: null,
      resultIndex: 0,
      busy: false,
      queue: [],
      drainRunning: false,
      lastHeardAt: 0,
    };
    $("call-dialog")?.showModal();
    $("call-transcript").replaceChildren();
    $("call-status").textContent = "Listening… speak naturally. Bob will answer out loud.";
    $("live-call").classList.add("call-active");
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = (event) => {
      if (!callSession) return;
      let heardInterim = false;
      for (let index = callSession.resultIndex; index < event.results.length; index += 1) {
        const row = event.results[index];
        const said = (row[0]?.transcript || "").trim();
        if (!row.isFinal && said.length > 1) heardInterim = true;
        if (!row.isFinal) continue;
        callSession.resultIndex = index + 1;
        if (said.length > 2) enqueueCallUtterance(said, callSession);
      }
      if (heardInterim && callSession.speaking) {
        speechSynthesis.cancel();
        callSession.speaking = null;
        $("call-status").textContent = "Listening… (interrupted Bob)";
      }
    };
    rec.onerror = (event) => {
      if (!callSession) return;
      if (event.error === "not-allowed") $("call-status").textContent = "Microphone blocked — allow mic in Settings.";
      else if (event.error !== "aborted") $("call-status").textContent = "Mic error — try again or type in chat.";
    };
    rec.onend = () => {
      if (callSession?.recognition === rec) {
        callSession.resultIndex = 0;
        try { rec.start(); } catch (_) { /* restart loop while call open */ }
      }
    };
    callSession.resultIndex = 0;
    try { rec.start(); } catch (_) {
      stopLiveCall();
      $("notice").textContent = "Could not start live call.";
    }
  });
  $("end-call")?.addEventListener("click", () => stopLiveCall());
  $("call-dialog")?.addEventListener("close", () => stopLiveCall());
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
      const versions = $("song-versions");
      if (versions) {
        const rows = (project.versions || []).slice().reverse().slice(0, 6);
        if (rows.length) {
          versions.hidden = false;
          versions.replaceChildren(...rows.map((v) => {
            const li = document.createElement("li");
            const when = v.at ? new Date(v.at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";
            li.textContent = `${when}${v.note ? " · " + v.note : ""}`;
            return li;
          }));
        } else {
          versions.hidden = true;
          versions.replaceChildren();
        }
      }
      markSongClean();
    } catch (_) { $("song-notice").textContent = "Offline — edits stay on device until you save."; }
  }
  $("song-picker")?.addEventListener("change", async () => {
    if (!(await confirmLeaveSongEdits())) {
      $("song-picker").value = songProjectId || "";
      return;
    }
    await loadSong($("song-picker").value);
  });
  $("song-new")?.addEventListener("click", async () => {
    if (!(await confirmLeaveSongEdits())) return;
    songProjectId = "";
    $("song-picker").value = "";
    $("song-title").value = "";
    $("song-lyrics").value = "";
    $("song-chords").value = "";
    $("song-notes").value = "";
    $("song-title").focus();
    markSongClean();
  });
  $("song-coach")?.addEventListener("click", () => {
    if (!setBottomTab("chat")) return;
    const title = ($("song-title")?.value || "Untitled").trim().slice(0, 80);
    const lyricLine = ($("song-lyrics")?.value || "").trim().split("\n").find((l) => l.trim())?.slice(0, 120) || "";
    const chords = ($("song-chords")?.value || "").trim().slice(0, 80);
    const field = $("message");
    const draft = lyricLine
      ? `help with rhyme and meter for "${title}" — opening line: ${lyricLine}${chords ? ` · chords: ${chords}` : ""}`
      : `help with rhyme and song structure for "${title}" (add lyrics in Songs if you want line-level edits)`;
    field.value = draft;
    field.focus();
    field.dispatchEvent(new Event("input"));
    $("song-notice").textContent = "Prepared in chat — send when ready.";
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
      markSongClean();
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
  function jobLogLines(job) {
    const events = (job.events || []).filter((e) => e && (e.text || e.sha || e.state));
    if (events.length) {
      return events.filter((e) => e.kind === "log" && e.text).map((e) => e.text).slice(-3);
    }
    return (job.log_tail || []).slice(-3);
  }
  function jobHeadline(job) {
    const events = (job.events || []).filter((e) => e && (e.text || e.sha || e.state));
    const status = events.find((e) => e.kind === "status");
    return status?.text || job.plain_now || "Working…";
  }
  function renderOpsDetail(ops, hostId = "ops-detail") {
    const host = $(hostId);
    if (!host) return;
    if (!ops || !Object.keys(ops).length) {
      host.hidden = true;
      return;
    }
    host.hidden = false;
    const spend = ops.minimax_spend || {};
    const roles = ops.roles || {};
    const allJobs = ops.running_jobs || [];
    const jobs = allJobs.filter((j) => j.live_screen);
    const screenCount = ops.service_screen_count;
    const rows = [
      ["Now", ops.now_line || "—"],
      ["Dashboard", ops.dashboard_freshness_seconds == null ? "unknown" : `${ops.dashboard_freshness_seconds}s ago`],
      ["Round", ops.webchat_round != null ? String(ops.webchat_round) : "—"],
      ["Builder", roles.building || "idle"],
      ["Reviews", roles.reviewing || "idle"],
      ["MiniMax", spend.committed_usd == null ? "unknown" : `$${Number(spend.committed_usd).toFixed(2)} / $${minimaxCapUsd(spend)}`],
      ["Service screens", screenCount == null ? "—" : String(screenCount)],
      ["Live jobs", jobs.length ? `${jobs.length} on screen` : "none on screen"],
    ];
    const dl = document.createElement("dl");
    rows.forEach(([label, value]) => {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      dl.append(dt, dd);
    });
    if (hostId === "jobs-ops-detail" && allJobs.length) {
      allJobs.slice(0, 12).forEach((job, index) => {
        const dt = document.createElement("dt");
        dt.textContent = `Job ${index + 1}`;
        const dd = document.createElement("dd");
        dd.className = "ops-job-snippet";
        const lines = jobLogLines(job);
        const sha = job.last_commit?.sha ? ` · ${job.last_commit.sha}` : "";
        const round = job.round ? ` · round ${job.round}` : "";
        const elapsed = job.elapsed_seconds != null ? ` · ${Math.round(job.elapsed_seconds / 60)}m elapsed` : "";
        const stall = job.stall_plain ? ` · ${job.stall_plain}` : (job.stall_state ? ` · ${job.stall_state}` : "");
        const display = job.display_state ? ` · ${job.display_state}` : "";
        dd.textContent = `${jobHeadline(job)}${round}${elapsed}${stall}${display}${sha}${lines.length ? "\n" + lines.join("\n") : ""}`;
        dl.append(dt, dd);
      });
    }
    host.replaceChildren(dl);
    if (hostId === "ops-detail") {
      renderOpsDetail(ops, "jobs-ops-detail");
    }
  }
  function renderScoresTable(scores, hostId = "scores-table") {
    const host = $(hostId);
    if (!host) return;
    if (!scores?.length) {
      host.hidden = hostId === "jobs-scores-table";
      host.replaceChildren();
      return;
    }
    host.hidden = false;
    host.replaceChildren(...scores.slice(0, 8).map((row) => {
      const card = document.createElement("article");
      card.className = "score-card";
      const label = document.createElement("span");
      label.textContent = row.area || "Score";
      const val = document.createElement("strong");
      val.textContent = row.score != null && String(row.score).length ? String(row.score) : "—";
      card.append(label, val);
      return card;
    }));
  }
  function plainJobTitle(job) {
    const round = job.round ? `Round ${job.round}` : "Job";
    const engine = (job.engine || "worker").replace(/_/g, " ");
    const state = job.display_state ? ` · ${job.display_state}` : "";
    if (job.live_screen) return `${round} · live on screen${state}`;
    return `${round} · ${engine}${state}`;
  }
  function renderLiveJobs(jobs) {
    const host = $("live-jobs");
    const empty = $("jobs-empty");
    if (!host) return;
    const rows = (jobs || []).slice(0, 6);
    if (empty) empty.hidden = rows.length > 0;
    host.replaceChildren(...rows.map((job) => {
      const card = document.createElement("article");
      card.className = "live-job";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = plainJobTitle(job);
      const stall = document.createElement("span");
      stall.className = "stall";
      const elapsed = document.createElement("span");
      const mins = Math.round((job.elapsed_seconds || 0) / 60);
      const roundNote = job.round ? ` · round ${job.round}` : "";
      elapsed.textContent = `${mins}m elapsed${roundNote}${job.started_at ? " · " + job.started_at.replace("T", " ").slice(0, 16) : ""}`;
      header.append(title, stall, elapsed);
      const now = document.createElement("p");
      const events = (job.events || []).filter((e) => e && (e.text || e.sha || e.state));
      const stallEvent = events.find((e) => e.kind === "stall");
      const resolvedStall = stallEvent?.state || job.stall_state || "unknown";
      const stallLabel = job.stall_plain || (resolvedStall === "stalled" ? "Stalled" : resolvedStall === "running" ? "Running" : resolvedStall);
      const isStalled = resolvedStall === "stalled" || /stalled/i.test(stallLabel);
      stall.textContent = stallLabel;
      stall.classList.toggle("stalled", isStalled);
      stall.classList.toggle("running", !isStalled);
      now.textContent = jobHeadline(job);
      const tail = document.createElement("pre");
      tail.className = "log-tail";
      const logLines = jobLogLines(job);
      tail.textContent = logLines.length ? logLines.join("\n") : "";
      const commit = document.createElement("p");
      commit.className = "job-commit muted";
      if (job.last_commit?.sha) {
        const msg = job.last_commit.message ? job.last_commit.message.replace(/\.md\b/gi, "").slice(0, 80) : "";
        commit.textContent = `Latest commit ${job.last_commit.sha}${msg ? " — " + msg : ""}`;
      }
      const actions = document.createElement("div");
      actions.className = "live-job-actions";
      const stopBtn = document.createElement("button");
      stopBtn.type = "button";
      stopBtn.className = "quiet";
      stopBtn.textContent = "Stop";
      stopBtn.addEventListener("click", () => {
        const label = plainJobTitle(job);
        submitChatText(`stop job: ${label} (draft only)`, { confirmStop: true, confirmMessage: `Stop ${label}?` });
      });
      const detailBtn = document.createElement("button");
      detailBtn.type = "button";
      detailBtn.className = "quiet";
      detailBtn.textContent = "Details";
      detailBtn.setAttribute("aria-label", `Details for ${plainJobTitle(job)}`);
      detailBtn.addEventListener("click", () => {
        const bodyParts = [job.plain_now || "", ...logLines, ...(job.log_tail || [])].filter(Boolean);
        const body = [...new Set(bodyParts)].join("\n\n") || "No extra detail yet.";
        $("report-title").textContent = plainJobTitle(job);
        $("report-date").textContent = elapsed.textContent || "";
        $("report-body").textContent = body;
        $("report")?.showModal();
      });
      actions.append(stopBtn, detailBtn);
      card.append(header, now, tail, commit, actions);
      return card;
    }));
  }
  async function refreshPanel() {
    try {
      const data = await api("/api/panel");
      const meta = data.live_ops_meta || {};
      lastPanelMeta = meta;
      const ops = data.live_ops || {};
      lastPanelOps = ops;
      renderOpsDetail(ops, "jobs-ops-detail");
      const spend = ops.minimax_spend || {};
      const roles = ops.roles || {};
      const jobs = ops.running_jobs || [];
      const committed = spend.committed_usd;
      const cap = minimaxCapUsd(spend);
      const spendText = committed === undefined || committed === null ? "budget unknown" : `$${committed.toFixed(2)} of $${cap}`;
      const dashAge = ops.dashboard_freshness_seconds;
      const dashNote = dashAge === null || dashAge === undefined ? "" : ` · dashboard ${dashAge}s ago`;
      const freshness = meta.stale ? `Stale snapshot${dashNote}` : `Live${dashNote}`;
      const scoreStamp = ops.generated_at ? ` · scores ${ops.generated_at.replace("T", " ").slice(0, 16)} UTC` : "";
      const liveCards = jobs.filter((j) => j.live_screen && j.stall_state === "running");
      const jobLead = liveCards.length
        ? `${liveCards.length} job${liveCards.length === 1 ? "" : "s"} running on screen`
        : (jobs.length ? `${jobs.length} tracked — none on screen right now` : "Nothing running on screen");
      const nowHost = $("now-line");
      const nowLine = ops.now_line || data.alignment?.now_line;
      if (nowHost) {
        if (nowLine) {
          nowHost.hidden = false;
          nowHost.textContent = nowLine;
        } else {
          nowHost.hidden = true;
          nowHost.textContent = "";
        }
      }
      $("status-summary").textContent = `${freshness}${scoreStamp} · ${jobLead} · MiniMax ${spendText} · round ${ops.webchat_round || "?"}`;
      renderLiveJobs(jobs);
      lastPanelScores = ops.scores;
      lastPanelOps = ops;
      renderScoresTable(ops.scores, "jobs-scores-table");
      if (activeBottomTab === "lanes") {
        renderOpsDetail(ops);
        renderScoresTable(ops.scores);
      }
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
      const age = si.log_age_seconds;
      const logFresh = age != null && age < 48 * 3600
        ? `Log updated ${age < 3600 ? Math.round(age / 60) + "m" : Math.round(age / 3600) + "h"} ago`
        : (age != null ? "Self-improve log stale (>48h)" : "");
      const streak = si.tick_ok_streak ? `${si.tick_ok_streak} OK tick${si.tick_ok_streak === 1 ? "" : "s"} in a row` : "";
      const loaded = si.launchd_loaded === true ? "Scheduled tick loaded"
        : (si.launchd_loaded === false ? "Tick not loaded — run bootstrap on mini" : (si.launchd_loaded === null ? "Launchd probe unavailable" : ""));
      const health = si.loop_ready === true ? "Self-improve loop ready"
        : (si.install_ready === true && si.launchd_loaded !== true ? "Self-improve installed — load launchd on mini"
        : (si.healthy === true ? "Loop healthy"
        : (si.healthy === false && si.launchd_files_ok ? "Needs a successful tick — check mini bootstrap"
          : (si.launchd_files_ok ? "Status unknown — refresh Jobs tab" : "Install tick + plist — see mini setup"))));
      const schedule = si.schedule_hint ? `Schedule: ${si.schedule_hint.replace(/\.$/, "")}` : "";
      const bootstrap = si.bootstrap_command
        ? `One-time on mini: ${si.bootstrap_command}`
        : (si.bootstrap_script ? `One-time on mini: bash ${si.bootstrap_script}` : "");
      const siLine = [health, streak, loaded, schedule, bootstrap, logFresh, si.summary || ""].filter(Boolean).join(" · ");
      $("self-improve-status").textContent = siLine;
      const jobsSi = $("jobs-self-improve-status");
      if (jobsSi) {
        if (siLine.trim()) {
          jobsSi.hidden = false;
          jobsSi.textContent = `Self-improve: ${siLine}`;
        } else {
          jobsSi.hidden = true;
        }
      }
      const cl = data.round_changelog || {};
      const clHost = $("changelog-line");
      if (clHost) {
        clHost.textContent = cl.round
          ? `Round ${cl.round}: ${(cl.line || "").replace(/\*\*/g, "")}`
          : (cl.line || "Round notes load from the latest RESULT file on the mini.");
      }
    } catch (_) {
      lastPanelMeta = { stale: true };
      lastPanelOps = null;
      lastPanelScores = null;
      $("status-summary").textContent = "Jobs panel unavailable — dashboard may be stale";
      renderOpsDetail({}, "jobs-ops-detail");
      renderOpsDetail({}, "ops-detail");
      renderScoresTable(null, "jobs-scores-table");
      renderLiveJobs([]);
      const jobsSi = $("jobs-self-improve-status");
      if (jobsSi) {
        jobsSi.hidden = false;
        jobsSi.textContent = "Self-improve status unavailable — refresh when the mini is back.";
      }
    }
  }
  $("refresh-dashboard")?.addEventListener("click", async () => {
    const btn = $("refresh-dashboard");
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    const prior = btn.textContent;
    btn.textContent = "Refreshing…";
    const timeout = new Promise((_, reject) => {
      setTimeout(() => reject(new Error("Refresh timed out — try again in a moment.")), 15000);
    });
    try {
      const result = await Promise.race([api("/api/panel/refresh", {}), timeout]);
      await refreshPanel();
      $("notice").textContent = result?.spawned
        ? "Dashboard refresh queued on the mini."
        : "Dashboard already fresh — showing the latest snapshot.";
    } catch (error) {
      $("notice").textContent = error.message;
    } finally {
      btn.disabled = false;
      btn.textContent = prior || "Refresh";
    }
  });
  let lastPanelScores = null;
  let lastPanelOps = null;
  let lastPanelMeta = { stale: false };
  async function refreshLanes() {
    try {
      const ops = lastPanelOps || {};
      renderOpsDetail(ops);
      renderScoresTable(lastPanelScores);
      const spend = ops.minimax_spend || {};
      const roles = ops.roles || {};
      const dashAge = ops.dashboard_freshness_seconds;
      const opsLead = [
        ops.now_line || "Live ops from the mini",
        dashAge == null ? "dashboard age unknown" : `dashboard ${dashAge}s ago`,
        spend.committed_usd == null ? "MiniMax spend unknown" : `MiniMax $${Number(spend.committed_usd).toFixed(2)} / $${minimaxCapUsd(spend)}`,
        `Builder ${roles.building || "idle"} · Reviews ${roles.reviewing || "idle"}`,
        ops.webchat_round ? `Round ${ops.webchat_round} scores below` : "",
      ].filter(Boolean).join(" · ");
      const data = await api("/api/lanes" + (current ? "?conversation_id=" + encodeURIComponent(current) : ""));
      const entries = Object.entries(data.providers);
      const cooling = entries.filter(([, lane]) => lane.state === "cooldown").length;
      const busy = entries.filter(([, lane]) => lane.state === "busy").length;
      const allReady = entries.length > 0 && entries.every(([, lane]) => lane.state === "ready");
      const laneNote = cooling
        ? `${cooling} model${cooling === 1 ? "" : "s"} cooling down`
        : (busy ? `${busy} model${busy === 1 ? "" : "s"} busy` : (allReady ? "All lanes ready" : "Lane status updating"));
      const stalePrefix = lastPanelMeta.stale ? "Stale snapshot · " : "";
      $("lanes-summary").textContent = `${stalePrefix}${opsLead} · ${laneNote}`;
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
        state.textContent = ({ ready: "Ready", cooldown: "Cooling down", busy: "Busy" }[lane.state] || lane.state.replace(/_/g, " "));
        const detail = document.createElement("p");
        detail.className = "lane-detail muted";
        const spend = lane.spend;
        const capUsd = name === "minimax" ? minimaxCapUsd(spend) : spend.cap_usd;
        const capPart = spend.cap_usd != null ? ` / $${capUsd} cap` : "";
        const cost = spend.committed_usd !== undefined && ["gemini", "minimax"].includes(name)
          ? `$${spend.committed_usd.toFixed(2)}${capPart}`
          : spend.billing;
        detail.textContent = [lane.detail, cost, lane.retry_at > Date.now() / 1000 ? `Retry ${new Date(lane.retry_at * 1000).toLocaleTimeString()}` : ""].filter(Boolean).join(" · ");
        card.append(dot, title, state, detail);
        return card;
      }));
    } catch (_) { $("lanes-summary").textContent = "Health unavailable"; }
  }
  async function init() {
    try {
      primeSpeechVoices();
      const micBtn = $("mic");
      const speakBtn = $("speak");
      if (micBtn && !window.SpeechRecognition && !window.webkitSpeechRecognition) {
        micBtn.setAttribute("title", "Use keyboard dictation (mic key on iOS keyboard)");
      }
      if (speakBtn && !("speechSynthesis" in window)) speakBtn.hidden = true;
      csrf = (await api("/api/session")).csrf; current = stored("bob.conversation");
      await refreshList(); await poll(); $("messages").scrollTop = $("messages").scrollHeight;
      await refreshPanel(); await refreshLanes(); await loadSong();
      setInterval(refreshPanel, 8000);
      setInterval(refreshLanes, 5000);
      setInterval(poll, 1200);
      if ("EventSource" in window) {
        let alignSince = 0;
        const connectAlign = () => {
          const source = new EventSource(`/api/alignment/stream?since=${alignSince}`);
          source.onmessage = (event) => {
            try {
              const row = JSON.parse(event.data);
              if (row.seq) alignSince = Math.max(alignSince, row.seq);
              if (["chat-turn", "handback-turn", "inbox", "tick"].includes(row.kind)) refreshPanel();
            } catch (_) { /* ignore */ }
          };
          source.onerror = () => {
            source.close();
            setTimeout(connectAlign, 5000);
          };
        };
        connectAlign();
      }
    } catch (error) { $("notice").textContent = error.message; }
  }
  composerState(); init();
}

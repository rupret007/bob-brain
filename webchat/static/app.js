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
  const providers = { codex: "Codex", cursor: "Cursor", gemini: "Gemini", minimax: "MiniMax", claude: "Claude", texting: "Texts · private" };
  function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
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
    html = html.replace(/\[([^\]\n]+)\]\(\/api\/jobs\/result\?id=(webchat-[a-f0-9]{32})\)/g,
      '<button type="button" class="job-result-link" data-job-id="$2">$1</button>');
    html = html.replace(/!\[([^\]]*)\]\((\/api\/captures\/[0-9a-f]+)\)/g,
      '<img class="chat-capture" src="$2" alt="$1" loading="lazy" />');
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
  async function api(path, data, signal) {
    const response = await fetch(path, { credentials: "same-origin", cache: "no-store",
      ...(data === undefined ? { signal: signal || AbortSignal.timeout(15000) } : { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(data) }) });
    if (response.status === 401) { location.assign("/login"); throw new Error("Please log in."); }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed.");
    return result;
  }
  async function showJobResult(url, project = "Job result", task = "") {
    $("report-title").textContent = project;
    $("report-date").textContent = task;
    $("report-body").textContent = "Loading…";
    $("report").showModal();
    try {
      const result = await api(url);
      $("report-title").textContent = result.project || project;
      $("report-date").textContent = result.task || task;
      $("report-body").textContent = result.text;
    } catch (_) { $("report-body").textContent = "This result could not be loaded. Please try again."; }
  }
  function composerState() {
    $("send").disabled = busy || sending || !current;
    $("stop").hidden = !busy;
    $("message").disabled = !current;
    const dot = $("status-dot");
    if (dot) dot.classList.toggle("busy", busy || sending);
  }
  let activeBottomTab = "chat";
  let songSnapshot = songFieldsText();
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
    document.title = `Bob · ${{chat: "Chat", ops: "Jobs", song: "Songs", lanes: "Models", settings: "Settings"}[name]}`;
    if (name === "ops") refreshJobs();
    if (["lanes", "settings"].includes(name) && Date.now() - overviewFetchedAt > 8000) refreshOverview();
    return true;
  }
  for (const btn of document.querySelectorAll(".bottom-tab")) {
    btn.addEventListener("click", () => setBottomTab(btn.dataset.bottom));
  }
  $("open-chats").addEventListener("click", () => $("chats-dialog").showModal());
  $("close-chats").addEventListener("click", () => $("chats-dialog").close());
  $("quick-chips").addEventListener("click", (event) => {
    const key = event.target.closest("[data-chip]")?.dataset.chip;
    if (key === "song") { setBottomTab("song"); $("song-new").click(); }
    if (key === "status") setBottomTab("ops");
    if (key === "texts") {
      setBottomTab("chat");
      submitChatText("texts");
    }
  });
  $("provider-choice").addEventListener("change", () => remember("bob.provider", $("provider-choice").value));
  function render(conversation) {
    if (conversation.id !== current) return;
    const nextRevision = JSON.stringify(conversation);
    busy = conversation.messages.some((message) => ["running", "queued", "waiting"].includes(message.status));
    composerState();
    if (nextRevision === revision) return;
    revision = nextRevision;
    const last = conversation.messages.at(-1);
    if (last?.status === "cancelled" && last.role === "assistant" && !sending) {
      $("notice").textContent = "Reply stopped. Send again when ready.";
    }
    const panel = $("messages"), nearBottom = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 100;
    const openDetails = new Set([...panel.querySelectorAll("details[open]")].map((detail) => detail.dataset.detailKey));
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
      if (message.texting) article.classList.add("texting");
      if (message.role === "user") article.setAttribute("aria-label", "You");
      else article.setAttribute("aria-label", message.provider ? `Assistant, ${providers[message.provider] || "Bob"}` : "Assistant");
      const body = document.createElement("div"); body.className = "body";
      if (pending) body.textContent = providers[message.provider] ? `${providers[message.provider]} is replying…` : "One moment…";
      else if (message.role === "assistant" && !message.texting) body.innerHTML = renderMarkdown(message.content || "");
      else body.textContent = message.content;
      article.append(body);
      const messageTools = document.createElement("div");
      messageTools.className = "message-tools";
      if (message.text_draft) article.append(textDraftCard(message.text_draft));
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
        if (!pending) messageTools.append(copyBtn);
      }
      if (message.role === "assistant" && providers[message.provider] && !pending) {
        const hint = document.createElement("div");
        hint.className = "provider-hint";
        hint.textContent = providers[message.provider];
        messageTools.append(hint);
      }
      article.append(messageTools);
      if (message.status === "waiting" && message.retry_at) {
        const retry = document.createElement("div"); retry.className = "attempt";
        retry.textContent = `Queued · retry after ${new Date(message.retry_at * 1000).toLocaleTimeString()}`;
        article.append(retry);
      }
      if (message.action_card?.state === "confirm") {
        const card = document.createElement("div"); card.className = "action-card";
        const title = document.createElement("div"); title.className = "action-card-title";
        title.textContent = message.action_card.reason || "Action";
        card.append(title);
        const suffix = message.action_card.state === "queued" ? "Waiting to start"
          : message.action_card.state === "confirm" ? "Review and approve to start"
          : message.action_card.state === "refused" ? "Blocked by safety rules"
          : "No action executed";
        const hint = document.createElement("div"); hint.className = "action-card-hint"; hint.textContent = suffix;
        card.append(hint);
        if (message.action_card.state === "confirm" && message.action_card.executable) {
          const actions = document.createElement("div"); actions.className = "action-card-actions";
          const council = /council/i.test(message.action_card.reason || "");
          const memory = message.action_card.kind === "memory" || /^memory:/i.test(message.action_card.reason || "");
          const proposalId = message.action_card.proposal_id || message.action_card.id || "";
          const approve = document.createElement("button");
          approve.type = "button"; approve.className = "action-approve";
          approve.textContent = memory ? "Save memory" : council ? "Start review" : "Start job";
          approve.addEventListener("click", () => {
            const suffix = proposalId ? ` proposal ${proposalId}` : "";
            $("message").value = memory ? `yes, save memory${suffix}` : council ? `yes, run council${suffix}` : `yes, start job${suffix}`;
            $("message").dispatchEvent(new Event("input"));
            $("composer").requestSubmit();
          });
          const deny = document.createElement("button");
          deny.type = "button"; deny.className = "action-deny";
          deny.textContent = memory ? "Dismiss" : council ? "Dismiss" : "Not now";
          deny.addEventListener("click", () => {
            $("message").value = memory ? "never mind memory" : council ? "never mind council" : "never mind";
            $("message").dispatchEvent(new Event("input"));
            $("composer").requestSubmit();
          });
          actions.append(approve, deny);
          card.append(actions);
        }
        article.append(card);
      }
      if (message.attempts?.length) {
        const rows = [...new Set(message.attempts.map((attempt) => {
          const name = providers[attempt.provider];
          return name ? `${name}: ${modelReason(attempt.kind || attempt.error)}` : "Another model could not reply.";
        }))];
        const detail = document.createElement("details");
        detail.className = "reply-details";
        detail.dataset.detailKey = message.request_id || message.id || String(fragment.childElementCount);
        detail.open = openDetails.has(detail.dataset.detailKey);
        detail.append(element("summary", "Reply details"));
        rows.forEach((text) => detail.append(element("p", text, "muted")));
        article.append(detail);
      }
      fragment.append(article);
    }
    panel.replaceChildren(fragment);
    if (nearBottom || sending) panel.scrollTop = panel.scrollHeight;
  }
  function textDraftCard(draft) {
    const card = document.createElement("section");
    card.className = "text-draft-card";
    card.dataset.draftId = draft.id;
    card.dataset.state = draft.state;
    card.setAttribute("aria-label", "Text draft");
    const title = document.createElement("h3");
    title.textContent = "Text draft · " + ({ pending: "not sent", editing: "editing", expired: "confirmation expired",
      superseded: "replaced", cancelled: "cancelled", confirmed_not_sent: "confirmed here, not sent",
      sent: "sent via Andrea", delivery_unconfirmed: "delivery unconfirmed" }[draft.state] || "not sent");
    const recipient = document.createElement("p");
    recipient.className = "text-recipient";
    recipient.textContent = `To: ${draft.recipient.name}\n${draft.recipient.addresses.join(", ")}\nThread: ${draft.recipient.guid}`;
    const body = document.createElement("pre");
    body.className = "text-draft-body"; body.textContent = draft.body;
    card.append(title, recipient, body);
    if (draft.state === "editing") {
      const form = document.createElement("form");
      const toLabel = document.createElement("label");
      toLabel.textContent = "Recipient or exact thread ID";
      const to = document.createElement("input");
      to.value = draft.recipient.guid; to.required = true; to.maxLength = 500;
      toLabel.append(to);
      const bodyLabel = document.createElement("label"); bodyLabel.textContent = "Text body";
      const field = document.createElement("textarea");
      field.value = draft.body; field.required = true; field.maxLength = 4000; field.rows = 4;
      bodyLabel.append(field);
      const review = document.createElement("button"); review.type = "submit"; review.textContent = "Review new draft";
      form.append(toLabel, bodyLabel, review);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        submitChatText(`replace text draft ${draft.id} to ${to.value}: ${field.value}`);
      });
      card.append(form);
    }
    if (draft.confirm_message) {
      const hint = document.createElement("p");
      hint.textContent = `To confirm this exact draft, send separately in chat by ${new Date(draft.expires_at * 1000).toLocaleTimeString()}:`;
      const code = document.createElement("code"); code.className = "text-confirmation"; code.textContent = draft.confirm_message;
      const prepare = document.createElement("button"); prepare.type = "button"; prepare.textContent = "Put confirmation in chat";
      prepare.addEventListener("click", () => {
        $("message").value = draft.confirm_message;
        $("message").dispatchEvent(new Event("input")); $("message").focus();
      });
      card.append(hint, code, prepare);
    }
    if (["pending", "expired", "confirmed_not_sent"].includes(draft.state)) {
      const edit = document.createElement("button"); edit.type = "button"; edit.textContent = "Edit draft";
      // Clear consent on the server before exposing editable fields, including in other tabs.
      edit.addEventListener("click", () => submitChatText(`edit text draft ${draft.id}`));
      const cancel = document.createElement("button"); cancel.type = "button"; cancel.textContent = "Cancel draft";
      cancel.addEventListener("click", () => submitChatText(`cancel text draft ${draft.id}`));
      card.append(edit, cancel);
    }
    const status = document.createElement("p"); status.className = "text-delivery-status";
    status.textContent = draft.state === "sent"
      ? "Sent through Andrea’s BlueBubbles bridge."
      : draft.state === "delivery_unconfirmed"
        ? "Delivery is unconfirmed. Check the recipient’s thread before preparing another draft."
        : draft.state === "confirmed_not_sent"
          ? "Not sent. Andrea could not accept this delivery; this confirmation cannot be reused."
          : "Nothing has been sent until you confirm with the exact yes + token in chat.";
    card.append(status);
    return card;
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
      $("connection").textContent = "Connected to Bob";
      const dot = $("status-dot");
      if (dot) {
        dot.classList.remove("warn");
        dot.classList.add("connected");
        dot.setAttribute("aria-label", "Connected");
      }
      $("offline-banner")?.setAttribute("hidden", "");
      if (!busy && $("notice").textContent === "Stopping this reply…") $("notice").textContent = "";
    } catch (error) {
      pollFailures += 1;
      const offline = pollFailures >= 3;
      $("connection").textContent = offline ? "Cannot reach Bob" : "Reconnecting…";
      const dot = $("status-dot");
      if (dot) {
        dot.classList.remove("connected");
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
    const result = event.target.closest(".job-result-link[data-job-id]");
    if (result) {
      await showJobResult("/api/jobs/result?id=" + result.dataset.jobId);
      return;
    }
    const btn = event.target.closest(".copy-code");
    if (!btn) return;
    const code = btn.parentElement?.querySelector("code")?.textContent || "";
    try {
      await navigator.clipboard.writeText(code);
      btn.textContent = "Copied";
      setTimeout(() => { btn.textContent = "Copy"; }, 1200);
    } catch (_) { $("notice").textContent = "Could not copy — select the code manually."; }
  });
  function submitChatText(text) {
    if (!current || busy || sending) return;
    $("message").value = text;
    $("message").dispatchEvent(new Event("input"));
    $("composer").requestSubmit();
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
    if (!setBottomTab("chat")) { $("conversations").value = current; return; }
    $("chats-dialog").close();
    current = $("conversations").value; remember("bob.conversation", current); revision = ""; busy = false;
    await poll(); $("messages").scrollTop = $("messages").scrollHeight;
  });
  $("new-chat").addEventListener("click", async () => {
    if (!setBottomTab("chat")) return;
    $("chats-dialog").close();
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
      $("call-status").textContent = "Listening… speak anytime, or tap End call.";
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
    if (!(await confirmLeaveSongEdits())) return;
    $("settings-notice").textContent = "";
    try { await api("/api/logout", {}); markSongClean(); location.assign("/login"); }
    catch (_) { $("settings-notice").textContent = "Could not log out. Please try again."; }
  });
  $("close-report").addEventListener("click", () => $("report").close());
  let songProjectId = stored("bob.songProject") || "", songBusy = false;
  function setSongBusy(value) {
    songBusy = value;
    for (const id of ["song-new", "song-picker", "song-save", "song-title", "song-lyrics", "song-chords", "song-notes", "song-demo", "song-upload", "song-coach"]) $(id).disabled = value;
  }
  function clearSongMedia() {
    $("song-player").pause();
    $("song-player").removeAttribute("src");
    $("song-player").load();
    $("song-player").hidden = true;
    $("song-versions").replaceChildren();
    $("song-history").hidden = true;
    $("song-notice").textContent = "";
    for (const id of ["song-arrangement", "song-audio", "song-history"]) $(id).open = false;
  }
  function showSong(project, keepAudio = false) {
    if (!keepAudio) clearSongMedia();
    for (const key of ["title", "lyrics", "chords", "notes"]) $("song-" + key).value = project[key] || "";
    $("song-editor").hidden = false;
    $("songs-empty").hidden = true;
    $("song-summary").textContent = project.updated_at ? `Saved ${timestamp(project.updated_at)}` : "New song · not saved yet";
    const seen = new Set();
    const versions = (project.versions || []).slice().reverse().filter((row) => {
      const key = JSON.stringify([row.at, row.lyrics]);
      if (!row.at || seen.has(key)) return false;
      seen.add(key); return true;
    });
    $("song-history").hidden = !versions.length;
    $("song-versions").replaceChildren(...versions.map((row) => {
      const item = element("li");
      item.append(element("p", timestamp(row.at)));
      if (row.lyrics) item.append(element("p", row.lyrics, "version-lyrics"));
      return item;
    }));
    markSongClean();
  }
  async function loadSongList() {
    const list = await api("/api/song-projects");
    const seen = new Set();
    list.projects = (list.projects || []).filter((project) => {
      if (!project.id || seen.has(project.id)) return false;
      seen.add(project.id); return true;
    });
    $("song-picker").replaceChildren(...list.projects.map((project) => {
      const option = element("option", project.title || "Untitled song");
      option.value = project.id;
      return option;
    }));
    $("song-library").hidden = !list.projects.length;
    return list;
  }
  async function loadSong(id) {
    if (songBusy) return;
    setSongBusy(true);
    try {
      const list = await loadSongList();
      const row = list.projects.find((project) => project.id === (id || songProjectId)) || list.projects[0];
      if (!row) {
        songProjectId = ""; remember("bob.songProject", "");
        clearSongMedia();
        $("song-editor").hidden = true;
        $("songs-empty").hidden = false;
        $("song-summary").textContent = "No saved songs yet.";
        markSongClean();
        return;
      }
      const project = await api(`/api/song-projects/${row.id}`);
      songProjectId = row.id;
      remember("bob.songProject", songProjectId);
      $("song-picker").value = songProjectId;
      showSong(project);
    } catch (_) {
      $("song-picker").value = songProjectId;
      $("song-summary").textContent = "Could not load songs. Choose a song again or reload to retry.";
    } finally { setSongBusy(false); }
  }
  $("song-picker").addEventListener("change", async () => {
    if (!(await confirmLeaveSongEdits())) { $("song-picker").value = songProjectId; return; }
    await loadSong($("song-picker").value);
  });
  $("song-new").addEventListener("click", async () => {
    if (songBusy || !(await confirmLeaveSongEdits())) return;
    songProjectId = ""; remember("bob.songProject", "");
    $("song-picker").value = "";
    showSong({});
    $("song-title").focus();
  });
  for (const id of ["song-title", "song-lyrics", "song-chords", "song-notes"]) {
    $(id).addEventListener("input", () => { $("song-summary").textContent = "Unsaved changes"; $("song-notice").textContent = ""; });
  }
  window.addEventListener("beforeunload", (event) => {
    if (songFieldsText() !== songSnapshot) { event.preventDefault(); event.returnValue = ""; }
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
    if (songBusy) return;
    setSongBusy(true);
    $("song-notice").textContent = "Saving…";
    try {
      const project = await api("/api/song-projects", {
        id: songProjectId || undefined,
        title: $("song-title").value,
        lyrics: $("song-lyrics").value,
        chords: $("song-chords").value,
        notes: $("song-notes").value,
        version_note: "Saved",
      });
      songProjectId = project.id; remember("bob.songProject", songProjectId);
      // Apply the saved response before refreshing the list, which can fail independently.
      showSong(project, true);
      $("song-notice").textContent = "Song saved.";
      try { await loadSongList(); $("song-picker").value = project.id; }
      catch (_) { $("song-notice").textContent = "Song saved. Reload to refresh the song list."; }
    } catch (error) { $("song-notice").textContent = `Not saved. ${error.message} Keep this page open to retain your edits.`; }
    finally { setSongBusy(false); }
  });
  $("song-demo").addEventListener("click", async () => {
    if (songBusy) return;
    setSongBusy(true);
    try {
      const lyrics = $("song-lyrics").value.trim();
      if (!lyrics) { $("song-notice").textContent = "Add lyrics first."; return; }
      let receipt = "";
      try {
        const quote = await api("/api/music/demo", { lyrics, style: $("song-notes").value || "acoustic songwriter" });
        if (quote.needs_confirm) {
          receipt = quote.receipt || "";
          if (!quote.can_afford_demo) { $("song-notice").textContent = quote.message || "The spending limit does not allow this audio request."; return; }
          if (!window.confirm(quote.message || "Create rough audio from these lyrics?")) return;
        }
      } catch (error) { $("song-notice").textContent = error.message; return; }
      $("song-notice").textContent = "Creating audio…";
      try {
        const demo = await api("/api/music/demo", {
          lyrics, style: $("song-notes").value || "acoustic songwriter", confirm: true, receipt,
        });
        if (demo.audio_id) {
          const player = $("song-player");
          player.hidden = false;
          player.src = `/api/audio/${demo.audio_id}`;
          $("song-notice").textContent = "Audio ready to play.";
        } else $("song-notice").textContent = demo.message || "No audio was returned. Try again.";
      } catch (error) { $("song-notice").textContent = error.message; }
    } finally { setSongBusy(false); }
  });
  $("song-upload").addEventListener("change", async (event) => {
    if (songBusy) return;
    setSongBusy(true);
    try {
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
    } finally { setSongBusy(false); }
  });
  function element(tag, text, className = "") {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function duration(seconds) {
    if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return "";
    if (seconds < 60) return "less than a minute";
    const minutes = Math.floor(seconds / 60);
    return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} hr ${minutes % 60} min`;
  }
  function timestamp(value) {
    if (!value) return "";
    const date = new Date(typeof value === "number" ? value * 1000 : value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }
  function disclosure(label, rows, key) {
    const detail = element("details", null, "disclosure card-details");
    detail.dataset.detailKey = key;
    detail.append(element("summary", label));
    const list = document.createElement("dl");
    for (const [name, value] of rows) {
      if (value === undefined || value === null || value === "") continue;
      list.append(element("dt", name), element("dd", value));
    }
    detail.append(list);
    return detail;
  }
  function replaceCards(host, cards) {
    const open = new Set([...host.querySelectorAll("details[open]")].map((item) => item.dataset.detailKey));
    cards.forEach((card) => card.querySelectorAll("details").forEach((item) => { item.open = open.has(item.dataset.detailKey); }));
    host.replaceChildren(...cards);
  }
  function modelReason(reason) {
    return ({ not_logged_in: "Sign-in needed", rate_limit: "Usage limit reached", timeout: "Reply took too long",
      network: "Connection problem", invalid_output: "No usable reply", nonzero_exit: "Could not reply",
      budget: "Spending limit reached", not_installed: "Not set up", session_unavailable: "Could not reopen the conversation",
      busy: "Already in use", cooldown: "Waiting before trying again" })[reason] || "Could not reply";
  }
  let overviewFetchedAt = 0, overviewLoading = false;
  function clearOverview() {
    $("lanes-summary").textContent = "Cannot check models. Try Refresh.";
    $("lanes").replaceChildren();
    $("models-empty").hidden = true;
    $("self-improve-status").textContent = "Cannot check the schedule right now.";
  }
  function jobElement(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    if (text != null) element.textContent = text;
    return element;
  }
  function jobDuration(seconds) {
    if (!Number.isFinite(seconds)) return "Time not reported";
    const minutes = Math.floor(Math.max(0, seconds) / 60);
    if (!minutes) return "Less than a minute";
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    return hours < 24 ? `${hours} hr${minutes % 60 ? ` ${minutes % 60} min` : ""}` : `${Math.floor(hours / 24)}d ${hours % 24} hr`;
  }
  function jobAge(seconds) {
    return Number.isFinite(seconds) ? seconds < 60 ? "Just now" : `${jobDuration(seconds)} ago` : "Not reported";
  }
  function jobLink(url, label) {
    if (!url) return null;
    let parsed;
    try { parsed = new URL(url, location.origin); } catch (_) { return null; }
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) return null;
    const link = jobElement("a", "job-result-link", label);
    link.href = parsed.href;
    link.rel = "noopener noreferrer";
    link.target = "_blank";
    return link;
  }
  function uniqueJobs(rows) {
    const seen = new Set();
    return (rows || []).filter((row) => { if (seen.has(row.key)) return false; seen.add(row.key); return true; });
  }
  function renderJobs(data) {
    const rows = uniqueJobs(data.working);
    const complete = data.inspection?.screens_available && data.inspection?.processes_available && data.inspection?.queue_available;
    $("working-count").hidden = !rows.length;
    $("working-count").textContent = String(rows.length);
    $("jobs-notice").hidden = complete;
    $("jobs-notice").textContent = complete ? "" : "Some live activity could not be checked. Retrying…";
    $("jobs-empty").hidden = rows.length > 0 || !complete;
    $("live-jobs").replaceChildren(...rows.map((job) => {
      const card = jobElement("article", "job-card");
      const header = jobElement("div", "job-card-heading");
      const state = ({ running: "Live", paused: "Paused", unverified: "Session open", claimed: "Unconfirmed" })[job.state] || "Unconfirmed";
      const status = jobElement("span", `job-state ${job.state === "running" ? "is-live" : ""}`, state);
      const dot = jobElement("span", "job-dot");
      dot.setAttribute("aria-hidden", "true");
      status.prepend(dot);
      if (job.project !== "Project not specified") header.append(jobElement("p", "job-project", job.project));
      header.append(status);
      const metadata = jobElement("div", "job-metadata");
      const models = (job.models || []).filter((model) => model && model !== "Model not reported");
      if (models.length) metadata.append(jobElement("span", "job-model", models.join(" / ")));
      if (Number.isFinite(job.elapsed_seconds)) metadata.append(jobElement("span", "job-elapsed", jobDuration(job.elapsed_seconds)));
      card.append(header, jobElement("h3", "job-task", job.task), metadata);
      if (job.state === "unverified" || job.state === "claimed") {
        card.append(jobElement("p", "job-unconfirmed muted", "Worker activity is not confirmed."));
      }
      return card;
    }));
    const finished = data.inspection?.queue_available ? uniqueJobs(data.recently_finished).slice(0, 5) : [];
    $("finished-empty").hidden = finished.length > 0;
    $("finished-empty").textContent = data.inspection?.queue_available ? "No finished jobs yet." : "Finished jobs could not be checked.";
    $("finished-jobs").replaceChildren(...finished.map((job) => {
      const card = jobElement("article", "finished-job");
      const heading = jobElement("div", "job-card-heading");
      heading.append(jobElement("h3", "job-project", job.project),
        jobElement("span", `job-outcome ${job.state === "failed" ? "is-failed" : ""}`,
          job.state === "done" ? "Finished" : job.state === "failed" ? "Failed" : "Stopped"));
      card.append(heading, jobElement("p", "finished-task", job.task));
      const footer = jobElement("div", "finished-footer");
      if (Number.isFinite(job.finished_at)) footer.append(jobElement("span", "muted", jobAge(data.checked_at - job.finished_at)));
      if (job.result_url?.startsWith("/api/jobs/result?")) {
        const result = jobElement("button", "job-result-link", "View result");
        result.type = "button";
        result.setAttribute("aria-label", `View result for ${job.project}: ${job.task}`);
        result.addEventListener("click", () => showJobResult(job.result_url, job.project, job.task));
        footer.append(result);
      }
      const external = jobLink(job.external_result_url, "View result");
      const pr = jobLink(job.pr_url, "View PR ↗");
      if (external && !job.result_url) footer.append(external);
      if (pr) footer.append(pr);
      card.append(footer);
      return card;
    }));
    const details = data.details || {};
    const list = jobElement("dl", "jobs-detail-list");
    const add = (label, value) => list.append(jobElement("dt", "", label), jobElement("dd", "", value));
    add("Live check", new Date(data.checked_at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }));
    add("Waiting", data.inspection?.queue_available
      ? `${details.queued || 0} queued${details.unconfirmed ? ` · ${details.unconfirmed} assigned, activity unconfirmed` : ""}`
      : "Waiting jobs could not be checked.");
    list.append(jobElement("dt", "", "Activity"), jobElement("dd", "", "A running worker does not confirm progress or completion."));
    $("jobs-detail-body").replaceChildren(list);
  }
  let jobsRefreshing = false, jobsFetchedAt = 0;
  function clearJobs() {
    $("jobs-notice").hidden = false;
    $("jobs-notice").textContent = "Live work is unavailable. Retrying…";
    $("jobs-empty").hidden = true;
    $("finished-empty").hidden = true;
    $("working-count").hidden = true;
    $("live-jobs").replaceChildren();
    $("finished-jobs").replaceChildren();
    $("jobs-detail-body").replaceChildren(jobElement("p", "muted", "Live check unavailable."));
  }
  async function refreshJobs() {
    if (jobsRefreshing) return;
    jobsRefreshing = true;
    $("refresh-jobs").disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const data = await api("/api/jobs/activity", undefined, controller.signal);
      const age = Date.now() - data.checked_at * 1000;
      if (!Number.isFinite(age) || age > 30000 || age < -30000) throw new Error("Current work unavailable");
      jobsFetchedAt = Date.now();
      renderJobs(data);
    } catch (_) { jobsFetchedAt = 0; clearJobs(); }
    finally {
      clearTimeout(timeout);
      jobsRefreshing = false;
      $("refresh-jobs").disabled = false;
    }
  }
  $("refresh-jobs").addEventListener("click", refreshJobs);
  function renderModels(data) {
    const entries = Object.entries(data.models || {}).filter(([name]) => providers[name]);
    $("lanes-summary").textContent = !entries.length ? "Model status is unavailable."
      : data.inspection?.processes_available === true ? "Current activity and reply availability." : "Reply availability. Background activity could not be checked.";
    $("models-empty").hidden = entries.length > 0;
    replaceCards($("lanes"), entries.map(([name, model]) => {
      const work = (data.work || []).filter((job) => job.worker === name && job.state === "running");
      const busy = model.state === "busy" || work.length > 0;
      const needsAction = ["not_logged_in", "not_installed", "budget"].includes(model.reason) && model.state !== "ready";
      const state = busy ? "In use" : needsAction ? modelReason(model.reason) : ({ ready: "Available to try", cooldown: "Waiting to retry", half_open: "Ready to retry", unchecked: "No reply checked yet" })[model.state] || "Status unavailable";
      const card = element("article", null, "lane-card");
      const heading = element("header", null, "card-heading");
      heading.append(element("h3", providers[name]), element("span", state, `state-label ${busy ? "running" : ""}`));
      card.append(heading);
      const usage = model.usage || {};
      const details = [];
      if (work.length) details.push(["Current work", [...new Set(work.map((job) => job.title).filter((title) => title && title !== "Task details unavailable"))].join("; ")]);
      if (model.reason && model.state !== "ready") details.push(["Last reply issue", modelReason(model.reason)]);
      if (model.retry_at > Date.now() / 1000) details.push(["Try again after", timestamp(model.retry_at)]);
      if (model.last_success) details.push(["Last reply", timestamp(model.last_success)]);
      if (typeof usage.spent_usd === "number") details.push(["Recorded cost", `$${usage.spent_usd.toFixed(2)}`]);
      if (typeof usage.reserved_usd === "number" && usage.reserved_usd > 0) details.push(["Pending cost", `$${usage.reserved_usd.toFixed(2)}`]);
      if (typeof usage.used_percent === "number") details.push(["Reported plan use", `${usage.used_percent}%`], ["Resets", timestamp(usage.reset_at)]);
      if (usage.observed_at) details.push(["Usage recorded", timestamp(usage.observed_at)]);
      if (details.length) card.append(disclosure("Details", details, name));
      return card;
    }));
  }
  function renderSettings(data) {
    const si = data.automation || {};
    $("self-improve-status").textContent = si.launchd_files_ok === false ? "Not set up on this computer."
      : si.launchd_loaded === true ? "Scheduled on this computer."
      : si.launchd_loaded === false ? "Not scheduled."
      : "Schedule status is unavailable.";
    $("quiet-hours-hint").textContent = isQuietHoursCt()
      ? "Quiet hours are on until 7 AM Central. Read-aloud is off."
      : "Read-aloud is off from 11 PM to 7 AM Central.";
  }
  async function refreshOverview() {
    if (overviewLoading) return;
    overviewLoading = true;
    const buttons = [...document.querySelectorAll("[data-refresh]")];
    buttons.forEach((button) => { button.disabled = true; button.textContent = "Refreshing…"; });
    try {
      const data = await api("/api/overview" + (current ? "?conversation_id=" + encodeURIComponent(current) : ""));
      const age = Date.now() - Date.parse(data.captured_at);
      if (!Number.isFinite(age) || age > 30000 || age < -30000) throw new Error("Current status unavailable");
      overviewFetchedAt = Date.now();
      renderModels(data); renderSettings(data);
    } catch (_) { overviewFetchedAt = 0; clearOverview(); }
    finally {
      overviewLoading = false;
      buttons.forEach((button) => { button.disabled = false; button.textContent = "Refresh"; });
    }
  }
  document.querySelectorAll("[data-refresh]").forEach((button) => button.addEventListener("click", refreshOverview));
  async function init() {
    try {
      primeSpeechVoices();
      const recognition = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
      $("mic").hidden = !recognition;
      $("live-call").hidden = !recognition || !("speechSynthesis" in window);
      $("speak").hidden = !("speechSynthesis" in window);
      $("voice-status").textContent = recognition ? "Use the microphone in Chat to dictate. Voice chat listens and reads replies aloud."
        : "Use your keyboard’s microphone to dictate. Voice chat is unavailable in this browser.";
      const preference = stored("bob.provider");
      if ([...$("provider-choice").options].some((option) => option.value === preference)) $("provider-choice").value = preference;
      csrf = (await api("/api/session")).csrf; current = stored("bob.conversation");
      await refreshList(); await poll(); $("messages").scrollTop = $("messages").scrollHeight;
      await Promise.allSettled([refreshJobs(), refreshOverview(), loadSong()]);
      setInterval(() => { if (!document.hidden) { refreshJobs(); refreshOverview(); } }, 8000);
      setInterval(() => { if (!document.hidden) poll(); }, 1200);
      setInterval(() => { if (overviewFetchedAt && Date.now() - overviewFetchedAt > 30000) clearOverview(); if (jobsFetchedAt && Date.now() - jobsFetchedAt > 30000) clearJobs(); }, 1000);
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) { if (Date.now() - overviewFetchedAt > 30000) clearOverview(); if (Date.now() - jobsFetchedAt > 30000) clearJobs(); refreshJobs(); refreshOverview(); poll(); }
      });
    } catch (error) { $("notice").textContent = error.message; }
  }
  composerState(); init();
}

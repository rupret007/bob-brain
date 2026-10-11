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
  let csrf = "", current = "", busy = false, replyStopping = false, sending = false, revision = "", polling = false, draftRequest = null, pollFailures = 0;
  let pendingAttachments = [];
  let uploading = false, quickRequest = null;
  const composerDrafts = new Map();
  let chatReady = false, connecting = false, authRedirecting = false, connectFailures = 0, connectAfter = 0;
  const MEDIA_LIMITS = { image: 12 * 1024 * 1024, video: 35 * 1024 * 1024, file: 8 * 1024 * 1024 };
  const MAX_PENDING_ATTACHMENTS = 6;
  let lastQuietHoursActive = null, lastQuietHoursFetchedAt = 0, lastBootstrapCommand = "";
  const providers = { voice: "Bob voice", codex: "Codex", cursor: "Cursor", gemini: "Gemini", minimax: "MiniMax", claude: "Claude", texting: "Texts · private" };
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
    // Keep fenced code out of prose formatting: <br> loses newlines when
    // copied as textContent, and inline Markdown must remain literal code.
    return text.split(/(```[\s\S]*?```)/g).map((part, index) => {
      if (index % 2) {
        let code = part.slice(3, -3);
        const firstLine = code.indexOf("\n");
        if (firstLine >= 0) code = code.slice(firstLine + 1).replace(/\r?\n$/, "");
        return `<pre class="code-block" tabindex="0"><button type="button" class="copy-code" aria-label="Copy code">Copy</button><code>${escapeHtml(code)}</code></pre>`;
      }
      let html = escapeHtml(part);
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
    }).join("");
  }
  const stored = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  async function api(path, data, signal) {
    const requestSignal = signal || AbortSignal.timeout(data === undefined ? 15000 : 45000);
    try {
      const response = await fetch(path, { credentials: "same-origin", cache: "no-store", signal: requestSignal,
        keepalive: path === "/api/voice/end" || path === "/api/voice/transcript",
        ...(data === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(data) }) });
      if (response.status === 401) { authRedirecting = true; location.assign("/login"); throw new Error("Please log in."); }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Request failed.");
      return result;
    } catch (error) {
      // A timed-out mutation may already have reached the server. Keep the
      // composer request identity and never replay it automatically.
      if (data !== undefined && requestSignal.aborted && requestSignal.reason?.name === "TimeoutError") {
        throw new Error("Request timed out. Check the result before retrying; it may still finish.");
      }
      throw error;
    }
  }
  let jobResultRequest = null, jobResultRetry = null, jobResultOrigin = null;
  function cancelJobResult() {
    if (jobResultRequest) clearTimeout(jobResultRequest.timeout);
    jobResultRequest?.controller.abort();
    jobResultRequest = jobResultRetry = null;
    $("report-body").setAttribute("aria-busy", "false");
    $("retry-report").hidden = true;
  }
  async function showJobResult(url, project = "Job result", task = "", opener = document.activeElement) {
    cancelJobResult();
    if (!$("report").open) jobResultOrigin = { opener, url };
    const request = { url, project, task, controller: new AbortController() };
    jobResultRequest = request;
    $("report-title").textContent = project;
    $("report-date").textContent = task;
    $("report-body").textContent = "";
    $("report-body").setAttribute("aria-busy", "true");
    $("report-status").textContent = "Loading result…";
    if (!$("report").open) $("report").showModal();
    // Supplying a cancellable signal must preserve api()'s normal read bound.
    request.timeout = setTimeout(() => request.controller.abort(), 15000);
    try {
      const result = await api(url, undefined, request.controller.signal);
      if (jobResultRequest !== request || !$("report").open) return;
      if (request.controller.signal.aborted) throw new Error("Result read timed out");
      $("report-title").textContent = result.project || project;
      $("report-date").textContent = result.task || task;
      $("report-body").textContent = result.text;
      $("report-status").textContent = "";
    } catch (_) {
      if (jobResultRequest !== request || !$("report").open) return;
      $("report-status").textContent = "This result could not be loaded. Try again.";
      jobResultRetry = request;
      $("retry-report").hidden = false;
    } finally {
      clearTimeout(request.timeout);
      if (jobResultRequest === request) {
        jobResultRequest = null;
        $("report-body").setAttribute("aria-busy", "false");
      }
    }
  }
  $("retry-report").addEventListener("click", () => {
    if (jobResultRetry) return showJobResult(jobResultRetry.url, jobResultRetry.project, jobResultRetry.task);
  });
  $("close-report").addEventListener("click", () => { cancelJobResult(); $("report").close(); });
  $("report").addEventListener("cancel", cancelJobResult);
  // A queued close event from an earlier dismissal can arrive after reopening.
  $("report").addEventListener("close", () => {
    if ($("report").open) return;
    cancelJobResult();
    const origin = jobResultOrigin;
    jobResultOrigin = null;
    // Polling can replace the Jobs button while its report is open.
    const opener = origin?.opener?.isConnected && origin.opener.getClientRects().length ? origin.opener
      : [...document.querySelectorAll('[data-result-url], [data-job-id]')].find(node =>
        node.getClientRects().length &&
        (node.dataset.resultUrl || '/api/jobs/result?id=' + node.dataset.jobId) === origin?.url);
    opener?.focus();
  });
  function mediaKindFromFile(file) {
    const extension = file.name.split(".").pop().toLowerCase();
    if (["jpg", "jpeg", "png", "gif", "webp", "heic", "heif"].includes(extension)) return "image";
    if (["mp4", "mov", "webm", "m4v", "mkv"].includes(extension)) return "video";
    if (["pdf", "txt", "md", "csv", "json", "log"].includes(extension)) return "file";
    return null;
  }
  function switchConversation(id) {
    if (current) composerDrafts.set(current, { attachments: pendingAttachments, message: $("message").value, request: draftRequest });
    current = id;
    const draft = composerDrafts.get(id);
    pendingAttachments = draft?.attachments || [];
    $("message").value = draft?.message || "";
    draftRequest = draft?.request || null;
    revision = ""; busy = false; replyStopping = false;
    renderAttachmentStrip(); composerState();
    remember("bob.conversation", id);
  }
  function uploadMedia(file, conversationId) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/media/upload");
      xhr.timeout = 120000;
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
      xhr.setRequestHeader("X-CSRF-Token", csrf);
      xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
      xhr.setRequestHeader("X-Conversation-Id", conversationId);
      xhr.upload.onprogress = (event) => {
        $("notice").textContent = `Uploading ${file.name}${event.lengthComputable ? ` — ${Math.round(event.loaded * 100 / event.total)}%` : "…"}`;
      };
      xhr.onload = () => {
        if (xhr.status === 401) { location.assign("/login"); reject(new Error("Please log in.")); return; }
        try {
          const result = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) resolve(result);
          else reject(new Error(result.error || "Upload failed. Please retry."));
        } catch (_) { reject(new Error("Upload failed. Please retry.")); }
      };
      xhr.onerror = xhr.ontimeout = xhr.onabort = () => reject(new Error(`Could not upload ${file.name}. Please retry.`));
      xhr.send(file);
    });
  }
  function mediaLimitForKind(kind) {
    return MEDIA_LIMITS[kind] || MEDIA_LIMITS.file;
  }
  function renderAttachmentStrip() {
    const host = $("attach-preview");
    if (!host) return;
    host.replaceChildren();
    if (!pendingAttachments.length) {
      host.hidden = true;
      return;
    }
    host.hidden = false;
    for (const item of pendingAttachments) {
      const chip = document.createElement("div");
      chip.className = "attach-chip";
      if (item.kind === "image") {
        const img = document.createElement("img");
        img.src = item.url + "&preview=1";
        img.alt = item.filename || "Image preview";
        chip.append(img);
      } else if (item.kind === "video") {
        const label = document.createElement("div");
        label.className = "attach-file-label";
        label.textContent = "Video";
        chip.append(label);
      } else {
        const label = document.createElement("div");
        label.className = "attach-file-label";
        label.textContent = item.filename || "File";
        chip.append(label);
      }
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "attach-remove quiet";
      remove.setAttribute("aria-label", "Remove attachment");
      remove.textContent = "×";
      remove.disabled = sending;
      remove.addEventListener("click", () => {
        pendingAttachments = pendingAttachments.filter((row) => row.media_id !== item.media_id);
        renderAttachmentStrip();
        composerState();
      });
      chip.append(remove);
      host.append(chip);
    }
  }
  function appendMessageAttachments(parent, attachments) {
    if (!attachments?.length) return;
    const wrap = document.createElement("div");
    wrap.className = "message-attachments";
    for (const att of attachments) {
      const url = att.url || `/api/media/${att.media_id}?conversation_id=${current}`;
      const item = document.createElement("div");
      item.className = "message-attachment";
      if (att.kind === "image") {
        const img = document.createElement("img");
        img.src = url + "&preview=1";
        img.alt = att.filename || "Image";
        img.loading = "lazy";
        img.addEventListener("error", () => { img.hidden = true; });
        const open = document.createElement("a");
        open.href = url; open.target = "_blank"; open.rel = "noopener noreferrer";
        open.append(img); item.append(open);
      } else if (att.kind === "video") {
        const video = document.createElement("video");
        video.src = url;
        video.controls = true;
        video.preload = "metadata";
        video.playsInline = true;
        video.addEventListener("error", () => {
          const fallback = document.createElement("p");
          fallback.textContent = "Video preview unavailable in this browser. Download the original below.";
          video.replaceWith(fallback);
        });
        item.append(video);
      }
      const link = document.createElement("a");
      link.href = url + "&download=1";
      link.className = "attach-download";
      link.textContent = att.filename || "Download file";
      link.download = att.filename || "";
      item.append(link); wrap.append(item);
    }
    parent.append(wrap);
  }
  function composerState() {
    const hasText = Boolean($("message").value.trim());
    const hasAttach = pendingAttachments.length > 0;
    $("send").disabled = !chatReady || busy || sending || uploading || !current || (!hasText && !hasAttach);
    $("stop").hidden = !busy || replyStopping;
    $("message").disabled = !chatReady || !current;
    const attachBtn = $("attach-plus");
    if (attachBtn) attachBtn.disabled = !chatReady || !current || busy || sending || uploading;
    $("conversations").disabled = !chatReady || sending || uploading;
    $("new-chat").disabled = !chatReady || sending || uploading;
    $("conversations-dialog").disabled = !chatReady || sending || uploading;
    $("new-chat-dialog").disabled = !chatReady || sending || uploading;
    document.querySelectorAll(".attach-remove").forEach((button) => { button.disabled = sending; });
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
    if (!chatReady || !text || !current) return;
    if (confirmStop && !window.confirm(confirmMessage || "Stop this job?")) return;
    if (uploading || ((busy || sending) && !confirmStop)) {
      $("notice").textContent = "Wait for the current reply to finish, then try again.";
      setBottomTab("chat");
      return;
    }
    setBottomTab("chat");
    const provider = $("provider-choice").value;
    if (!quickRequest || quickRequest.message !== text || quickRequest.conversation_id !== current || quickRequest.provider !== provider) {
      quickRequest = { conversation_id: current, message: text, provider, request_id: crypto.randomUUID(), attachments: [] };
    }
    const payload = quickRequest;
    sending = true;
    composerState();
    $("notice").textContent = "";
    try {
      const conversation = await api("/api/messages", payload);
      if (payload === quickRequest) quickRequest = null;
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
  function setBottomTab(name) {
    if (!["chat", "ops", "lanes", "settings"].includes(name)) name = "chat";
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
    document.title = `Bob · ${{chat: "Chat", ops: "Jobs", lanes: "Models", settings: "Settings"}[name]}`;
    if (name === "ops") refreshJobs();
    if (["lanes", "settings"].includes(name) && Date.now() - overviewFetchedAt > 8000) refreshOverview();
    return true;
  }
  for (const btn of document.querySelectorAll(".bottom-tab")) {
    btn.addEventListener("click", () => setBottomTab(btn.dataset.bottom));
  }
  $("open-chats").addEventListener("click", () => {
    syncConversationDialog();
    $("chats-dialog").showModal();
  });
  $("close-chats").addEventListener("click", () => $("chats-dialog").close());
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
    $("chats-dialog").close();
  });
  $("new-chat-dialog")?.addEventListener("click", () => { $("new-chat").click(); $("chats-dialog").close(); });
  $("quick-chips").addEventListener("click", (event) => {
    const key = event.target.closest("[data-chip]")?.dataset.chip;
    if (key === "status") setBottomTab("ops");
    if (key === "texts") {
      setBottomTab("chat");
      submitChatText("texts");
    }
  });
  $("provider-choice").addEventListener("change", () => remember("bob.provider", $("provider-choice").value));
  $("manage-memory")?.addEventListener("click", () => {
    setBottomTab("chat");
    submitChatText("manage saved memories");
  });
  $("show-memory")?.addEventListener("click", () => {
    setBottomTab("chat");
    submitChatText("show my saved memories");
  });
  $("project-context")?.addEventListener("click", () => {
    setBottomTab("chat");
    submitChatText("show saved project context");
  });
  const messageText = new WeakMap();
  function render(conversation) {
    if (conversation.id !== current) return;
    const nextRevision = JSON.stringify(conversation);
    const wasStopping = replyStopping;
    replyStopping = Boolean(conversation.reply_stopping);
    busy = replyStopping || conversation.messages.some((message) => ["running", "queued", "waiting"].includes(message.status));
    composerState();
    if (nextRevision === revision) return;
    revision = nextRevision;
    const last = conversation.messages.at(-1);
    if (replyStopping && !sending) {
      $("notice").textContent = "Stopping the reply. You can keep writing; Send will return when it finishes.";
    } else if (last?.status === "cancelled" && last.role === "assistant" && !sending) {
      $("notice").textContent = "Reply stopped. Send again when ready.";
    } else if (wasStopping && !sending) {
      $("notice").textContent = "The previous reply has finished stopping. You can send again.";
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
      if (message.private_memory) article.classList.add("private-memory");
      if (message.role === "user") article.setAttribute("aria-label", "You");
      else article.setAttribute("aria-label", message.provider ? `Assistant, ${providers[message.provider] || "Bob"}` : "Assistant");
      const body = document.createElement("div"); body.className = "body";
      if (pending) body.textContent = providers[message.provider] ? `${providers[message.provider]} is replying…` : "One moment…";
      else if (message.role === "assistant" && !message.texting && !message.private_memory) {
        if (message.artifact?.accepted && message.artifact?.kind === "writing") {
          const label = document.createElement("div");
          label.className = "artifact-label";
          label.textContent = "Draft";
          body.append(label);
          const content = document.createElement("div");
          content.innerHTML = renderMarkdown(message.artifact.text || message.content || "");
          body.append(content);
          if (message.artifact.commentary) {
            const note = document.createElement("p");
            note.className = "artifact-commentary";
            note.textContent = message.artifact.commentary;
            body.append(note);
          }
        } else body.innerHTML = renderMarkdown(message.content || "");
      }
      else body.textContent = message.private_memory && message.memory_action_label || message.content;
      article.append(body);
      if (message.private_memory && Array.isArray(message.project_facts)) {
        for (const fact of message.project_facts) {
          const remove = document.createElement("button");
          remove.type = "button";
          remove.textContent = `Review removal: ${fact.kind}`;
          remove.addEventListener("click", () => submitChatText(
            `forget project fact ${fact.project_id} ${fact.id} at revision ${fact.revision}`));
          article.append(remove);
        }
      }
      if (message.private_memory && Array.isArray(message.memory_notes)) {
        for (const note of message.memory_notes) {
          const card = document.createElement("div"); card.className = "action-card memory-note";
          const content = document.createElement("div"); content.textContent = note.text;
          const review = document.createElement("button"); review.type = "button";
          review.textContent = "Review removal";
          review.addEventListener("click", () => submitChatText(`remove saved note ${note.id}`));
          card.append(content, review); article.append(card);
        }
      }
      appendMessageAttachments(article, message.attachments);
      const messageTools = document.createElement("div");
      messageTools.className = "message-tools";
      if (message.text_draft) article.append(textDraftCard(message.text_draft));
      {
        const raw = (message.private_memory && message.memory_action_label || message.content || "").trim();
        messageText.set(article, raw);
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
        hint.textContent = (providers[message.provider] || message.provider) + (message.voice_interrupted ? " · interrupted (may include unplayed words)" : "");
        messageTools.append(hint);
      }
      article.append(messageTools);
      if (message.handoff_receipt?.handoff_id) {
        const handoff = message.handoff_receipt;
        const query = new URLSearchParams({conversation_id: current, handoff_id: handoff.handoff_id});
        const tools = document.createElement('div'); tools.className = 'action-card-actions';
        const download = document.createElement('a'); download.className = 'job-result-link';
        download.href = '/api/project-handoffs/export?' + query;
        download.textContent = 'Download handoff'; download.download = 'webbob-handoff.json';
        tools.append(download);
        if (handoff.state === 'returned_unverified') {
          const returned = document.createElement('a'); returned.className = 'job-result-link';
          returned.href = '/api/project-handoffs/return?' + query;
          returned.textContent = 'Download returned review'; returned.download = 'webbob-review.json';
          tools.append(returned);
        } else {
          const picker = document.createElement('input'); picker.type = 'file'; picker.accept = '.json,application/json';
          picker.hidden = true;
          const importButton = document.createElement('button'); importButton.type = 'button';
          importButton.textContent = 'Import returned review';
          importButton.addEventListener('click', () => picker.click());
          picker.addEventListener('change', async () => {
            const file = picker.files?.[0]; if (!file) return;
            const conversationId = query.get('conversation_id');
            importButton.disabled = true;
            try {
              if (file.size > 170000) throw new Error('The returned review is too large.');
              const artifact = JSON.parse(await file.text());
              if (artifact.handoff_id !== handoff.handoff_id) throw new Error('This return belongs to another handoff.');
              await api('/api/project-handoffs/import', {conversation_id: conversationId, artifact});
              if (current === conversationId) render(await api('/api/conversations/' + conversationId));
              $('notice').textContent = 'Review imported. The claimed author remains unverified.';
            } catch (error) { $('notice').textContent = error.message || 'The returned review could not be imported.'; }
            finally { importButton.disabled = false; picker.value = ''; }
          });
          tools.append(importButton, picker);
        }
        article.append(tools);
      }
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
          const removal = message.action_card.kind === "memory-remove";
          const projectRemoval = message.action_card.kind === "project-forget";
          const memory = message.action_card.kind === "memory" || /^memory:/i.test(message.action_card.reason || "");
          const proposalId = message.action_card.proposal_id || message.action_card.id || "";
          const approve = document.createElement("button");
          approve.type = "button"; approve.className = "action-approve";
          approve.textContent = projectRemoval ? "Forget this fact" : removal ? "Remove this note" : memory ? "Save memory" : council ? "Start review" : "Start job";
          approve.addEventListener("click", () => {
            const suffix = proposalId ? ` proposal ${proposalId}` : "";
            submitChatText(projectRemoval ? `yes, forget project fact${suffix}` : removal ? `yes, remove saved note${suffix}` : memory ? `yes, save memory${suffix}` : council ? `yes, run council${suffix}` : `yes, start job${suffix}`);
          });
          const deny = document.createElement("button");
          deny.type = "button"; deny.className = "action-deny";
          deny.textContent = projectRemoval ? "Keep fact" : removal ? "Keep note" : memory ? "Dismiss" : council ? "Dismiss" : "Not now";
          deny.addEventListener("click", () => {
            submitChatText(removal || memory ? "never mind memory" : council ? "never mind council" : "never mind");
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
      read_only: "read-only · never sent", submitted: "submitted · delivery unconfirmed", sent: "sent · delivery unconfirmed",
      delivered: "delivered", delivery_failed: "delivery failed", delivery_unconfirmed: "delivery unconfirmed" }[draft.state] || "not sent");
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
    if (["pending", "expired", "confirmed_not_sent", "read_only"].includes(draft.state)) {
      const edit = document.createElement("button"); edit.type = "button"; edit.textContent = "Edit draft";
      // Clear consent on the server before exposing editable fields, including in other tabs.
      edit.addEventListener("click", () => submitChatText(`edit text draft ${draft.id}`));
      const cancel = document.createElement("button"); cancel.type = "button"; cancel.textContent = "Cancel draft";
      cancel.addEventListener("click", () => submitChatText(`cancel text draft ${draft.id}`));
      card.append(edit, cancel);
    }
    const status = document.createElement("p"); status.className = "text-delivery-status";
    if (draft.check_delivery_message && !draft.read_only && ["submitted", "sent", "delivered", "delivery_failed", "delivery_unconfirmed"].includes(draft.state)) {
      const check = document.createElement("button"); check.type = "button"; check.textContent = "Check delivery";
      check.addEventListener("click", () => submitChatText(draft.check_delivery_message));
      card.append(check);
    }
    status.textContent = draft.read_only || draft.state === "read_only"
      ? "Instinct is read-only. This draft cannot be sent from Web Bob."
      : draft.state === "delivery_failed"
      ? "Messages reports a delivery failure. No automatic resend. A new send needs a fresh draft and confirmation."
      : draft.state === "delivered"
      ? "Messages reports this text delivered."
      : draft.state === "submitted" || draft.state === "sent"
      ? "Submitted through Andrea. Delivery is not confirmed; Check delivery refreshes the original message without resending."
      : draft.state === "delivery_unconfirmed"
        ? "Delivery is unconfirmed. Check delivery to look for Andrea’s receipt without resending."
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
    if (!chatReady || authRedirecting || !current || polling) return;
    polling = true;
    try {
      render(await api(`/api/conversations/${current}`));
      connectionRestored();
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
    const text = messageText.get(article);
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
      await showJobResult("/api/jobs/result?id=" + result.dataset.jobId, "Job result", "", result);
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
  function composerMessage(value) {
    // Local Drive replacements bind the exact typed text, including its ending.
    return /^\s*prepare\s+drive\s+replacement\b/i.test(value) ? value : value.trim();
  }
  $("composer").addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = composerMessage($("message").value);
    if (!chatReady || (!message && !pendingAttachments.length) || busy || sending || uploading) return;
    const provider = $("provider-choice").value;
    const attachIds = pendingAttachments.map((row) => row.media_id);
    if (!draftRequest || draftRequest.message !== message || draftRequest.conversation_id !== current || draftRequest.provider !== provider
        || JSON.stringify(draftRequest.attachments || []) !== JSON.stringify(attachIds)) {
      draftRequest = { conversation_id: current, message, provider, request_id: crypto.randomUUID(), attachments: attachIds };
    }
    sending = true; composerState(); $("notice").textContent = "";
    const submitted = draftRequest;
    try {
      const conversation = await api("/api/messages", submitted);
      if (submitted.conversation_id === current && submitted.message === composerMessage($("message").value)) {
        $("message").value = "";
        $("message").style.height = "auto";
      }
      if (submitted === draftRequest) draftRequest = null;
      pendingAttachments = pendingAttachments.filter((row) => !submitted.attachments.includes(row.media_id));
      renderAttachmentStrip();
      render(conversation); await refreshList();
    } catch (error) { $("notice").textContent = error.message; }
    finally { sending = false; composerState(); $("message").focus(); }
  });
  $("attach-plus")?.addEventListener("click", () => $("attach-input")?.click());
  $("attach-input")?.addEventListener("change", async (event) => {
    const files = [...(event.target.files || [])];
    event.target.value = "";
    if (!chatReady || !files.length || uploading || sending || busy || !current) return;
    if (pendingAttachments.length + files.length > MAX_PENDING_ATTACHMENTS) {
      $("notice").textContent = `At most ${MAX_PENDING_ATTACHMENTS} attachments per message.`;
      return;
    }
    uploading = true; composerState();
    const errors = [];
    try {
      for (const file of files) {
        const kind = mediaKindFromFile(file);
        const limit = mediaLimitForKind(kind);
        if (!kind || !file.size || file.size > limit) {
          errors.push(!kind ? `${file.name}: unsupported file type.` : `${file.name}: file must be between 1 byte and ${limit / 1024 / 1024}MB.`);
          continue;
        }
        try {
          $("notice").textContent = `Uploading ${file.name}…`;
          const stored = await uploadMedia(file, current);
          pendingAttachments.push(stored);
          renderAttachmentStrip();
        } catch (error) {
          errors.push(error.message);
        }
      }
    } finally {
      uploading = false;
      $("notice").textContent = errors.join(" ");
      renderAttachmentStrip();
      composerState();
    }
  });
  $("message").addEventListener("input", () => {
    $("message").style.height = "auto";
    $("message").style.height = Math.min($("message").scrollHeight, 180) + "px";
    composerState();
  });
  $("message").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !matchMedia("(pointer: coarse)").matches) {
      event.preventDefault(); $("composer").requestSubmit();
    }
  });
  $("conversations").addEventListener("change", async () => {
    if (!chatReady || uploading || sending) return;
    if (!setBottomTab("chat")) { $("conversations").value = current; return; }
    $("chats-dialog").close();
    switchConversation($("conversations").value);
    await poll(); $("messages").scrollTop = $("messages").scrollHeight;
  });
  $("new-chat").addEventListener("click", async () => {
    if (!chatReady || uploading || sending) return;
    if (!setBottomTab("chat")) return;
    $("chats-dialog").close();
    try { const conversation = await api("/api/conversations", {}); switchConversation(conversation.id); await refreshList(); render(conversation); $("message").focus(); }
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
    if (!chatReady) return;
    try { await api("/api/cancel", { conversation_id: current }); $("notice").textContent = "Stopping this reply…"; }
    catch (error) { $("notice").textContent = error.message; }
  });
  const voice = new BobVoice({
    api,
    onState(text, phase) {
      $("call-status").textContent = text;
      $("call-dialog").dataset.phase = phase;
      $("live-call").classList.toggle("call-active", voice.active);
      $("live-call").setAttribute("aria-pressed", String(voice.active));
      $("live-call").setAttribute("aria-label", voice.active ? "Hang up voice call" : "Start live voice call");
      // WebKit can drop a pending click if its text node is replaced between
      // press and release. Streaming state updates must keep this label stable.
      const endLabel = voice.active ? "Hang up" : "Back to chat";
      if ($("end-call").textContent !== endLabel) $("end-call").textContent = endLabel;
      $("resume-call").hidden = phase !== "paused";
      $("retry-voice-save").hidden = phase !== "unsaved";
      $("call-hint").textContent = voice.active ? "Your transcript saves to this chat." : "Choose Back to chat, then use the waveform button to call again.";
    },
    onTranscript(entries) {
      const rows = entries.filter(e => e.content.trim()).map(entry => {
        const row = document.createElement("p");
        row.className = entry.role === "user" ? "call-you" : "call-bob";
        row.textContent = (entry.role === "user" ? "You: " : "Bob: ") + entry.content + (entry.interrupted ? " [interrupted]" : "");
        return row;
      });
      $("call-transcript").replaceChildren(...rows);
      $("call-transcript").scrollTop = $("call-transcript").scrollHeight;
    },
    onSaved() { revision = ""; },
  });
  $("live-call").addEventListener("click", () => {
    if (voice.active) { voice.stop(); return; }
    if (!chatReady || busy || sending || !current) { $("notice").textContent = "Wait for chat to load and Bob’s reply to finish before starting a call."; return; }
    if (micRecognition) { micRecognition.abort(); micRecognition = null; $("mic").classList.remove("mic-active"); $("mic").setAttribute("aria-pressed", "false"); }
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    $("call-transcript").replaceChildren();
    $("call-dialog").showModal();
    voice.start(current);
  });
  $("end-call").addEventListener("click", () => {
    if (voice.active) voice.stop();
    else $("call-dialog").close();
  });
  $("resume-call").addEventListener("click", () => voice.resume());
  $("retry-voice-save").addEventListener("click", () => voice.retrySave());
  $("call-dialog").addEventListener("close", () => voice.stop());
  window.addEventListener("pagehide", () => voice.stop());
  window.addEventListener("offline", () => voice.stop("Connection lost. Your transcript will save when you reconnect."));
  window.addEventListener("online", () => voice.retrySave());
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && voice.active) voice.stop("Call ended when you left this page. Tap the waveform to call again.");
  });
  window.addEventListener("beforeunload", event => {
    if (voice.pending.length) { event.preventDefault(); event.returnValue = ""; }
  });
  $("logout").addEventListener("click", async () => {
    $("settings-notice").textContent = "";
    try { await voice.stop(); await api("/api/logout", {}); location.assign("/login"); }
    catch (_) { $("settings-notice").textContent = "Could not log out. Please try again."; }
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
      budget: "Spending limit reached", refill_required: "Gemini funding needs attention", not_installed: "Not set up", session_unavailable: "Could not reopen the conversation",
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
    const dispatch = data.dispatch;
    const waiting = Number.isInteger(dispatch?.queued) && dispatch.queued > 0
      ? ` ${dispatch.queued} ${dispatch.queued === 1 ? 'job is' : 'jobs are'} waiting.` : '';
    const dispatchMessage = dispatch?.mode === 'solo'
      ? 'Solo mode: additional workers and council are paused.'
      : dispatch?.paused ? 'Automatic dispatch is paused.' : '';
    $("jobs-dispatch").textContent = dispatchMessage + waiting;
    $("jobs-dispatch").hidden = !(dispatchMessage || waiting);
    const teammates = $('teammate-cards');
    if (teammates) {
      teammates.replaceChildren();
      for (const row of data.teammates || []) {
        const card = jobElement('article', 'job-card');
        card.append(jobElement('h4', 'job-task', row.name), jobElement('p', '', row.summary));
        if (row.source) card.append(jobElement('p', 'muted', 'Source: ' + row.source + (row.modified_at ? ' · saved ' + new Date(row.modified_at * 1000).toLocaleString() : '')));
        teammates.append(card);
      }
    }
    const reminders = $("reminder-cards");
    if (reminders) {
      reminders.replaceChildren();
      const rows = (data.reminders || []).filter(r => r.state !== 'cancelled').slice(0, 20);
      for (const row of rows) {
        const card = jobElement('article', 'job-card');
        card.append(jobElement('p', 'job-task', row.body));
        const when = new Date(row.due_at * 1000).toLocaleString();
        card.append(jobElement('p', 'muted', `${row.state === 'fired' ? 'Delivered' : 'Due'} ${when}${row.interval_seconds ? ' · Repeating' : ''}`));
        const open = jobElement('button', 'job-result-link', 'Open reminder chat');
        open.type = 'button';
        open.addEventListener('click', () => { if (setBottomTab('chat')) { $('conversations').value = row.conversation_id; $('conversations').dispatchEvent(new Event('change')); } });
        card.append(open);
        reminders.append(card);
      }
      if (!rows.length) reminders.append(jobElement('p', 'muted', 'No reminders yet.'));
    }
    const rows = uniqueJobs(data.working);
    const complete = data.inspection?.screens_available && data.inspection?.processes_available && data.inspection?.queue_available;
    $("working-count").hidden = !rows.length;
    $("working-count").textContent = String(rows.length);
    $("jobs-notice").hidden = complete;
    $("jobs-notice").textContent = complete ? "" : "Some live activity could not be checked. Retrying…";
    $("jobs-empty").hidden = rows.length > 0 || !complete;
    $("live-jobs").replaceChildren(...rows.map((job) => {
      const card = jobElement("article", "job-card");
      const top = jobElement("div", "job-card-top");
      const stateLabel = ({ running: "Live", paused: "Paused", unverified: "Session open", claimed: "Unconfirmed" })[job.state] || "Unconfirmed";
      const status = jobElement("span", `job-state ${job.state === "running" ? "is-live" : ""}`, stateLabel);
      const dot = jobElement("span", "job-dot");
      dot.setAttribute("aria-hidden", "true");
      status.prepend(dot);
      top.append(status);
      if (Number.isFinite(job.elapsed_seconds)) top.append(jobElement("span", "job-elapsed", jobDuration(job.elapsed_seconds)));
      card.append(top);
      const models = (job.models || []).filter((model) => model && model !== "Model not reported");
      if (models.length) {
        const llmRow = jobElement("div", "job-llm-row");
        models.forEach((model) => llmRow.append(jobElement("span", "job-llm", model)));
        card.append(llmRow);
      }
      if (job.project !== "Project not specified") card.append(jobElement("p", "job-project", job.project));
      card.append(jobElement("h3", "job-task", job.task));
      if (job.state === "unverified" || job.state === "claimed") {
        card.append(jobElement("p", "job-unconfirmed muted", "Worker activity is not confirmed."));
      }
      return card;
    }));
    const finished = data.inspection?.queue_available ? uniqueJobs(data.recently_finished).slice(0, 5) : [];
    $("finished-empty").hidden = finished.length > 0;
    $("finished-empty").textContent = data.inspection?.queue_available ? "No finished jobs yet." : "Finished jobs could not be checked.";
    $("finished-jobs").replaceChildren(...finished.map((job) => {
      const card = jobElement("article", "finished-job job-card");
      const top = jobElement("div", "job-card-top");
      top.append(jobElement("span", `job-outcome ${job.state === "failed" ? "is-failed" : ""}`,
        job.state === "done" ? "Finished" : job.state === "failed" ? "Failed" : job.state === "unverified" ? "Outcome unverified" : "Stopped"));
      if (Number.isFinite(job.finished_at)) top.append(jobElement("span", "job-elapsed muted", jobAge(data.checked_at - job.finished_at)));
      else if (Number.isFinite(job.last_activity_at)) top.append(jobElement("span", "job-elapsed muted", 'Last activity ' + jobAge(data.checked_at - job.last_activity_at)));
      card.append(top);
      card.append(jobElement("p", "job-project", job.project));
      card.append(jobElement("p", "finished-task", job.task));
      const footer = jobElement("div", "finished-footer");
      if (job.result_url?.startsWith("/api/jobs/result?")) {
        const result = jobElement("button", "job-result-link", "View result");
        result.type = "button";
        result.dataset.resultUrl = job.result_url;
        result.setAttribute("aria-label", `View result for ${job.project}: ${job.task}`);
        result.addEventListener("click", () => showJobResult(job.result_url, job.project, job.task, result));
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
    $("jobs-dispatch").textContent = '';
    $("jobs-dispatch").hidden = true;
    $("jobs-notice").hidden = false;
    $("jobs-notice").textContent = "Live work is unavailable. Retrying…";
    $("jobs-empty").hidden = true;
    $("finished-empty").hidden = true;
    $("working-count").hidden = true;
    $("teammate-cards")?.replaceChildren(jobElement("p", "muted", "Teammate status unavailable."));
    $("reminder-cards")?.replaceChildren(jobElement("p", "muted", "Reminder list unavailable."));
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
      const needsAction = ["not_logged_in", "not_installed", "budget", "refill_required"].includes(model.reason) && model.state !== "ready";
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
  function connectionRestored() {
    pollFailures = 0;
    $("connection").textContent = "Connected to Bob";
    const dot = $("status-dot");
    if (dot) {
      dot.classList.remove("warn");
      dot.classList.add("connected");
      dot.setAttribute("aria-label", "Connected");
    }
    $("offline-banner")?.setAttribute("hidden", "");
  }
  const STARTUP_RETRY_MESSAGE = "Cannot connect to Bob yet. Retrying shortly…";
  async function connectChat(force = false) {
    if (chatReady || connecting || authRedirecting || (!force && Date.now() < connectAfter)) return;
    connecting = true;
    try {
      // Retry only bounded reads. Do not enable mutations with a remembered
      // conversation ID until its current server history has actually loaded.
      csrf = (await api("/api/session")).csrf;
      await refreshList();
      const conversation = await api(`/api/conversations/${current}`);
      if (conversation.id !== current) throw new Error("Conversation changed while connecting");
      chatReady = true;
      connectFailures = 0;
      connectAfter = 0;
      if ($("notice").textContent === STARTUP_RETRY_MESSAGE) $("notice").textContent = "";
      render(conversation);
      connectionRestored();
      $("messages").scrollTop = $("messages").scrollHeight;
      void Promise.allSettled([refreshJobs(), refreshOverview()]);
    } catch (_) {
      chatReady = false;
      if (!authRedirecting) {
        connectFailures += 1;
        connectAfter = Date.now() + Math.min(30000, 5000 * 2 ** Math.min(connectFailures - 1, 3));
        $("notice").textContent = STARTUP_RETRY_MESSAGE;
        $("connection").textContent = "Reconnecting to Bob";
        $("offline-banner")?.removeAttribute("hidden");
        const dot = $("status-dot");
        if (dot) { dot.classList.add("warn"); dot.setAttribute("aria-label", "Reconnecting"); }
      }
    } finally { connecting = false; composerState(); }
  }
  function refreshAfterReconnect() {
    if (document.hidden || authRedirecting) return;
    if (!chatReady) { void connectChat(true); return; }
    if (Date.now() - overviewFetchedAt > 30000) clearOverview();
    if (Date.now() - jobsFetchedAt > 30000) clearJobs();
    refreshJobs(); refreshOverview(); poll();
  }
  function init() {
    try {
      primeSpeechVoices();
      const recognition = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
      $("mic").hidden = !recognition;
      // Live audio uses getUserMedia + Web Audio; it does not require either
      // browser dictation or device read-aloud support.
      $("live-call").hidden = false;
      $("speak").hidden = !("speechSynthesis" in window);
      $("voice-status").textContent = (recognition ? "Tap the microphone to dictate. " : "Use your keyboard’s microphone to dictate. ")
        + "Tap the waveform to talk with Bob in an AI voice. Interrupt anytime, then tap Hang up. Your transcript saves to this chat. Keep this page open during the call.";
      const preference = stored("bob.provider");
      if ([...$("provider-choice").options].some((option) => option.value === preference)) $("provider-choice").value = preference;
      current = stored("bob.conversation");
      // Install once, before the first network read. A failed bootstrap must
      // leave its own recovery path alive, without adding timers on retries.
      setInterval(() => { if (chatReady && !authRedirecting && !document.hidden) { refreshJobs(); refreshOverview(); } }, 8000);
      setInterval(() => { if (!document.hidden) { if (chatReady) poll(); else void connectChat(); } }, 1200);
      setInterval(() => { if (overviewFetchedAt && Date.now() - overviewFetchedAt > 30000) clearOverview(); if (jobsFetchedAt && Date.now() - jobsFetchedAt > 30000) clearJobs(); }, 1000);
      document.addEventListener("visibilitychange", refreshAfterReconnect);
      window.addEventListener("online", refreshAfterReconnect);
      void connectChat();
    } catch (error) { $("notice").textContent = error.message; }
  }
  composerState(); init();
}

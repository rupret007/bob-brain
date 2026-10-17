"use strict";

const ActionHistory = (() => {
  const MAX_ENTRIES = 50;
  const ACTION_PROVIDERS = new Set(["local-tasks", "calendar", "reminders"]);
  const OUTCOME_KEYS = ["outcome", "status", "state", "delivery_state"];

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatPrimitive(value) {
    if (value == null) return "";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function formatReceiptPayload(value) {
    if (value == null) return "";
    if (typeof value === "string") return value;
    if (typeof value !== "object") return formatPrimitive(value);
    const lines = [];
    for (const [key, val] of Object.entries(value)) {
      if (key === "kind" && val === "action.receipt") continue;
      lines.push(`${key}: ${formatPrimitive(val)}`);
    }
    return lines.join("\n");
  }

  function isoFromUnix(seconds) {
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) return null;
    try {
      return new Date(seconds * 1000).toISOString();
    } catch (_) {
      return null;
    }
  }

  function timestampSortKey(timestamp, createdAt) {
    if (typeof timestamp === "string" && timestamp) {
      const parsed = Date.parse(timestamp);
      if (Number.isFinite(parsed)) return parsed;
    }
    if (typeof createdAt === "number" && Number.isFinite(createdAt)) return createdAt * 1000;
    return 0;
  }

  function structuredOutcomeFromReceipt(receipt) {
    if (receipt == null) return null;
    if (typeof receipt === "object" && !Array.isArray(receipt)) {
      for (const key of OUTCOME_KEYS) {
        if (receipt[key] != null && receipt[key] !== "") return String(receipt[key]);
      }
      return null;
    }
    return null;
  }

  function structuredOutcome(actionReceipt) {
    if (actionReceipt.outcome != null && actionReceipt.outcome !== "") {
      return String(actionReceipt.outcome);
    }
    const fromReceipt = structuredOutcomeFromReceipt(actionReceipt.receipt);
    if (fromReceipt != null) return fromReceipt;
    if (typeof actionReceipt.receipt === "object" && actionReceipt.receipt) return null;
    return null;
  }

  function entryBase(message, fields) {
    return {
      sourceMessageId: fields.sourceMessageId || message.id || "",
      provider: fields.provider || "unknown",
      type: fields.type || "action",
      timestamp: fields.timestamp ?? null,
      outcomeLabel: fields.outcomeLabel ?? null,
      receiptBody: fields.receiptBody || "",
      sortKey: timestampSortKey(fields.timestamp, message.created_at),
      messageStatus: message.status,
    };
  }

  function entryFromStructured(message, actionReceipt) {
    const provider = actionReceipt.provider || message.provider || "unknown";
    const type = actionReceipt.type || (actionReceipt.kind === "action.receipt" ? "action" : actionReceipt.kind) || "action";
    const timestamp = actionReceipt.timestamp ?? isoFromUnix(message.created_at);
    const bodySource = actionReceipt.receipt != null ? actionReceipt.receipt : actionReceipt;
    return entryBase(message, {
      sourceMessageId: actionReceipt.sourceMessageId || message.id,
      provider,
      type,
      timestamp,
      outcomeLabel: structuredOutcome(actionReceipt),
      receiptBody: formatReceiptPayload(bodySource),
    });
  }

  function entryFromTexting(message, textingReceipt) {
    const timestamp = textingReceipt.timestamp ?? isoFromUnix(message.created_at);
    let outcomeLabel = null;
    if (textingReceipt.outcome != null && textingReceipt.outcome !== "") {
      outcomeLabel = String(textingReceipt.outcome);
    } else {
      outcomeLabel = structuredOutcomeFromReceipt(textingReceipt.receipt ?? textingReceipt);
    }
    return entryBase(message, {
      sourceMessageId: textingReceipt.sourceMessageId || message.id,
      provider: "texting",
      type: textingReceipt.type || "text.send",
      timestamp,
      outcomeLabel,
      receiptBody: formatReceiptPayload(textingReceipt.receipt ?? textingReceipt),
    });
  }

  function entryFromProvider(message) {
    return entryBase(message, {
      sourceMessageId: message.id,
      provider: message.provider,
      type: message.action_type || "reply",
      timestamp: isoFromUnix(message.created_at),
      outcomeLabel: null,
      receiptBody: typeof message.content === "string" ? message.content : "",
    });
  }

  function extractActionReceipts(messages) {
    if (!Array.isArray(messages)) return { entries: [], total: 0 };
    const collected = [];
    for (const message of messages) {
      if (message.role !== "assistant") continue;
      if (["queued", "running"].includes(message.status)) continue;
      if (message.action_receipt) {
        collected.push(entryFromStructured(message, message.action_receipt));
        continue;
      }
      if (message.texting_receipt) {
        collected.push(entryFromTexting(message, message.texting_receipt));
        continue;
      }
      if (message.provider && ACTION_PROVIDERS.has(message.provider)) {
        collected.push(entryFromProvider(message));
      }
    }
    collected.sort((a, b) => b.sortKey - a.sortKey);
    const total = collected.length;
    return { entries: collected.slice(0, MAX_ENTRIES), total };
  }

  function formatTimestamp(timestamp) {
    if (timestamp == null || timestamp === "") return "—";
    return String(timestamp);
  }

  function outcomeLine(entry) {
    if (entry.outcomeLabel == null || entry.outcomeLabel === "") return "Outcome: unknown";
    return `Outcome: ${entry.outcomeLabel}`;
  }

  function renderEntry(entry, index) {
    const article = document.createElement("article");
    article.className = "action-history-entry";
    article.dataset.entryIndex = String(index);
    const meta = document.createElement("dl");
    meta.className = "action-history-meta";
    const addRow = (label, value) => {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      meta.append(dt, dd);
    };
    addRow("provider", entry.provider);
    addRow("type", entry.type);
    addRow("timestamp", formatTimestamp(entry.timestamp));
    article.append(meta);
    const outcome = document.createElement("p");
    outcome.className = "action-history-outcome";
    outcome.textContent = outcomeLine(entry);
    article.append(outcome);
    const body = document.createElement("pre");
    body.className = "receipt-body";
    body.textContent = entry.receiptBody;
    article.append(body);
    if (entry.sourceMessageId) {
      const jump = document.createElement("button");
      jump.type = "button";
      jump.className = "action-history-jump";
      jump.textContent = "Jump to message";
      jump.dataset.messageId = entry.sourceMessageId;
      article.append(jump);
    }
    return article;
  }

  function jumpToMessage(messageId, messagesRoot) {
    const root = messagesRoot || document.getElementById("messages");
    if (!root || !messageId) return false;
    let target = null;
    for (const node of root.querySelectorAll("[data-message-id]")) {
      if (node.dataset.messageId === messageId) {
        target = node;
        break;
      }
    }
    if (!target) return false;
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    target.classList.add("message-highlight");
    window.setTimeout(() => target.classList.remove("message-highlight"), 450);
    return true;
  }

  function focusJumpAt(entries, index) {
    const links = [...entries.querySelectorAll(".action-history-jump")];
    if (!links.length) return;
    const clamped = Math.max(0, Math.min(index, links.length - 1));
    links[clamped].focus();
    return clamped;
  }

  function handleListKeydown(event, list) {
    const links = [...list.querySelectorAll(".action-history-jump")];
    if (!links.length) return;
    const active = document.activeElement;
    let index = links.indexOf(active);
    if (index < 0) index = 0;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusJumpAt(list, index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusJumpAt(list, index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusJumpAt(list, 0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusJumpAt(list, links.length - 1);
    } else if ((event.key === "Enter" || event.key === " ") && active?.classList.contains("action-history-jump")) {
      event.preventDefault();
      jumpToMessage(active.dataset.messageId);
    }
  }

  function updatePanel(conversation) {
    const panel = document.getElementById("action-history");
    const body = document.getElementById("action-history-body");
    const count = document.getElementById("action-history-count");
    if (!panel || !body || !count) return;
    const { entries, total } = extractActionReceipts(conversation?.messages || []);
    body.replaceChildren();
    count.textContent = total ? `${entries.length} of ${total}` : "0";
    if (!total) {
      const empty = document.createElement("p");
      empty.className = "action-history-empty muted";
      empty.textContent = "No receipts in this chat.";
      body.append(empty);
      return;
    }
    const list = document.createElement("div");
    list.className = "action-history-list";
    list.setAttribute("role", "list");
    entries.forEach((entry, index) => list.append(renderEntry(entry, index)));
    body.append(list);
    if (!body.dataset.keysBound) {
      body.dataset.keysBound = "1";
      body.addEventListener("keydown", (event) => {
        const currentList = body.querySelector(".action-history-list");
        if (currentList) handleListKeydown(event, currentList);
      });
      body.addEventListener("click", (event) => {
        const jump = event.target.closest(".action-history-jump");
        if (!jump) return;
        jumpToMessage(jump.dataset.messageId);
      });
    }
  }

  function mount() {
    const panel = document.getElementById("action-history");
    if (!panel || panel.dataset.mounted) return;
    panel.dataset.mounted = "1";
    panel.hidden = false;
  }

  return {
    MAX_ENTRIES,
    escapeHtml,
    extractActionReceipts,
    formatReceiptPayload,
    outcomeLine,
    jumpToMessage,
    handleListKeydown,
    focusJumpAt,
    updatePanel,
    mount,
  };
})();

if (typeof window !== "undefined") window.ActionHistory = ActionHistory;
if (typeof module !== "undefined") module.exports = ActionHistory;

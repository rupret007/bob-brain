"use strict";

const AttachmentReminder = (() => {
  const SELECTION_CHAR_CAP = 2000;
  const SCHEDULE_EXAMPLES = "2026-10-15 08:00 or 10/15/2026 8:00";

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizePreview(preview) {
    if (!preview || typeof preview !== "object") return null;
    return preview;
  }

  function isOwned(preview, conversationId) {
    const row = normalizePreview(preview);
    if (!row || !conversationId) return false;
    return row.conversation_id === conversationId;
  }

  function pageEntry(preview, pageNumber) {
    const pages = preview?.pages;
    if (!Array.isArray(pages)) return null;
    return pages.find((row) => row.page === pageNumber) || null;
  }

  function pageIsSelectable(page) {
    if (!page) return false;
    if (page.status === "image_only" || page.status === "unavailable" || page.status === "empty") return false;
    return Boolean(String(page.text || "").trim());
  }

  function voiceTranscriptUnavailable(preview) {
    if (!preview || preview.kind !== "voice") return false;
    if (preview.transcript_unavailable) return true;
    const segments = preview.segments;
    if (!Array.isArray(segments) || !segments.length) return true;
    return !segments.some((seg) => seg.available && String(seg.text || "").trim());
  }

  function coverageNoteForPreview(preview, pageNumber) {
    if (!preview) return "unconfirmed — could not verify";
    if (preview.kind === "voice") {
      if (voiceTranscriptUnavailable(preview)) return "voice transcription unavailable";
      return preview.coverage_note || "voice transcript";
    }
    const page = pageEntry(preview, pageNumber);
    if (page?.status === "image_only") return "image-only — text unavailable";
    if (page?.status === "unavailable") return preview.coverage_note || "text unavailable";
    if (page?.status === "empty") return preview.coverage_note || "page has no readable text";
    return preview.coverage_note || "page text, fully available";
  }

  function capSelection(text, cap = SELECTION_CHAR_CAP) {
    const raw = String(text || "");
    if (raw.length <= cap) return { text: raw, truncated: false, dropped: 0 };
    return { text: raw.slice(0, cap), truncated: true, dropped: raw.length - cap };
  }

  function selectionExtendsPastVoiceCoverage(selectedText, preview) {
    if (!preview || preview.kind !== "voice" || !Array.isArray(preview.segments)) return false;
    const available = preview.segments.filter((seg) => seg.available).map((seg) => seg.text || "").join(" ");
    if (!available.trim()) return false;
    const sel = String(selectedText || "");
    if (!sel.trim()) return false;
    const unavailableChunks = preview.segments.filter((seg) => !seg.available).map((seg) => seg.text || "").filter(Boolean);
    for (const chunk of unavailableChunks) {
      if (chunk && sel.includes(chunk)) return true;
    }
    if (sel.length > available.length && available && sel.includes(available.slice(-20))) {
      const beyond = sel.replace(available, "").trim();
      if (beyond) return true;
    }
    if (preview.coverage_clipped_hint) return true;
    return Boolean(preview.selection_past_coverage);
  }

  function analyzeSelection({ preview, pageNumber, selectedText }) {
    const capped = capSelection(selectedText);
    const clippedCoverage = selectionExtendsPastVoiceCoverage(selectedText, preview);
    return {
      body: capped.text,
      truncated: capped.truncated,
      dropped: capped.dropped,
      clippedCoverage,
      coverageNote: coverageNoteForPreview(preview, pageNumber),
    };
  }

  function canOfferReminderAction({ preview, conversationId, pageNumber, selectedText }) {
    if (!normalizePreview(preview)) {
      return { allowed: false, reason: "unconfirmed", tooltip: "unconfirmed — could not verify" };
    }
    if (!isOwned(preview, conversationId)) {
      return { allowed: false, reason: "wrong_conversation", tooltip: "attachment belongs to another conversation" };
    }
    if (preview.kind === "voice" && voiceTranscriptUnavailable(preview)) {
      return { allowed: false, reason: "transcript_unavailable", tooltip: "voice transcription unavailable" };
    }
    const page = pageEntry(preview, pageNumber);
    if (preview.kind === "pdf" || preview.kind === "text") {
      if (page && !pageIsSelectable(page)) {
        return { allowed: false, reason: "no_text", tooltip: "no selectable text on this page" };
      }
    }
    const hasSelection = Boolean(String(selectedText || "").trim());
    if (!hasSelection && preview.kind !== "pdf" && preview.kind !== "text") {
      return { allowed: false, reason: "no_selection", tooltip: "Select text in the excerpt first" };
    }
    if (!hasSelection && page && !pageIsSelectable(page)) {
      return { allowed: false, reason: "no_text", tooltip: "no selectable text on this page" };
    }
    return { allowed: true, reason: "ok", tooltip: "Add selected excerpt to a reminder draft" };
  }

  function validateScheduleInput(raw) {
    const value = String(raw || "").trim();
    if (!value) return { ok: false, error: "Enter explicit date and time." };
    if (/\b(tomorrow|tonight|next\s+\w+|in\s+\d+\s+(minute|hour|day|week)s?)\b/i.test(value)) {
      return { ok: false, error: "Enter explicit date and time." };
    }
    const explicit = /^\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}/.test(value)
      || /^\d{1,2}\/\d{1,2}\/\d{4} \d{1,2}:\d{2}/.test(value);
    if (!explicit) return { ok: false, error: "Enter explicit date and time." };
    return { ok: true, value };
  }

  function buildComposerDraft(body, schedule) {
    const trimmedBody = String(body || "").trim();
    const trimmedSchedule = String(schedule || "").trim();
    return `Create a reminder for ${trimmedSchedule} to ${trimmedBody}`;
  }

  function receiptIdentity(preview, pageNumber, selectionId) {
    return {
      attachment: preview?.filename || preview?.media_id || "attachment",
      page: pageNumber ?? null,
      selection_id: selectionId || "",
      source: "attachment-excerpt",
    };
  }

  let dialogState = null;

  function getDialogElements() {
    const dialog = document.getElementById("attachment-reminder-dialog");
    if (!dialog) return null;
    return {
      dialog,
      filename: document.getElementById("attachment-reminder-filename"),
      page: document.getElementById("attachment-reminder-page"),
      coverage: document.getElementById("attachment-reminder-coverage"),
      clipped: document.getElementById("attachment-reminder-clipped"),
      truncated: document.getElementById("attachment-reminder-truncated"),
      body: document.getElementById("attachment-reminder-body"),
      schedule: document.getElementById("attachment-reminder-schedule"),
      scheduleError: document.getElementById("attachment-reminder-schedule-error"),
      ownership: document.getElementById("attachment-reminder-ownership"),
      insert: document.getElementById("attachment-reminder-insert"),
      receipt: document.getElementById("attachment-reminder-receipt"),
    };
  }

  function closeDialog() {
    const ui = getDialogElements();
    dialogState = null;
    if (ui?.dialog?.open) ui.dialog.close();
  }

  function refreshDialogValidation() {
    const ui = getDialogElements();
    if (!ui || !dialogState) return;
    const schedule = validateScheduleInput(ui.schedule.value);
    ui.scheduleError.textContent = schedule.ok ? "" : schedule.error;
    const bodyOk = Boolean(ui.body.value.trim());
    const owned = isOwned(dialogState.preview, dialogState.conversationId);
    ui.ownership.hidden = owned;
    ui.insert.disabled = !owned || !bodyOk || !schedule.ok;
  }

  function openReminderDialog(options) {
    const preview = normalizePreview(options?.preview);
    const conversationId = options?.conversationId || "";
    const pageNumber = options?.pageNumber ?? null;
    const selectedText = options?.selectedText || "";
    const selectionId = options?.selectionId || "";
    const insertIntoComposer = options?.insertIntoComposer;
    if (!preview || typeof insertIntoComposer !== "function") return { ok: false, reason: "unconfirmed" };

    const gate = canOfferReminderAction({ preview, conversationId, pageNumber, selectedText });
    const analysis = analyzeSelection({ preview, pageNumber, selectedText });
    const ui = getDialogElements();
    if (!ui) return { ok: false, reason: "ui_missing" };

    dialogState = {
      preview,
      conversationId,
      pageNumber,
      selectionId,
      insertIntoComposer,
      gate,
      analysis,
    };

    ui.filename.textContent = preview.filename || preview.media_id || "attachment";
    ui.page.textContent = pageNumber != null ? `p.${pageNumber}` : "";
    ui.page.hidden = pageNumber == null;
    ui.coverage.textContent = analysis.coverageNote;
    ui.clipped.hidden = !analysis.clippedCoverage;
    ui.clipped.textContent = analysis.clippedCoverage ? "clipped — review before scheduling" : "";
    ui.truncated.hidden = !analysis.truncated;
    ui.truncated.textContent = analysis.truncated
      ? `truncated to ${SELECTION_CHAR_CAP} chars; remainder dropped (${analysis.dropped} dropped)`
      : "";
    ui.body.value = analysis.body;
    ui.schedule.value = "";
    ui.scheduleError.textContent = "";
    ui.receipt.textContent = JSON.stringify(receiptIdentity(preview, pageNumber, selectionId));
    ui.ownership.hidden = isOwned(preview, conversationId);
    ui.ownership.textContent = "attachment belongs to another conversation";
    ui.insert.disabled = true;
    if (!gate.allowed && gate.reason === "no_text") {
      ui.body.value = "";
    }
    if (!ui.dialog.open) ui.dialog.showModal();
    refreshDialogValidation();
    return { ok: true };
  }

  function handleInsertClick() {
    const ui = getDialogElements();
    if (!ui || !dialogState) return { ok: false };
    const schedule = validateScheduleInput(ui.schedule.value);
    if (!schedule.ok) {
      ui.scheduleError.textContent = schedule.error;
      return { ok: false, reason: "schedule" };
    }
    if (!isOwned(dialogState.preview, dialogState.conversationId)) return { ok: false, reason: "ownership" };
    const body = ui.body.value.trim();
    if (!body) return { ok: false, reason: "body" };
    const draft = buildComposerDraft(body, schedule.value);
    dialogState.insertIntoComposer(draft);
    closeDialog();
    return { ok: true, draft };
  }

  function mount() {
    const ui = getDialogElements();
    if (!ui || ui.dialog.dataset.mounted) return;
    ui.dialog.dataset.mounted = "1";
    ui.body.addEventListener("input", refreshDialogValidation);
    ui.schedule.addEventListener("input", refreshDialogValidation);
    ui.insert.addEventListener("click", (event) => {
      event.preventDefault();
      handleInsertClick();
    });
    document.getElementById("attachment-reminder-cancel")?.addEventListener("click", (event) => {
      event.preventDefault();
      closeDialog();
    });
    ui.dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      closeDialog();
    });
  }

  function updatePreviewAction({ button, preview, conversationId, pageNumber, selectedText }) {
    if (!button) return;
    const gate = canOfferReminderAction({ preview, conversationId, pageNumber, selectedText });
    button.disabled = !gate.allowed;
    button.title = gate.tooltip || "";
    button.setAttribute("aria-disabled", gate.allowed ? "false" : "true");
  }

  return {
    SELECTION_CHAR_CAP,
    SCHEDULE_EXAMPLES,
    escapeHtml,
    normalizePreview,
    isOwned,
    pageEntry,
    pageIsSelectable,
    voiceTranscriptUnavailable,
    coverageNoteForPreview,
    capSelection,
    analyzeSelection,
    canOfferReminderAction,
    validateScheduleInput,
    buildComposerDraft,
    receiptIdentity,
    openReminderDialog,
    closeDialog,
    handleInsertClick,
    mount,
    updatePreviewAction,
  };
})();

if (typeof window !== "undefined") window.AttachmentReminder = AttachmentReminder;
if (typeof module !== "undefined") module.exports = AttachmentReminder;

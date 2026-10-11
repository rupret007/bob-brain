"use strict";
// Expandable plan checklist: projects dispatch_intent plan/subtask data and
// recorded job identifiers (from the conversation and /api/jobs/activity)
// into a read-only checklist. Never infers completion from titles or wording;
// every "completed"/"failed" row must carry an exact recorded job id.
(function (global) {
  const STALE_SECONDS = 180;

  const STATUS_MAP = {
    succeeded: "completed", done: "completed", blocked: "failed", failed: "failed",
    cancelled: "cancelled", canceled: "cancelled", queued: "queued", claimed: "claimed",
    running: "running", paused: "paused", unverified: "unknown",
  };

  function normalizeStatus(raw) {
    if (!raw) return "unknown";
    return STATUS_MAP[raw] || String(raw);
  }

  function cleanText(value, fallback) {
    const text = (value == null ? "" : String(value)).trim();
    return text || fallback;
  }

  function stepTitle(entry, index) {
    if (entry && typeof entry === "object") {
      const text = cleanText(entry.title || entry.prompt, "");
      if (text) return text.split("\n")[0].slice(0, 160);
    }
    return "Step " + (index + 1);
  }

  function planIntent(message) {
    if (!message || typeof message !== "object") return null;
    if (message.dispatch_intent) return { intent: message.dispatch_intent, state: "active" };
    if (message.blocked_dispatch_intent) return { intent: message.blocked_dispatch_intent, state: "held" };
    if (message.cancelled_dispatch_intent) return { intent: message.cancelled_dispatch_intent, state: "cancelled" };
    return null;
  }

  // True only when nothing displayable can be built at all (no steps, no
  // goal/prompt text). A normal not-yet-dispatched plan still has text and
  // stays "proposed", not "unavailable".
  function lacksIdentity(intent) {
    if (!intent || typeof intent !== "object") return true;
    const hasSteps = Array.isArray(intent.subtasks) && intent.subtasks.length > 0;
    const hasText = Boolean(cleanText(intent.goal, "") || cleanText(intent.prompt, ""));
    return !hasSteps && !hasText;
  }

  function extractSteps(intent) {
    if (Array.isArray(intent.subtasks) && intent.subtasks.length) {
      return intent.subtasks.map((entry, index) => ({
        index,
        title: stepTitle(entry, index),
        worker: (entry && typeof entry === "object" && entry.worker) || intent.worker || null,
      }));
    }
    return [{ index: 0, title: stepTitle(intent, 0), worker: intent.worker || null }];
  }

  // Ids come only from the message's own recorded task_ids/task_id fields,
  // and only when their count matches the step count exactly. A mismatch
  // (corrupt/partial data) must never guess which id belongs to which step.
  function stepIds(message, steps) {
    if (Array.isArray(message.task_ids) && message.task_ids.length === steps.length) {
      return message.task_ids.map((id) => (typeof id === "string" && id ? id : null));
    }
    if (steps.length === 1 && typeof message.task_id === "string" && message.task_id) {
      return [message.task_id];
    }
    return steps.map(() => null);
  }

  function buildJobsIndex(jobsData) {
    const workingByKey = new Map();
    const finishedByKey = new Map();
    if (jobsData && Array.isArray(jobsData.working)) {
      for (const row of jobsData.working) if (row && typeof row.key === "string") workingByKey.set(row.key, row);
    }
    if (jobsData && Array.isArray(jobsData.recently_finished)) {
      for (const row of jobsData.recently_finished) if (row && typeof row.key === "string") finishedByKey.set(row.key, row);
    }
    const checkedAt = jobsData && typeof jobsData.checked_at === "number" ? jobsData.checked_at : null;
    return { workingByKey, finishedByKey, checkedAt };
  }

  function latestTimestamp(source, keys) {
    let best = null;
    for (const key of keys) {
      const value = source[key];
      if (typeof value === "number" && Number.isFinite(value) && (best === null || value > best)) best = value;
    }
    return best;
  }

  const TERMINAL = new Set(["completed", "failed", "cancelled"]);

  function resolveStep(conversation, planMessage, id, jobsIndex, now) {
    if (!id) return { status: "proposed", observedAt: null, stale: false, resultId: null };
    const messages = (conversation && conversation.messages) || [];
    // 1) A group-completion message carries the richest, exact-id terminal
    //    evidence (status + timestamps) for every member of a batch dispatch.
    if (planMessage.group_id) {
      const group = messages.find((m) => m && m.group_id === planMessage.group_id && Array.isArray(m.subtasks));
      if (group) {
        const entry = group.subtasks.find((s) => s && s.id === id);
        if (entry) {
          const status = normalizeStatus(entry.status);
          const observedAt = latestTimestamp(entry, ["finished_at", "execution_started_at", "started_at", "claimed_at"]);
          return { status, observedAt, stale: false, resultId: TERMINAL.has(status) ? id : null };
        }
      }
    }
    // 2) A single-task completion message (task_id + task_status) is the
    //    same kind of exact-id terminal evidence for a non-batch dispatch.
    const single = messages.find((m) => m && m.task_id === id && Object.prototype.hasOwnProperty.call(m, "task_status"));
    if (single) {
      const status = normalizeStatus(single.task_status);
      const observedAt = latestTimestamp(single, ["finished_at", "started_at", "claimed_at"]);
      return { status, observedAt, stale: false, resultId: TERMINAL.has(status) ? id : null };
    }
    // 3) The Jobs response can confirm a terminal outcome by the same exact
    //    id before the conversation message catches up (a benign race).
    const finished = jobsIndex.finishedByKey.get(id);
    if (finished) {
      const status = normalizeStatus(finished.state);
      const observedAt = typeof finished.finished_at === "number" ? finished.finished_at : jobsIndex.checkedAt;
      return { status, observedAt, stale: false, resultId: finished.result_url ? id : null };
    }
    const snapshotStale = jobsIndex.checkedAt != null && typeof now === "number" && (now - jobsIndex.checkedAt) > STALE_SECONDS;
    // 4) Interim (not yet terminal) status recorded directly on the dispatch
    //    message's action card, by exact id.
    let interim = null;
    const card = planMessage.action_card;
    if (card && Array.isArray(card.tasks)) {
      const entry = card.tasks.find((t) => t && t.id === id);
      if (entry) interim = normalizeStatus(entry.status);
    } else if (card && card.task_id === id) {
      interim = normalizeStatus(card.state);
    }
    const working = jobsIndex.workingByKey.get(id);
    if (interim) {
      // Claimed to be active. If a live Jobs snapshot exists and does not
      // show it, the observation has gone stale (not promoted or hidden).
      // No snapshot at all is "not recorded", never a fabricated staleness.
      const stale = working ? snapshotStale : jobsIndex.checkedAt != null;
      return { status: interim, observedAt: jobsIndex.checkedAt, stale, resultId: null };
    }
    if (working) {
      return { status: normalizeStatus(working.state), observedAt: jobsIndex.checkedAt, stale: snapshotStale, resultId: null };
    }
    return { status: "unknown", observedAt: jobsIndex.checkedAt, stale: jobsIndex.checkedAt != null, resultId: null };
  }

  function buildModel(conversation, message, jobsData, now) {
    const found = planIntent(message);
    if (!found) return null;
    const { intent, state } = found;
    if (lacksIdentity(intent)) {
      return { available: false, reason: "identifiers-absent", planMessageId: message.id || null };
    }
    const steps = extractSteps(intent);
    const goal = cleanText(intent.goal || intent.prompt, "this work");
    const effectiveNow = typeof now === "number" ? now : Date.now() / 1000;
    let rows;
    if (state === "held" || state === "cancelled") {
      const observedAt = typeof message.created_at === "number" ? message.created_at : null;
      rows = steps.map((step) => ({ ...step, id: null, status: state, observedAt, stale: false, resultId: null }));
    } else {
      const jobsIndex = buildJobsIndex(jobsData);
      const ids = stepIds(message, steps);
      rows = steps.map((step, index) => {
        const id = ids[index];
        const resolved = resolveStep(conversation, message, id, jobsIndex, effectiveNow);
        return { ...step, id, status: resolved.status, observedAt: resolved.observedAt, stale: resolved.stale, resultId: resolved.resultId };
      });
    }
    const counts = {};
    for (const row of rows) counts[row.status] = (counts[row.status] || 0) + 1;
    return {
      available: true,
      planMessageId: message.id || null,
      groupId: message.group_id || null,
      goal,
      state,
      note: state === "held" || state === "cancelled" ? cleanText(message.content, "") || null : null,
      steps: rows,
      counts,
    };
  }

  const STATUS_LABELS = {
    proposed: "Proposed", held: "Held", cancelled: "Cancelled", queued: "Queued",
    claimed: "Assigned (unconfirmed)", running: "Running", paused: "Paused",
    completed: "Completed", failed: "Failed", unknown: "Unknown",
  };

  function statusLabel(status) {
    return STATUS_LABELS[status] || "Unknown";
  }

  function formatObservedAt(seconds) {
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "not recorded";
    const date = new Date(seconds * 1000);
    if (Number.isNaN(date.getTime())) return "not recorded";
    return date.toISOString().replace("T", " ").slice(0, 16) + " UTC";
  }

  const SUMMARY_ORDER = ["completed", "failed", "cancelled", "held", "running", "paused", "claimed", "queued", "unknown", "proposed"];

  function summaryLine(counts) {
    const parts = [];
    for (const status of SUMMARY_ORDER) {
      if (counts[status]) parts.push(counts[status] + " " + statusLabel(status).toLowerCase());
    }
    return parts.length ? parts.join(", ") : "No steps recorded";
  }

  // Builds real DOM nodes using only textContent/dataset (never innerHTML),
  // so untrusted titles/ids can never execute as markup.
  function render(doc, model, options) {
    if (!model) return null;
    options = options || {};
    const openDetails = options.openDetails || new Set();
    const keyPrefix = options.keyPrefix || model.planMessageId || "plan";
    if (!model.available) {
      const node = doc.createElement("div");
      node.className = "plan-checklist plan-checklist-unavailable";
      node.textContent = "Plan checklist unavailable — identifiers absent.";
      return node;
    }
    const section = doc.createElement("section");
    section.className = "plan-checklist";
    const header = doc.createElement("div");
    header.className = "plan-checklist-header";
    header.textContent = "Plan: " + model.goal;
    section.appendChild(header);
    if (model.note) {
      const note = doc.createElement("div");
      note.className = "plan-checklist-note muted";
      note.textContent = model.note;
      section.appendChild(note);
    }
    const summary = doc.createElement("div");
    summary.className = "plan-checklist-summary muted";
    summary.textContent = summaryLine(model.counts);
    section.appendChild(summary);
    const list = doc.createElement("div");
    list.className = "plan-checklist-steps";
    for (const step of model.steps) {
      const detail = doc.createElement("details");
      detail.className = "disclosure card-details plan-step status-" + step.status + (step.stale ? " is-stale" : "");
      const key = keyPrefix + ":step:" + (step.id || step.index);
      detail.dataset.detailKey = key;
      detail.open = openDetails.has(key);
      const summaryEl = doc.createElement("summary");
      const badge = doc.createElement("span");
      badge.className = "plan-step-status";
      badge.textContent = statusLabel(step.status) + (step.stale ? " · stale" : "");
      summaryEl.appendChild(badge);
      const titleEl = doc.createElement("span");
      titleEl.className = "plan-step-title";
      titleEl.textContent = " " + step.title;
      summaryEl.appendChild(titleEl);
      detail.appendChild(summaryEl);
      const dl = doc.createElement("dl");
      const addRow = (label, value) => {
        const dt = doc.createElement("dt");
        dt.textContent = label;
        const dd = doc.createElement("dd");
        dd.textContent = value;
        dl.appendChild(dt);
        dl.appendChild(dd);
      };
      addRow("Job", step.id || "Not yet dispatched (proposed)");
      addRow("Observed", formatObservedAt(step.observedAt));
      if (step.worker) addRow("Worker", step.worker);
      detail.appendChild(dl);
      if (step.resultId) {
        const button = doc.createElement("button");
        button.type = "button";
        button.className = "job-result-link";
        button.textContent = "View result";
        button.dataset.jobId = step.resultId;
        detail.appendChild(button);
      }
      list.appendChild(detail);
    }
    section.appendChild(list);
    return section;
  }

  const PlanChecklist = {
    buildModel,
    render,
    STALE_SECONDS,
    _internal: { normalizeStatus, stepTitle, lacksIdentity, extractSteps, stepIds, resolveStep, summaryLine, statusLabel, formatObservedAt },
  };
  global.PlanChecklist = PlanChecklist;
})(typeof window !== "undefined" ? window : globalThis);

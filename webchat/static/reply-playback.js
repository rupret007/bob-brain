"use strict";

const ReplyPlayback = (() => {
  const CHAR_CAP = 4000;
  const PREVIEW_MAX = 80;
  const NO_START_MS = 10_000;

  function previewLabel(text) {
    const normalized = String(text || "").replace(/\s+/g, " ").trim();
    if (!normalized) return "";
    if (normalized.length <= PREVIEW_MAX) return normalized;
    return `${normalized.slice(0, PREVIEW_MAX - 1)}…`;
  }

  function buildUtteranceText(raw, speechTextFn) {
    const spoken = speechTextFn(String(raw || ""));
    if (!spoken) return { text: "", spokenLength: 0, truncated: false, empty: true };
    const truncated = spoken.length > CHAR_CAP;
    const text = truncated ? spoken.slice(0, CHAR_CAP) : spoken;
    return { text, spokenLength: spoken.length, truncated, empty: !text };
  }

  function capNotice(truncated) {
    if (truncated) return "Reading first 4,000 characters (4,000-character read-aloud cap).";
    return "Up to 4,000 characters per read-aloud.";
  }

  function unsupportedFallback() {
    return "Read-aloud is not supported in this browser. Copy the message or use keyboard dictation.";
  }

  function stateLabel(state) {
    switch (state) {
      case "preparing": return "Preparing read-aloud…";
      case "speaking": return "Speaking";
      case "stopped": return "Stopped";
      case "failed": return "Read-aloud failed";
      default: return "";
    }
  }

  function pickEnglishVoice(getVoices) {
    const voices = (getVoices?.() || []).filter((voice) => String(voice.lang || "").startsWith("en"));
    if (!voices.length) return null;
    return voices.find((voice) => /samantha|daniel|english/i.test(voice.name)) || voices[0];
  }

  function createController(deps = {}) {
    const speech = () => deps.speechSynthesis;
    const UtteranceCtor = () => deps.SpeechSynthesisUtterance || globalThis.SpeechSynthesisUtterance;
    let token = 0;
    let state = "idle";
    let active = null;
    let noStartTimer = null;
    let lastSource = null;

    function clearNoStartTimer() {
      if (noStartTimer != null) {
        deps.clearTimeout?.(noStartTimer);
        noStartTimer = null;
      }
    }

    let onView = deps.onView || null;

    function emit(extra = {}) {
      onView?.({
        state,
        messageId: active?.messageId ?? null,
        preview: active?.preview ?? "",
        capNotice: active?.capNotice ?? "",
        truncated: Boolean(active?.truncated),
        source: active?.source ?? lastSource,
        fallback: active?.fallback ?? "",
        speakingClaimed: state === "speaking",
        ...extra,
      });
    }

    function isStale(utterToken) {
      return utterToken !== token;
    }

    function teardownPlayback() {
      clearNoStartTimer();
      if (speech() && (state === "preparing" || state === "speaking")) speech().cancel();
    }

    function resetToIdle() {
      token += 1;
      clearNoStartTimer();
      active = null;
      lastSource = null;
      state = "idle";
      emit();
    }

    function stop() {
      if (state === "idle") return;
      teardownPlayback();
      token += 1;
      const meta = active;
      active = null;
      state = "stopped";
      emit({ ...meta, reason: "user_stop" });
      state = "idle";
      emit();
    }

    function onConversationChange() {
      if (state === "idle") return;
      teardownPlayback();
      token += 1;
      active = null;
      state = "idle";
      emit({ reason: "conversation_change" });
    }

    function onLogout() {
      teardownPlayback();
      token += 1;
      active = null;
      state = "idle";
      emit({ reason: "logout" });
    }

    async function start(request) {
      const {
        rawText,
        messageId = null,
        source = "message",
        enforceQuietHours = false,
      } = request || {};
      lastSource = source;
      if (!deps.hasSpeech?.()) {
        state = "failed";
        active = {
          messageId,
          preview: previewLabel(rawText),
          capNotice: "",
          truncated: false,
          source,
          fallback: unsupportedFallback(),
        };
        emit();
        state = "idle";
        active = null;
        emit();
        return { ok: false, reason: "unsupported" };
      }
      if (enforceQuietHours && deps.isQuietHours?.()) {
        return { ok: false, reason: "quiet_hours", message: deps.quietHoursMessage?.() || "" };
      }
      const built = buildUtteranceText(rawText, deps.speechText || ((value) => value));
      if (built.empty) return { ok: false, reason: "empty" };
      teardownPlayback();
      token += 1;
      const utterToken = token;
      active = {
        messageId,
        preview: previewLabel(rawText),
        capNotice: capNotice(built.truncated),
        truncated: built.truncated,
        source,
      };
      state = "preparing";
      emit();
      await deps.ensureSpeechVoices?.();
      if (isStale(utterToken)) return { ok: false, reason: "superseded" };
      speech()?.cancel?.();
      const utter = new (UtteranceCtor())(built.text);
      utter.rate = 1.02;
      const voice = pickEnglishVoice(() => speech()?.getVoices?.() || []);
      if (voice) utter.voice = voice;
      utter.onstart = () => {
        clearNoStartTimer();
        if (isStale(utterToken)) return;
        state = "speaking";
        emit();
      };
      utter.onend = () => {
        clearNoStartTimer();
        if (isStale(utterToken)) return;
        const meta = active;
        active = null;
        state = "stopped";
        emit({ ...meta, reason: "ended" });
        state = "idle";
        emit();
      };
      utter.onerror = () => {
        clearNoStartTimer();
        if (isStale(utterToken)) return;
        const neverStarted = state === "preparing";
        const meta = active;
        active = {
          ...meta,
          fallback: neverStarted
            ? "Read-aloud could not start. Copy the message or try again."
            : "Read-aloud stopped with an error.",
          neverStarted,
        };
        state = "failed";
        emit();
        token += 1;
        active = null;
        state = "idle";
        emit();
      };
      noStartTimer = deps.setTimeout?.(() => {
        if (isStale(utterToken) || state !== "preparing") return;
        speech()?.cancel?.();
        const meta = active;
        active = {
          ...meta,
          fallback: "Read-aloud did not start in time. Try again or copy the message.",
          neverStarted: true,
        };
        state = "failed";
        emit();
        token += 1;
        active = null;
        state = "idle";
        emit();
      }, deps.noStartMs ?? NO_START_MS);
      speech().speak(utter);
      return { ok: true, token: utterToken };
    }

    function getSnapshot() {
      return { state, token, active, lastSource };
    }

    const api = {
      CHAR_CAP,
      start,
      stop,
      onConversationChange,
      onLogout,
      getSnapshot,
      previewLabel,
      buildUtteranceText,
      capNotice,
      unsupportedFallback,
      stateLabel,
    };
    Object.defineProperty(api, "onView", {
      get() { return onView; },
      set(fn) { onView = typeof fn === "function" ? fn : null; },
    });
    return api;
  }

  function mountUi({ getEl, controller, onFallbackNotice }) {
    const panel = getEl("reply-playback");
    const stateEl = getEl("reply-playback-state");
    const messageEl = getEl("reply-playback-message");
    const capEl = getEl("reply-playback-cap");
    const stopBtn = getEl("reply-playback-stop");
    if (!panel || !stateEl || !messageEl || !capEl || !stopBtn) return;
    stopBtn.addEventListener("click", () => controller.stop());
    controller.onView = (view) => {
      const busy = view.state === "preparing" || view.state === "speaking";
      panel.hidden = !busy && view.state !== "failed";
      if (view.state === "idle") {
        panel.hidden = true;
        stopBtn.hidden = true;
        return;
      }
      panel.dataset.state = view.state;
      stateEl.textContent = stateLabel(view.state);
      const idPart = view.messageId ? `Message ${view.messageId}` : "Selected message";
      const previewPart = view.preview ? ` — ${view.preview}` : "";
      messageEl.textContent = busy || view.state === "failed" ? `${idPart}${previewPart}` : "";
      capEl.textContent = view.capNotice || (busy ? capNotice(false) : "");
      stopBtn.hidden = view.state !== "speaking";
      if (view.fallback) onFallbackNotice?.(view.fallback);
      const speakBtn = getEl("speak");
      if (speakBtn && view.source === "latest") {
        const speaking = view.state === "speaking" || view.state === "preparing";
        speakBtn.classList.toggle("mic-active", speaking);
        speakBtn.setAttribute("aria-pressed", String(speaking));
      } else if (speakBtn && (view.state === "idle" || view.state === "stopped" || view.state === "failed")) {
        speakBtn.classList.remove("mic-active");
        speakBtn.setAttribute("aria-pressed", "false");
      }
    };
  }

  return {
    CHAR_CAP,
    PREVIEW_MAX,
    NO_START_MS,
    previewLabel,
    buildUtteranceText,
    capNotice,
    unsupportedFallback,
    stateLabel,
    createController,
    mountUi,
  };
})();

if (typeof window !== "undefined") window.ReplyPlayback = ReplyPlayback;
if (typeof module !== "undefined") module.exports = ReplyPlayback;

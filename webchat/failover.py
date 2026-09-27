"""Provider failures and a durable, thread-safe circuit breaker. No model calls."""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

ORDER = ("codex", "cursor", "gemini", "minimax")
NAMES = {name: name.title() for name in (*ORDER, "claude")}
NAMES["minimax"] = "MiniMax"
REASONS = {
    "not_logged_in": "needs a local sign-in or valid API key",
    "rate_limit": "hit its rate or usage limit",
    "timeout": "timed out",
    "nonzero_exit": "exited unsuccessfully",
    "invalid_output": "returned an empty, incomplete or invalid answer",
    "network": "had a network error",
    "busy": "is answering another chat; trying the next provider",
    "budget": "cannot fit another request under its $96 cap",
    "not_installed": "is not installed",
    "session_unavailable": "could not resume the saved session",
}


def reset_time(text, now):
    """Accept explicit delays, Unix/ISO reset stamps, HTTP dates and CLI dates."""
    match = re.search(r'(?:retry[-_ ]after|retryDelay)["\s:=]+(\d+(?:\.\d+)?)\s*(ms|s|seconds?|minutes?|m|hours?|h)?', text, re.I)
    if not match:
        match = re.search(r'(?:try again|retry|resets?)\s+in\s+(\d+(?:\.\d+)?)\s*(seconds?|s|minutes?|m|hours?|h)\b', text, re.I)
    if match:
        unit = (match[2] or "s").lower()
        multiplier = .001 if unit == "ms" else 3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1
        return now + max(1, float(match[1]) * multiplier)
    match = re.search(r'(?:reset(?:s|_at|_time)?|retry_at|x-ratelimit-reset)["\s:=]+(\d{10,13})\b', text, re.I)
    if match:
        stamp = float(match[1]) / (1000 if len(match[1]) == 13 else 1)
        if stamp > now:
            return stamp
    match = re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?', text)
    if match:
        try:
            stamp = datetime.fromisoformat(match[0].replace("Z", "+00:00")).timestamp()
            if stamp > now:
                return stamp
        except ValueError:
            pass
    match = re.search(r'retry-after:\s*([^\r\n]+)', text, re.I)
    if match:
        try:
            stamp = parsedate_to_datetime(match[1]).timestamp()
            if stamp > now:
                return stamp
        except (ValueError, TypeError, OverflowError):
            pass
    match = re.search(r'(?:try again|resets?)\s+(?:at|on)\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s+on\s+(\w+\s+\d{1,2},?\s+\d{4})', text, re.I)
    if match:
        for fmt in ("%I:%M %p %b %d, %Y", "%H:%M %b %d, %Y", "%I:%M%p %b %d, %Y"):
            try:
                stamp = datetime.strptime(match[1] + " " + match[2], fmt).timestamp()
                if stamp > now:
                    return stamp
            except ValueError:
                pass
    return None


def classify(code, text):
    text = text.lower()
    if any(s in text for s in ("$96 cap", "$48 cap", "budgetexceeded", "budget exhausted")):
        return "budget"
    if any(s in text for s in ("blockingioerror", "lane reserved", "busy with another job")):
        return "busy"
    if any(s in text for s in ("not logged in", "not authenticated", "authentication required", "please log in", "please login", "needs_login", "unauthorized", "invalid api key", "api_key missing", "http 401", "http 403", "sign-in required")):
        return "not_logged_in"
    if any(s in text for s in ("usage limit", "rate limit", "rate-limit", "rate_limit", "quota", "429", "out of usage", "hit your limit", "usage exceeded", "resource_exhausted")):
        return "rate_limit"
    if any(s in text for s in ("timed out", "timeout", "deadline exceeded", "curl_rc=28")):
        return "timeout"
    if any(s in text for s in ("network", "connection", "dns", "could not resolve", "econnreset", "enotfound", "http 5", "curl_rc=5", "curl_rc=6", "curl_rc=7", "curl_rc=35", "curl_rc=52", "curl_rc=56")):
        return "network"
    if any(s in text for s in ("session not found", "no session found", "failed to load rollout", "could not find session", "saved session unavailable")):
        return "session_unavailable"
    if "not installed" in text:
        return "not_installed"
    if code == 3 or any(s in text for s in ("empty", "garbage", "no completed answer", "invalid answer", "unusably short", "truncated", "reasoning-only", "output limit")):
        return "invalid_output"
    return "nonzero_exit" if code else "invalid_output"


class ProviderError(RuntimeError):
    def __init__(self, message="", *, kind=None, code=None, retry_at=None, partial=False):
        self.kind = kind or classify(code, message)
        self.retry_at = retry_at or (reset_time(message, time.time()) if self.kind == "rate_limit" else None)
        self.partial, self.code = partial, code
        super().__init__(message or REASONS[self.kind])


class Cancelled(ProviderError):
    pass


class AllDown(ProviderError):
    def __init__(self, attempts, retry_at, prompt):
        self.attempts, self.prompt = attempts, prompt
        super().__init__("No provider completed a reply. Your request is queued; Bob will retry after a provider's cooldown. You can stop the queued request.", retry_at=retry_at)


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".health-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Circuit:
    def __init__(self, path, log_path, clock=time.time, base=300, maximum=1800, audit_context="production"):
        self.path, self.log_path, self.clock = path, log_path, clock
        self.base, self.maximum = base, maximum
        self.audit_context = audit_context
        self.lock = threading.RLock()
        self.active = {}
        self.entries = json.loads(path.read_text()) if path.exists() else {}
        for name in (*ORDER, "claude"):
            self.entries.setdefault(name, {"failures": 0, "retry_at": 0, "reason": None, "checked_at": None})

    def log(self, event, **data):
        # Call sites pass enums, IDs and canned reasons only, never prompts/output.
        with self.lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a") as handle:
                os.fchmod(handle.fileno(), 0o600)
                handle.write(json.dumps({"timestamp": self.clock(), "event": event, "context": self.audit_context, **data}) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def save(self):
        atomic_json(self.path, self.entries)

    def snapshot(self):
        with self.lock:
            rows = copy.deepcopy(self.entries)
            for name, row in rows.items():
                row["state"] = ("busy" if name in self.active else "cooldown" if row["retry_at"] > self.clock()
                                else "half_open" if row["failures"] else "ready" if row.get("last_success") else "unchecked")
                row["automatic"] = name in ORDER
                row["detail"] = REASONS.get(row["reason"], "Ready" if row.get("last_success") else "Awaiting a completed reply")
            return rows

    def acquire(self, name):
        with self.lock:
            if self.entries[name]["retry_at"] > self.clock():
                return False
            # HTTP APIs allow concurrent chats. Only a half-open recovery attempt
            # or an interactive CLI slot is exclusive, never a background job.
            if name in self.active and (name not in ("gemini", "minimax") or self.entries[name]["failures"]):
                return False
            self.active[name] = self.active.get(name, 0) + 1
            return True

    def release(self, name):
        with self.lock:
            if self.active.get(name, 0) > 1:
                self.active[name] -= 1
            else:
                self.active.pop(name, None)

    def failed(self, name, error, cooldown=None):
        with self.lock:
            row = self.entries[name]
            row["failures"] = min(row["failures"] + 1, 20)
            delay = min(self.maximum, self.base * 2 ** min(row["failures"] - 1, 10))
            if error.kind == "busy":
                delay = 15
            if cooldown is not None:
                delay = cooldown
            retry_at = error.retry_at if error.kind == "rate_limit" and error.retry_at and error.retry_at > self.clock() else self.clock() + delay
            row.update(reason=error.kind, retry_at=retry_at, checked_at=self.clock())
            self.save()
            return retry_at

    def succeeded(self, name):
        with self.lock:
            self.entries[name].update(failures=0, reason=None, retry_at=0, checked_at=self.clock(), last_success=self.clock())
            self.save()

    def probed(self, name, error=None):
        with self.lock:
            row = self.entries[name]
            row.update(probed_at=self.clock(), probe="ok" if error is None else error.kind)
            # A credential/network probe does not prove quota recovery. Only an
            # actual completed turn closes the breaker, after its reset time.
            if error and not row["failures"]:
                self.failed(name, error)
            self.save()

    def next_retry(self, order=ORDER):
        with self.lock:
            return max(self.clock() + 1, min(self.entries[n]["retry_at"] for n in order))

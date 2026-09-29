# Strict LIVE MiniMax tip review draft/webbob-gaps-1725 @70d59e3 (70d59e3525b350ab8a01b81129cc0049ef085d93)

SCOPE: bob_gaps / profile memory / screenshot-window gaps ONLY.
Prior LIVE-GEMINI @ 70d59e3 = PASS. Offline GAPS-FIXED-2143 READY (atomic append_profile_memory via flock).
Old MiniMax was on 3a7a571 — this is a fresh tip review of 70d59e3.
Do NOT fail for missing voice/media/texting. Cite only real symbols.
List CRITICAL/HIGH real bugs only. End with exactly: VERDICT: PASS or VERDICT: FAIL

## FIXED-2143 summary
# GAPS-FIXED-2143

**Branch:** draft/webbob-gaps-1725
**New tip SHA:** 70d59e3
**Prior tip SHA:** e62b6e3
**Verdict:** READY

## Gate finding

LIVE-GEMINI-draft_webbob-gaps-1725-e62b6e3.md flagged a race in
`append_profile_memory` (webchat/bob_gaps.py): the append (open+write) and
the trim (`_trim_profile_file`, a separate read_text/write_text pair) were
two unlocked, non-atomic file operations. Concurrent "remember that"
confirmations could interleave and lose a memory line.

## Fix

- Merged the append and trim into a single critical section guarded by
  `fcntl.flock(LOCK_EX)` on a sibling `profile.lock` file, matching the
  existing lock pattern used elsewhere in webchat (e.g. `actions.py`'s
  `queue_once`).
- Replaced the trailing `path.write_text(...)` with `failover.atomic_text`
  (write to a temp file in the same directory, fsync, `os.replace`, fsync
  parent dir) so the on-disk file is never observed half-written.
- `_trim_profile_file` (path-based, did its own I/O) was replaced with
  `_trim_profile_lines` (pure, operates on an in-memory list) so trimming
  happens inside the same lock/read/write instead of as a second unlocked
  pass.

## Regression test

Added `test_append_profile_memory_concurrent_appends_not_lost` to
`webchat/test_bob_gaps.py`: spins up 12 threads behind a `threading.Barrier`
so they all call `append_profile_memory` at once, then asserts all 12
distinct lines are present in the final profile file with no exceptions
raised. This reproduces the lost-write window against the old
read-then-write-without-lock code (verified failing before the fix, passing
after).

## Test run

Ran the full webchat unit test suite (unittest, not pytest — pytest isn't
installed in this environment):

```
test_api_call        1 test    OK
test_bob_gaps        24 tests  OK  (incl. new concurrency regression test)
test_build_info      4 tests   OK
test_chat_intent     27 tests  OK
test_dispatch        37 tests  OK
test_failover        25 tests  OK
test_jobs_view       16 tests  OK
test_reply_authority 13 tests  OK
test_tab_status      8 tests   OK
test_webchat         94 tests  OK
test_worker_activity 9 tests   OK
```

(`test_live_*` suites were not run — they exercise live/deployed
integration paths outside this fix's scope.)

## Push

Committed and pushed as a regular (non-force) push to
`brain/draft/webbob-gaps-1725`. No deploy, merge, or undraft performed.

## git log
70d59e3 Fix race in append_profile_memory with atomic locked read-modify-write
e62b6e3 Limit bob_gaps disk growth and handle memory save failures.
9242839 Harden bob_gaps screenshots and expand gap security tests.
## diffstat vs live dff84e3 (gaps-focused)
 webchat/app.py           | 143 ++++++++++++++++++-
 webchat/bob_gaps.py      | 230 ++++++++++++++++++++++++++++++
 webchat/test_bob_gaps.py | 359 +++++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 731 insertions(+), 1 deletion(-)
## bob_gaps.py flock / append_profile_memory
4:import fcntl
67:def _trim_profile_lines(lines: list[str], max_bytes: int = PROFILE_MAX_BYTES) -> list[str]:
90:def append_profile_memory(root: Path, fact: str, when: datetime | None = None) -> str:
96:    with (path.parent / "profile.lock").open("a") as lock:
97:        fcntl.flock(lock, fcntl.LOCK_EX)
99:        lines = _trim_profile_lines(existing.splitlines(keepends=True) + [line])
## relevant source excerpt
"""Bob-the-Bot parity: durable memory, web research, and on-demand screenshots."""
from __future__ import annotations

import fcntl
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from failover import atomic_text

REMEMBER = re.compile(r"^remember\s+that\s+(.+?)\s*\.?\s*$", re.I | re.S)
MEMORY_CONFIRM = re.compile(r"^yes[,.]?\s*save\s+memory\s*$", re.I)
MEMORY_CONFIRM_PROPOSAL = re.compile(
    r"^yes[,.]?\s*save\s+memory(?:\s+proposal\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}))?\s*$",
    re.I,
)
MEMORY_CANCEL = re.compile(r"^(?:never mind|cancel|dismiss)(?:\s+memory)?\s*$", re.I)
SCREENSHOT = re.compile(
    r"^(?:please\s+)?take\s+(?:a\s+)?screenshot(?:\s+of\s+(?:the\s+)?(.+?))?\s*\.?\s*$",
    re.I,
)
WEB_SEARCH = re.compile(
    r"\b(?:search\s+(?:the\s+)?web|look\s+up|google)\b|"
    r"(?:what\s+(?:was|is)|who\s+won|score\s+of).{0,120}\?",
    re.I,
)

CAPTURE_MAX_COUNT = 100
CAPTURE_MAX_AGE_DAYS = 7
PROFILE_MAX_BYTES = 512 * 1024


def profile_path(root: Path) -> Path:
    return root / "bob-brain/memory/profile.md"


def parse_remember(text: str) -> str | None:
    match = REMEMBER.match((text or "").strip())
    if not match:
        return None
    fact = match.group(1).strip()
    return fact[:2000] if fact else None


def parse_memory_confirm(text: str) -> tuple[bool, str | None]:
    stripped = (text or "").strip()
    match = MEMORY_CONFIRM_PROPOSAL.match(stripped)
    if match:
        return True, match.group(1)
    if MEMORY_CONFIRM.match(stripped):
        return True, None
    return False, None


def memory_confirm_prompt(fact: str) -> str:
    return f"I can save this to durable memory:\n\n**{fact}**\n\nReply `yes, save memory` to confirm."


def _trim_profile_lines(lines: list[str], max_bytes: int = PROFILE_MAX_BYTES) -> list[str]:
    trimmed = list(lines)
    while trimmed and sum(len(entry) for entry in trimmed) > max_bytes:
        trimmed.pop(0)
    return trimmed


def _prune_captures(folder: Path, max_count: int = CAPTURE_MAX_COUNT, max_age_days: int = CAPTURE_MAX_AGE_DAYS) -> None:
    try:
        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        captures = [path for path in folder.glob("*.png") if path.is_file()]
        captures.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        to_delete = set(captures[max_count:])
        for path in captures:
            if now - path.stat().st_mtime > max_age_seconds:
                to_delete.add(path)
        for path in to_delete:
            path.unlink()
    except OSError:
        pass


def append_profile_memory(root: Path, fact: str, when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    stamp = when.astimezone().strftime("%Y-%m-%d")
    line = f"[{stamp}] {fact.strip()}\n"
    path = profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / "profile.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = _trim_profile_lines(existing.splitlines(keepends=True) + [line])
        atomic_text(path, "".join(lines))
    return line.strip()


def parse_screenshot(text: str) -> str | None:
    match = SCREENSHOT.match((text or "").strip())
    if not match:
        return None
    target = (match.group(1) or "").strip()
    return target[:120] if target else ""


def _escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _macos_window_id(app_name: str) -> int | None:
    if sys.platform != "darwin":
        raise RuntimeError("The screenshot feature is only available on macOS.")
    escaped_name = _escape_applescript_string(app_name)
    script = (
        'tell application "System Events" to id of first window of '
        f'(first process whose name contains "{escaped_name}")'
    )
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return None


def capture_screenshot(root: Path, target: str | None = None) -> tuple[str, Path]:
    if sys.platform != "darwin":
        raise RuntimeError("The screenshot feature is only available on macOS.")
    folder = root / "conductor/webchat/captures"
    folder.mkdir(parents=True, exist_ok=True)
    _prune_captures(folder)
    capture_id = secrets.token_hex(8)
    path = folder / f"{capture_id}.png"
    command = ["screencapture", "-x"]
    if target:
        window_id = _macos_window_id(target)
        if window_id is None:
            raise RuntimeError(f"I could not find an open window matching “{target}”.")
        command.extend(["-l", str(window_id)])
    command.append(str(path))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Screenshot capture failed ({exc}).") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()
        message = f"Screenshot capture failed (exit {completed.returncode})"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Screenshot capture produced no image.")
    return capture_id, path


def capture_reply(capture_id: str, target: str | None) -> str:
    label = target or "your screen"
    return (
        f"Captured **{label}**.\n\n"
        f"![screenshot](/api/captures/{capture_id})"
    )


def needs_web_search(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 600:
        return False
    return bool(WEB_SEARCH.search(stripped))


def web_search(query: str, opener=urllib.request.urlopen) -> dict:
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1}
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "WebBob/1.0 (bob-gaps web research)"},
    )
## tests
67:    def test_remember_requires_confirmation_then_appends_profile(self):
81:    def test_memory_dismiss_cancels_pending_save(self):
89:    def test_stale_memory_proposal_is_rejected(self):
99:    def test_memory_turn_skipped_for_non_auto_provider(self):
107:    def test_memory_save_oserror_surfaces_in_chat(self):
118:    def test_mets_score_triggers_search_with_source_link(self):
128:    def test_web_search_network_error_surfaces_in_chat(self):
135:    def test_calculator_screenshot_shown_in_chat(self):
150:    def test_screenshot_failure_surfaces_in_chat(self):
155:    def test_try_bob_gaps_skipped_when_ledger_root_mismatch(self):
206:    def test_capture_endpoint_serves_png_and_rejects_invalid_id(self):
220:    def test_parsers(self):
225:    def test_needs_web_search_negative_cases(self):
231:    def test_memory_regexes(self):
239:    def test_parse_memory_confirm(self):
248:    def test_append_profile_memory_line(self):
257:    def test_append_profile_memory_trims_when_oversized(self):
268:    def test_append_profile_memory_concurrent_appends_not_lost(self):
294:    def test_prune_captures_enforces_max_count(self):
308:    def test_format_web_search_reply_tolerates_missing_keys(self):
314:    def test_resolve_capture_path(self):
325:    def test_capture_screenshot_requires_macos(self):
332:    def test_macos_window_id_escapes_injection_payload(self):
343:    def test_web_search_sets_user_agent(self):

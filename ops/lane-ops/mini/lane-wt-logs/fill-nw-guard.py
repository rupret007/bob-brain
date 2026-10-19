#!/usr/bin/env python3
"""If NW.override is 0 with no reason in NW-CHANGES.md, alert and restore to at least 2."""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone

PROJ = os.path.expanduser(
    "~/Documents/bob-overnight-inject/local-proj-max-1010"
)
NW_FILE = os.path.join(PROJ, "NW.override")
NW_LOG = os.path.expanduser(
    "~/Documents/bob-overnight-inject/conductor/reviews/NW-CHANGES.md"
)
DISPATCH = os.path.expanduser("~/lane-wt/logs/dispatch.log")
FLOOR = int(os.environ.get("FILL_NW_FLOOR", "2"))


def log(msg: str) -> None:
    line = f"{datetime.now().astimezone():%a %b %d %H:%M:%S %Z %Y} fill-nw-guard {msg}"
    print(line)
    try:
        with open(DISPATCH, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def read_nw() -> int | None:
    if not os.path.isfile(NW_FILE):
        return None
    raw = open(NW_FILE).read().strip()
    if not raw:
        return None
    try:
        return int(raw.split()[0])
    except ValueError:
        return None


def reason_for_zero(within_hours: float = 36.0) -> str | None:
    """Return the matching NW-CHANGES line if a recent entry explains setting NW to 0."""
    if not os.path.isfile(NW_LOG):
        return None
    text = open(NW_LOG).read()
    # Match lines that record dropping to 0 / setting =0 / ->0
    pat = re.compile(
        r"(?im)^(.*\bNW(?:\.override)?\b.*(?:→|->|=)\s*0\b.*)$"
    )
    matches = pat.findall(text)
    if not matches:
        # also accept explicit phrases
        pat2 = re.compile(r"(?im)^(.*\bNW.*\b(?:set|drop|park|pin).*?\b0\b.*)$")
        matches = pat2.findall(text)
    if not matches:
        return None
    # Prefer last match; if it has a parseable date prefix, check freshness
    last = matches[-1].strip()
    # Try leading date like "Fri Oct 16 08:32:10 CDT 2026"
    m = re.match(
        r"^([A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} [A-Z]{2,4} \d{4})",
        last,
    )
    if m:
        for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S %Y"):
            try:
                # strip TZ name for strptime without %Z reliability
                ds = m.group(1)
                # remove timezone abbreviation
                ds2 = re.sub(r" [A-Z]{2,4} ", " ", ds)
                dt = datetime.strptime(ds2, "%a %b %d %H:%M:%S %Y").replace(
                    tzinfo=datetime.now().astimezone().tzinfo
                )
                if datetime.now().astimezone() - dt > timedelta(hours=within_hours):
                    return None
                break
            except ValueError:
                continue
    return last


def main() -> int:
    nw = read_nw()
    if nw is None:
        log(f"ALERT NW.override missing/unreadable -> set to {FLOOR}")
        os.makedirs(PROJ, exist_ok=True)
        open(NW_FILE, "w").write(f"{FLOOR}\n")
        with open(NW_LOG, "a") as f:
            f.write(
                f"{datetime.now().astimezone():%a %b %d %H:%M:%S %Z %Y} fill-nw-guard: "
                f"NW.override missing -> {FLOOR} (no reason on file)\n"
            )
        return 0
    if nw > 0:
        log(f"ok NW={nw}")
        return 0
    reason = reason_for_zero()
    if reason:
        log(f"NW=0 with recorded reason (holding): {reason[:160]}")
        return 0
    log(f"ALERT NW.override=0 with no reason recorded -> restore to {FLOOR}")
    open(NW_FILE, "w").write(f"{FLOOR}\n")
    with open(NW_LOG, "a") as f:
        f.write(
            f"{datetime.now().astimezone():%a %b %d %H:%M:%S %Z %Y} fill-nw-guard: "
            f"ALERT NW.override was 0 with no reason in NW-CHANGES.md -> restored to {FLOOR}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

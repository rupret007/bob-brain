#!/usr/bin/env python3
"""Live short-prompt checks with real lane leases and billing records."""
import concurrent.futures
import json
import time

from lanes import LANES, ask, refresh
from state import CONDUCTOR, atomic_write, write_json


def check(lane):
    started = time.time()
    try:
        text = ask(lane, "Reply with exactly: CONDUCTOR_SMOKE_OK: lane responded successfully. No tools or file changes.", timeout=90, purpose="smoke")
        ok = "CONDUCTOR_SMOKE_OK" in text
        return {"lane": lane, "ok": ok, "result": text[:400], "seconds": round(time.time() - started, 2)}
    except Exception as exc:
        return {"lane": lane, "ok": False, "error": str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
                "seconds": round(time.time() - started, 2)}


def main():
    refresh()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(check, LANES))
    write_json(CONDUCTOR / "reviews/smoke/results.json", results)
    atomic_write(CONDUCTOR / "reviews/SMOKE.md", "# Live lane smoke\n\n" + "\n".join(
        "- " + row["lane"] + ": " + ("PASS" if row["ok"] else "FAIL") + " — " +
        row.get("error", row.get("result", "")) + " (" + str(row["seconds"]) + "s)" for row in results) + "\n")
    for row in results:
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()

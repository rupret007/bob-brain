#!/usr/bin/env python3
"""No generation/spend: verify API configuration, cap and TLS reachability."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))


def main():
    lane = sys.argv[1]
    if lane not in ("gemini", "minimax"):
        return 2
    if not os.environ.get(lane.upper() + "_API_KEY"):
        print("API_KEY missing")
        return 1
    if lane == "minimax":
        import budget
        budget.import_ux_ledger()
        if budget.totals(lane)["committed_usd"] >= budget.CAP_USD:
            print("MiniMax $48 cap reached")
            return 1
    host = "https://api.minimax.io" if lane == "minimax" else "https://generativelanguage.googleapis.com"
    # Any HTTP response proves reachability; no key is sent, no inference occurs.
    result = subprocess.run(["/usr/bin/curl", "-sS", "-I", "--max-time", "8", "--connect-timeout", "4", "-o", os.devnull, host], stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    if result.returncode:
        print("network check failed curl_rc=" + str(result.returncode))
        return 1
    print("configured; TLS reachable; generation not tested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

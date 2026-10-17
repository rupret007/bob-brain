#!/usr/bin/env python3
"""Explicit live acceptance probe; prints only URL/hash evidence, never keys."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webbob.tool_host import research_host


async def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: research-evidence.py BRAVE_ENTRYPOINT QUERY")
    try:
        async with research_host(sys.argv[1]) as host:
            report = await host.research(sys.argv[2])
        evidence = {"sources": [{k: s[k] for k in ("url", "sha256", "fetched_at")} for s in report["sources"]],
                    "multiple_sources_retrieved": report.get("multiple_sources_retrieved", False),
                    "unavailable_count": len(report["unavailable"])}
        print(json.dumps(evidence, indent=2))
        return 0 if evidence["multiple_sources_retrieved"] else 1
    except Exception:
        print('{"status":"unavailable","multiple_sources_retrieved":false}')
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

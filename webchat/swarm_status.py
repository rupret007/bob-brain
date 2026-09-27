"""Read-only public projection of swarm assignment boards; never runs services."""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

STATUSES = {"assigned", "running", "finished", "integrating", "bounced", "conflict", "merged", "cancelled"}


def timestamp(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def read_boards(root, *, now=None, max_age=300):
    now = time.time() if now is None else now
    result = dict(projects=[], errors=[])
    for path in sorted((Path(root) / "conductor/state/projects").glob("*.json")):
        try:
            board = json.loads(path.read_text())
            if (board["version"] != 1 or board["project"] != path.stem or not isinstance(board["workers"], dict)
                    or not timestamp(board["updated_at"]) or not isinstance(board["integration_branch"], str)):
                raise ValueError("invalid board")
            workers = []
            for worker, row in board["workers"].items():
                required = ("worker", "llm", "vendor", "task", "role", "branch", "sha", "status")
                if (row["worker"] != worker or not timestamp(row["updated_at"])
                        or any(not isinstance(row.get(key), str) or not row[key] for key in required)
                        or row["status"] not in STATUSES or not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", row["sha"])):
                    raise ValueError("invalid worker")
                fields = ("worker", "llm", "vendor", "task", "role", "branch", "sha", "status", "updated_at", "integrated_sha")
                public = {key: row.get(key) for key in fields}
                public["lease"] = (row.get("lease") or {}).get("paths", [])
                if not isinstance(public["lease"], list) or any(not isinstance(p, str) for p in public["lease"]):
                    raise ValueError("invalid lease paths")
                public["stale"] = not -5 <= now - row["updated_at"] <= max_age
                workers.append(public)
            result["projects"].append(dict(project=board["project"], integration_branch=board["integration_branch"],
                updated_at=board["updated_at"], stale=not -5 <= now - board["updated_at"] <= max_age, workers=workers,
                queued_resolvers=sum(job.get("status") == "queued" for job in board.get("resolver_jobs", {}).values())))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            result["errors"].append(dict(project=path.stem, error="Project board unavailable or invalid"))
    return result


def format_boards(boards, *, detailed=False):
    lines = []
    for project in boards.get("projects", []):
        for row in project["workers"]:
            line = (project["project"] + ": " + row["task"] + " — " + row["llm"] + " (" + row["worker"]
                    + "), recorded " + row["status"])
            if row["stale"]:
                line += "; update is stale (over five minutes old or clock uncertain)"
            if detailed:
                line += "; " + row["branch"] + " @ " + row["sha"][:12]
                line += "; paths: " + (", ".join(row["lease"]) or "none")
            lines.append(line + ".")
        if project["queued_resolvers"]:
            lines.append(project["project"] + ": " + str(project["queued_resolvers"]) + " Codex resolver job(s) queued.")
    lines.extend(row["project"] + ": project board unavailable." for row in boards.get("errors", []))
    return ("Project assignments (saved state; live activity is checked separately):\n" + "\n".join(lines)) if lines else ""

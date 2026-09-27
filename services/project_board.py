"""One durable board per project; its records describe assignments, not liveness."""
from __future__ import annotations

import time
from pathlib import Path

try:
    from .swarm_store import identifier, locked, read_json, write_json
except ImportError:
    from swarm_store import identifier, locked, read_json, write_json


STATUSES = {"assigned", "running", "finished", "integrating", "bounced", "conflict", "merged", "cancelled"}


class ProjectBoard:
    def __init__(self, conductor, project):
        self.conductor = Path(conductor)
        self.project = identifier(project)
        self.path = self.conductor / "state/projects" / (self.project + ".json")

    def read(self):
        data = read_json(self.path, None)
        if (not isinstance(data, dict) or data.get("version") != 1 or data.get("project") != self.project
                or not isinstance(data.get("workers"), dict) or not isinstance(data.get("resolver_jobs"), dict)):
            raise ValueError("project board missing or invalid")
        return data

    def initialize(self, repo, integration_branch, contract_sha):
        with locked(self.conductor, "board-" + self.project):
            if self.path.exists():
                data = self.read()
                if (data["repo"], data["integration_branch"], data["contract_sha"]) != (str(Path(repo).resolve()), integration_branch, contract_sha):
                    raise ValueError("project already has a different integration contract")
                return data
            data = dict(version=1, project=self.project, repo=str(Path(repo).resolve()),
                        integration_branch=integration_branch, contract_sha=contract_sha,
                        workers={}, resolver_jobs={}, revision=0, updated_at=time.time())
            write_json(self.path, data)
            return data

    def change(self, callback):
        with locked(self.conductor, "board-" + self.project):
            data = self.read()
            result = callback(data)
            data.update(revision=data["revision"] + 1, updated_at=time.time())
            write_json(self.path, data)
            return result

    def update(self, worker, **fields):
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError("invalid worker status")
        def apply(data):
            row = data["workers"][worker]
            row.update(fields, updated_at=time.time())
            return row
        return self.change(apply)

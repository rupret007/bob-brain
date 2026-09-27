"""Conservative path ownership, held until an explicit, token-fenced release.

Paths name files or whole subtrees (no globs); '.' reserves the entire project.
Leases do not expire: a silent worker may still be writing in its worktree.
"""
from __future__ import annotations

import argparse
import json
import time
import unicodedata
import uuid
from pathlib import Path, PurePosixPath

try:
    from .swarm_store import identifier, locked, read_json, write_json
except ImportError:
    from swarm_store import identifier, locked, read_json, write_json


class LeaseConflict(ValueError):
    pass


def normalize(paths, repo=None):
    if isinstance(paths, (str, bytes)) or not paths:
        raise ValueError("a nonempty list of relative paths is required")
    result = set()
    for path in paths:
        if (not isinstance(path, str) or not path or path.startswith(("/", "~"))
                or any(c in path for c in "\\*?[]:\x00\n\r")
                or ".." in path.split("/")):
            raise ValueError("lease paths must be literal repository-relative paths")
        clean = str(PurePosixPath(path))
        if any(part.casefold() == ".git" for part in PurePosixPath(clean).parts):
            raise ValueError("Git metadata cannot be leased")
        if repo is not None:
            target = Path(repo)
            for part in PurePosixPath(clean).parts:
                target /= part
                if target.is_symlink():
                    raise ValueError("symlink paths cannot be leased; use the real repository path")
        # Refuse case/Unicode aliases conservatively, including on macOS.
        result.add(unicodedata.normalize("NFC", clean).casefold())
    return sorted(result)


def overlaps(left, right):
    return left == "." or right == "." or left == right or left.startswith(right + "/") or right.startswith(left + "/")


class LeaseStore:
    def __init__(self, conductor, project, repo=None):
        self.conductor = Path(conductor)
        self.project = identifier(project)
        self.repo = Path(repo).resolve() if repo is not None else None
        self.path = self.conductor / "leases" / (self.project + ".json")

    def _read(self):
        data = read_json(self.path, dict(version=1, project=self.project, leases=[]))
        if (not isinstance(data, dict) or data.get("version") != 1 or data.get("project") != self.project
                or not isinstance(data.get("leases"), list)):
            raise ValueError("invalid lease store; refusing new ownership")
        for row in data["leases"]:
            if (not isinstance(row, dict) or not row.get("token") or not row.get("owner")
                    or normalize(row.get("paths")) != row["paths"]):
                raise ValueError("invalid lease record; refusing new ownership")
        return data

    def list(self):
        with locked(self.conductor, "leases-" + self.project):
            return self._read()["leases"]

    def claim(self, owner, paths):
        owner, paths = identifier(owner), normalize(paths, self.repo)
        with locked(self.conductor, "leases-" + self.project):
            data = self._read()
            for row in data["leases"]:
                if row["owner"] == owner and row["paths"] == paths:
                    return row  # Idempotent retry, with the same fence.
                if row["owner"] == owner or any(overlaps(a, b) for a in paths for b in row["paths"]):
                    raise LeaseConflict("paths already owned by " + row["owner"])
            row = dict(owner=owner, paths=paths, token=uuid.uuid4().hex, claimed_at=time.time())
            data["leases"].append(row)
            write_json(self.path, data)
            return row

    def release(self, owner, token):
        with locked(self.conductor, "leases-" + self.project):
            data = self._read()
            row = next((r for r in data["leases"] if r["owner"] == owner), None)
            if row is None:
                return False
            if row["token"] != token:
                raise ValueError("lease ownership token mismatch")
            data["leases"].remove(row)
            write_json(self.path, data)
            return True

    def transfer(self, owner, token, new_owner):
        """Move existing ownership to a resolver without an unleased interval."""
        identifier(new_owner)
        with locked(self.conductor, "leases-" + self.project):
            data = self._read()
            transferred = next((r for r in data["leases"] if r["owner"] == new_owner
                                and r.get("previous_owner") == owner and r.get("previous_token") == token), None)
            if transferred:
                return transferred  # Recover after transfer but before the board write.
            row = next((r for r in data["leases"] if r["owner"] == owner and r["token"] == token), None)
            if row is None or any(r["owner"] == new_owner for r in data["leases"]):
                raise ValueError("lease transfer ownership mismatch")
            row.update(owner=new_owner, token=uuid.uuid4().hex, previous_owner=owner, previous_token=token)
            write_json(self.path, data)
            return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conductor", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--repo", type=Path)
    actions = parser.add_subparsers(dest="action", required=True)
    claim = actions.add_parser("claim")
    claim.add_argument("owner")
    claim.add_argument("paths", nargs="+")
    release = actions.add_parser("release")
    release.add_argument("owner")
    release.add_argument("token")
    actions.add_parser("list")
    args = parser.parse_args()
    store = LeaseStore(args.conductor, args.project, args.repo)
    result = (store.claim(args.owner, args.paths) if args.action == "claim" else
              store.release(args.owner, args.token) if args.action == "release" else store.list())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

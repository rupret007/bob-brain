"""Portable JSON backup of accepted-memory exports and nonsecret config only."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets

from webbob.shared_context import ContextError, safe_fact

CONFIG_FIELDS = {"timezone", "release_sha", "model_caps_microdollars", "routines_paused"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def validate(facts, config):
    if not isinstance(config, dict) or set(config) != CONFIG_FIELDS:
        raise ValueError("only explicitly nonsecret config fields may be backed up")
    if config["timezone"] != "America/Chicago" or not re.fullmatch(r"[a-f0-9]{40}", config["release_sha"]):
        raise ValueError("exact release and timezone required")
    if type(config["routines_paused"]) is not bool or not isinstance(config["model_caps_microdollars"], dict):
        raise ValueError("invalid nonsecret configuration")
    for model, cap in config["model_caps_microdollars"].items():
        if not re.fullmatch(r"[a-z0-9_.:/-]{1,80}", model) or type(cap) is not int or cap < 0:
            raise ValueError("invalid model cap")
    if not isinstance(facts, list) or len(facts) > 1000:
        raise ValueError("bounded accepted-fact export required")
    seen = set()
    for fact in facts:
        fields = {"id", "revision", "body", "provenance", "at", "classification", "execution_authority"}
        if not isinstance(fact, dict) or set(fact) != fields or fact["classification"] != "accepted_fact" or fact["execution_authority"] is not False:
            raise ValueError("raw memory, texts, credentials and voice are forbidden")
        if fact["id"] in seen or not re.fullmatch(r"[a-z0-9_.-]{1,80}", fact["id"]):
            raise ValueError("unique fact identity required")
        seen.add(fact["id"])
        if type(fact["revision"]) is not int or fact["revision"] < 1 or not isinstance(fact["body"], str) or len(fact["body"]) > 1200:
            raise ValueError("invalid fact")
        provenance = fact["provenance"]
        if (not isinstance(provenance, dict)
                or set(provenance) != {"kind", "uri", "sha256", "accepted_by", "accepted_at"}
                or provenance.get("kind") not in {"accepted_memory", "reviewed_fact"}):
            raise ValueError("accepted provenance required")
        if not all(isinstance(provenance[k], str) and 0 < len(provenance[k]) <= 300 for k in provenance):
            raise ValueError("bounded provenance fields required")
        if not provenance["uri"].startswith(("memory/", "user-memory/", "review:")) or not re.fullmatch(r"[a-f0-9]{64}", provenance["sha256"]):
            raise ValueError("accepted source and source digest required")
        if type(fact["at"]) not in (int, float) or not math.isfinite(fact["at"]):
            raise ValueError("finite fact timestamp required")
        try:
            safe_fact(fact["body"])
        except ContextError:
            raise ValueError("backup rejected: sensitive content") from None
    raw = canonical({"facts": facts, "config": config})
    if len(raw) > 2_000_000:
        raise ValueError("backup rejected: oversized content")
    return raw


def snapshot(destination, facts, config):
    # Validate before creating ANY file, including temporary files.
    raw = validate(facts, config)
    envelope = {"schema": 1, "payload": json.loads(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    path = Path(destination)
    if not path.parent.is_dir() or path.exists() or path.is_symlink():
        raise ValueError("new backup destination in private directory required")
    directory = path.parent.stat()
    if path.parent.is_symlink() or directory.st_uid != os.getuid() or directory.st_mode & 0o077:
        raise ValueError("backup directory must be owner-only")
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(envelope))
            stream.flush()
            os.fsync(stream.fileno())
        # link is no-clobber, unlike replace; duplicate nightly runs cannot
        # overwrite an existing snapshot. Only our own temp file is removed.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"file": path.name, "sha256": envelope["sha256"], "facts": len(facts)}


def read_snapshot(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 2_100_000:
        raise ValueError("unsafe snapshot")
    envelope = json.loads(path.read_text())
    if set(envelope) != {"schema", "payload", "sha256"} or envelope["schema"] != 1:
        raise ValueError("unsupported snapshot")
    payload = envelope["payload"]
    if set(payload) != {"facts", "config"}:
        raise ValueError("unsupported backup payload")
    raw = validate(payload["facts"], payload["config"])
    if hashlib.sha256(raw).hexdigest() != envelope["sha256"]:
        raise ValueError("snapshot integrity failed")
    return payload

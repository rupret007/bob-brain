"""Accepted context and durable addressed inbox on coord-owned SQLite.

SQLite supplies transactions. Existing memory remains authoritative at import;
this service never imports conversations or grants execution permission.
"""
from contextlib import contextmanager
import base64
import binascii
import copy
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import unicodedata

BOTS = {"bob", "webbob", "andrea", "karen"}
INBOX_CAP = 1000  # Pending notifications per recipient, across all senders.
SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
 id TEXT, revision INTEGER, body TEXT, provenance TEXT NOT NULL,
 audience TEXT NOT NULL, at REAL NOT NULL, forgotten INTEGER NOT NULL,
 PRIMARY KEY(id, revision));
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL,
 topic TEXT NOT NULL, refs TEXT NOT NULL, at REAL NOT NULL, acked INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS messages_pending ON messages(recipient, acked);
CREATE TABLE IF NOT EXISTS effects (
 message_id TEXT PRIMARY KEY, state TEXT NOT NULL, receipt TEXT,
 FOREIGN KEY(message_id) REFERENCES messages(id));
"""


class ContextError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _normalize_fact_text(value):
    value = unicodedata.normalize("NFKC", value)
    return "".join(c for c in value if unicodedata.category(c) != "Cf")


def safe_fact(body):
    if not isinstance(body, str) or not 1 <= len(body) <= 1200:
        raise ContextError("fact length must be 1..1200")
    # Enforce exclusions even for mislabeled accepted facts. Normalize common
    # Unicode disguises before checking, while preserving approved stored text.
    value = _normalize_fact_text(body)
    language = re.sub(r"[_-]+", " ", value)
    credential = re.compile(r"(?i)(-----BEGIN .*PRIVATE KEY|\b(?:sk-|ghp_|github_pat_)[a-z0-9_-]{12,}|"
                            r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bxox[bpars]-[a-z0-9-]+|"
                            r"(?:api[_ -]?key|password|secret|bearer|access[_ -]?token)\s*[:=]\s*\S+|"
                            r"\bbearer\s*[:=]?\s+\S+)")
    if credential.search(value):
        raise ContextError("credential-like content forbidden")
    # Inspect complete tokens, including short padded credentials. The fact
    # length limit bounds decoding work without leaving gaps at token lengths.
    for token in re.findall(r"[A-Za-z0-9+/]+={0,2}", value):
        try:
            decoded = base64.b64decode(token, validate=True)
        except (binascii.Error, ValueError):
            continue
        if credential.search(_normalize_fact_text(decoded.decode("utf-8", errors="ignore"))):
            raise ContextError("credential-like content forbidden")
    # Exempt only the benign format phrase, never other message markers in the
    # same fact or explicit labels such as "plain text message".
    text_language = re.sub(r"(?i)\bplain\s+text\b(?!\s+(?:body|content|messages?|transcript|from)\b)",
                           "", language)
    if re.search(r"(?i)\b(?:sms|imessage|texts?|texted|texting|"
                 r"message[ _-]*(?:body|content|transcript))\b|"
                 r"\btext[ _-]*(?:body|content|message|transcript)\b", text_language):
        raise ContextError("text/SMS content forbidden")
    if re.search(r"(?<!\w)(?:\+?\d[\s().-]*){10,15}(?!\w)|\b\d{3}[ .-]\d{4}\b", value):
        raise ContextError("phone numbers forbidden")
    if re.search(r"(?i)data\s*:\s*audio\s*/|\baudio\s*[/=:]|"
                 r"\b(?:raw[ _-]*(?:audio|voice)|(?:audio|voice)[ _-]*(?:blob|data|base64|bytes|recording|note|memo|transcript))\b|"
                 r"(?:^|\s)(?:RIFF|OggS|fLaC|ID3)|\b(?:UklGR|T2dnUw|ZkxhQw|SUQz)[a-z0-9+/=]*|"
                 r"[a-z0-9+/]{80,}={0,2}", value):
        raise ContextError("raw audio content forbidden")
    # Acceptance of a fact is never an approval to send. Conservatively deny
    # approval/action language in either order, including across line breaks.
    send_action = re.compile(r"(?i)\b(?:send\w*|sent|deliver\w*|outbound|publish\w*|post\w*|"
                             r"email\w*|message\w*|ship\w*)\b")
    send_approval = re.compile(r"(?i)\b(?:approv\w*|authoriz\w*|authoris\w*|consent\w*|permission|"
                                 r"go[ -]?ahead|green[ -]?light|okay|ok|yes|confirm\w*|permit\w*|allow\w*|"
                                 r"lgtm|jeff said)\b")
    if send_approval.search(language) and send_action.search(language):
        raise ContextError("send approval assertions forbidden")
    if re.search(r"(?i)\b(?:send|message)\s+it\s+to\s+the\s+band\b", language):
        raise ContextError("send approval assertions forbidden")
    if re.search(r"(?i)\bgo\s+ahead\s+and\s+message\b", language):
        raise ContextError("send approval assertions forbidden")
    return body


def validate_fact(fact):
    if set(fact) != {"id", "body", "classification", "audience", "provenance"}:
        raise ContextError("unexpected fact fields")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", fact["id"]):
        raise ContextError("invalid fact id")
    if fact["classification"] != "accepted_fact":
        raise ContextError("only accepted facts may enter shared context")
    safe_fact(fact["body"])
    if not fact["audience"] or not set(fact["audience"]) <= BOTS:
        raise ContextError("invalid visibility")
    source = fact["provenance"]
    if set(source) != {"kind", "uri", "sha256", "accepted_by", "accepted_at"}:
        raise ContextError("provenance required")
    if source["kind"] not in {"accepted_memory", "reviewed_fact"}:
        raise ContextError("texts, credentials and raw voice are forbidden sources")
    if not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
        raise ContextError("source digest required")
    if not all(isinstance(source[k], str) and 0 < len(source[k]) <= 300 for k in ("uri", "accepted_by", "accepted_at")):
        raise ContextError("source identity and acceptance required")
    if not source["uri"].startswith(("memory/", "user-memory/", "review:")):
        raise ContextError("unreviewed source")
    # Provenance is also persisted/shared; it cannot smuggle excluded payloads.
    safe_fact(fact["id"])
    for key in ("uri", "accepted_by", "accepted_at"):
        safe_fact(source[key])


class SharedContext:
    def __init__(self, path, bot):
        if bot not in BOTS:
            raise ContextError("unknown bot")
        self.path, self.bot = Path(path), bot
        # Deployment must provision the coord-owned directory, not arbitrary paths.
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise ContextError("store directory unavailable")
        with self.transaction() as db:
            db.executescript(SCHEMA)
        self.path.chmod(0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def propose_fact(self, fact):
        """Return a review candidate; unaccepted text is NOT persisted or shared."""
        validate_fact(fact)
        return {"status": "needs_acceptance", "digest": digest(fact), "candidate": fact}

    def read_context(self, limit=30):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ContextError("bounded context required")
        with self.transaction() as db:
            rows = db.execute("""SELECT f.* FROM facts f JOIN
                (SELECT id, MAX(revision) revision FROM facts GROUP BY id) latest
                ON f.id=latest.id AND f.revision=latest.revision
                WHERE f.forgotten=0 ORDER BY f.at DESC, f.id""").fetchall()
        return [self._fact(row) for row in rows if self.bot in json.loads(row["audience"])][:limit]

    @staticmethod
    def _fact(row):
        return {"id": row["id"], "revision": row["revision"], "body": row["body"],
                "provenance": json.loads(row["provenance"]), "at": row["at"],
                "classification": "accepted_fact", "execution_authority": False}

    def post_message(self, message_id, recipient, topic, fact_ids):
        """Typed notifications contain accepted fact references, never raw messages.

        Caller supplies a stable id for replay. Retry must have identical content.
        """
        if recipient not in BOTS or topic not in {"context_updated", "review_requested", "result_available"}:
            raise ContextError("invalid message address or topic")
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,100}", message_id) or not 1 <= len(fact_ids) <= 20:
            raise ContextError("invalid message identity or references")
        safe_fact(message_id)
        refs = json.dumps(sorted(set(fact_ids)))
        with self.transaction() as db:
            for fact_id in fact_ids:
                row = db.execute("SELECT * FROM facts WHERE id=? ORDER BY revision DESC LIMIT 1", (fact_id,)).fetchone()
                if not row or row["forgotten"] or not {self.bot, recipient} <= set(json.loads(row["audience"])):
                    raise ContextError("unaccepted or private reference")
            prior = db.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            identity = (self.bot, recipient, topic, refs)
            if prior:
                if tuple(prior[k] for k in ("sender", "recipient", "topic", "refs")) != identity:
                    raise ContextError("message id reused with different content")
                return message_id
            pending = db.execute("SELECT COUNT(*) FROM messages WHERE recipient=? AND acked=0", (recipient,)).fetchone()[0]
            if pending >= INBOX_CAP:
                raise ContextError("recipient inbox is full; acknowledge pending messages first")
            db.execute("INSERT INTO messages(id,sender,recipient,topic,refs,at) VALUES (?,?,?,?,?,?)",
                       (message_id, *identity, time.time()))
        return message_id

    def read_inbox(self, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ContextError("bounded inbox required")
        with self.transaction() as db:
            rows = db.execute("""SELECT m.*, e.state, e.receipt FROM messages m
                LEFT JOIN effects e ON e.message_id=m.id
                WHERE m.recipient=? AND m.acked=0 ORDER BY m.at,m.id LIMIT ?""", (self.bot, limit)).fetchall()
            visible = {}
            for fact_id in {f for row in rows for f in json.loads(row["refs"])}:
                fact = db.execute("SELECT * FROM facts WHERE id=? ORDER BY revision DESC LIMIT 1", (fact_id,)).fetchone()
                if fact and not fact["forgotten"] and self.bot in json.loads(fact["audience"]):
                    visible[fact_id] = self._fact(fact)
        return [{"id": r["id"], "sender": r["sender"], "topic": r["topic"],
                 "facts": [visible[f] for f in json.loads(r["refs"]) if f in visible],
                 "effect_state": r["state"], "receipt": r["receipt"],
                 "execution_authority": False} for r in rows]

    def _message(self, db, message_id):
        row = db.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
        if not row or row["recipient"] != self.bot:
            raise ContextError("only recipient may consume message")
        return row

    def ack_message(self, message_id):
        with self.transaction() as db:
            self._message(db, message_id)
            db.execute("UPDATE messages SET acked=1 WHERE id=?", (message_id,))

    def begin_effect(self, message_id):
        """Trusted executor only. Persist uncertainty BEFORE an external effect.

        This grants no permission: executor must separately enforce consent and
        ownership. A crash/lost response requires reconciliation, never retry.
        """
        with self.transaction() as db:
            row = self._message(db, message_id)
            if row["acked"]:
                return False
            prior = db.execute("SELECT state FROM effects WHERE message_id=?", (message_id,)).fetchone()
            if prior:
                return False
            db.execute("INSERT INTO effects(message_id,state) VALUES (?, 'uncertain')", (message_id,))
        return True

    def complete_effect(self, message_id, receipt_id):
        if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,200}", receipt_id):
            raise ContextError("receipt identifier only; no raw effect payload")
        safe_fact(receipt_id)
        with self.transaction() as db:
            self._message(db, message_id)
            row = db.execute("SELECT * FROM effects WHERE message_id=?", (message_id,)).fetchone()
            if not row or (row["state"] == "complete" and row["receipt"] != receipt_id):
                raise ContextError("missing or conflicting effect receipt")
            db.execute("UPDATE effects SET state='complete',receipt=? WHERE message_id=?", (receipt_id, message_id))


@dataclass(frozen=True)
class VerifiedAcceptance:
    """Trusted verifier result, derived from an authenticated approval receipt.

    This object is not a caller-provided receipt and is never an MCP argument.
    """
    accepted_by: str
    accepted_at: str


class AcceptedWriter:
    """Host-only ingress. NEVER expose this object as a bot/model MCP tool.

    verify_acceptance must check a current, exact-payload receipt from the existing
    memory approval service and return VerifiedAcceptance from that receipt.
    Boolean success is insufficient: provenance requires the verified principal
    and acceptance time. No default accept-all implementation is supplied.
    """
    def __init__(self, store, verify_acceptance):
        if not callable(verify_acceptance):
            raise ContextError("trusted acceptance verifier required")
        self.store, self.verify = store, verify_acceptance

    def _acceptance(self, payload, receipt):
        accepted = self.verify(digest(payload), receipt)
        if not isinstance(accepted, VerifiedAcceptance):
            raise ContextError("missing or stale acceptance")
        for value in (accepted.accepted_by, accepted.accepted_at):
            if not isinstance(value, str) or not value.strip() or len(value) > 300:
                raise ContextError("verified acceptance identity and time required")
            safe_fact(value)
        try:
            dt.datetime.fromisoformat(accepted.accepted_at)
        except ValueError:
            raise ContextError("invalid verified acceptance time") from None
        return accepted

    def put(self, fact, expected_revision, receipt):
        # Snapshot before verification so mutations cannot change approved data.
        fact = copy.deepcopy(fact)
        validate_fact(fact)
        payload = {"operation": "put", "fact": fact, "expected_revision": expected_revision}
        accepted = self._acceptance(payload, receipt)
        fact["provenance"]["accepted_by"] = accepted.accepted_by
        fact["provenance"]["accepted_at"] = accepted.accepted_at
        with self.store.transaction() as db:
            row = db.execute("SELECT MAX(revision) FROM facts WHERE id=?", (fact["id"],)).fetchone()
            revision = row[0] or 0
            if type(expected_revision) is not int or revision != expected_revision:
                raise ContextError("stale correction")
            db.execute("UPDATE facts SET body=NULL WHERE id=?", (fact["id"],))
            db.execute("INSERT INTO facts VALUES (?,?,?,?,?,?,0)",
                       (fact["id"], revision + 1, fact["body"], json.dumps(fact["provenance"]),
                        json.dumps(sorted(set(fact["audience"]))), time.time()))
        return revision + 1

    def forget(self, fact_id, expected_revision, receipt):
        payload = {"operation": "forget", "id": fact_id, "expected_revision": expected_revision}
        self._acceptance(payload, receipt)
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM facts WHERE id=? ORDER BY revision DESC LIMIT 1", (fact_id,)).fetchone()
            if not row or row["revision"] != expected_revision:
                raise ContextError("stale forget")
            # Remove bodies in history; retain revision and source receipts only.
            db.execute("UPDATE facts SET body=NULL WHERE id=?", (fact_id,))
            db.execute("INSERT INTO facts VALUES (?,?,NULL,?,?,?,1)",
                       (fact_id, expected_revision + 1, row["provenance"], row["audience"], time.time()))


def import_day_one(store, repo_root, manifest, *, verify_acceptance=None):
    """Exact-line allowlist plus independent receipts; never approve our writes.

    Each manifest item needs a receipt reference checked by the host's verifier.
    The checked-in manifest is a selection of candidates, not an approval.
    """
    writer = AcceptedWriter(store, verify_acceptance)
    root = Path(repo_root).resolve()
    imported = []
    for item in manifest:
        relative = Path(item["path"])
        if not relative.parts or relative.parts[0] not in {"memory", "user-memory"} or relative.name != "profile.md":
            raise ContextError("only selected profile facts may be imported")
        path = root / relative
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ContextError("unsafe import path")
        lines = path.read_text().splitlines()
        if type(item["line"]) is not int or not 1 <= item["line"] <= len(lines):
            raise ContextError("import line must be within the source document")
        line = lines[item["line"] - 1]
        if hashlib.sha256(line.encode()).hexdigest() != item["line_sha256"]:
            raise ContextError("source changed; review import again")
        match = re.fullmatch(r"- \((\d{4}-\d{2}-\d{2})\) (.+)", line)
        if not match or match[2] != item["body"]:
            raise ContextError("accepted profile fact mismatch")
        fact = {"id": item["id"], "body": item["body"], "classification": "accepted_fact",
                "audience": sorted(BOTS), "provenance": {"kind": "accepted_memory",
                "uri": item["path"] + "#L" + str(item["line"]), "sha256": item["line_sha256"],
                "accepted_by": "grok-bot-profile", "accepted_at": match[1]}}
        with store.transaction() as db:
            prior = db.execute("SELECT * FROM facts WHERE id=? ORDER BY revision DESC LIMIT 1", (fact["id"],)).fetchone()
        if prior:
            # Corrections/tombstones are authoritative; import never revives them.
            continue
        writer.put(fact, 0, item.get("receipt"))
        imported.append(fact["id"])
    return imported

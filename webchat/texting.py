"""Owner-only texting: bounded BlueBubbles reads and exact, unsent draft cards.

Andrea's installed control API has no send capability. Do not translate a Web
Bob approval into a forged Telegram/self-thread message or a BlueBubbles send.
BlueBubbles methods use an explicit read allowlist, including chat/query. Only
Andrea's separate Web Bob bridge is probed after durable, exact owner consent.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

CONFIRM_SECONDS = 300
MAX_RESPONSE = 2 * 1024 * 1024
HELP = ("I can read recent texts and keep replies as drafts. Try ‘texts’, "
        "‘read texts from Alex’, ‘summarize texts from Alex’, or "
        "‘draft reply to Alex: I’ll be there at 6.’ Review the recipient and body, "
        "then send the card’s exact yes + token as a separate chat message. "
        "Andrea’s current bridge cannot accept sends from Web Bob; drafts stay unsent.")
BRIDGE_BLOCKED = ("Not sent. Your confirmation was recorded here, but Andrea’s current "
                  "control API does not accept sends or owner approvals from Web Bob. "
                  "Ask Andrea for a fresh recipient-bound draft in its registered owner "
                  "chat and approve that card there. This Web Bob confirmation cannot be reused.")
SENT_VIA_ANDREA = "Sent via Andrea’s BlueBubbles bridge."
DELIVERY_UNCONFIRMED = ("Confirmation recorded; delivery is unconfirmed. Check the recipient’s "
                        "thread before preparing another draft. This confirmation cannot be reused.")


class TextingError(Exception):
    """A safe, owner-facing error; never include response bodies or credential URLs."""

    def __init__(self, message, *, status=None):
        super().__init__(message)
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise TextingError("The local messaging service redirected the request; nothing was sent.")


def local_url(value):
    try:
        parsed = urllib.parse.urlsplit(value)
        valid = (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                 and parsed.port and 0 < parsed.port < 65536
                 and not parsed.username and not parsed.password
                 and parsed.path in ("", "/") and not parsed.query and not parsed.fragment)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise TextingError("Messaging must use an exact http://127.0.0.1:port address.")
    return value.rstrip("/")


def request_json(base, path, *, data=None, headers=None, timeout=5):
    # No environment proxies, redirects, retries, or URL supplied by a chat.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(local_url(base) + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise TextingError("The messaging response was too large. Try a smaller thread.")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("expected object")
        return result
    except TextingError:
        raise
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise TextingError("Local messaging authentication failed. Nothing was sent.", status=exc.code) from None
        raise TextingError("The local messaging service rejected the request. Nothing was sent.", status=exc.code) from None
    except (OSError, ValueError, UnicodeError):
        raise TextingError("Local messaging is unavailable or returned invalid data. Nothing was sent.") from None


class BlueBubbles:
    def __init__(self, config_db=None):
        self.config_db = Path(config_db or os.environ.get("BOB_BLUEBUBBLES_CONFIG_DB") or
                              Path.home() / "Library/Application Support/bluebubbles-server/config.db")

    def _read(self, path, data=None, params=None):
        if not (path == "/chat/query" and data is not None or
                re.fullmatch(r"/chat/[^/]+/message", path) and data is None):
            raise TextingError("That BlueBubbles operation is not a permitted read.")
        try:
            with closing(sqlite3.connect(self.config_db.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                cfg = dict(connection.execute("SELECT name, value FROM config WHERE name IN ('password', 'socket_port')"))
            password = cfg.get("password")
            port = int(cfg.get("socket_port") or 1234)
            if not isinstance(password, str) or not password or not 0 < port < 65536:
                raise ValueError("missing config")
        except (sqlite3.Error, OSError, ValueError, TypeError):
            raise TextingError("BlueBubbles read configuration is unavailable. Nothing was sent.") from None
        query = urllib.parse.urlencode({"password": password, **(params or {})})
        # Large recent-thread queries can exceed five seconds while Messages is
        # syncing. Reads get a bounded longer budget; sends retain their original
        # timeout and are never retried after an uncertain delivery outcome.
        result = request_json(f"http://127.0.0.1:{port}", "/api/v1" + path + "?" + query, data=data, timeout=12)
        rows = result.get("data")
        if result.get("status", 200) != 200 or not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise TextingError("BlueBubbles returned an invalid read response. Nothing was sent.")
        return rows

    def chats(self):
        chats = self._read("/chat/query", {"limit": 200, "offset": 0,
                          "with": ["participants", "lastMessage"], "sort": "lastmessage"})[:200]
        if any(not isinstance(c.get("guid"), str) or not c["guid"] or len(c["guid"]) > 500 or
               not isinstance(c.get("participants") or [], list) for c in chats):
            raise TextingError("BlueBubbles returned invalid thread details. Nothing was sent.")
        return chats

    def messages(self, guid):
        return self._read("/chat/" + urllib.parse.quote(guid, safe="") + "/message",
                          params={"limit": 30, "sort": "DESC"})[:30]


class Andrea:
    """Authenticated control health and an optional owner-approved Web Bob bridge."""
    def __init__(self, base=None, token=None):
        self.base = base or os.environ.get("BOB_ANDREA_CONTROL_URL", "http://127.0.0.1:4315")
        self.token = token if token is not None else os.environ.get("BOB_ANDREA_CONTROL_TOKEN", "")

    def status(self):
        if not self.token:
            return "Andrea control access is not configured for this Web Bob instance."
        result = request_json(self.base, "/health", headers={"Authorization": "Bearer " + self.token})
        if result.get("service") != "bluebubbles-control" or result.get("ok") is not True:
            raise TextingError("Andrea did not return a recognized control-service response.")
        return ("Andrea’s control service is reachable. " +
                ("Its BlueBubbles channel is connected." if result.get("connected") is True else
                 "Its BlueBubbles channel is unavailable."))

    def deliver(self, chat_guid, body):
        """Return True for delivery, False for rejection, or None for an unknown outcome."""
        if not self.token or not isinstance(chat_guid, str) or not chat_guid or not isinstance(body, str) or not body.strip():
            return False
        try:
            result = request_json(self.base, "/web-bob/send",
                                  data={"chatGuid": chat_guid, "text": body},
                                  headers={"Authorization": "Bearer " + self.token})
        except TextingError as exc:
            # Auth or an absent endpoint rejects the handoff. A lost response or
            # server error may follow delivery, so it cannot prove "not sent".
            return False if exc.status in (401, 403, 404, 405) else None
        guid = result.get("messageGuid")
        return True if result.get("ok") is True and isinstance(guid, str) and guid.strip() else None


def fingerprint(draft):
    return hashlib.sha256(json.dumps([draft[k] for k in
        ("id", "conversation_id", "recipient", "body", "revision")],
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def label(chat):
    return str(chat.get("displayName") or chat.get("name") or chat.get("guid") or "Unnamed thread")


def recipient(chat):
    guid = chat.get("guid")
    people = chat.get("participants")
    if not isinstance(guid, str) or not guid or len(guid) > 500:
        raise TextingError("This thread has no valid identifier.")
    addresses = sorted({p["address"] for p in (people or []) if isinstance(p, dict)
                        and isinstance(p.get("address"), str) and p["address"]}) if isinstance(people, list) else []
    if not addresses or any(len(p) > 320 for p in addresses):
        raise TextingError("I could not verify this thread’s recipients. No draft was prepared.")
    return {"guid": guid, "name": label(chat), "addresses": addresses}


def timestamp(message):
    try:
        value = float(message.get("dateCreated") or 0)
        return value if 0 <= value <= 4102444800000 else 0
    except (ValueError, TypeError):
        return 0


def time_label(message):
    value = timestamp(message)
    return datetime.fromtimestamp(value / 1000, timezone.utc).strftime("%b %d %H:%M UTC") if value else "Time unknown"


class Texting:
    def __init__(self, bluebubbles=None, andrea=None, clock=time.time):
        self.bluebubbles = bluebubbles or BlueBubbles()
        self.andrea = andrea or Andrea()
        self.clock = clock
        self.epoch = secrets.token_hex(16)

    def invalidate(self, conversation, state="superseded"):
        for draft in conversation.get("_texting", {}).get("drafts", {}).values():
            if draft["state"] in ("pending", "editing"):
                draft.update(state=state, token=None)

    def public(self, conversation):
        value = copy.deepcopy(conversation)
        state = value.pop("_texting", {})
        drafts = state.get("drafts", {})
        for message in value["messages"]:
            draft = drafts.get(message.get("text_draft_id"))
            if not draft:
                continue
            card = {key: copy.deepcopy(draft[key]) for key in
                    ("id", "recipient", "body", "revision", "state", "expires_at")}
            if card["state"] == "pending" and (draft["epoch"] != self.epoch or self.clock() >= draft["expires_at"]):
                card["state"] = "expired"
            card["confirm_message"] = "yes " + draft["token"] if card["state"] == "pending" else None
            message["text_draft"] = card
        return value

    @staticmethod
    def provider_view(conversation):
        value = copy.deepcopy(conversation)
        value.pop("_texting", None)
        if any(m.get("texting") for m in value["messages"]):
            value["title"] = "Conversation with private texting history"
        # Thread contents, phone numbers and confirmation tokens stay out of model context.
        value["messages"] = [m for m in value["messages"] if not m.get("texting")]
        return value

    def resolve(self, query):
        chats = self.bluebubbles.chats()
        exact = [c for c in chats if query == c.get("guid")]
        matches = exact or [c for c in chats if label(c).casefold() == query.casefold() or
                           query in [p.get("address") for p in (c.get("participants") or []) if isinstance(p, dict)]]
        matches = matches or [c for c in chats if query.casefold() in label(c).casefold()]
        if not matches:
            raise TextingError("No matching thread in the 200 most recent threads. Try ‘texts’ and use an exact thread ID.")
        if len(matches) != 1:
            choices = "\n".join(f"• {label(c)} — {c.get('guid', '?')}" for c in matches[:10])
            raise TextingError("Several threads match. Use an exact thread ID; I won’t choose a recipient for you.\n" + choices)
        return matches[0]

    def draft(self, conversation, target, body, actor, request_id):
        if not actor:
            raise TextingError("Log in again before preparing a confirmation-bound text draft.")
        if not body.strip() or len(body) > 4000:
            raise TextingError("Write a text body between 1 and 4,000 characters.")
        state = conversation.setdefault("_texting", {"drafts": {}, "audit": []})
        self.invalidate(conversation)
        identifier = secrets.token_hex(8)
        draft = dict(id=identifier, conversation_id=conversation["id"], recipient=target, body=body,
                     revision=len(state["drafts"]) + 1, state="pending", token="wbtxt-" + secrets.token_hex(16),
                     created_at=self.clock(), expires_at=self.clock() + CONFIRM_SECONDS, epoch=self.epoch,
                     actor=actor, request_id=request_id)
        draft["fingerprint"] = fingerprint(draft)
        state["drafts"][identifier] = draft
        state["active"] = identifier
        conversation["messages"][-1]["text_draft_id"] = identifier
        return "Draft ready for review. Nothing sent."

    def confirm(self, conversation, text, actor, request_id, persist):
        state = conversation.get("_texting", {})
        draft = state.get("drafts", {}).get(state.get("active"))
        match = re.fullmatch(r"yes (wbtxt-[0-9a-f]{32})", text, re.I)
        if not draft or not match:
            if text.lower().startswith("yes wbtxt-"):
                self.invalidate(conversation)
            return "Nothing sent. Review a fresh text draft and send its exact ‘yes wbtxt-…’ message separately in this chat."
        if draft["state"] != "pending":
            return "Nothing sent. That text confirmation was already used, cancelled, or replaced. Review a fresh draft."
        if draft["epoch"] != self.epoch or self.clock() >= draft["expires_at"]:
            draft.update(state="expired", token=None)
            return "Nothing sent. That text confirmation expired. Review a fresh draft."
        # The draft-creation request cannot also authorize delivery: the owner
        # must review the card and submit its exact token in a later request.
        if (not actor or not hmac.compare_digest(actor, draft["actor"]) or
                request_id == draft["request_id"] or draft["conversation_id"] != conversation["id"] or
                not hmac.compare_digest(match[1], draft["token"]) or
                not hmac.compare_digest(fingerprint(draft), draft["fingerprint"])):
            return "Nothing sent. This yes does not match the exact draft and login that presented it. Review a fresh draft."
        # Save consumed consent before any handoff. Never replay on restart/error.
        draft.update(state="delivery_unconfirmed", token=None, approved_at=self.clock())
        audit = {"event": "owner_confirmed_delivery_unconfirmed", "actor": actor,
                 "conversation_id": conversation["id"], "draft_id": draft["id"], "revision": draft["revision"],
                 "recipient": copy.deepcopy(draft["recipient"]), "body": draft["body"],
                 "fingerprint": draft["fingerprint"], "at": self.clock(), "request_id": request_id}
        state["audit"].append(audit)
        conversation["messages"][-1].update(status="done", provider="texting", content=DELIVERY_UNCONFIRMED)
        persist(conversation)
        delivered = self.andrea.deliver(draft["recipient"]["guid"], draft["body"])
        if delivered is True:
            draft["state"] = "sent"
            audit["event"] = "owner_sent_via_andrea"
            content = SENT_VIA_ANDREA
        elif delivered is False:
            draft["state"] = "confirmed_not_sent"
            audit["event"] = "owner_confirmed_not_sent"
            content = BRIDGE_BLOCKED
        else:
            content = DELIVERY_UNCONFIRMED
        return content

    def handle(self, conversation, text, actor, request_id, persist, redact):
        state = conversation.get("_texting", {})
        active = state.get("drafts", {}).get(state.get("active"))
        clean = re.sub(r"^(?:please |can you |could you )", "", text, flags=re.I).strip()
        # A worker/job prefix is not a way around the texting gate. Only matching
        # texting commands use this stripped value; other work keeps normal routing.
        clean = re.sub(r"^(?:(?:ask|have|tell|use) (?:codex|claude|cursor|gemini|minimax|mini)(?: to)?\s+|"
                       r"start (?:a )?job:\s*|(?:codex|claude|cursor|gemini|minimax|mini):\s*)", "", clean, flags=re.I)
        command = clean.casefold().rstrip(".?!")
        text_context = active and (active["state"] in ("pending", "editing") or
            len(conversation["messages"]) >= 3 and conversation["messages"][-3].get("texting"))
        # Bare approvals are routed here for token guidance only; confirm() still
        # requires the entire message to match the exact yes + token format.
        confirmation = re.match(r"^yes\s+wbtxt-", clean, re.I) or (text_context and command in ("yes", "ok", "send it", "send it now", "send now", "go", "do it"))
        edit = re.fullmatch(r"(edit|cancel) text draft ([0-9a-f]{16})", clean, re.I)
        replace = re.fullmatch(r"replace text draft ([0-9a-f]{16}) to (.+?):\s*([\s\S]+)", clean, re.I)
        compose = re.fullmatch(r"(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)(?: reply)? to (.+?)(?::\s*| saying )([\s\S]+)", clean, re.I)
        compose = compose or re.fullmatch(r"text (.+?):\s*([\s\S]+)", clean, re.I)
        read = re.fullmatch(r"(read|show|summari[sz]e) (?:the )?(?:recent )?(?:texts?|messages?|imessages?|sms|thread) (?:from |with |in |for )?(.+)", clean, re.I)
        listing = command in ("texts", "list texts", "show texts", "recent texts", "show recent texts", "list recent texts", "summarize recent texts", "summarize texts")
        # Incomplete texting commands only — not colloquial chat like “text me when you're free”.
        help_request = command in ("texting", "texting help", "texting status") or re.match(
            r"^(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)\b", clean, re.I
        )
        cancel = active and command in ("cancel text", "cancel text draft", "never mind", "cancel")
        if not any((confirmation, edit, replace, compose, read, listing, help_request, cancel)):
            # An intervening turn also withdraws consent, including unsupported edits.
            self.invalidate(conversation)
            return False
        conversation["messages"][-2]["texting"] = True
        answer = conversation["messages"][-1]
        answer.update(texting=True, provider="texting", status="done")
        try:
            if confirmation:
                # The chat turn itself must be yes + token, never a command prefix
                # or quoted/embedded approval extracted from another request.
                content = self.confirm(conversation, text, actor, request_id, persist)
            elif cancel:
                self.invalidate(conversation, "cancelled")
                content = "Text draft cancelled. Nothing sent."
            elif edit:
                draft = state.get("drafts", {}).get(edit[2])
                if not draft or state.get("active") != draft["id"] or draft["state"] not in ("pending", "expired", "editing", "confirmed_not_sent"):
                    raise TextingError("That draft is no longer current. Prepare a fresh text draft.")
                draft.update(state="editing" if edit[1].lower() == "edit" else "cancelled", token=None)
                content = "Confirmation cleared. Edit the draft card, then review it again." if draft["state"] == "editing" else "Text draft cancelled. Nothing sent."
            elif replace or compose:
                # Even a failed/ambiguous edit withdraws the previous confirmation.
                self.invalidate(conversation)
                if replace:
                    if not active or replace[1] != active["id"]:
                        raise TextingError("That draft is no longer current. Prepare a fresh text draft.")
                    query, body = replace[2], replace[3]
                else:
                    query, body = compose[1], compose[2]
                target = recipient(self.resolve(query.strip()))
                if redact(json.dumps(target, ensure_ascii=False)) != json.dumps(target, ensure_ascii=False):
                    raise TextingError("The thread details contain sensitive credentials; no draft was prepared.")
                content = self.draft(conversation, target, body, actor, request_id)
            else:
                self.invalidate(conversation)
                if listing:
                    chats = self.bluebubbles.chats()[:20]
                    content = "Recent text threads (up to 20):\n" + ("\n".join(
                        f"• {label(c)} — {c.get('guid', '?')}\n  {str((c.get('lastMessage') if isinstance(c.get('lastMessage'), dict) else {}).get('text') or '[No text preview]')[:180]}"
                        for c in chats) or "No recent threads.")
                elif read:
                    chat = self.resolve(read[2].strip())
                    messages = sorted(self.bluebubbles.messages(chat["guid"]), key=timestamp)
                    content = f"{label(chat)} — {chat['guid']}\n"
                    if not messages:
                        content += "No recent messages in this thread."
                    elif read[1].lower().startswith("summari"):
                        incoming = sum(m.get("isFromMe") is not True for m in messages)
                        content += (f"Recent thread summary: {len(messages)} messages, {incoming} incoming and "
                                    f"{len(messages) - incoming} from you.\n"
                                    f"Window: {time_label(messages[0])} – {time_label(messages[-1])}.\n"
                                    "Latest messages:\n")
                        content += "\n".join(self.message_line(m, 400) for m in messages[-4:])
                    else:
                        content += "Last 30 messages at most, oldest first:\n" + "\n".join(self.message_line(m, 1200) for m in messages)
                elif command == "texting status":
                    content = self.andrea.status() + " Web Bob delivery is blocked: Andrea requires approval in its registered owner chat."
                else:
                    content = HELP
        except TextingError as exc:
            content = str(exc)
        answer["content"] = redact(content)
        # Every handled turn is saved once here. Confirmations also persist consumed
        # consent before delivery so an interrupted receipt cannot authorize a replay.
        persist(conversation)
        return True

    @staticmethod
    def message_line(message, limit):
        handle = message.get("handle")
        sender = "You" if message.get("isFromMe") is True else str((handle.get("address") if isinstance(handle, dict) else None) or "Contact")
        body = str(message.get("text") or "[Attachment or non-text message]")
        return f"• {time_label(message)} · {sender}: {body[:limit]}" + ("… [excerpt]" if len(body) > limit else "")

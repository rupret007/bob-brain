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
import math
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
        "Direct-recipient sends use Andrea’s configured owner bridge. A missing delivery receipt means delivery is unconfirmed; "
        "use Check delivery on the draft to inspect it without resending. Instinct is always read-only.")
BRIDGE_BLOCKED = ("Not sent. Your confirmation was recorded here, but Andrea’s "
                  "owner bridge could not accept this exact draft. "
                  "Ask Andrea for a fresh recipient-bound draft in its registered owner "
                  "chat and approve that card there. This Web Bob confirmation cannot be reused.")
SENT_VIA_ANDREA = "Sent via Andrea. Messages reports sent; delivery is not confirmed."
SUBMITTED_VIA_ANDREA = "Submitted to Messages via Andrea. Delivery is not confirmed. Use Check delivery to inspect it without resending."
DELIVERED_VIA_ANDREA = "Messages reports this text delivered."
FAILED_VIA_ANDREA = "Messages reports this text failed. Nothing was resent. Any new send needs a fresh draft and your confirmation."
DELIVERY_UNCONFIRMED = ("Confirmation recorded; delivery is unconfirmed. Use Check delivery on this draft "
                        "to look for Andrea’s receipt without resending. This confirmation cannot be reused.")
DELIVERY_STATES = ('delivery_unconfirmed', 'submitted', 'sent', 'delivered', 'delivery_failed')


def delivery_reply(draft):
    state = draft['state']
    # Historical sent records only proved submission. Do not grandfather them
    # into transport confirmation when a conversation is reopened after upgrade.
    if state == 'sent' and not draft.get('transport_verified'):
        state = 'submitted'
    return {'submitted': SUBMITTED_VIA_ANDREA, 'sent': SENT_VIA_ANDREA,
            'delivered': DELIVERED_VIA_ANDREA, 'delivery_failed': FAILED_VIA_ANDREA}.get(state, DELIVERY_UNCONFIRMED)


def consumed_delivery_reply(draft):
    """An approval or cancellation cannot undo a handoff or establish its outcome."""
    if draft and draft['state'] in DELIVERY_STATES:
        outcome = ('Delivery remains unconfirmed. Use Check delivery; it never resends.'
                   if draft['state'] == 'delivery_unconfirmed' else delivery_reply(draft))
        return 'That text confirmation was already used. ' + outcome + ' Nothing was resent.'
    return None


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
        # syncing. Reads get a bounded budget; confirmations have their own
        # bounded receipt wait and are never retried after an uncertain outcome.
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

    def exact_chat(self, guid):
        # The recent list is a browsing window, not an identity directory.
        # BlueBubbles supports a GUID filter on this same read-only endpoint.
        chats = self._read("/chat/query", {"guid": guid, "limit": 2, "offset": 0,
                                         "with": ["participants"]})
        if len(chats) > 1 or any(c.get("guid") != guid for c in chats):
            raise TextingError("BlueBubbles did not verify the exact thread. Nothing was sent.")
        if chats:
            recipient(chats[0])  # Require returned metadata; never infer recipients from the GUID.
        return chats


class Andrea:
    """Dedicated owner bridge; never use Andrea's read/control credentials."""
    def __init__(self, base=None, token=None):
        self.base, self.token = base or "http://127.0.0.1:4316", token or ""
        if base is None and token is None:
            config_path = os.environ.get("BOB_ANDREA_WEBBOB_CONFIG")
            if config_path:
                try:
                    path = Path(config_path)
                    if not path.is_absolute() or path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_size > 24000:
                        raise ValueError("private config required")
                    cfg = json.loads(path.read_text())
                    self.base = local_url(cfg["url"])
                    if not isinstance(cfg["token"], str) or len(cfg["token"]) < 32:
                        raise ValueError("dedicated token required")
                    self.token = cfg["token"]
                except (OSError, ValueError, KeyError, TypeError, TextingError):
                    self.token = ""

    def call(self, route, payload=None):
        return request_json(self.base, "/web-bob/v1/" + route, data=payload,
                            headers={"Authorization": "Bearer " + self.token},
                            timeout=20 if route == "confirm" else 15 if route == "draft" else 5)

    @staticmethod
    def scope(draft):
        def canonical(address):
            value = address.strip().lower()
            if "@" in value:
                return value
            digits = re.sub(r"\D", "", value)
            return "+" + ("1" if len(digits) == 10 else "") + digits
        return dict(issuer="web-bob", audience="andrea", actor=draft["actor"],
                    conversationId=draft["conversation_id"], epoch=draft["epoch"],
                    draftId=draft["id"], revision=draft["revision"], draftRequestId=draft["request_id"],
                    chatGuid=draft["recipient"]["guid"],
                    addresses=[canonical(a) for a in draft["recipient"]["addresses"]], text=draft["body"])

    @staticmethod
    def scope_digest(scope):
        return hashlib.sha256(json.dumps(scope, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    def prepare(self, draft):
        if not self.token:
            return None
        scope = self.scope(draft)
        try:
            result = self.call("draft", scope)
        except TextingError:
            return None  # No send endpoint is called while preparing a draft.
        if (result.get("ok") is not True or result.get("digest") != self.scope_digest(scope) or
                not re.fullmatch(r"[a-f0-9]{64}", str(result.get("draftId", ""))) or
                not re.fullmatch(r"wbtxt-[a-f0-9]{32}", str(result.get("challenge", ""))) or
                not isinstance(result.get("actionId"), str) or not result["actionId"] or
                not isinstance(result.get("expiresAt"), (int, float)) or
                not time.time() * 1000 < result["expiresAt"] <= (time.time() + CONFIRM_SECONDS + 5) * 1000):
            return None
        return result

    def cancel(self, draft):
        remote = draft.get("bridge")
        if not remote or not self.token:
            return
        try:
            self.call("cancel", {**self.scope(draft), "bridgeDraftId": remote["draftId"]})
        except TextingError:
            pass  # Local consent is revoked regardless; the remote challenge expires.

    def status(self):
        if not self.token:
            return "Andrea Web Bob bridge access is not configured. Delivery is blocked."
        result = self.call("health")
        if (result.get("service") != "andrea-web-bob" or result.get("protocol") != 1 or
                result.get("ok") is not True or result.get("instinctReadOnly") is not True):
            raise TextingError("Andrea did not return a recognized owner-bridge response. Delivery is blocked.")
        if result.get("paused") is not False or result.get("connected") is not True:
            return "Andrea’s Web Bob bridge is reachable, but outbound messaging is paused or unavailable. Delivery is blocked."
        return "Andrea’s Web Bob bridge is connected. Review an exact direct-recipient draft and confirm it separately to send. Instinct remains read-only."

    def deliver(self, draft, confirmation, request_id):
        """Return correlated transport state, False for rejection, or None if unknown."""
        remote = draft.get("bridge")
        if not self.token or not remote:
            return False
        scope = self.scope(draft)
        if remote["digest"] != self.scope_digest(scope):
            return False
        try:
            result = self.call("confirm", {**scope, "bridgeDraftId": remote["draftId"],
                "confirmation": confirmation, "confirmationRequestId": request_id,
                "approvedAt": draft["approved_at"] * 1000})
        except TextingError as exc:
            # Auth or an absent endpoint rejects the handoff. A lost response or
            # server error may follow delivery, so it cannot prove "not sent".
            return False if exc.status in (400, 401, 403, 404, 405, 409, 413, 415) else None
        return self.delivery_receipt(draft, result)

    @staticmethod
    def delivery_receipt(draft, result):
        remote = draft['bridge']
        guid = result.get("messageGuid")
        correlated = (result.get("ok") is True and result.get("state") in DELIVERY_STATES and
            result.get("draftId") == remote["draftId"] and result.get("digest") == remote["digest"] and
            result.get("actionId") == remote["actionId"] and isinstance(guid, str) and guid.strip())
        if not correlated:
            return None
        # Version-one bridge receipts attest only submission/action correlation.
        if result.get('deliveryProtocol') != 1:
            return 'submitted'
        evidence = result.get('delivery')
        if result['state'] != 'submitted':
            if (not isinstance(evidence, dict) or evidence.get('state') != result['state'] or
                    type(evidence.get('checkedAt')) not in (int, float) or
                    not math.isfinite(evidence['checkedAt']) or evidence['checkedAt'] <= 0):
                return None
            error = evidence.get('error')
            if (result['state'] in ('sent', 'delivered') and (type(error) is not int or error != 0) or
                    result['state'] == 'delivery_failed' and (type(error) is not int or error <= 0)):
                return None
        return result['state']

    def check_delivery(self, draft):
        """Inspect consumed consent without confirming again; revoke any unconsumed handoff.

        Andrea's bound cancel route returns the same durable receipt for consumed
        drafts. For a still-pending handoff it atomically cancels consent, including
        a confirm handler still waiting on recipient validation. It cannot dispatch.
        """
        remote = draft.get('bridge')
        if not self.token or not remote or remote['digest'] != self.scope_digest(self.scope(draft)):
            return None
        try:
            result = self.call('cancel', {**self.scope(draft), 'bridgeDraftId': remote['draftId']})
        except TextingError:
            return None  # A failed inspection says nothing about delivery.
        if (result.get('ok') is True and result.get('state') == 'cancelled' and
                all(result.get(k) == remote[k] for k in ('draftId', 'digest', 'actionId'))):
            return False
        try:
            result = self.call('status', {**self.scope(draft), 'bridgeDraftId': remote['draftId']})
        except TextingError:
            return None
        if result.get('deliveryRefreshUnavailable'):
            return None
        return self.delivery_receipt(draft, result)


def fingerprint(draft):
    return hashlib.sha256(json.dumps([draft[k] for k in
        ("id", "conversation_id", "recipient", "body", "revision")],
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def label(chat):
    return str(chat.get("displayName") or chat.get("name") or chat.get("guid") or "Unnamed thread")


def recipient_name(query):
    """Normalize conversational wrappers, never an exact transport identifier."""
    name = re.sub(r'^the\s+', '', query.strip(), flags=re.I)
    return re.sub(r'\s+(?:group(?:\s+chat)?|chat|thread)$', '', name, flags=re.I).casefold()


def message_body(body, *, natural=False):
    """Remove trailing instructions to Bob, leaving quoted/literal text alone."""
    hold = (r"(?:please\s+)?(?:don['’]t send(?: it)?(?: yet| for now)?|"
            r"do not send(?: it)?(?: yet| for now)?|hold off (?:on )?sending(?: it)?(?: for now)?|"
            r"(?:just )?(?:keep|save) (?:it|this) as a draft(?: for now)?|"
            r"show me first|for now)")
    # Require a clause boundary: 'We need a drummer for now' is message content.
    pattern = r'(?:\s*[,;.!—–]\s*|\s+(?:but|and)\s+)(?:(?:but|and)\s+)?' + hold + r'[.!\s]*$'
    cleaned = body.strip()
    while True:
        shortened = re.sub(pattern, '', cleaned, flags=re.I).rstrip()
        if shortened == cleaned:
            break
        cleaned = shortened
    if cleaned and (natural or cleaned != body.strip()) and not cleaned.startswith(('"', '“', "'", '‘')):
        cleaned = cleaned[0].upper() + cleaned[1:]
        if cleaned[-1] not in '.!?':
            cleaned += '.'
    return cleaned


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
        from instinct import Instinct
        self.instinct = Instinct(self)

    def invalidate(self, conversation, state="superseded"):
        for draft in conversation.get("_texting", {}).get("drafts", {}).values():
            if draft["state"] in ("pending", "editing"):
                draft.update(state=state, token=None)
                self.andrea.cancel(draft)

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
            card['delivery_available'] = bool(draft.get('bridge')) and card['state'] == 'pending'
            card['check_delivery_message'] = ('check text delivery ' + draft['id']
                if draft.get('bridge') and draft['state'] in DELIVERY_STATES else None)
            if card['state'] == 'sent' and not draft.get('transport_verified'):
                card['state'] = 'submitted'
            if draft.get('read_only') or self.instinct.is_target(draft['recipient']):
                card['read_only'] = True
                card['check_delivery_message'] = None
                if card['state'] == 'pending':
                    card['state'] = 'read_only'
            if card["state"] == "pending" and (draft["epoch"] != self.epoch or self.clock() >= draft["expires_at"]):
                card["state"] = "expired"
            card["confirm_message"] = "yes " + draft["token"] if card["state"] == "pending" and not card.get('read_only') else None
            message["text_draft"] = card
        return value

    @staticmethod
    def provider_view(conversation):
        value = copy.deepcopy(conversation)
        value.pop("_texting", None)
        value.pop("pending_memory_removal", None)
        if any(m.get("texting") for m in value["messages"]):
            value["title"] = "Conversation with private texting history"
        if any(m.get('private_memory') for m in value['messages']):
            value['title'] = 'Conversation with private saved memory'
        # Thread contents, phone numbers and confirmation tokens stay out of model context.
        value["messages"] = [m for m in value["messages"] if not m.get("texting") and not m.get('private_memory')]
        return value

    def resolve(self, query):
        if query.casefold() == "instinct":
            return self.instinct.resolve()
        chats = self.bluebubbles.chats()
        self.instinct.observe(chats)
        exact = [c for c in chats if query == c.get("guid")]
        if not exact and re.fullmatch(r"(?:iMessage|SMS|RCS);[+-];[^\s]{1,480}", query):
            exact = self.bluebubbles.exact_chat(query)
            self.instinct.observe(exact)
            if not exact:
                raise TextingError("No matching thread for that exact thread ID. Nothing was sent.")
        name = recipient_name(query)
        matches = exact or [c for c in chats if recipient_name(label(c)) == name or
                           query in [p.get("address") for p in (c.get("participants") or []) if isinstance(p, dict)]]
        matches = matches or [c for c in chats if name and name in recipient_name(label(c))]
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
        body = self.instinct.prepare_body(target, body)
        if len(body) > 4000:
            raise TextingError("Keep the text, including its Bob via Andrea tag, within 4,000 characters.")
        state = conversation.setdefault("_texting", {"drafts": {}, "audit": []})
        self.invalidate(conversation)
        identifier = secrets.token_hex(8)
        draft = dict(id=identifier, conversation_id=conversation["id"], recipient=target, body=body,
                     revision=len(state["drafts"]) + 1, state="pending", token="wbtxt-" + secrets.token_hex(16),
                     created_at=self.clock(), expires_at=self.clock() + CONFIRM_SECONDS, epoch=self.epoch,
                     actor=actor, request_id=request_id)
        if self.instinct.is_target(target):
            draft.update(state='read_only', token=None, read_only=True)
        else:
            bridge = self.andrea.prepare(draft)
            if bridge:
                draft["bridge"] = {k: bridge[k] for k in ("draftId", "digest", "actionId")}
                draft["token"] = bridge["challenge"]
                draft["expires_at"] = min(draft["expires_at"], bridge["expiresAt"] / 1000)
        draft["fingerprint"] = fingerprint(draft)
        state["drafts"][identifier] = draft
        state["active"] = identifier
        conversation["messages"][-1]["text_draft_id"] = identifier
        from instinct import READ_ONLY
        return (READ_ONLY if draft.get('read_only') else
                f"Draft to {target.get('name') or target.get('guid', 'this recipient')}:\n\n{body}\n\n"
                f"Reply exactly “yes {draft['token']}” in a separate message. "
                f"OK to send this to {target.get('name') or 'this recipient'}?")

    def confirm(self, conversation, text, actor, request_id, persist):
        state = conversation.get("_texting", {})
        draft = state.get("drafts", {}).get(state.get("active"))
        if draft and (draft.get('read_only') or self.instinct.is_target(draft['recipient'])):
            from instinct import READ_ONLY
            draft.update(state='read_only', token=None, read_only=True)
            return READ_ONLY
        consumed = consumed_delivery_reply(draft)
        if consumed:
            return consumed
        match = re.fullmatch(r"yes (wbtxt-[0-9a-f]{32})", text, re.I)
        if not draft or not match:
            if text.lower().startswith("yes wbtxt-"):
                self.invalidate(conversation)
            return "Nothing sent. Review a fresh text draft and send its exact ‘yes wbtxt-…’ message separately in this chat."
        if draft["state"] != "pending":
            return "Nothing sent. That text confirmation was already used, cancelled, or replaced. Review a fresh draft."
        if self.instinct.is_target(draft['recipient'], refresh=True):
            from instinct import READ_ONLY
            draft.update(state='read_only', token=None, read_only=True)
            return READ_ONLY
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
        delivered = self.andrea.deliver(draft, text, request_id)
        if isinstance(delivered, str) and delivered in DELIVERY_STATES:
            draft.update(state=delivered, transport_verified=True)
            audit["event"] = "owner_sent_via_andrea" if delivered == "sent" else "owner_delivery_" + delivered
            content = delivery_reply(draft)
        elif delivered is False:
            draft["state"] = "confirmed_not_sent"
            audit["event"] = "owner_confirmed_not_sent"
            content = BRIDGE_BLOCKED
        else:
            content = DELIVERY_UNCONFIRMED
        return content

    def check_delivery(self, conversation, identifier):
        state = conversation.get('_texting', {})
        draft = state.get('drafts', {}).get(identifier)
        if not draft or draft['state'] not in DELIVERY_STATES:
            return 'No uncertain delivery to check for that draft. Nothing was sent by this check.'
        if draft.get('read_only') or self.instinct.is_target(draft['recipient']):
            from instinct import READ_ONLY
            return READ_ONLY
        delivered = self.andrea.check_delivery(draft)
        if delivered is None:
            return 'Could not refresh delivery status. Last recorded status: ' + delivery_reply(draft)
        draft['state'] = delivered if isinstance(delivered, str) else 'confirmed_not_sent'
        draft['transport_verified'] = isinstance(delivered, str)
        draft['token'] = None
        for audit in state.get('audit', []):
            if audit.get('draft_id') == identifier:
                # Keep the original confirmation event and append later facts.
                audit.setdefault('delivery_checks', []).append(dict(state=draft['state'], at=self.clock()))
        return (delivery_reply(draft) + ' Checked the original message; nothing was resent.'
                if isinstance(delivered, str) else 'Not sent. Andrea cancelled the unconsumed handoff; nothing was resent.')

    @staticmethod
    def confirmation_requested(conversation, clean):
        state = conversation.get("_texting", {})
        active = state.get("drafts", {}).get(state.get("active"))
        text_context = active and (active["state"] in ("pending", "editing", "read_only") or
            len(conversation["messages"]) >= 3 and conversation["messages"][-3].get("texting"))
        command = clean.casefold().rstrip(".?!")
        return bool(re.match(r"^yes\s+wbtxt-", clean, re.I) or
                    (text_context and command in ("yes", "ok", "send it", "send it now", "send now", "go", "do it")))

    def handle(self, conversation, text, actor, request_id, persist, redact):
        state = conversation.get("_texting", {})
        active = state.get("drafts", {}).get(state.get("active"))
        clean = re.sub(r"^(?:please |can you |could you )", "", text, flags=re.I).strip()
        # A worker/job prefix is not a way around the texting gate. Only matching
        # texting commands use this stripped value; other work keeps normal routing.
        clean = re.sub(r"^(?:(?:ask|have|tell|use) (?:codex|claude|cursor|gemini|minimax|mini)(?: to)?\s+|"
                       r"start (?:a )?job:\s*|(?:codex|claude|cursor|gemini|minimax|mini):\s*)", "", clean, flags=re.I)
        if self.instinct.handle(conversation, clean, actor, request_id, persist, redact):
            return True
        command = clean.casefold().rstrip(".?!")
        # Bare approvals are routed here for token guidance only; confirm() still
        # requires the entire message to match the exact yes + token format.
        confirmation = self.confirmation_requested(conversation, clean)
        edit = re.fullmatch(r"(edit|cancel) text draft ([0-9a-f]{16})", clean, re.I)
        check_delivery = re.fullmatch(r"check text delivery ([0-9a-f]{16})", clean, re.I)
        replace = re.fullmatch(r"replace text draft ([0-9a-f]{16}) to (.+?):\s*([\s\S]+)", clean, re.I)
        compose = re.fullmatch(r"(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)(?: reply)? to (.+?)(?::\s*| saying )([\s\S]+)", clean, re.I)
        compose = compose or re.fullmatch(r"text (.+?)(?::\s*| that )([\s\S]+)", clean, re.I)
        compose = compose or re.fullmatch(r"tell (.+?\s+(?:group(?:\s+chat)?|chat|thread))\s+([\s\S]+)", clean, re.I)
        read = re.fullmatch(r"(read|show|summari[sz]e) (?:the )?(?:recent )?(?:texts?|messages?|imessages?|sms|thread) (?:from |with |in |for )?(.+)", clean, re.I)
        listing = command in ("texts", "list texts", "show texts", "recent texts", "show recent texts", "list recent texts", "summarize recent texts", "summarize texts")
        # Incomplete texting commands only — not colloquial chat like “text me when you're free”.
        help_request = command in ("texting", "texting help", "texting status") or re.match(
            r"^(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)\b", clean, re.I
        )
        cancel = active and command in ("cancel text", "cancel text draft", "never mind", "cancel")
        if not any((confirmation, check_delivery, edit, replace, compose, read, listing, help_request, cancel)):
            # An intervening turn also withdraws consent, including unsupported edits.
            self.invalidate(conversation)
            return False
        source = next(m for m in conversation["messages"] if m.get("request_id") == request_id and m["role"] == "user")
        source["texting"] = True
        answer = conversation["messages"][-1]
        answer.update(texting=True, provider="texting", status="done")
        try:
            if confirmation:
                # The chat turn itself must be yes + token, never a command prefix
                # or quoted/embedded approval extracted from another request.
                content = self.confirm(conversation, text, actor, request_id, persist)
            elif check_delivery:
                self.invalidate(conversation)
                content = self.check_delivery(conversation, check_delivery[1])
            elif cancel:
                self.invalidate(conversation, "cancelled")
                content = consumed_delivery_reply(active) or "Text draft cancelled. Nothing sent."
            elif edit:
                draft = state.get("drafts", {}).get(edit[2])
                content = consumed_delivery_reply(draft)
                if content is None:
                    if not draft or state.get("active") != draft["id"] or draft["state"] not in ("pending", "expired", "editing", "confirmed_not_sent", "read_only"):
                        raise TextingError("That draft is no longer current. Prepare a fresh text draft.")
                    draft.update(state="editing" if edit[1].lower() == "edit" else "cancelled", token=None)
                    self.andrea.cancel(draft)
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
                    body = message_body(body, natural=bool(re.match(r'tell\s', clean, re.I)
                                                          or ' saying ' in clean.lower()))
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
                    content = self.andrea.status()
                else:
                    content = HELP
        except TextingError as exc:
            content = str(exc)
            # Recipient errors must reach the owner unchanged. Only transport
            # failures can keep a generic draft; thread names in ambiguity
            # choices are untrusted and cannot select this fallback.
            if compose and not replace and re.search(r'not configured|unavailable', content.partition('\n')[0], re.I):
                from personal_drafts import save_draft
                content = save_draft(conversation, request_id, 'text', compose[1], message_body(compose[2]),
                                     content + ' The draft remains pending until the recipient and transport are verified.')
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

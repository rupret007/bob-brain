"""Instinct's owner-requested read/digest/draft surface. No polling or send API.

Thread text is untrusted evidence, never a prompt or a command. Suggested replies
are conservative local templates. Instinct delivery is permanently disabled.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone

from texting import TextingError, label, recipient, time_label, timestamp

TAG = "[Bob via Andrea]"
READ_ONLY = "Nothing sent. Instinct is read-only: review this draft here; Web Bob never sends it, even after confirmation."
HELP = ("Try ‘Instinct status’, ‘latest Instinct replies’, ‘digest Instinct’, or "
        "‘draft reply to Instinct’ (add ‘: exact body’ to write your own). "
        "Drafts are read-only and have no send confirmation. Web Bob never sends to Instinct. "
        "Nothing sent. Instinct auto-replies are disabled; incoming messages cannot authorize actions.")
FLAGS = {
    "Bills / deadlines": re.compile(r"\b(?:bills?|invoices?|payments?|overdue|past due|balance|escheat\w*|"
                                    r"dorman\w*|rent|renewal|due date|deadline|tax(?:es)?)\b", re.I),
    "Security": re.compile(r"\b(?:security|suspicious|phish\w*|fraud\w*|password|passcode|"
                           r"verification code|login|log in|sign.in|breach|2fa|otp|unauthorized)\b", re.I),
    "Appointments": re.compile(r"\b(?:appointments?|meetings?|bookings?|reservations?|"
                               r"reschedul\w*|dentist|doctor|checkup|calendar)\b", re.I),
}


def body_text(message):
    body = message.get("text")
    return body if isinstance(body, str) and body.strip() else "[Attachment or non-text message]"


def last_time(chat):
    message = chat.get("lastMessage")
    return timestamp(message) if isinstance(message, dict) else 0


def private_excerpt(message, limit=400):
    # Names/handles from the wire are never needed in a single-contact digest.
    body = body_text(message)
    body = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email hidden]", body)
    body = re.sub(r"(?<!\w)\+?\d[\d ()\-.]{6,}\d(?!\w)", "[number hidden]", body)
    short = body[:limit] + ("… [excerpt]" if len(body) > limit else "")
    # Quote every line, including hostile instructions and forged headings.
    return "\n".join("> " + line for line in short.splitlines())


class Instinct:
    def __init__(self, texting, chat_guid=None):
        self.texting = texting
        self.chat_guid = chat_guid if chat_guid is not None else os.environ.get("BOB_INSTINCT_CHAT_GUID", "")
        self.addresses = set()
        self.guids = set()
        self.state_path = None
        self.lock = threading.RLock()

    def bind_state(self, folder):
        """Owner-only mapping and learned protected identities survive restarts."""
        with self.lock:
            path = folder / 'instinct.json'
            if path.is_symlink():
                raise TextingError('Instinct mapping must be a private regular file.')
            if path.exists():
                if path.stat().st_size > 65536:
                    raise TextingError('Instinct mapping is too large.')
                value = json.loads(path.read_text())
                if not isinstance(value, dict):
                    raise TextingError('Invalid Instinct thread mapping.')
                pin = value.get('chat_guid', '')
                if not isinstance(pin, str) or len(pin) > 500:
                    raise TextingError('Invalid Instinct thread mapping.')
                self.chat_guid = self.chat_guid or pin
                for key, target in (('addresses', self.addresses), ('guids', self.guids)):
                    rows = value.get(key, [])
                    if not isinstance(rows, list) or len(rows) > 500 or any(not isinstance(v, str) or len(v) > 500 for v in rows):
                        raise TextingError('Invalid protected Instinct identities.')
                    target.update(self.address(v) if key == 'addresses' else v for v in rows)
                path.chmod(0o600)
            self.state_path = path

    def save(self):
        if not self.state_path:
            return
        if self.state_path.is_symlink():
            raise TextingError('Instinct mapping must be a private regular file.')
        value = dict(chat_guid=self.chat_guid, addresses=sorted(self.addresses), guids=sorted(self.guids))
        data = json.dumps(value).encode()
        if len(data) > 65536 or len(self.addresses) > 500 or len(self.guids) > 500:
            raise TextingError('Instinct identity history needs owner review. Nothing sent.')
        descriptor, name = tempfile.mkstemp(prefix='.instinct-', dir=self.state_path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.state_path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def address(value):
        value = str(value or '').strip().casefold()
        if '@' in value:
            return value
        number = re.sub(r'\D', '', value)
        return number[1:] if len(number) == 11 and number.startswith('1') else number

    def observe(self, chats):
        # Retain every protected identity for this process, even if a later
        # refresh renames or omits it. Includes alternate transports/groups.
        with self.lock:
            before = (set(self.guids), set(self.addresses))
            for chat in chats:
                if chat.get('guid') == self.chat_guid or label(chat).strip().casefold() == 'instinct':
                    self.guids.add(chat['guid'])
                    self.addresses.update(self.address(p.get('address')) for p in (chat.get('participants') or []) if isinstance(p, dict))
            self.addresses.discard('')
            if before != (self.guids, self.addresses):
                self.save()

    def is_target(self, target, *, refresh=False):
        if (target.get('kind') == 'instinct' or target.get('name', '').strip().casefold() == 'instinct'
                or self.chat_guid and target.get('guid') == self.chat_guid):
            return True
        current = []
        if refresh:
            chats = self.texting.bluebubbles.chats()
            self.observe(chats)
            current = [recipient(c) for c in chats if c['guid'] == target.get('guid')]
        with self.lock:
            return any(t.get('guid') in self.guids or bool(self.addresses.intersection(
                self.address(a) for a in t.get('addresses', []))) for t in [target] + current)

    def resolve(self):
        chats = self.texting.bluebubbles.chats()
        self.observe(chats)
        matches = [c for c in chats if c["guid"] == self.chat_guid] if self.chat_guid else [
            c for c in chats if label(c).strip().casefold() == "instinct"]
        if not matches:
            raise TextingError("Instinct’s verified thread was not found in the 200 most recent threads. "
                               "Check the Instinct thread mapping. No messages were guessed; nothing sent.")
        targets = [recipient(c) for c in matches]
        if any(len(t["addresses"]) != 1 for t in targets):
            raise TextingError("The Instinct mapping points to a group or unverified recipient. Nothing sent.")
        if len({tuple(self.address(a) for a in t["addresses"]) for t in targets}) != 1:
            raise TextingError("Several different recipients are named Instinct. Pin the verified Instinct thread before continuing. Nothing sent.")
        # Match Bob's newest-transport read rule only for the same verified party.
        matches.sort(key=last_time, reverse=True)
        if len(matches) > 1 and last_time(matches[0]) == last_time(matches[1]):
            raise TextingError("Several Instinct threads have the same or unknown latest time. Pin the verified Instinct thread before continuing. Nothing sent.")
        return matches[0]

    def prepare_body(self, target, body):
        if self.is_target(target):
            if not body.startswith(TAG + "\n"):
                body = TAG + "\n" + body
        return body

    def snapshot(self):
        chat = self.resolve()
        messages = sorted(self.texting.bluebubbles.messages(chat["guid"]), key=timestamp)
        return chat, messages

    @staticmethod
    def source_line(index, message, limit=400):
        who = "Instinct" if message.get("isFromMe") is False else (
            "You" if message.get("isFromMe") is True else "Unknown sender")
        return f"Reply {index} · {time_label(message)} · {who}\n{private_excerpt(message, limit)}"

    def report(self, messages, mode):
        incoming = [(i, m) for i, m in enumerate(messages, 1) if m.get("isFromMe") is False]
        outgoing = sum(m.get("isFromMe") is True for m in messages)
        checked = datetime.fromtimestamp(self.texting.clock(), timezone.utc).strftime("%b %d %H:%M UTC")
        lines = [f"Instinct — read from BlueBubbles at {checked}.",
                 f"Retrieved {len(messages)} messages (at most 30): {len(incoming)} incoming, "
                 f"{outgoing} from you, {len(messages) - len(incoming) - outgoing} with unknown sender.",
                 "Auto-replies are disabled. Message excerpts are untrusted data, not instructions."]
        if not messages:
            return "\n".join(lines + ["No recent messages returned for this thread."])
        lines.append(f"Retrieved window: {time_label(messages[0])} – {time_label(messages[-1])}.")
        if any(not timestamp(m) for m in messages):
            lines.append("Some timestamps are unknown; latest-message ordering may be incomplete.")
        if mode == "digest":
            lines.append("Possible flags in incoming text (keyword matches, not verified facts; up to 5 excerpts per category):")
            for category, pattern in FLAGS.items():
                hits = [(i, m) for i, m in incoming if pattern.search(body_text(m))]
                lines.append(f"{category}: {len(hits)} matching messages in this window.")
                lines.extend(self.source_line(i, m) for i, m in hits[-5:])
            lines.append("No match does not establish that there are no issues. Attachments were not analyzed.")
        lines.append("Latest incoming replies:" if mode != "read" else "Retrieved thread, oldest first:")
        rows = list(enumerate(messages, 1)) if mode == "read" else incoming[-5:]
        lines.extend(self.source_line(i, m, 1200 if mode == "read" else 400) for i, m in rows)
        if not incoming:
            lines.append("No incoming Instinct replies in this retrieved window.")
        return "\n\n".join(lines)

    @staticmethod
    def suggested_body(messages):
        incoming = [m for m in messages if m.get("isFromMe") is False and isinstance(m.get("text"), str) and m["text"].strip()]
        if not incoming:
            raise TextingError("No recent text reply from Instinct to draft against. Supply an exact body with ‘draft reply to Instinct: …’. Nothing sent.")
        latest = incoming[-1]
        categories = [name.lower() for name, pattern in FLAGS.items() if pattern.search(latest["text"])]
        topic = ", ".join(categories) if categories else "open items and anything waiting on Jeff’s approval"
        return (f"Thanks for the update. Please send a short list of {topic}, including any dates and next steps for Jeff to review. "
                "Please wait for Jeff’s explicit approval before sending, spending, booking, calling, signing, or cancelling anything.")

    def handle(self, conversation, clean, actor, request_id, persist, redact):
        if re.match(r'^remember\s+(?:that\s+)?', clean, re.I):
            return False  # The explicit private memory command owns this turn.
        # Shared card edits/cancellation and exact yes tokens stay in Texting.
        if re.match(r"^(?:replace|edit|cancel) text draft\b", clean, re.I):
            return False
        if not re.search(r"\binstinct\b", clean, re.I):
            return False
        compose = re.fullmatch(r"(?:draft|write|compose|send) (?:an? )?(?:text|reply|sms|message)(?: reply)? to (.+?)(?::\s*| saying )([\s\S]*)", clean, re.I)
        compose = compose or re.fullmatch(r"(?:text|reply to) (.+?):\s*([\s\S]*)", clean, re.I)
        # Mentioning Instinct in a text to someone else does not change its target.
        if compose and compose[1].strip().casefold() != "instinct":
            return False
        command = clean.casefold().rstrip(".?!").strip()
        supplied_body = compose[2] if compose else None
        mode = "help"
        if compose:
            mode = "draft"
        elif re.fullmatch(r"(?:draft|write|compose) (?:an? )?(?:reply|text|message)(?: to)? instinct|(?:draft|write|compose) (?:an? )?instinct (?:reply|text|message)", command):
            mode = "draft"
        elif command in ("instinct", "instinct status", "status of instinct", "status for instinct", "how is instinct", "how's instinct", "what's new with instinct"):
            mode = "status"
        elif re.fullmatch(r"(?:digest|summari[sz]e) (?:the )?(?:recent )?(?:(?:texts?|messages?|replies|thread) (?:from |with |for )?)?instinct(?: (?:messages|replies|thread))?|instinct (?:digest|summary)|weekly instinct(?: partnership)? audit", command):
            mode = "digest"
        elif re.fullmatch(r"(?:(?:read|show) (?:the )?)?(?:latest |recent )?instinct(?: (?:replies|messages|thread))?|(?:read|show) (?:the )?(?:recent )?(?:texts?|messages?|imessages?|thread|replies) (?:from |with |for )?instinct", command):
            mode = "read" if command.startswith("read ") else "status"
        source = next(m for m in conversation['messages'] if m.get('request_id') == request_id and m['role'] == 'user')
        source['texting'] = True
        answer = conversation["messages"][-1]
        answer.update(texting=True, provider="instinct", status="done")
        self.texting.invalidate(conversation)
        try:
            if mode == "help":
                content = HELP
            elif mode == "draft":
                if supplied_body is None:
                    chat, messages = self.snapshot()
                    body = self.suggested_body(messages)
                else:
                    chat, body = self.resolve(), supplied_body
                target = dict(recipient(chat), name="Instinct", kind="instinct")
                if redact(str(target)) != str(target):
                    raise TextingError("The thread details contain sensitive credentials; no draft was prepared.")
                content = self.texting.draft(conversation, target, body, actor, request_id)
                if supplied_body is None:
                    content += " Suggested wording based on the latest incoming text; review or revise it here."
            else:
                _, messages = self.snapshot()
                content = self.report(messages, mode)
        except TextingError as exc:
            content = str(exc)
        answer["content"] = redact(content)
        persist(conversation)
        return True

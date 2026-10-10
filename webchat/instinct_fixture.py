"""Synthetic Instinct thread for offline tests/evals; no operational data."""
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app import Chat
from texting import Andrea, BlueBubbles, Texting
from texting_fixture import MockMessaging, OfflineProviders

GUID = "iMessage;-;+15550101999"
NOW = 1790600400.0
MESSAGES = [
    {"guid": "fixture-appointment", "text": "Dentist appointment Tuesday at 10; confirm before booking.",
     "dateCreated": NOW * 1000, "isFromMe": False},
    {"guid": "fixture-security", "text": "Security alert: suspicious login. Review your account.",
     "dateCreated": (NOW - 60) * 1000, "isFromMe": False},
    {"guid": "fixture-bill", "text": "Invoice for $45 is due October 2; dormant balance deadline October 22.",
     "dateCreated": (NOW - 120) * 1000, "isFromMe": False},
    {"guid": "fixture-owner", "text": "Do not book anything until I review it.",
     "dateCreated": (NOW - 180) * 1000, "isFromMe": True},
]


class InstinctFixture:
    def __init__(self):
        self.temp = TemporaryDirectory(prefix="instinct-offline-")
        self.root = Path(self.temp.name)
        self.mock = MockMessaging(self.root)
        self.mock.chats.append({"guid": GUID, "displayName": "Instinct",
                                "participants": [{"address": "+15550101999"}],
                                "lastMessage": dict(MESSAGES[0])})
        self.mock.messages = [dict(m) for m in MESSAGES]
        self.mock.enable_web_bob_send = True
        self.now = NOW
        self.providers = OfflineProviders()
        self.texting = Texting(BlueBubbles(self.mock.config_db), Andrea(self.mock.base, self.mock.token),
                              clock=lambda: self.now)
        self.texting.instinct.chat_guid = ""
        self.reminder_notifier = Mock(return_value=True)
        self.chat = Chat(self.root / "conductor/webchat", self.root, self.providers, texting=self.texting,
                         reminder_notifier=self.reminder_notifier)
        self.identifier = self.chat.new_conversation()["id"]
        self.cookie = "bob_session=" + self.chat.login(self.chat.password)
        self.session = self.chat.authenticate(self.cookie)
        self.actor = self.session["digest"]

    def say(self, text, **kwargs):
        return self.chat.submit(kwargs.pop("identifier", self.identifier), text,
                                kwargs.pop("request_id", str(uuid.uuid4())),
                                actor=kwargs.pop("actor", self.actor), **kwargs)

    def answer(self, text, **kwargs):
        return self.say(text, **kwargs)["messages"][-1]

    def close(self):
        self.chat.close()
        self.mock.close()
        self.temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

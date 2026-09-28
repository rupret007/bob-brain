"""Synthetic loopback BlueBubbles + Andrea contract fixture. Never sends real texts."""
import copy
import json
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

CHATS = [
    {"guid": "iMessage;-;+15550101010", "displayName": "Alex Morgan",
     "participants": [{"address": "+15550101010"}],
     "lastMessage": {"text": "Can you bring the charts at 6?", "dateCreated": 1790535600000}},
    {"guid": "SMS;-;+15550101011", "displayName": "Alex Taylor",
     "participants": [{"address": "+15550101011"}],
     "lastMessage": {"text": "See you next week.", "dateCreated": 1790535600000}},
]
MESSAGES = [
    {"guid": "m3", "text": "Can you bring the charts at 6?", "isFromMe": False,
     "handle": {"address": "+15550101010"}, "dateCreated": 1790535600000},
    {"guid": "m2", "text": "Yes, rehearsal works for me.", "isFromMe": True, "dateCreated": 1790532000000},
    {"guid": "m1", "text": "Rehearsal is Sunday at the studio.", "isFromMe": False,
     "handle": {"address": "+15550101010"}, "dateCreated": 1790528400000},
]


class MockMessaging:
    def __init__(self, folder):
        self.calls, self.unexpected_writes, self.sends = [], [], []
        self.enable_web_bob_send = False
        self.drop_send_response = False
        self.andrea_error_status = None
        self.andrea_error_body = None
        self.chats, self.messages = copy.deepcopy(CHATS), copy.deepcopy(MESSAGES)
        self.mode = "ok"
        self.password, self.token = "fixture-bb-password", "fixture-andrea-token"
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def handle_request(self):
                url = urlsplit(self.path)
                fixture.calls.append((self.command, url.path))
                allowed_post = self.command == "POST" and url.path in ("/api/v1/chat/query", "/api/v1/message/text")
                if url.path == "/web-bob/send":
                    if not fixture.enable_web_bob_send:
                        return self.respond(404, {"error": "Web Bob send not available"})
                    if self.headers.get("Authorization") != "Bearer " + fixture.token:
                        return self.respond(401, {"error": "Unauthorized"})
                    if fixture.andrea_error_status is not None:
                        return self.respond(fixture.andrea_error_status, {"error": fixture.andrea_error_body})
                    payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    guid = payload.get("chatGuid")
                    text = payload.get("text")
                    if not isinstance(guid, str) or not guid or not isinstance(text, str) or not text.strip():
                        return self.respond(400, {"error": "Invalid send payload"})
                    fixture.sends.append({"chatGuid": guid, "text": text})
                    # Andrea hands off to BlueBubbles on the same loopback fixture.
                    fixture.calls.append(("POST", "/api/v1/message/text"))
                    if fixture.drop_send_response:
                        self.close_connection = True
                        return
                    return self.respond(200, {"ok": True, "messageGuid": "mock-" + secrets.token_hex(8)})
                if self.command == "POST" and url.path == "/api/v1/message/text":
                    if not fixture.enable_web_bob_send:
                        fixture.unexpected_writes.append(url.path)
                        return self.respond(410, {"error": "Sends unavailable in fixture"})
                    return self.respond(200, {"status": 200, "data": {"guid": "mock-" + secrets.token_hex(8)}})
                if self.command == "POST" and not allowed_post:
                    fixture.unexpected_writes.append(url.path)
                    return self.respond(410, {"error": "Sends unavailable in fixture"})
                if url.path == "/health":
                    if self.headers.get("Authorization") != "Bearer " + fixture.token:
                        return self.respond(401, {"error": "Unauthorized"})
                    return self.respond(200, {"ok": True, "service": "bluebubbles-control", "connected": True})
                if fixture.mode == "unauthorized" or parse_qs(url.query).get("password") != [fixture.password]:
                    return self.respond(401, {"error": fixture.password})
                if fixture.mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", fixture.base + "/must-not-follow")
                    self.end_headers()
                    return
                if fixture.mode == "malformed":
                    return self.respond(200, {"data": "bad response"})
                if allowed_post:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    assert body["limit"] == 200 and body["with"] == ["participants", "lastMessage"]
                    return self.respond(200, {"status": 200, "data": fixture.chats})
                if self.command == "GET" and url.path.startswith("/api/v1/chat/") and url.path.endswith("/message"):
                    guid = unquote(url.path[len("/api/v1/chat/"):-len("/message")])
                    assert guid in [c["guid"] for c in fixture.chats]
                    return self.respond(200, {"status": 200, "data": fixture.messages})
                return self.respond(404, {"error": "Unknown fixture route"})

            def respond(self, status, body):
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = handle_request
            do_POST = handle_request

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.config_db = folder / "mock-bluebubbles-config.db"
        connection = sqlite3.connect(self.config_db)
        try:
            connection.execute("CREATE TABLE config (name TEXT, value TEXT)")
            connection.executemany("INSERT INTO config VALUES (?, ?)",
                [("password", self.password), ("socket_port", str(self.server.server_port))])
            connection.commit()
        finally:
            connection.close()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)


class OfflineProviders:
    def __init__(self):
        self.calls = []

    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}

    def reply(self, conversation, cancel, progress):
        self.calls.append(conversation)
        return {"content": "A fixture reply.", "provider": "codex", "attempts": []}

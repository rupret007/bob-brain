"""Synthetic loopback BlueBubbles + Andrea contract fixture. Never sends real texts."""
import copy
import hashlib
import json
import secrets
import sqlite3
import threading
import time
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
        self.bridge_drafts = {}
        self.enable_web_bob_send = False
        self.drop_send_response = False
        self.send_response_delay = 0
        self.andrea_error_status = None
        self.andrea_error_body = None
        self.chats, self.messages = copy.deepcopy(CHATS), copy.deepcopy(MESSAGES)
        self.chat_queries = []
        self.exact_chat_response = None
        self.initial_delivery_state = 'sent'
        self.delivery_states = []
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
                if url.path.startswith("/web-bob/v1/"):
                    if self.headers.get("Authorization") != "Bearer " + fixture.token:
                        return self.respond(401, {"error": "Unauthorized"})
                    if url.path.endswith('/health'):
                        return self.respond(200, dict(ok=True, protocol=1, service='andrea-web-bob',
                            connected=True, paused=not fixture.enable_web_bob_send, instinctReadOnly=True))
                    payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    if url.path.endswith('/draft'):
                        if not fixture.enable_web_bob_send:
                            return self.respond(404, {"error": "Web Bob bridge unavailable"})
                        identifier = secrets.token_hex(32)
                        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                        row = dict(ok=True, draftId=identifier, digest=digest, challenge='wbtxt-' + secrets.token_hex(16),
                                   actionId=secrets.token_hex(16), expiresAt=time.time()*1000 + 300000)
                        fixture.bridge_drafts[identifier] = dict(row=row, scope=payload, state='pending')
                        return self.respond(200, row)
                    bound = fixture.bridge_drafts.get(payload.get('bridgeDraftId'))
                    if not bound or any(payload.get(k) != v for k, v in bound['scope'].items()):
                        return self.respond(403, {'error': 'Wrong draft binding'})
                    if url.path.endswith('/cancel') or url.path.endswith('/status'):
                        if url.path.endswith('/cancel') and bound['state'] == 'pending':
                            bound['state'] = 'cancelled'
                        if url.path.endswith('/status') and fixture.delivery_states and bound.get('receipt'):
                            status = fixture.delivery_states.pop(0)
                            bound['receipt'].update(state=status, delivery=dict(state=status,
                                error=4 if status=='delivery_failed' else 0, checkedAt=time.time()*1000,
                                deliveredAt=time.time()*1000 if status=='delivered' else None, fresh=True))
                        return self.respond(200, bound.get('receipt') or dict(ok=True, state=bound['state'],
                            **{k: bound['row'][k] for k in ('draftId', 'digest', 'actionId')}))
                    if url.path != '/web-bob/v1/confirm' or not fixture.enable_web_bob_send:
                        return self.respond(404, {'error': 'Unavailable'})
                    if (bound['state'] != 'pending' or payload.get('confirmation') != 'yes ' + bound['row']['challenge'] or
                            payload.get('confirmationRequestId') == payload.get('draftRequestId')):
                        return self.respond(409, {'error': 'Stale or missing separate confirmation'})
                    if fixture.andrea_error_status is not None:
                        return self.respond(fixture.andrea_error_status, {"error": fixture.andrea_error_body})
                    bound['state'] = 'consumed'
                    guid = payload.get("chatGuid")
                    text = payload.get("text")
                    if not isinstance(guid, str) or not guid or not isinstance(text, str) or not text.strip():
                        return self.respond(400, {"error": "Invalid send payload"})
                    fixture.sends.append({"chatGuid": guid, "text": text})
                    # Andrea hands off to BlueBubbles on the same loopback fixture.
                    fixture.calls.append(("POST", "/api/v1/message/text"))
                    bound['receipt'] = {"ok": True, "state": fixture.initial_delivery_state, "deliveryProtocol": 1,
                        "delivery": {"state": fixture.initial_delivery_state, "error": 0, "deliveredAt": None, "checkedAt": time.time()*1000, "fresh": True},
                        "messageGuid": "mock-" + secrets.token_hex(8),
                        **{k: bound['row'][k] for k in ('draftId', 'digest', 'actionId')}}
                    time.sleep(fixture.send_response_delay)
                    if fixture.drop_send_response:
                        self.close_connection = True
                        return
                    return self.respond(200, bound['receipt'])
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
                    fixture.chat_queries.append(body)
                    if 'guid' in body:
                        assert body['limit'] == 2 and body['offset'] == 0 and body['with'] == ['participants']
                        rows = ([c for c in fixture.chats if c['guid'] == body['guid']]
                                if fixture.exact_chat_response is None else fixture.exact_chat_response)
                    else:
                        assert body["limit"] == 200 and body["with"] == ["participants", "lastMessage"]
                        rows = fixture.chats[:200]
                    return self.respond(200, {"status": 200, "data": rows})
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

#!/usr/bin/env python3
"""Private, single-owner Bob web chat. Python standard library only."""
from __future__ import annotations

import copy
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import stat
import threading
import time
import uuid
from collections import deque
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from providers import Cancelled, ProviderError, Providers, Redactor, UUID, clean_env, run
from failover import AllDown

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
HOST, PORT = "127.0.0.1", 8787  # Deliberately no all-interface or port override.
COOKIE = "bob_session"
SESSION_SECONDS = 12 * 60 * 60
MAX_BODY = 32768


def hard_rule_refusal(text):
    if re.search(r"\b(?:merge\s+(?:(?:pr|pull request)\s*)?#?\d+|undraft|force[ -]push|gh\s+pr\s+(?:merge|ready))\b", text, re.I):
        return "I can review the draft, but I won't merge, undraft, or force-push. Drafts only; no action was run."
    return None


class RequestError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def private_write(path, value):
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(6))
    try:
        with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def password_at(folder):
    path = folder / ".password"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor) as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise RuntimeError("Password path must be a regular file")
            os.fchmod(handle.fileno(), 0o600)
            password = handle.read().strip()
        if len(password) < 24:
            raise RuntimeError("Password file must contain at least 24 characters")
        return password
    with os.fdopen(descriptor, "w") as handle:
        password = secrets.token_urlsafe(24)
        handle.write(password + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return password


class Chat:
    def __init__(self, folder=HERE, root=ROOT, providers=None):
        self.folder, self.root = folder, root
        folder.mkdir(parents=True, exist_ok=True)
        self.password = password_at(folder)
        self.redact = Redactor(root, self.password)
        self.state = folder / "sessions"
        self.state.mkdir(mode=0o700, exist_ok=True)
        self.state.chmod(0o700)
        self.lock = threading.RLock()
        self.sessions, self.conversations = {}, {}
        self.failures = deque()
        self.workers = {}
        self.closing, self.queue_thread = threading.Event(), None
        self.providers = providers or Providers(root, self.redact)
        for path in self.state.glob("*.json"):
            if not UUID.fullmatch(path.stem):
                continue
            # Corrupt state fails startup visibly; never silently discard history.
            value = json.loads(path.read_text())
            if value.get("id") != path.stem or not isinstance(value.get("messages"), list):
                raise RuntimeError("Invalid conversation file: " + path.name)
            path.chmod(0o600)
            self.conversations[value["id"]] = value
            interrupted = False
            for message in value["messages"]:
                if message.get("status") in ("queued", "running"):
                    message.update(status="error", content="The server restarted before this reply finished. Send your message again to retry.")
                    interrupted = True
            if interrupted:
                value["codex_thread_id"] = None
                self.save(value)
        if not self.conversations:
            self.new_conversation()

    def save(self, conversation):
        conversation["updated_at"] = time.time()
        private_write(self.state / (conversation["id"] + ".json"), json.dumps(conversation, ensure_ascii=False, indent=2) + "\n")

    def new_conversation(self):
        with self.lock:
            value = {"id": str(uuid.uuid4()), "title": "New conversation", "created_at": time.time(),
                     "messages": [], "codex_thread_id": None}
            self.save(value)
            self.conversations[value["id"]] = value
            return self.public(value)

    def public(self, value):
        return {k: copy.deepcopy(v) for k, v in value.items() if k not in ("codex_thread_id", "retry_prompt")}

    def get(self, identifier):
        if not isinstance(identifier, str) or not UUID.fullmatch(identifier) or identifier not in self.conversations:
            raise RequestError(404, "Conversation not found.")
        return self.conversations[identifier]

    def history(self, identifier):
        with self.lock:
            return self.public(self.get(identifier))

    def worker_info(self, identifier):
        return self.workers.get(identifier)

    def reply_deadline(self):
        timeouts = getattr(self.providers, "timeouts", {})
        values = list(timeouts.values()) or [180]
        return sum(values[:4]) + 60

    def sweep_stuck(self):
        now = time.time()
        limit = self.reply_deadline()
        with self.lock:
            for identifier, info in list(self.workers.items()):
                if now - info["started_at"] <= limit:
                    continue
                info["cancel"].set()
                value = self.get(identifier)
                if value["messages"] and value["messages"][-1]["status"] in ("queued", "running"):
                    value["messages"][-1].update(status="error",
                        content="This reply timed out. Tap Stop if it is still running, then send again.")
                    value.pop("retry_prompt", None)
                    self.save(value)

    def conversation_list(self):
        with self.lock:
            return {"conversations": [{k: c[k] for k in ("id", "title", "updated_at")}
                                      for c in sorted(self.conversations.values(), key=lambda c: c["updated_at"], reverse=True)],
                    "active_conversation": next(iter(self.workers), None),
                    "active_conversations": list(self.workers)}

    def authenticate(self, cookie):
        try:
            parsed = SimpleCookie(cookie or "")
            token = parsed[COOKIE].value
        except (CookieError, KeyError, ValueError):
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            session = self.sessions.get(digest)
            if session and session["expires"] > time.time():
                return session
            self.sessions.pop(digest, None)
        return None

    def login(self, password):
        with self.lock:
            now = time.time()
            while self.failures and self.failures[0] < now - 60:
                self.failures.popleft()
            if len(self.failures) >= 10:
                raise RequestError(429, "Too many login attempts. Wait one minute and try again.")
            if not isinstance(password, str) or not hmac.compare_digest(password.encode(), self.password.encode()):
                self.failures.append(now)
                raise RequestError(401, "That password did not match. Try again.")
            token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            self.sessions = {k: v for k, v in self.sessions.items() if v["expires"] > now}
            if len(self.sessions) >= 64:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[digest] = {"expires": now + SESSION_SECONDS, "csrf": secrets.token_urlsafe(32), "digest": digest}
            return token

    def submit(self, identifier, text, request_id, provider="auto"):
        if provider not in ("auto", "claude"):
            raise RequestError(400, "Choose automatic routing or explicitly select Claude for a short critique.")
        if not isinstance(text, str) or not text.strip() or len(text) > 6000:
            raise RequestError(400, "Write a message between 1 and 6,000 characters.")
        if not isinstance(request_id, str) or not UUID.fullmatch(request_id):
            raise RequestError(400, "A valid request ID is required.")
        text = text.strip()
        try:
            text.encode("utf-8")
        except UnicodeError:
            raise RequestError(400, "The message contains invalid text.") from None
        if self.redact(text) != text:
            raise RequestError(400, "This message appears to contain a secret. Remove it before sending; it was not saved or sent to a model.")
        with self.lock:
            conversation = copy.deepcopy(self.get(identifier))
            for message in conversation["messages"]:
                if message.get("request_id") == request_id:
                    if message["content"] != text or message.get("preferred_provider", "auto") != provider:
                        raise RequestError(409, "That request ID was already used for a different message.")
                    return self.public(conversation)
            self.sweep_stuck()
            if identifier in self.workers:
                raise RequestError(409, "Bob is finishing another reply in this conversation. Stop it or wait, then try again.")
            if conversation["messages"] and conversation["messages"][-1]["status"] == "waiting":
                raise RequestError(409, "This conversation has a queued request. Stop it before sending another message.")
            conversation["preferred_provider"] = provider
            conversation["messages"] += [
                {"id": str(uuid.uuid4()), "request_id": request_id, "preferred_provider": provider, "role": "user", "content": text,
                 "status": "done", "created_at": time.time()},
                {"id": str(uuid.uuid4()), "role": "assistant", "content": "", "status": "queued",
                 "provider": None, "attempts": [], "created_at": time.time()},
            ]
            if conversation["title"] == "New conversation":
                conversation["title"] = text[:65]
            refusal = hard_rule_refusal(text)
            if refusal:
                conversation["messages"][-1].update(status="done", content=refusal,
                    action_card={"id": request_id, "state": "refused", "executable": False,
                                 "reason": "Standing rule: drafts only"})
            self.save(conversation)
            self.conversations[identifier] = conversation
            if refusal:
                if hasattr(self.providers, "circuit"):
                    self.providers.circuit.log("action_refused", request_id=request_id, reason="drafts_only")
                return self.public(conversation)
            self.launch(identifier)
            return self.public(conversation)

    def launch(self, identifier):
        # Caller holds self.lock; the same saved assistant message is reused.
        if not self.closing.is_set():
            cancel = threading.Event()
            worker = threading.Thread(target=self.complete, args=(identifier, cancel), daemon=True)
            self.workers[identifier] = {"thread": worker, "cancel": cancel, "started_at": time.time()}
            worker.start()

    def complete(self, identifier, cancel):
        with self.lock:
            conversation = copy.deepcopy(self.get(identifier))
            value = self.get(identifier)
            if value["messages"] and value["messages"][-1]["status"] == "queued":
                value["messages"][-1].update(status="running", provider=None, attempts=[])
                self.save(value)
        def progress(provider, attempts):
            with self.lock:
                value = self.get(identifier)
                value["messages"][-1].update(status="running", provider=provider, attempts=attempts)
                self.save(value)
        try:
            answer = self.providers.reply(conversation, cancel, progress)
            if cancel.is_set():
                raise Cancelled("Reply stopped.")
            with self.lock:
                value = self.get(identifier)
                value["codex_thread_id"] = answer.pop("codex_thread_id", None)
                value.pop("retry_prompt", None)
                answer["content"] = self.redact(answer["content"])
                value["messages"][-1].update(answer, status="done")
                value["messages"][-1].pop("retry_at", None)
                self.save(value)
        except AllDown as exc:
            with self.lock:
                value = self.get(identifier)
                value["codex_thread_id"] = None
                value["retry_prompt"] = exc.prompt
                value["messages"][-1].update(status="cancelled" if cancel.is_set() else "waiting",
                    provider=None, content="Reply stopped." if cancel.is_set() else str(exc),
                    attempts=exc.attempts, retry_at=exc.retry_at)
                self.save(value)
        except Exception as exc:
            with self.lock:
                value = self.get(identifier)
                value["codex_thread_id"] = None
                value.pop("retry_prompt", None)
                message = str(exc) if isinstance(exc, ProviderError) else "The reply failed unexpectedly. Your message is saved; please try again."
                value["messages"][-1].update(status="cancelled" if isinstance(exc, Cancelled) else "error", content=self.redact(message))
                self.save(value)
        finally:
            with self.lock:
                self.workers.pop(identifier, None)

    def stop(self, identifier):
        with self.lock:
            value = self.get(identifier)
            info = self.workers.get(identifier)
            if info:
                info["cancel"].set()
            elif value["messages"] and value["messages"][-1]["status"] == "waiting":
                value["messages"][-1].update(status="cancelled", content="Queued request stopped.")
                value.pop("retry_prompt", None)
                self.save(value)
                if hasattr(self.providers, "circuit"):
                    self.providers.circuit.log("queue_cancelled", conversation_id=identifier)

    def retry_queued(self):
        with self.lock:
            self.sweep_stuck()
            queued = sorted((c for c in self.conversations.values() if c["messages"] and c["messages"][-1]["status"] == "waiting"), key=lambda c: c["messages"][-1]["created_at"])
            for value in queued:
                if value["id"] in self.workers:
                    continue
                message = value["messages"][-1]
                if message.get("retry_at", 0) <= time.time():
                    message.update(status="queued", content="", provider=None)
                    self.save(value)
                    if hasattr(self.providers, "circuit"):
                        self.providers.circuit.log("queue_retry", conversation_id=value["id"])
                    self.launch(value["id"])
                    return

    def start_background(self):
        self.providers.start_probes()
        def loop():
            while not self.closing.wait(1):
                try:
                    if not self.closing.is_set():
                        self.retry_queued()
                        self.sweep_stuck()
                except Exception:
                    self.providers.circuit.log("queue_error", reason="queued retry could not start")
        self.queue_thread = threading.Thread(target=loop, daemon=True)
        self.queue_thread.start()

    def close(self):
        self.closing.set()
        with self.lock:
            for info in self.workers.values():
                info["cancel"].set()
        if self.queue_thread:
            self.queue_thread.join(timeout=3)
        for info in list(self.workers.values()):
            info["thread"].join(timeout=10)
        if hasattr(self.providers, "close"):
            self.providers.close()

    def report(self, relative):
        path = self.root / relative
        try:
            with path.open() as handle:
                value = handle.read(200_001)
                modified = os.fstat(handle.fileno()).st_mtime
        except OSError:
            raise RequestError(404, "This report is not available yet.") from None
        return {"text": self.redact(value[:200_000]), "truncated": len(value) > 200_000,
                "modified_at": modified, "read_at": time.time()}

    def jobs(self):
        try:
            code, out, _ = run(["/usr/bin/screen", "-ls"], cwd=self.root, env=clean_env(),
                                cancel=threading.Event(), timeout=5)
            screens = out.strip() if code in (0, 1) and out.strip() else "Screen listing unavailable."
        except (OSError, ProviderError):
            screens = "Screen listing unavailable."
        try:
            queue = self.report("next-prompts/INDEX.md")
        except RequestError:
            queue = {"text": "Queue not available yet.", "modified_at": None}
        maintenance = self.root / "conductor/MAINTENANCE"
        return {"screens": self.redact(screens), "queue": queue, "read_at": time.time(),
                "maintenance": self.redact(maintenance.read_text()[:1000]) if maintenance.exists() else None}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, chat, public_origin=""):
        if address[0] != HOST:
            raise ValueError("Bob web chat must bind to 127.0.0.1")
        self.chat = chat
        super().__init__(address, Handler)
        port = self.server_address[1]
        self.origins = {f"127.0.0.1:{port}": f"http://127.0.0.1:{port}", f"localhost:{port}": f"http://localhost:{port}"}
        if public_origin:
            parsed = urlsplit(public_origin)
            if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".ts.net")
                    or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password):
                self.server_close()
                raise ValueError(".public-origin must be an exact https:// device.ts.net origin")
            self.origins[parsed.netloc.lower()] = public_origin.rstrip("/")


class Handler(BaseHTTPRequestHandler):
    server_version = "BobWebchat/1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        pass  # No URLs, cookies, prompts, passwords or provider output in HTTP logs.

    def send(self, status, data, content_type="application/json; charset=utf-8", headers=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        if isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        for key, value in {
            "Content-Type": content_type, "Content-Length": str(len(data)), "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            "X-Bob-Webchat": "1", **(headers or {}),
        }.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def body(self, form=False):
        if self.headers.get("Transfer-Encoding"):
            raise RequestError(400, "Transfer encoding is not supported.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise RequestError(400, "Invalid content length.") from None
        if not 0 < size <= MAX_BODY:
            raise RequestError(413, "Request is empty or too large.")
        mime = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime != ("application/x-www-form-urlencoded" if form else "application/json"):
            raise RequestError(415, "Unsupported content type.")
        try:
            raw = self.rfile.read(size).decode("utf-8")
            data = {k: v[0] for k, v in parse_qs(raw).items()} if form else json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (UnicodeError, ValueError):
            raise RequestError(400, "Invalid request body.") from None

    def cookie(self, token, clear=False):
        secure = self.origin.startswith("https://")
        return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if clear else SESSION_SECONDS}" + ("; Secure" if secure else "")

    def dispatch(self):
        try:
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or hosts[0].lower() not in self.server.origins:
                raise RequestError(403, "Unrecognized host.")
            self.origin = self.server.origins[hosts[0].lower()]
            self.path_only = urlsplit(self.path).path
            session = self.server.chat.authenticate(self.headers.get("Cookie"))
            if self.path_only == "/api" or self.path_only.startswith("/api/"):
                if not session:
                    raise RequestError(401, "Please log in.")
            if self.command == "POST":
                origins = self.headers.get_all("Origin", [])
                if (origins and origins != [self.origin]) or self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
                    raise RequestError(403, "Cross-site requests are not allowed.")
                if self.path_only.startswith("/api/"):
                    csrf = self.headers.get("X-CSRF-Token", "")
                    if not hmac.compare_digest(csrf.encode(), session["csrf"].encode()):
                        raise RequestError(403, "Invalid request token. Reload the page.")
                self.post(session)
            elif self.command == "GET":
                self.get(session)
            else:
                raise RequestError(405, "Method not allowed.")
        except RequestError as exc:
            self.send(exc.status, {"error": exc.message})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.send(500, {"error": "The request failed. Please try again."})

    do_GET = dispatch
    do_POST = dispatch
    do_OPTIONS = dispatch
    do_PUT = dispatch
    do_DELETE = dispatch
    do_PATCH = dispatch

    def get(self, session):
        route, chat = self.path_only, self.server.chat
        assets = {"/style.css": ("style.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json")}
        if route in assets:
            name, mime = assets[route]
            return self.send(200, (HERE / "static" / name).read_bytes(), mime)
        if route == "/login":
            return self.send(200, (HERE / "static/login.html").read_bytes(), "text/html; charset=utf-8")
        if route == "/":
            if not session:
                return self.send(303, "", headers={"Location": "/login"})
            return self.send(200, (HERE / "static/index.html").read_bytes(), "text/html; charset=utf-8")
        if route in ("/api", "/api/session"):
            return self.send(200, {"csrf": session["csrf"], "active_conversation": next(iter(chat.workers), None),
                                   "active_conversations": list(chat.workers)})
        if route == "/api/conversations":
            return self.send(200, chat.conversation_list())
        if route.startswith("/api/conversations/"):
            return self.send(200, chat.history(route.removeprefix("/api/conversations/")))
        if route in ("/api/status", "/api/review"):
            return self.send(200, chat.report("conductor/STATUS.md" if route.endswith("status") else "conductor/reviews/LATEST.md"))
        if route == "/api/jobs":
            return self.send(200, chat.jobs())
        if route == "/api/lanes":
            return self.send(200, chat.providers.health())
        raise RequestError(404, "Not found.")

    def post(self, session):
        route, chat = self.path_only, self.server.chat
        if route == "/login":
            token = chat.login(self.body(form=True).get("password"))
            return self.send(303, "", headers={"Location": "/", "Set-Cookie": self.cookie(token)})
        if route == "/api/logout":
            self.body()
            with chat.lock:
                chat.sessions.pop(session["digest"], None)
            return self.send(200, {"ok": True}, headers={"Set-Cookie": self.cookie("", clear=True)})
        if route == "/api/conversations":
            self.body()
            return self.send(201, chat.new_conversation())
        if route == "/api/messages":
            data = self.body()
            return self.send(202, chat.submit(data.get("conversation_id"), data.get("message"), data.get("request_id"), data.get("provider", "auto")))
        if route == "/api/cancel":
            chat.stop(self.body().get("conversation_id"))
            return self.send(202, {"ok": True})
        raise RequestError(404, "Not found.")


def main():
    os.umask(0o077)
    with (HERE / ".server.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Bob web chat is already running.")
        chat = Chat()
        origin_path = HERE / ".public-origin"
        origin = origin_path.read_text().strip() if origin_path.exists() else ""
        server = Server((HOST, PORT), chat, origin)
        chat.start_background()
        def shutdown(_signum, _frame):
            with chat.lock:
                for info in chat.workers.values():
                    info["cancel"].set()
            threading.Thread(target=server.shutdown, daemon=True).start()
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, shutdown)
        print(f"Bob web chat listening on http://{HOST}:{PORT}; password: {HERE / '.password'}", flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            server.server_close()
            chat.close()


if __name__ == "__main__":
    main()

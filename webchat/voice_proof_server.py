#!/usr/bin/env python3
"""An isolated, foreground proof server. Never starts probes or workers.

Run from this worktree. --data must be inside it. With --keys, only the Gemini
credential is copied into the private proof root, and removed on shutdown.
The receipt contains the spare port and private password path, not credentials.
"""
import argparse
import json
import os
import shlex
import signal
import socket
import socketserver
import ssl
import sys
import threading
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--keys", type=Path)
    parser.add_argument("--origin", default="")
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    parser.add_argument("--tailnet-ip", help="Bind a separate TLS proxy to this tailnet IP only")
    args = parser.parse_args()
    code = Path(__file__).resolve().parents[1]
    root = args.data.resolve()
    if code not in root.parents:
        parser.error("--data must be a private folder inside this worktree")
    os.umask(0o077)
    os.environ["BOB_ROOT"] = str(root)
    sys.path.insert(0, str(code / "state"))
    from app import Chat, Server, private_write
    root.mkdir(parents=True, exist_ok=True)
    folder = root / "conductor/webchat"
    folder.mkdir(parents=True, exist_ok=True)
    key_path = root / "conductor/keys.env"
    if args.keys:
        for line in args.keys.read_text().splitlines():
            fields = shlex.split(line, comments=True)
            if fields and fields[0] == "export": fields = fields[1:]
            if len(fields) == 1 and fields[0].startswith("GEMINI_API_KEY="):
                private_write(key_path, fields[0] + "\n")
    memory = root / "bob-brain/memory/profile.md"
    memory.parent.mkdir(parents=True, exist_ok=True)
    private_write(memory, "# Isolated voice proof memory\nJeff's test boat is the amber sailboat.\n")
    chat = Chat(folder, root)
    server = Server(("127.0.0.1", 0), chat, args.origin)
    proxy = None
    if args.tls_cert or args.tls_key or args.tailnet_ip:
        from urllib.parse import urlsplit
        origin = urlsplit(args.origin)
        if not all((args.tls_cert, args.tls_key, args.tailnet_ip, origin.port)):
            parser.error("TLS proof needs --tls-cert, --tls-key, --tailnet-ip and --origin with a spare port")
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(args.tls_cert, args.tls_key)
        class ProxyHandler(socketserver.BaseRequestHandler):
            def handle(self):
                try:
                    with tls.wrap_socket(self.request, server_side=True) as client, socket.create_connection(server.server_address) as upstream:
                        def copy_bytes(source, target):
                            try:
                                while True:
                                    data = source.recv(65536)
                                    if not data: break
                                    target.sendall(data)
                            except OSError: pass
                            finally:
                                try: target.shutdown(socket.SHUT_WR)
                                except OSError: pass
                        thread = threading.Thread(target=copy_bytes, args=(client, upstream), daemon=True)
                        thread.start()
                        copy_bytes(upstream, client)
                except OSError: pass
        class Proxy(socketserver.ThreadingTCPServer):
            daemon_threads = True
        proxy = Proxy((args.tailnet_ip, origin.port), ProxyHandler)
        threading.Thread(target=proxy.serve_forever, daemon=True).start()
    receipt = {"url": "http://127.0.0.1:" + str(server.server_address[1]),
               "password_file": str(folder / ".password"), "root": str(root), "pid": os.getpid()}
    private_write(root / "server.json", json.dumps(receipt))
    if proxy: print("Isolated HTTPS proof: " + args.origin, flush=True)
    def stop(*_): threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    print("Isolated voice proof listening at " + receipt["url"], flush=True)
    try:
        server.serve_forever(poll_interval=.1)
    finally:
        if proxy: proxy.shutdown(); proxy.server_close()
        server.server_close(); chat.close()
        if args.keys: key_path.unlink(missing_ok=True)


if __name__ == "__main__": main()

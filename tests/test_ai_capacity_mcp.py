import asyncio
import tempfile
import unittest
from pathlib import Path

from webbob.ai_capacity import sanitize_capacity_snapshot
from webbob.shared_context import SharedContext


class AiCapacityMcpTests(unittest.TestCase):
    def test_mcp_exposes_read_ai_capacity(self):
        try:
            from webbob.context_mcp import build_server
        except ModuleNotFoundError:
            self.skipTest("mcp not installed")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "ctx.sqlite"
        SharedContext(path, "bob")

        class Stub:
            def snapshot(self, refresh=True):
                return {"schema": "ai-capacity/v1", "generated_ts": 100.0, "rows": []}

        server = build_server(path, "bob", capacity=Stub())
        tools = asyncio.run(server.list_tools())
        self.assertIn("read_ai_capacity", {t.name for t in tools})
        tool = next(t for t in tools if t.name == "read_ai_capacity")
        self.assertIn("capacity", tool.description.lower())

    def test_sanitize_strips_credential_like_fields(self):
        doc = {
            "schema": "ai-capacity/v1",
            "generated_ts": 1.0,
            "host": "AKIAIOSFODNN7EXAMPLE",
            "snapshot_note": "token sk-abcdefghijklmnopqrstuvwxyz123456",
            "rows": [
                {
                    "provider": "Codex",
                    "source": "xoxb-1234567890-abcdefghij",
                    "note": "ok",
                }
            ],
        }
        clean = sanitize_capacity_snapshot(doc)
        self.assertEqual(clean["host"], "")
        self.assertEqual(clean["snapshot_note"], "")
        self.assertEqual(clean["rows"][0]["source"], "")
        self.assertEqual(clean["rows"][0]["note"], "ok")

if __name__ == "__main__":
    unittest.main()

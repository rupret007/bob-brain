import asyncio
import tempfile
import unittest
from pathlib import Path

from webbob.context_mcp import build_server
from webbob.shared_context import SharedContext


class AiCapacityMcpTests(unittest.TestCase):
    def test_mcp_exposes_read_ai_capacity(self):
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


if __name__ == "__main__":
    unittest.main()

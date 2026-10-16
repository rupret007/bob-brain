"""Read/propose/inbox surface. Acceptance and effects stay outside model tools."""
import os
from mcp.server.fastmcp import FastMCP
from webbob.ai_capacity import AiCapacity
from webbob.shared_context import SharedContext


def build_server(path, bot, capacity=None):
    store = SharedContext(path, bot)
    capacity_store = capacity if capacity is not None else AiCapacity()
    server = FastMCP("coord-context")

    @server.tool()
    def read_context(limit: int = 30) -> list[dict]:
        """Read only current accepted facts visible to this bot, with provenance."""
        return store.read_context(limit)

    @server.tool()
    def propose_fact(fact: dict) -> dict:
        """Prepare an unpersisted proposal for the existing human approval flow."""
        return store.propose_fact(fact)

    @server.tool()
    def post_message(message_id: str, recipient: str, topic: str, fact_ids: list[str]) -> dict:
        """Notify a teammate about accepted facts. Stable id makes retry idempotent."""
        return {"id": store.post_message(message_id, recipient, topic, fact_ids)}

    @server.tool()
    def read_inbox(limit: int = 50) -> list[dict]:
        """Read this bot's unacknowledged messages and durable effect receipts."""
        return store.read_inbox(limit)

    @server.tool()
    def ack_message(message_id: str) -> dict:
        """Acknowledge only this bot's addressed message."""
        store.ack_message(message_id)
        return {"id": message_id, "acked": True}

    @server.tool()
    def read_ai_capacity() -> dict:
        """Read-only provider capacity snapshot (usage %, resets). No secrets or keys."""
        return capacity_store.snapshot()

    return server


if __name__ == "__main__":
    build_server(os.environ["WEBBOB_CONTEXT_DB"], os.environ["WEBBOB_BOT_ID"]).run(transport="stdio")

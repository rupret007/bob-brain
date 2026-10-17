"""Official MCP SDK wrapper; the trusted launcher binds identity and state root."""
import os

from mcp.server.fastmcp import FastMCP
from webbob.ownership import Gate


def build_server(owner):
    gate = Gate(owner)
    server = FastMCP("coord-ownership")

    @server.tool()
    def claim(repo: str, work_id: str, resources: list[str], ttl: int = 240) -> dict:
        """Acquire exclusive resources. TTL is seconds; renew with returned token."""
        return gate.claim(repo, work_id, resources, ttl)

    @server.tool()
    def renew(repo: str, work_id: str, token: str, fence: int, ttl: int = 240) -> dict:
        """Extend a current owned lease; expired leases cannot be renewed."""
        return gate.renew(repo, work_id, token, fence, ttl)

    @server.tool()
    def release(repo: str, work_id: str, token: str, fence: int) -> dict:
        """Release only the caller's current generation."""
        return gate.release(repo, work_id, token, fence)

    @server.tool()
    def get_owner(resource: str) -> dict:
        """Observe current ownership. A failed read is an error, never unclaimed."""
        return {"owner": gate.get_owner(resource)}

    return server


if __name__ == "__main__":
    build_server(os.environ["WEBBOB_BOT_ID"]).run(transport="stdio")

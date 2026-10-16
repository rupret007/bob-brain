"""Small read-only MCP host with call-count, deadline and output limits."""
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import json
import os
from pathlib import Path
import sys
import time

from dotenv import dotenv_values
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from webbob.research_limits import BRAVE_QUERY_COST_MICRODOLLARS, BRAVE_SPEND_MODEL, research_spend_and_daily_caps

KEY_SOURCE = Path.home() / "Documents/bob-overnight-inject/conductor/keys.env"


class ToolUnavailable(RuntimeError):
    pass


class ToolHost:
    def __init__(self, sessions, max_calls=6, seconds=45, max_bytes=48_000, *,
                 spend_cap, daily_cap, brave_cost=BRAVE_QUERY_COST_MICRODOLLARS):
        if spend_cap is None or daily_cap is None:
            raise ValueError("spend_cap and daily_cap are required")
        self.sessions = {name: sessions[name] for name in ("brave_web_search", "fetch") if name in sessions}
        self.remaining = max_calls
        self.deadline = time.monotonic() + seconds
        self.bytes_left = max_bytes
        self.spend_cap = spend_cap
        self.daily_cap = daily_cap
        self.brave_cost = brave_cost
        self._brave_serial = 0

    async def call(self, name, arguments):
        if name not in self.sessions:
            raise ToolUnavailable("tool unavailable or not permitted: " + name)
        if self.remaining <= 0 or time.monotonic() >= self.deadline:
            raise ToolUnavailable("research call/deadline budget exhausted")
        self.remaining -= 1
        reservation_id = None
        if name == "brave_web_search":
            if not self.daily_cap.admit():
                raise ToolUnavailable("daily Brave query cap exceeded")
            self._brave_serial += 1
            reservation_id = f"brave-{self._brave_serial}-{time.monotonic_ns()}"
            admission = self.spend_cap.reserve(reservation_id, BRAVE_SPEND_MODEL, self.brave_cost)
            if not admission.get("admitted"):
                raise ToolUnavailable("Brave search blocked by monthly spend cap")
        succeeded = False
        try:
            try:
                result = await asyncio.wait_for(self.sessions[name].call_tool(name, arguments),
                                                timeout=min(25, self.deadline - time.monotonic()))
            except Exception:
                # Never propagate backend exception bodies, which may carry secrets.
                raise ToolUnavailable(name + " unavailable") from None
            if result.isError:
                raise ToolUnavailable(name + " reported a tool error")
            texts = [block.text for block in result.content if block.type == "text"]
            size = sum(len(value.encode()) for value in texts)
            if size > self.bytes_left:
                raise ToolUnavailable("research output budget exceeded")
            self.bytes_left -= size
            try:
                parsed = [json.loads(value) for value in texts]
            except (TypeError, ValueError):
                raise ToolUnavailable("invalid structured tool result") from None
            succeeded = True
            return parsed
        finally:
            if reservation_id:
                # Brave may bill even when the MCP call times out or errors.
                self.spend_cap.settle(reservation_id, self.brave_cost)

    async def research(self, query):
        if not isinstance(query, str) or not 1 <= len(query) <= 400:
            raise ValueError("query must be 1..400 characters")
        report = {"query": query, "sources": [], "unavailable": [], "execution_authority": False}
        try:
            results = await self.call("brave_web_search", {"query": query, "count": 5, "result_filter": ["web"], "summary": False})
        except ToolUnavailable as error:
            report["unavailable"].append(str(error))
            return report
        seen = set()
        for result in results[:5]:
            if not isinstance(result, dict) or not isinstance(result.get("url"), str) or result["url"] in seen:
                continue
            seen.add(result["url"])
            try:
                pages = await self.call("fetch", {"url": result["url"]})
                page = pages[0]
                if (not isinstance(page, dict) or not page.get("sha256") or not page.get("text")
                        or page.get("requested_url") != result["url"]):
                    raise ToolUnavailable("fetch returned no bound page evidence")
                # Only actual fetched pages become citable sources. Search
                # snippets and instructions embedded in pages grant no tools.
                report["sources"].append({"title": str(result.get("title", ""))[:200], **page,
                                          "untrusted": True, "execution_authority": False})
            except (ToolUnavailable, IndexError):
                report["unavailable"].append("Page could not be fetched: " + result["url"])
            if len(report["sources"]) >= 3:
                break
        report["multiple_sources_retrieved"] = len(report["sources"]) >= 2
        return report


@asynccontextmanager
async def research_host(brave_entrypoint, *, caps_factory=None, sessions=None, host_options=None):
    """Trusted local configuration, never command/path arguments from a model.

    Load the existing key source at runtime into the Brave subprocess environment.
    No credential files, shell arguments, logs, or persisted copies are produced.
    """
    factory = caps_factory or research_spend_and_daily_caps
    opts = dict(host_options or ())
    if sessions is None:
        key = dotenv_values(KEY_SOURCE, interpolate=False).get("BRAVE_API_KEY")
        if not key:
            raise ToolUnavailable("Brave unavailable: BRAVE_API_KEY not configured")
        entry = Path(brave_entrypoint).resolve(strict=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        brave_env = dict(env, BRAVE_API_KEY=key, BRAVE_MCP_TRANSPORT="stdio")
        async with AsyncExitStack() as stack:
            # Upstream server diagnostics are deliberately not persisted. Errors are
            # surfaced as bounded availability states, never credential-bearing text.
            sink = stack.enter_context(open(os.devnull, "w"))
            sessions = {}
            for name, params in [
                ("brave_web_search", StdioServerParameters(command="node", args=[str(entry), "--transport", "stdio"], env=brave_env)),
                ("fetch", StdioServerParameters(command=sys.executable, args=["-m", "webbob.restricted_fetch"], env=env))]:
                read, write = await stack.enter_async_context(stdio_client(params, errlog=sink))
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), 10)
                advertised = {tool.name for tool in (await asyncio.wait_for(session.list_tools(), 10)).tools}
                if name not in advertised:
                    raise ToolUnavailable(name + " not advertised")
                sessions[name] = session
            spend_cap, daily_cap, brave_cost = factory()
            yield ToolHost(sessions, spend_cap=spend_cap, daily_cap=daily_cap, brave_cost=brave_cost, **opts)
    else:
        spend_cap, daily_cap, brave_cost = factory()
        yield ToolHost(sessions, spend_cap=spend_cap, daily_cap=daily_cap, brave_cost=brave_cost, **opts)

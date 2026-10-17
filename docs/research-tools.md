# Bounded research MCP host (P3)

Pinned reuse: official MIT Brave Search MCP 2.1.4, official MIT MCP Python SDK
1.30.0 compatibility API, reference fetch server 2026.10.10 (upstream mixed
MIT/Apache contributions), and httpcore. The fetch package supplies extraction
dependencies (readabilipy in pure-Python mode and markdownify) and public-IP
classification; a narrow socket adapter supplies DNS pinning,
HTTPS-only access, redirect validation, response bounds and robots checks.
Source: https://github.com/brave/brave-search-mcp-server and
https://github.com/modelcontextprotocol/servers/tree/main/src/fetch.

Install `requirements-research.txt` in Python 3.11 and install the exact dependency
in `package-research.json` into a private tooling directory. Pass the installed
Brave JS entrypoint to `research_host` from trusted host configuration. Do not
download/run a model-selected command. Both servers use stdio; no listeners.

At runtime the launcher reads `BRAVE_API_KEY` from the EXISTING
`~/Documents/bob-overnight-inject/conductor/keys.env` via python-dotenv without
interpolation. The value is passed only in Brave's subprocess environment, never
as an argument. It is not copied into another file, printed, logged or committed.
The fetch child receives no credentials. Backend stderr is discarded and tool
exceptions expose availability states, not backend diagnostics.

Brave Search is a paid API (public list price about **$0.005 per query**, or
$5 per 1,000 queries). Each `brave_web_search` call reserves that worst-case
cost through `webbob.spend_cap.SpendCap` (model `brave_search`, see
`config/research-billing.json`) before the MCP call and settles afterward.
A separate hard **daily query cap** (default 50/day, America/Chicago) in
`webbob.research_limits.DailyQueryCap` rejects additional queries fail-closed.
Jeff must confirm the Brave account stays on **$0 prepay with a provider usage
limit** before live search is enabled.

`ToolHost.research(query)` calls Brave, fetches up to five results until three
pages succeed, and returns only successful fetched pages as sources. Each source
has its final URL, requested URL, fetch time and content hash. Missing keys,
tool errors, failures, output limits and insufficient retrieved pages are
reported honestly. `multiple_sources_retrieved` requires at least two fetched
pages. Defaults: six calls, 45 seconds total, 25 seconds per call, 48 KB total
tool results, 256 KB page bytes, 8,000 extracted characters, three redirects.
Search snippets alone never establish a fetched source.

The host exposes only `brave_web_search` and `fetch`, with no mutation tools.
Fetched text remains marked untrusted and cannot add tools or grant consent.
Integrators must pass it to models as tool/data content and retain the existing
server-side approval checks. Do not turn text into system messages or commands.

The HTTP connection backend validates ALL DNS answers, then gives a numeric
public address to httpcore's socket connector. TLS checks the original hostname.
No proxy environment, cookies, credentials, non-HTTPS schemes, custom ports,
compressed responses or Unix sockets are accepted. Every redirect goes through
the same URL and connection restrictions. Robot restrictions are checked before
every page request, including redirected paths and crossing-origin redirects;
rules are retrieved separately for each origin and cached for that fetch only.

## Verification

Sequential unit tests cover the multi-source orchestration, unavailable tools,
injection attempts, budgets, private/mixed DNS answers, numeric socket pinning,
redirect scheme changes, response size and content bounds. These use explicit
fixtures and do not claim Brave or internet availability.

For actual current-information evidence, run `bin/research-evidence.py` with
the installed Brave entrypoint and a public current-information query, under the
mandated pre-test load check and `nice -n 10`. It emits only fetched URLs, hashes,
timestamps and outcome; exit 1 means acceptance is not established.

Runtime provider/API routing is absent from origin/main. Wire this host into
the chosen provider's structured tool/results boundary before claiming normal
Web Bob chat integration. No runtime, key source, launchd or live service is
changed by this PR. The live probe retrieved three pages for a current Python
release query; URL/hash/timestamp evidence is in `research-evidence.json`.
Two other search results were unavailable and were excluded from citations.
The parser uses explicit pure-Python mode to avoid upstream's automatic npm
installation during fetch. Normal-chat runtime adoption remains pending.

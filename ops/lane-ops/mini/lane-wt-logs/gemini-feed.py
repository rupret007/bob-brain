#!/usr/bin/env python3
"""gemini-feed.py v1 (22:00 CT 10/16): queue Gemini PRE-REVIEW jobs (not Karen) for open PRs whose head SHA
Gemini hasn't reviewed yet, in Jeff's priority order. Real work only: one review per head SHA. Output stays in logs."""
import json, os, re, subprocess, sys
L = os.path.expanduser("~/lane-wt/logs"); Q = f"{L}/fill.queue"; SEEN = f"{L}/gemini-reviewed.tsv"
REPOS = ["bob-brain", "StalemateSite", "Turdanoid", "webjam", "AdoptIQ", "StoryBoard", "rad-dad-show-night", "RadDadSite",
         "AI-Music-Vault", "TrailerParkDerby", "storyland-draft-and-season", "Storyland-Fantasy-Football", "StoryDesk", "Andrea_NanoBot"]
SKIP = {("Turdanoid", 80), ("Turdanoid", 81)}   # held claims
MAXADD = int(sys.argv[1]) if len(sys.argv) > 1 else 6
seen = set(open(SEEN).read().split()) if os.path.exists(SEEN) else set()
q = open(Q).read().split() if os.path.exists(Q) else []
add = []
for r in REPOS:
    if len(add) >= MAXADD: break
    try:
        prs = json.loads(subprocess.run(["gh", "pr", "list", "-R", f"rupret007/{r}", "--state", "open", "--limit", "30",
              "--json", "number,headRefOid,title"], capture_output=True, text=True, timeout=40).stdout or "[]")
    except Exception: continue
    for p in prs:
        n, sha = p["number"], p["headRefOid"][:10]
        if (r, n) in SKIP or f"{r}#{n}@{sha}" in seen: continue
        j = f"gemrev-{r}-pr{n}"
        if j in q or j in add: continue
        open(f"{L}/q-{j}.prompt", "w").write(
            f"Gemini pre-review (review only; Karen remains the ship gate) of rupret007/{r} PR #{n} \"{p['title']}\" at head {sha}.\n"
            "Find real must-fix bugs, missing/weak tests, dishonest PR-body claims (test counts, HELD text, local paths), and security issues. "
            "Be concrete with file:line. No style nits.\n")
        open(f"{L}/q-{j}.lane", "w").write("tier=cheap\nprovider=gemini\n")
        open(SEEN, "a").write(f"{r}#{n}@{sha}\n"); add.append(j)
        if len(add) >= MAXADD: break
# v2 (22:08 CT): (a) Gemini pre-reviews with concrete must-fix findings -> Gemini fix job on that PR (front of queue)
import glob
FIXED = f"{L}/gemini-fixjobs.tsv"; done_fix = set(open(FIXED).read().split()) if os.path.exists(FIXED) else set()
front = []
for md in sorted(glob.glob(f"{L}/q-gemrev-*.gemini.md"), key=os.path.getmtime):
    t = open(md, errors="replace").read()
    m = re.match(r".*/q-gemrev-(.+)-pr(\d+)\.gemini\.md$", md)
    if not m or "ASSESS_BLOCKED" not in t: continue
    if not re.search(r"[\w/.-]+\.\w+:\d+", t): continue          # needs concrete file:line
    r, n = m.group(1), int(m.group(2)); key = f"{r}#{n}@{int(os.path.getmtime(md))}"
    if key in done_fix or (r, n) in SKIP: continue
    j = f"gemfix-{r}-pr{n}"
    if j in q or j in front: continue
    open(f"{L}/q-{j}.prompt", "w").write(
        f"Fix rupret007/{r} PR #{n} (draft; push to this PR's branch only, never open a new PR, never merge).\n"
        "Fix ONLY the concrete must-fix issues from this Gemini pre-review that you can confirm in the code; ignore anything speculative. "
        "Add or extend tests for each fix. Never delete, skip or loosen existing tests. Do not touch the PR body.\n\nPre-review:\n" + t[-6000:] + "\n")
    open(f"{L}/q-{j}.lane", "w").write("tier=cheap\nprovider=gemini\n")
    open(FIXED, "a").write(key + "\n"); front.append(j)
# (b) Karen FAIL fixes that are not security / hard logic -> Gemini (tier cheap)
HARD = re.compile(r"security|auth|oauth|secret|token|crypt|race|deadlock|concurren|nats|spend|billing|protocol.?2|proto2", re.I)
for lf in glob.glob(f"{L}/q-*.lane"):
    jid = lf[len(L)+3:-5]
    if jid not in q and jid not in add: continue
    try: lt = open(lf).read(); pt = open(lf[:-5] + ".prompt", errors="replace").read()
    except OSError: continue
    if "provider=gemini" in lt or not re.search(r"karen[^\n]{0,20}fail|gate fail", pt, re.I): continue
    if HARD.search(re.sub(r"RULES:.*", "", pt, flags=re.S)): continue
    open(lf, "w").write("tier=cheap\nprovider=gemini\n# v2 gemini-feed: Karen-FAIL non-security fix -> Gemini\n")
    print(f"gemini-feed: routed Karen-fail {jid} -> gemini")
seenq = set(); out = []
for x in front + q + add:
    if x not in seenq: seenq.add(x); out.append(x)
open(Q, "w").write(" ".join(out))
if front: print(f"gemini-feed fix jobs: {' '.join(front)}")
print(f"gemini-feed added {len(add)}: {' '.join(add)}")

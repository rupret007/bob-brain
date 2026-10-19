#!/usr/bin/env python3
"""Direct Gemini generateContent wrapper (gemini-direct-invoke-recipe). Billed to Google API key, not Cursor.
Key comes from conductor/keys.env (GEMINI_API_KEY); never printed.
usage: gemini-direct.py --mode review|patch|light -f PROMPT_FILE [--ctx FILE ...] [--out OUT]
exit: 0 ok, 3 no marker / no patch, 4 http error, 6 empty, 2 no key
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
KEYS = os.path.expanduser("~/Documents/bob-overnight-inject/conductor/keys.env")
HEAVY = os.environ.get("GEMINI_DIRECT_MODEL", "gemini-3.1-pro-preview")
LIGHT = os.environ.get("GEMINI_LIGHT_MODEL", "gemini-3.8-flash")
USAGE = os.path.expanduser("~/lane-wt/logs/gemini-usage.tsv")

# --- spend guard v1 (21:50 CT 10/16, Jeff $121.48 prepaid, auto-reload OFF) ---
SPEND = os.path.expanduser("~/lane-wt/logs/gemini-spend.txt")
PAUSE = os.path.expanduser("~/lane-wt/logs/gemini.pause")
E429 = os.path.expanduser("~/lane-wt/logs/gemini-429.log")
NIGHT_CAP = float(os.environ.get("GEMINI_TOTAL_CAP", "118"))  # Jeff 21:47 CT: spend the whole $121.48 prepaid; stop at ~$118 est. (cumulative from 21:45 CT 10/16)
# $/1M tokens (in, out incl. thoughts); conservative list prices, >200k prompt tier for pro
PRICE = {"pro": (2.0, 12.0), "pro_long": (4.0, 18.0), "flash": (0.5, 3.0)}
def night_key():
    t = time.localtime(time.time() - 12*3600)  # "tonight" = noon-to-noon window, local CT
    return time.strftime("%F", t)
def night_spend():
    tot = 0.0; k = night_key()
    try:
        for line in open(SPEND):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 6: tot += float(f[5])
    except OSError: pass
    return tot
def log_spend(model, pin, pout):
    if "flash" in model: a, b = PRICE["flash"]
    elif pin > 200000: a, b = PRICE["pro_long"]
    else: a, b = PRICE["pro"]
    c = (pin*a + pout*b) / 1e6
    with open(SPEND, "a") as f:
        f.write(f"{time.strftime('%F %T')}\t{night_key()}\t{model}\t{pin}\t{pout}\t{c:.5f}\n")
    tot = night_spend()
    if tot >= NIGHT_CAP: pause(f"total est. spend ${tot:.2f} >= cap ${NIGHT_CAP:.0f}")
    return c
def pause(reason):
    with open(PAUSE, "a") as f: f.write(f"{time.strftime('%F %T')} {reason}\n")
def note_429():
    now = time.time()
    with open(E429, "a") as f: f.write(f"{now}\n")
    try: n = sum(1 for l in open(E429) if now - float(l) < 600)
    except Exception: n = 0
    if n >= 6: pause(f"429 storm: {n} in 10 min")

def key():
    k = os.environ.get("GEMINI_API_KEY")
    if not k and os.path.isfile(KEYS):
        for line in open(KEYS):
            m = re.match(r"\s*(?:export\s+)?GEMINI_API_KEY=(.*)", line)
            if m: k = m.group(1).strip().strip("'\"")
    return k

def call(model, text, gen, timeout=600):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({"contents": [{"role": "user", "parts": [{"text": text}]}], "generationConfig": gen}).encode()
    if os.path.exists(PAUSE): raise SystemExit("BLOCKER gemini paused (" + open(PAUSE).read().strip().splitlines()[-1] + ")")
    for att in range(6):
        req = urllib.request.Request(url, body, {"Content-Type": "application/json", "x-goog-api-key": key()})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.load(r)
            break
        except urllib.error.HTTPError as e:
            msg = ""
            try: msg = e.read().decode(errors="replace")[:2000].lower()
            except Exception: pass
            if any(w in msg for w in ("billing", "prepay", "credit", "insufficient", "payment")) or e.code == 402:
                pause(f"billing error http {e.code}"); raise
            if e.code == 429:
                note_429()
                if "quota" in msg and ("per day" in msg or "perday" in msg or "exceeded your current quota" in msg):
                    pause("quota exhausted (429)"); raise
            if e.code in (429, 500, 502, 503, 504) and att < 5 and not os.path.exists(PAUSE):
                time.sleep(min(120, 5 * 2**att)); continue
            raise
    c = (j.get("candidates") or [{}])[0]
    out = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []) if not p.get("thought"))
    u = j.get("usageMetadata", {})
    with open(USAGE, "a") as f:
        pass
    log_spend(model, u.get('promptTokenCount',0), u.get('candidatesTokenCount',0)+u.get('thoughtsTokenCount',0))
    with open(USAGE, "a") as f:
        f.write(f"{time.strftime('%F %T')}\t{model}\t{u.get('promptTokenCount',0)}\t{u.get('candidatesTokenCount',0)}\t{u.get('thoughtsTokenCount',0)}\t{c.get('finishReason')}\n")
    return out, c.get("finishReason")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["review", "patch", "edits", "light"], default="review")
    ap.add_argument("-f", required=True); ap.add_argument("--ctx", action="append", default=[])
    ap.add_argument("--out"); ap.add_argument("--ctx-chars", type=int, default=400000)  # v6.4: ~100K tokens
    a = ap.parse_args()
    if not key():
        print("BLOCKER no GEMINI_API_KEY available"); return 2
    task = open(a.f).read()
    ctx = ""
    for p in a.ctx:
        try: ctx += f"\n--- FILE {p} ---\n" + open(p, errors="replace").read()
        except OSError: pass
    ctx = ctx[: a.ctx_chars]
    # v6.4 hard limit: keep prompt under the 200K-token price tier (assume >=3 chars/token -> 570K chars total)
    room = 570000 - len(task) - 2000
    if len(ctx) > room: ctx = ctx[: max(0, room)]
    if a.mode == "light":
        model, gen, marks = LIGHT, {"temperature": 0.1, "maxOutputTokens": 4096, "thinkingConfig": {"thinkingLevel": os.environ.get("GEMINI_LIGHT_THINK", "medium")}}, ("LIGHT_OK", "LIGHT_FAIL")
        text = task + "\nEnd with LIGHT_OK or LIGHT_FAIL."
    elif a.mode == "review":
        model, marks = HEAVY, ("ASSESS_OK", "ASSESS_BLOCKED")
        gen = {"temperature": 0.1, "maxOutputTokens": 24576, "thinkingConfig": {"thinkingLevel": os.environ.get("GEMINI_REVIEW_THINK", "high")}}  # v6.2 Jeff 21:59: pro high thinking
        text = ("You are a strict code reviewer. Task:\n" + task + "\nContext:\n" + ctx +
                "\nGive numbered must-fix findings with file:line, then end with exactly ASSESS_OK or ASSESS_BLOCKED.")
    elif a.mode == "edits":
        # lane-ops v2: SEARCH/REPLACE blocks apply far more reliably than LLM-written unified diffs
        # (no line numbers or hunk counts to get wrong); apply-edits.py on the NucBox turns them into a git diff.
        model, marks = HEAVY, ("EDITS_END",)
        gen = {"temperature": 0.1, "maxOutputTokens": 65536, "thinkingConfig": {"thinkingLevel": "high"}}
        text = ("You edit a git repo. Task:\n" + task + "\nRepo context:\n" + ctx +
                "\nOutput ONLY edit blocks between a line EDITS_BEGIN and a line EDITS_END. Each block is exactly:\n"
                "FILE: <path relative to repo root>\n<<<<<<< SEARCH\n<lines copied EXACTLY from the current file, enough to be unique>\n"
                "=======\n<replacement lines>\n>>>>>>> REPLACE\n"
                "Use an empty SEARCH section only to create a new file. Keep each SEARCH small (3-15 lines) and unique. "
                "Use several blocks for several places. No line numbers, no diff markers, no prose. "
                "Add/extend tests as the task asks; never delete, skip or weaken tests.")
    else:
        model, marks = HEAVY, ("PATCH_END",)
        gen = {"temperature": 0.1, "maxOutputTokens": 65536, "thinkingConfig": {"thinkingLevel": "high"}}  # v6.2: code fixes at highest thinking
        text = ("You edit a git repo. Task:\n" + task + "\nRepo context:\n" + ctx +
                "\nUse full exact context lines copied from the files shown. Output ONLY one unified diff (git apply format, paths a/ b/ relative to repo root) between lines "
                "PATCH_BEGIN and PATCH_END. Add/extend tests and docs only as the task asks; never delete or weaken tests.")
    out, fin = "", None
    for mx in (gen["maxOutputTokens"], min(65536, gen["maxOutputTokens"] * 2)):
        gen["maxOutputTokens"] = mx
        try:
            out, fin = call(model, text, gen)
        except urllib.error.HTTPError as e:
            print(f"BLOCKER gemini http {e.code}"); return 4
        except Exception as e:
            print(f"BLOCKER gemini error {type(e).__name__}"); return 4
        if any(m in out for m in marks): break
    if a.out: open(a.out, "w").write(out)
    if not out.strip(): print("BLOCKER gemini empty"); return 6
    if a.mode == "edits":
        m = re.search(r"EDITS_BEGIN\s*\n(.*?)EDITS_END", out, re.S)
        body = m.group(1) if m else out
        if "<<<<<<< SEARCH" not in body or ">>>>>>> REPLACE" not in body:
            print(f"BLOCKER no edit blocks (finish={fin})"); return 3
        sys.stdout.write(body.rstrip() + "\n"); return 0
    if a.mode == "patch":
        m = re.search(r"PATCH_BEGIN\s*\n(?:```(?:diff|patch)?\n)?(.*?)(?:```\s*)?PATCH_END", out, re.S) \
            or re.search(r"```(?:diff|patch)\n(.*?)```", out, re.S) or re.search(r"((?:diff --git|--- a/).*)", out, re.S)
        if not m or "@@" not in m.group(1): print(f"BLOCKER no patch (finish={fin})"); return 3
        d = m.group(1).replace("PATCH_END", "").rstrip() + "\n"
        sys.stdout.write(d); return 0
    print(out)
    return 0 if any(m in out for m in marks) else 3

if __name__ == "__main__":
    sys.exit(main())

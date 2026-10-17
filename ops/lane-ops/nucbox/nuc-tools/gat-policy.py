#!/usr/bin/env python3
"""gat-policy.py [--push] PATCH  -- refuse patches that could weaken tests or CI before an unattended push.

Used by gemini-apply-test.sh before `git apply` (strict mode), and since lane-ops v3 by the lane pre-push hook
for EVERY provider (Codex, Cursor, Claude, Gemini) and by pre-karen-check (`--push` mode). Exit 0 = allowed,
3 = refused (reasons on stdout), 2 = usage.
Strict rules (fail closed, Gemini patches):
  * no deleted lines in test files (existing GAT rule, kept);
  * no edits to CI workflows or test-runner configuration (incl. jest/vitest blocks in package.json,
    Makefile/justfile test targets);
  * no edits to package.json lines that define test scripts;
  * no added skip/only/todo markers anywhere (incl. skipIf/runIf, `pytestmark = pytest.mark.skip`,
    `pytest.importorskip`);
  * a patch that names no files is refused.
--push rules (human-reviewed lanes; Karen still gates): skip markers and runner-config edits are refused as above,
but a test-file line may be removed when the same line is added back elsewhere in the diff (a move, e.g. putting
`unittest.main()` at the end of the file). Removing an assertion, a test function or a whole test file is refused.
CI workflow edits are reported as WARN (stdout, exit 0) so a lane can fix CI; pre-karen-check lists them for Karen.
v4 (Karen #151 N3/N4):
  * the diff is read STRICTLY: headers only outside hunks, @@ counts consumed exactly, so an added "++ x" line can
    no longer pose as a "+++ x" file header; malformed input (counts off, stray text) is refused;
  * `--staged REPO` (or `--range REPO BASE HEAD` for pushed commits) checks what is actually staged in REPO (git diff --cached -M, cross-checked with --name-status -z),
    with full old/new file contents. gemini-apply-test.sh runs it after applying, so renames, deletes, binary and
    mode changes are seen even when a patch has no +/- lines;
  * also refused: deleting/renaming/moving a test file, binary or mode changes to test/protected files, early
    `return` / `if False:` / `sys.exit` in tests, a re-definition that shadows a test, tautological asserts
    (`assert True`, `expect(true).toBe(true)`), expectedFailure / xfail / `.failing`, every skip spelling
    (`it .skip`, `it["skip"]`, `test.concurrent.skip`, `test.runIf`, `this.skip()`, `__test__ = False`, ...),
    jest/vitest/playwright configs in any extension, `testing/` dirs, `scripts/*test*`, `.gitattributes`, and
    numeric tolerance/threshold constants changed outside test files. Undecidable cases are refused for a human.
"""
import ast
import os
import re
import subprocess
import sys

from collections import Counter

TEST_FILE = re.compile(
    r"(^|/)(tests?|specs?|__tests__|e2e|testing|__snapshots__)/|(^|/)test_[^/]*\.py$|_test\.(py|go)$"
    r"|\.(test|spec)\.[cm]?[jt]sx?$|\.snap$", re.I
)
CI_OR_RUNNER = re.compile(
    r"(^|/)\.github/|(^|/)\.gitlab-ci\.yml$|(^|/)\.circleci/|(^|/)\.buildkite/|(^|/)Jenkinsfile$|(^|/)\.travis\.yml$"
    r"|(^|/)(azure|bitbucket)-pipelines\.ya?ml$"
    r"|(^|/)(vitest|jest|playwright|karma|cypress|ava|wdio|nightwatch)\.(config|workspace|conf|setup)(\.[\w-]+)*\.[a-z]+$"
    r"|(^|/)vitest\.workspace\.[a-z]+$|(^|/)jest\.config$|(^|/)\.mocharc(\.[a-z]+)?$|(^|/)\.(nycrc|c8rc)(\.[a-z]+)?$"
    r"|(^|/)(pytest\.ini|tox\.ini|noxfile\.py|conftest\.py|setup\.cfg|\.coveragerc|unittest\.cfg)$"
    r"|(^|/)scripts?/[^/]*test[^/]*$|(^|/)\.gitattributes$|(^|/)testing/",
    re.I,
)
CI_FILE = re.compile(r"(^|/)\.github/workflows/|(^|/)\.gitlab-ci\.yml$", re.I)
# B6: Makefile / justfile / Taskfile test targets and recipes
TASK_FILE = re.compile(r"(^|/)(GNUmakefile|[Mm]akefile|[Jj]ustfile|\.justfile|Taskfile\.ya?ml)$")
PKG_TEST_LINE = re.compile(
    r'(^|[{,\s])"(test|pretest|posttest|test:[^"]*|jest|vitest|mocha|ava|nyc|c8|testMatch|testRegex|testPathIgnorePatterns'
    r'|modulePathIgnorePatterns|coveragePathIgnorePatterns|coverageThreshold|testEnvironment|testTimeout|setupFiles[A-Za-z]*)"\s*:',
    re.I,
)
ASSERTION = re.compile(r"\bassert|\bexpect\s*\(|\.should\b|\bself\.assert|\bt\.(is|ok|equal|deepEqual|throws|true|false)\b"
                       r"|\bdef test|\b(it|test|describe)\s*\(|\bclass \w*Test|\bpytest\.raises|assertRaises", re.I)
PYPROJECT_TEST = re.compile(r"\[tool\.(pytest|coverage)|addopts|testpaths", re.I)
# v4 N4: skip/only spelled any way JS allows: `it .skip`, `it["skip"]`, `test.concurrent.skip`, `test.runIf(...)`,
# `describe.each(t).skip`, plus xfail/expectedFailure/failing and collection switches.
JS_SKIP = re.compile(
    r"\b(describe|it|test|context|suite|bench|specify)\b(\s*(\.\s*\w+|\[\s*[\"'`]\w+[\"'`]\s*\]|\([^()]*\)))*?"
    r"\s*(\.\s*|\[\s*[\"'`])(skip|only|todo|fixme|skipIf|runIf|failing|fails)\b"
)
XFAIL_MARK = re.compile(r"\bexpectedFailure\b|\bxfail\b|\b__test__\s*=\s*False\b|\b__unittest_skip__\b|\bSkipTest\b"
                        r"|\bdef\s+load_tests\s*\(|\bpytestmark\b|\bcollect_ignore")
TEST_SKIP_CALL = re.compile(r"\b(this|ctx|context|t)\s*\.\s*skip\s*\(")
# early exits; `return <promise>` idioms common in JS tests (return expect(...)/new Promise/request(...)) stay allowed
EARLY_EXIT = re.compile(r"(^\s*|[:;{)]\s*)(return\b(?!\s+(expect\b|new\s+Promise\b|Promise\.|request\s*\(|supertest\b|page\.|await\b))"
                        r"|sys\.exit\s*\(|os\._exit\s*\(|process\.exit\s*\()")
DEAD_BRANCH = re.compile(r"^\s*(el)?(if|while)\s*\(?\s*(not\s+(True|1)|!\s*(true|1)|False|false|0|None|null|undefined|void 0)\s*\)?\s*[:{)]?\s*$"
                         r"|^\s*(el)?(if|while)\s*\(?\s*(False|false|0|None|null)\s*(and|&&)")
TAUTOLOGY = re.compile(
    r"^\s*assert\s*\(?\s*(True|1|not\s+(False|0|None)|[\"'][^\"']+[\"'])\s*\)?\s*(,|#|$)"
    r"|\bassert(True|_)\s*\(\s*(True|1|true)\s*[,)]|\bassertFalse\s*\(\s*(False|0|None)\s*[,)]"
    r"|\bexpect\s*\(\s*(true|1|!0|!!1)\s*\)\s*\.\s*(toBe|toEqual|toStrictEqual|toBeTruthy|toBeDefined)\s*\("
    r"|\bassert(\.ok)?\s*\(\s*(true|1)\s*[,)]|\bt\.pass\s*\("
)
SAME_ARGS = re.compile(r"\b(assertEqual|assertEquals|assertIs|assert_equal|deepEqual|strictEqual|equal)\s*\(\s*([^,()]+?)\s*,\s*\2\s*[,)]"
                       r"|\bexpect\s*\(\s*([^()]+?)\s*\)\s*\.\s*(toBe|toEqual|toStrictEqual)\s*\(\s*\3\s*\)"
                       r"|^\s*assert\s+([\w.]+)\s*==\s*\5\s*$")
SHADOW_ASSIGN = re.compile(r"^\s*(del\s+)?([\w.]+\.)?(test_\w+|Test\w+)\s*(=(?!=)|$)|\b(setattr|delattr)\s*\([^,]+,\s*[\"']test")
# v4 N4: numeric tolerance/threshold constants outside tests (loosening one is test-weakening by another route)
TOL_WORDS = {"tol", "tolerance", "tolerances", "eps", "epsilon", "threshold", "thresholds", "slack", "atol", "rtol",
             "fuzz", "leeway", "allowance", "maxdiff", "maxerr"}
ASSIGN_NAME = re.compile(r"^\s*(?:export\s+)?(?:(?:const|let|var|static|final|public|private|readonly)\s+)*"
                         r"[\"']?([A-Za-z_][\w.\-]*)[\"']?\s*(?::\s*[\w\[\], .|]+?)?\s*(=(?!=)|:)\s*(.*)$")


def _words(name):
    out = []
    for part in re.split(r"[^A-Za-z0-9]+", name):
        out += [w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", part)]
    joined = name.replace("_", "").replace("-", "").replace(".", "").lower()
    return set(out) | ({"maxdiff"} if "maxdiff" in joined else set()) | ({"maxerr"} if "maxerr" in joined else set())


def tolerance_line(line):
    m = ASSIGN_NAME.match(line)
    if not m or not re.search(r"\d", m.group(3) or ""):
        return False
    return bool(_words(m.group(1)) & TOL_WORDS)


SKIP_MARK = re.compile(
    r"\b(describe|it|test|context|suite|bench)\.(skip|only|todo|skipIf|runIf|fails|fixme)\b"
    r"|\bx(it|describe|test)\s*\(|\bf(it|describe)\s*\("
    r"|\bpytest\.mark\.(skip|skipif|xfail)\b|\bpytest\.(skip|importorskip|xfail)\s*\(|@unittest\.(skip|expectedFailure)"
    r"|\bunittest\.skip(If|Unless)?\s*\(|\bskipTest\s*\(|test\.fixme\s*\(|\bt\.Skip(Now|f)?\s*\(",
)


# ---- Karen #151 N3: strict unified-diff reader ----------------------------------------------------------------------
# File headers ("diff --git", "--- "/"+++ ", rename/copy/mode/index/binary lines) count ONLY outside hunks. Inside a
# hunk the @@ counts are consumed exactly, so an added line "++ x" (shown as "+++ x") stays an added line and can never
# start a new file. Counts that do not match the body, or stray text between hunks, are malformed -> refused.
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
EXT_HDR = re.compile(r"^(old mode|new mode|deleted file mode|new file mode|similarity index|dissimilarity index"
                     r"|rename from|rename to|copy from|copy to|index)( |$)")
GIT_LINE = re.compile(r'^diff --git ("(?:[^"\\]|\\.)*"|\S+) ("(?:[^"\\]|\\.)*"|\S+)$')


class Malformed(Exception):
    pass


def _unquote(p):
    p = p.strip()
    if len(p) >= 2 and p[0] == '"' and p[-1] == '"':
        try:
            return p[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape").encode("latin-1").decode("utf-8", "replace")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return p[1:-1]
    return p


def _strip(p, pre):
    return p[len(pre):] if p.startswith(pre) else p


class FileDiff:
    def __init__(self, git):
        self.git = git
        self.old = self.new = None
        self.status = "M"           # M, A, D, R, C
        self.binary = False
        self.mode_change = False
        self.minus = self.plus = False
        self.hunks = 0
        self.lines = []             # (sign, text)

    def paths(self):
        return sorted({p for p in (self.old, self.new) if p})


def parse_files(text):
    """Strictly parse a unified/git diff into [FileDiff]. Raises Malformed."""
    files, cur = [], None
    rem_old = rem_new = 0
    state = "out"                   # out | hunk | binary
    prev_minus = False
    for n, line in enumerate(text.splitlines(), 1):
        line = line[:-1] if line.endswith("\r") else line
        if state == "hunk":
            if line.startswith("\\"):
                continue
            tag, body = (line[0], line[1:]) if line else (" ", "")
            if tag == " ":
                rem_old -= 1; rem_new -= 1
            elif tag == "-":
                rem_old -= 1; cur.lines.append(("-", body))
            elif tag == "+":
                rem_new -= 1; cur.lines.append(("+", body))
            else:
                raise Malformed(f"line {n}: hunk shorter than its @@ header says")
            if rem_old < 0 or rem_new < 0:
                raise Malformed(f"line {n}: hunk body does not match its @@ counts")
            if rem_old == 0 and rem_new == 0:
                state = "out"
            continue
        if state == "binary":
            if not line.startswith("diff --git "):
                continue
            state = "out"
        was_minus, prev_minus = prev_minus, False
        if line.startswith("diff --git "):
            m = GIT_LINE.match(line)
            if not m:
                raise Malformed(f"line {n}: unreadable diff --git header")
            cur = FileDiff(True); files.append(cur)
            cur.old = _strip(_unquote(m.group(1)), "a/")
            cur.new = _strip(_unquote(m.group(2)), "b/")
            continue
        hdr_ok = cur is not None and cur.hunks == 0 and not cur.plus
        m = EXT_HDR.match(line)
        if m and hdr_ok and cur.git and not cur.minus:
            h, val = m.group(1), _unquote(line[len(m.group(1)):].strip())
            if h == "deleted file mode":
                cur.status = "D"
            elif h == "new file mode":
                cur.status = "A"
            elif h in ("rename from", "copy from"):
                cur.status, cur.old = ("R" if h[0] == "r" else "C"), val
            elif h in ("rename to", "copy to"):
                cur.new = val
            elif h in ("old mode", "new mode"):
                cur.mode_change = True
            continue
        if hdr_ok and cur.git and line.startswith("Binary files ") and line.endswith(" differ"):
            cur.binary = True
            continue
        if hdr_ok and cur.git and line == "GIT binary patch":
            cur.binary = True; state = "binary"
            continue
        if line.startswith("--- "):
            if not (cur is not None and cur.git and hdr_ok and not cur.minus):
                cur = FileDiff(False); files.append(cur)          # plain (non-git) diff file
            cur.minus = True; prev_minus = True
            p = _unquote(line[4:].split("\t")[0])
            if p == "/dev/null":
                cur.status = "A"
            elif not cur.git:
                cur.old = _strip(p, "a/")
            continue
        if line.startswith("+++ "):
            if not was_minus:
                raise Malformed(f"line {n}: '+++' outside a file header (an added '++' line outside its hunk?)")
            cur.plus = True
            p = _unquote(line[4:].split("\t")[0])
            if p == "/dev/null":
                cur.status = "D"
            elif not cur.git:
                cur.new = _strip(p, "b/")
            if cur.status == "A":
                cur.old = None
            if cur.status == "D":
                cur.new = None
            continue
        mh = HUNK.match(line)
        if mh:
            if cur is None or not cur.plus:
                raise Malformed(f"line {n}: hunk without ---/+++ file header")
            rem_old = int(mh.group(2)) if mh.group(2) is not None else 1
            rem_new = int(mh.group(4)) if mh.group(4) is not None else 1
            cur.hunks += 1
            state = "hunk" if (rem_old or rem_new) else "out"
            continue
        if line.startswith("\\") or line.strip() == "":
            continue
        if cur is None:
            continue                 # preamble before the first file (mail headers, commit text)
        raise Malformed(f"line {n}: text outside any hunk ({line[:40]!r}); hunk counts do not match")
    if state == "hunk":
        raise Malformed("patch ends inside a hunk (@@ counts do not match)")
    for f in files:
        if f.status == "D":
            f.new = None
        if f.status == "A":
            f.old = None
    return files


def parse(text):
    """Yield (path, sign, line) for every added/removed line (removed lines carry the OLD path, added the NEW)."""
    for f in parse_files(text):
        for sign, body in f.lines:
            path = (f.old or f.new) if sign == "-" else (f.new or f.old)
            yield path, sign, body


def _is_test(p):
    return bool(p and TEST_FILE.search(p))


def _protected(p):
    return bool(p and (CI_OR_RUNNER.search(p) or TASK_FILE.search(p)))


def _py_defs(text):
    """Count test defs/classes per (scope, name); also count returns/dead branches/tautologies inside test bodies."""
    try:
        tree = ast.parse(text or "")
    except SyntaxError:
        return None
    names, stats = Counter(), Counter()

    def falsy(node):
        return isinstance(node, ast.Constant) and not node.value or (
            isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and isinstance(node.operand, ast.Constant) and node.operand.value)

    def body_stats(fn):
        stack = list(fn.body)
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(n, ast.Return):
                stats[(fn.name, "return")] += 1
            if isinstance(n, (ast.If, ast.While)) and falsy(n.test):
                stats[(fn.name, "dead")] += 1
            if isinstance(n, ast.Assert) and isinstance(n.test, ast.Constant) and n.test.value:
                stats[(fn.name, "taut")] += 1
            stack.extend(ast.iter_child_nodes(n))

    def walk(body, scope):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if n.name.startswith(("test", "Test")):
                    names[(scope, n.name)] += 1
                if isinstance(n, ast.ClassDef):
                    walk(n.body, scope + "." + n.name)
                elif n.name.startswith("test"):
                    body_stats(n)
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.Delete)):
                tgts = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                for t in tgts:
                    if isinstance(t, ast.Name) and t.id.startswith(("test", "Test")):
                        names[(scope, t.id)] += 1
                    elif isinstance(t, ast.Attribute) and t.attr.startswith("test"):
                        names[(scope + ".<attr>", t.attr)] += 2   # rebinding a test attribute always shadows it
    walk(tree.body, "")
    return names, stats


def check_files(files, push=False, warnings=None, contents=None):
    """Return refusal reasons for parsed FileDiffs. contents: {path: (old_text|None, new_text|None)} when known."""
    reasons = []
    contents = contents or {}
    rows = [(f, ((f.old or f.new) if s == "-" else (f.new or f.old)), s, l) for f in files for s, l in f.lines]
    # Moves: a test-file line removed and added back (stripped) anywhere in the diff is not a deletion (push mode).
    added = Counter(l.strip() for f, p, sg, l in rows if sg == "+" and _is_test(p))
    for f in files:
        for p in f.paths():
            if push and CI_FILE.search(p):
                if warnings is not None:
                    warnings.append(f"edits CI workflow {p} (Karen must confirm it still runs every test)")
            elif CI_OR_RUNNER.search(p):
                reasons.append(f"edits CI/test-runner config {p}")
        if f.status == "D" and _is_test(f.old):
            reasons.append(f"deletes test file {f.old}")
        if f.status in ("R", "C") and _is_test(f.old) and f.status == "R":
            reasons.append(f"renames/moves test file {f.old} -> {f.new} (may stop it being collected)")
        if f.binary and any(_is_test(p) or _protected(p) for p in f.paths()):
            reasons.append(f"binary change to test/protected file {' -> '.join(f.paths())}")
        if f.mode_change and any(_is_test(p) or _protected(p) for p in f.paths()):
            reasons.append(f"mode change on test/protected file {' -> '.join(f.paths())}")
    for f, path, sign, line in rows:
        test = _is_test(path)
        if sign == "-" and test:
            if not push:
                reasons.append(f"deletes a line in test file {path}")
            elif added[line.strip()] > 0:
                added[line.strip()] -= 1
            elif ASSERTION.search(line):
                reasons.append(f"removes an assertion or test in {path}: {line.strip()[:80]}")
        if push and CI_FILE.search(path):
            continue
        if TASK_FILE.search(path) and re.search(r"test", line, re.I):
            reasons.append(f"changes a test target in {path}: {line.strip()[:80]}")
        if path.endswith("package.json") and PKG_TEST_LINE.search(line):
            reasons.append(f"changes a test script in {path}")
        if path.endswith("pyproject.toml") and PYPROJECT_TEST.search(line):
            reasons.append(f"changes pytest/coverage settings in {path}")
        if not test and tolerance_line(line):
            reasons.append(f"changes a tolerance/threshold constant in {path} (needs human review): {line.strip()[:80]}")
        if sign != "+":
            continue
        if SKIP_MARK.search(line) or JS_SKIP.search(line) or XFAIL_MARK.search(line):
            reasons.append(f"adds a skip/only/xfail marker in {path}: {line.strip()[:80]}")
        if not test:
            continue
        if TEST_SKIP_CALL.search(line):
            reasons.append(f"adds a runtime skip in {path}: {line.strip()[:80]}")
        if DEAD_BRANCH.search(line):
            reasons.append(f"adds a dead branch (if False / while 0) in {path}: {line.strip()[:80]}")
        if TAUTOLOGY.search(line) or SAME_ARGS.search(line):
            reasons.append(f"adds a tautological assertion in {path}: {line.strip()[:80]}")
        py_known = path.endswith(".py") and path in contents
        if SHADOW_ASSIGN.search(line) and not py_known:   # with the file, the AST check below decides precisely
            reasons.append(f"rebinds or deletes a test name in {path} (needs human review): {line.strip()[:80]}")
        if EARLY_EXIT.search(line) and f.status != "A" and not py_known:
            # can't tell a helper's return from an early exit in an existing test without the file -> human review
            reasons.append(f"adds an early exit to an existing test file {path} (needs human review): {line.strip()[:80]}")
    # Full-content Python checks (staged mode): shadowing re-definitions, early returns, dead branches inside tests.
    for path, (old, new) in contents.items():
        if not (_is_test(path) and path.endswith(".py")) or new is None:
            continue
        a, b = _py_defs(old or ""), _py_defs(new)
        if b is None:
            reasons.append(f"test file {path} does not parse; refusing (needs human review)")
            continue
        (on, ost), (nn, nst) = a if a is not None else (Counter(), Counter()), b
        for key, cnt in nn.items():
            if cnt > 1 and cnt > on.get(key, 0):
                reasons.append(f"re-defines {key[0] + '.' if key[0] else ''}{key[1].lstrip('.')} in {path}; the later one shadows the earlier test")
        for (fn, kind), cnt in nst.items():
            if cnt <= ost.get((fn, kind), 0):
                continue
            existed = any(k[1] == fn for k in on)
            if kind == "return" and not existed:
                continue          # a brand-new test cannot weaken an existing one by returning early
            what = {"return": "an early return", "dead": "a dead branch", "taut": "a tautological assert"}[kind]
            reasons.append(f"adds {what} inside {'existing ' if existed else ''}test {fn} in {path}")
    if not files:
        reasons.append("patch names no files")
    out, seen = [], set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def check(text, push=False, warnings=None):
    """Return refusal reasons for a patch text. In push mode, CI-workflow edits go to `warnings` instead (if given)."""
    try:
        files = parse_files(text)
    except Malformed as e:
        return [f"malformed diff ({e}); regenerate it with git diff"]
    return check_files(files, push=push, warnings=warnings)


def _git(repo, *args):
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotePath=false", *args], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout


def staged(repo, base="HEAD", head=None):
    """Read what is staged in repo vs base (or the commits base..head): (FileDiff list, contents).
    Raises RuntimeError/Malformed (fail closed)."""
    rev = [base, head] if head else ["--cached", base]
    common = ["-M", "--no-color", "--no-ext-diff", "--no-textconv", "--ignore-submodules=none", *rev]
    text = _git(repo, "diff", "--src-prefix=a/", "--dst-prefix=b/", *common).decode("utf-8", "surrogateescape")
    files = parse_files(text)
    raw = _git(repo, "diff", "--name-status", "-z", *common).split(b"\0")
    ns, i = [], 0
    while i < len(raw) and raw[i]:
        st = raw[i].decode()[:1]
        if st in "RC":
            ns.append((st, raw[i + 1].decode("utf-8", "surrogateescape"), raw[i + 2].decode("utf-8", "surrogateescape"))); i += 3
        else:
            ns.append((st, raw[i + 1].decode("utf-8", "surrogateescape"), None)); i += 2
    seen = {p for f in files for p in f.paths()}
    for st, a, b in ns:
        for p in (a, b):
            if p and p not in seen:
                raise Malformed(f"name-status lists {p!r} but the patch text does not (unreadable change)")
        for f in files:
            if (b or a) == (f.new or f.old):
                if st in "ADRC":
                    f.status = st
                elif st == "T":
                    f.mode_change = True
    contents = {}
    for f in files:
        key = f.new or f.old
        if not (_is_test(key) or _is_test(f.old)) or not key.endswith(".py"):
            continue
        old = _git(repo, "show", f"{base}:{f.old}").decode("utf-8", "replace") if f.old else None
        new = _git(repo, "show", f"{head or ''}:{f.new}").decode("utf-8", "replace") if f.new else None
        contents[key] = (old, new)
    return files, contents


def main(argv):
    args = argv[1:]
    push = "--push" in args
    args = [a for a in args if a != "--push"]
    warnings = []
    if (len(args) == 2 and args[0] == "--staged") or (len(args) == 4 and args[0] == "--range"):
        try:
            files, contents = staged(args[1]) if args[0] == "--staged" else staged(args[1], args[2], args[3])
        except (RuntimeError, Malformed, OSError, subprocess.TimeoutExpired) as e:
            print(f"GAT policy refuses: cannot read the staged change ({e})")
            return 3
        reasons = check_files(files, push=push, warnings=warnings, contents=contents)
        if not files and args[0] == "--staged":
            reasons = ["nothing is staged"]
    elif len(args) == 1 and not args[0].startswith("--"):
        try:
            text = open(args[0], errors="replace").read()
        except OSError as e:
            print(f"GAT policy refuses: cannot read patch ({e.strerror})")
            return 3
        reasons = check(text, push=push, warnings=warnings)
    else:
        print("usage: gat-policy.py [--push] PATCH | [--push] --staged REPO | [--push] --range REPO BASE HEAD")
        return 2
    for w in warnings:
        print(f"GAT policy WARN: {w}")
    for r in reasons:
        print(f"GAT policy refuses: {r}")
    return 3 if reasons else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

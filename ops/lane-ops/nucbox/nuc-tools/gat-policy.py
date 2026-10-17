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
"""
import re
import sys

from collections import Counter

TEST_FILE = re.compile(
    r"(^|/)(tests?|specs?|__tests__|e2e)/|(^|/)test_[^/]*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$", re.I
)
CI_OR_RUNNER = re.compile(
    r"(^|/)\.github/|(^|/)\.gitlab-ci\.yml$|(^|/)(vitest|jest|playwright|karma|cypress)\.config\.[cm]?[jt]s$"
    r"|(^|/)\.mocharc(\.[a-z]+)?$|(^|/)(pytest\.ini|tox\.ini|noxfile\.py|conftest\.py|setup\.cfg)$",
    re.I,
)
CI_FILE = re.compile(r"(^|/)\.github/workflows/|(^|/)\.gitlab-ci\.yml$", re.I)
# B6: Makefile / justfile / Taskfile test targets and recipes
TASK_FILE = re.compile(r"(^|/)(GNUmakefile|[Mm]akefile|[Jj]ustfile|\.justfile|Taskfile\.ya?ml)$")
PKG_TEST_LINE = re.compile(
    r'^\s*"(test|pretest|posttest|test:[^"]*|jest|vitest|mocha|ava|nyc|c8|testMatch|testRegex|testPathIgnorePatterns'
    r'|modulePathIgnorePatterns|coveragePathIgnorePatterns|coverageThreshold|testEnvironment|testTimeout|setupFiles[A-Za-z]*)"\s*:',
    re.I,
)
ASSERTION = re.compile(r"\bassert|\bexpect\s*\(|\.should\b|\bself\.assert|\bt\.(is|ok|equal|deepEqual|throws|true|false)\b"
                       r"|\bdef test|\b(it|test|describe)\s*\(|\bclass \w*Test|\bpytest\.raises|assertRaises", re.I)
PYPROJECT_TEST = re.compile(r"\[tool\.(pytest|coverage)|addopts|testpaths", re.I)
SKIP_MARK = re.compile(
    r"\b(describe|it|test|context|suite|bench)\.(skip|only|todo|skipIf|runIf|fails|fixme)\b"
    r"|\bx(it|describe|test)\s*\(|\bf(it|describe)\s*\("
    r"|\bpytest\.mark\.(skip|skipif|xfail)\b|\bpytest\.(skip|importorskip|xfail)\s*\(|@unittest\.(skip|expectedFailure)"
    r"|\bunittest\.skip(If|Unless)?\s*\(|\bskipTest\s*\(|test\.fixme\s*\(|\bt\.Skip(Now|f)?\s*\(",
)


def parse(text):
    """Yield (path, sign, line) for every added/removed line of a unified diff."""
    old = new = None
    for raw in text.splitlines():
        if raw.startswith("--- "):
            old = raw[4:].split("\t")[0].strip()
            old = None if old == "/dev/null" else re.sub(r"^a/", "", old)
            continue
        if raw.startswith("+++ "):
            new = raw[4:].split("\t")[0].strip()
            new = None if new == "/dev/null" else re.sub(r"^b/", "", new)
            continue
        path = new or old
        if path is None or raw.startswith(("@@", "diff ", "index ", "\\")):
            continue
        if raw.startswith("+"):
            yield path, "+", raw[1:]
        elif raw.startswith("-"):
            yield path, "-", raw[1:]


def check(text, push=False, warnings=None):
    """Return refusal reasons. In push mode, CI-workflow edits go to `warnings` instead (if given)."""
    reasons = []
    files = set()
    rows = list(parse(text))
    # Moves: a test-file line removed and added back (stripped) anywhere in the diff is not a deletion (push mode).
    added = Counter(l.strip() for p, sg, l in rows if sg == "+" and TEST_FILE.search(p))
    for path, sign, line in rows:
        files.add(path)
        if sign == "-" and TEST_FILE.search(path):
            if not push:
                reasons.append(f"deletes a line in test file {path}")
            elif added[line.strip()] > 0:
                added[line.strip()] -= 1
            elif ASSERTION.search(line):
                reasons.append(f"removes an assertion or test in {path}: {line.strip()[:80]}")
        if push and CI_FILE.search(path):
            if warnings is not None:
                warnings.append(f"edits CI workflow {path} (Karen must confirm it still runs every test)")
            continue
        if CI_OR_RUNNER.search(path):
            reasons.append(f"edits CI/test-runner config {path}")
        if TASK_FILE.search(path) and re.search(r"test", line, re.I):
            reasons.append(f"changes a test target in {path}: {line.strip()[:80]}")
        if path.endswith("package.json") and PKG_TEST_LINE.search(line):
            reasons.append(f"changes a test script in {path}")
        if path.endswith("pyproject.toml") and PYPROJECT_TEST.search(line):
            reasons.append(f"changes pytest/coverage settings in {path}")
        if sign == "+" and SKIP_MARK.search(line):
            reasons.append(f"adds a skip/only marker in {path}: {line.strip()[:80]}")
    if not files:
        reasons.append("patch names no files")
    out, seen = [], set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def main(argv):
    args = argv[1:]
    push = "--push" in args
    args = [a for a in args if a != "--push"]
    if len(args) != 1:
        print("usage: gat-policy.py [--push] PATCH")
        return 2
    try:
        text = open(args[0], errors="replace").read()
    except OSError as e:
        print(f"GAT policy refuses: cannot read patch ({e.strerror})")
        return 3
    warnings = []
    reasons = check(text, push=push, warnings=warnings)
    for w in warnings:
        print(f"GAT policy WARN: {w}")
    for r in reasons:
        print(f"GAT policy refuses: {r}")
    return 3 if reasons else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

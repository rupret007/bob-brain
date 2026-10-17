#!/usr/bin/env python3
"""gat-policy.py PATCH  -- refuse LLM patches that could weaken tests or CI before an unattended push.

Used by gemini-apply-test.sh before `git apply`. Exit 0 = allowed, 3 = refused (reasons on stdout).
Rules (fail closed):
  * no deleted lines in test files (existing GAT rule, kept);
  * no edits to CI workflows or test-runner configuration;
  * no edits to package.json lines that define test scripts;
  * no added skip/only/todo markers anywhere;
  * a patch that names no files is refused.
"""
import re
import sys

TEST_FILE = re.compile(
    r"(^|/)(tests?|specs?|__tests__|e2e)/|(^|/)test_[^/]*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$", re.I
)
CI_OR_RUNNER = re.compile(
    r"(^|/)\.github/|(^|/)\.gitlab-ci\.yml$|(^|/)(vitest|jest|playwright|karma|cypress)\.config\.[cm]?[jt]s$"
    r"|(^|/)\.mocharc(\.[a-z]+)?$|(^|/)(pytest\.ini|tox\.ini|noxfile\.py|conftest\.py|setup\.cfg)$",
    re.I,
)
PKG_TEST_LINE = re.compile(r'^\s*"(test|pretest|posttest|test:[^"]*)"\s*:', re.I)
PYPROJECT_TEST = re.compile(r"\[tool\.(pytest|coverage)|addopts|testpaths", re.I)
SKIP_MARK = re.compile(
    r"\b(describe|it|test|context|suite)\.(skip|only|todo)\b|\bx(it|describe|test)\s*\(|\bf(it|describe)\s*\("
    r"|@pytest\.mark\.(skip|skipif|xfail)|pytest\.skip\s*\(|@unittest\.skip|\bskipTest\s*\(|test\.fixme\s*\(",
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


def check(text):
    reasons = []
    files = set()
    for path, sign, line in parse(text):
        files.add(path)
        if sign == "-" and TEST_FILE.search(path):
            reasons.append(f"deletes a line in test file {path}")
        if CI_OR_RUNNER.search(path):
            reasons.append(f"edits CI/test-runner config {path}")
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
    if len(argv) != 2:
        print("usage: gat-policy.py PATCH")
        return 2
    try:
        text = open(argv[1], errors="replace").read()
    except OSError as e:
        print(f"GAT policy refuses: cannot read patch ({e.strerror})")
        return 3
    reasons = check(text)
    for r in reasons:
        print(f"GAT policy refuses: {r}")
    return 3 if reasons else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

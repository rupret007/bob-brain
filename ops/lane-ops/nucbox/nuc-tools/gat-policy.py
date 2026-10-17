#!/usr/bin/env python3
"""gat-policy.py [--push] PATCH  -- refuse patches that could weaken tests or CI before an unattended push.

Used by gemini-apply-test.sh before `git apply` (strict mode), and since lane-ops v3 by the lane pre-push hook
for EVERY provider (Codex, Cursor, Claude, Gemini) and by pre-karen-check (`--push` mode). Exit 0 = allowed,
3 = refused (reasons on stdout), 2 = usage.
Strict rules (fail closed, Gemini patches):
  * no deleted lines in test files, except a proven value-preserving JS/TS helper return-alias refactor;
  * no edits to CI workflows or test-runner configuration (incl. jest/vitest blocks in package.json,
    Makefile/justfile test targets);
  * no edits to package.json lines that define test scripts;
  * no added skip/only/todo markers anywhere (incl. skipIf/runIf, `pytestmark = pytest.mark.skip`,
    `pytest.importorskip`);
  * added returns in existing JS/TS tests must be the final statement of the test callback itself;
  * added lines must not close existing JS/TS blocks; only a proven helper return-alias refactor is exempt;
  * assertions in added/changed JS/TS functions need a proven direct invocation path;
  * added JS/TS runner/assertion bindings, process.exit calls and jest.mock/vi.mock are refused;
  * returns in hooks are refused, including terminal returns;
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
import difflib
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
# Legacy return heuristics for push mode and other languages. Strict JS/TS checks parse structure.
EARLY_EXIT = re.compile(r"(^\s*|[:;{)]\s*)(return\b(?!\s+(expect\b|new\s+Promise\b|Promise\.|request\s*\(|supertest\b|page\.|await\b))"
                        r"|sys\.exit\s*\(|os\._exit\s*\(|process\.exit\s*\()")
JS_FILE = re.compile(r"\.[cm]?[jt]sx?$", re.I)
EXIT_CALL = re.compile(r"(^\s*|[:;{)]\s*)(sys\.exit\s*\(|os\._exit\s*\(|process\.exit\s*\()")
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
        self.new_lines = {}         # new-file line number -> added/context text (never bridge hunk gaps)
        self.removed_lines = {}     # old-file line number -> index in lines
        self.added_lines = set()    # new-file line numbers of additions

    def paths(self):
        return sorted({p for p in (self.old, self.new) if p})


def parse_files(text):
    """Strictly parse a unified/git diff into [FileDiff]. Raises Malformed."""
    files, cur = [], None
    rem_old = rem_new = 0
    old_lineno = new_lineno = 0
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
            if tag in (" ", "-"):
                if tag == "-":
                    cur.removed_lines[old_lineno] = len(cur.lines) - 1
                old_lineno += 1
            if tag in (" ", "+"):
                cur.new_lines[new_lineno] = body
                if tag == "+":
                    cur.added_lines.add(new_lineno)
                new_lineno += 1
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
            old_lineno = int(mh.group(1))
            new_lineno = int(mh.group(3))
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


class JSSyntaxError(ValueError):
    pass


class JSNode:
    """A lexical token or balanced delimiter node, with source line provenance."""
    def __init__(self, kind, text, line, children=(), end_line=None):
        self.kind, self.text, self.line = kind, text, line
        self.children = list(children)
        self.end_line = line if end_line is None else end_line


def _js_parse(source):
    """Conservative JS/TS structural parser; never execute the candidate's code.

    Strings/comments are lexed before delimiters. Expressions remain token trees;
    callback argument lists and statement boundaries are parsed below. Regex literals,
    interpolated templates, JSX and escaped identifiers are deliberately undecidable
    here: refuse for review rather than mistaking their contents for control flow.
    This keeps the standalone Python gate independent of a candidate repo's packages.
    """
    root = JSNode('root', '', 1)
    stack = [root]
    i, line = 0, 1
    while i < len(source):
        c = source[i]
        if c.isspace():
            line += c == '\n'
            i += 1
            continue
        if source.startswith('//', i):
            end = source.find('\n', i)
            i = len(source) if end < 0 else end
            continue
        if source.startswith('/*', i):
            end = source.find('*/', i + 2)
            if end < 0:
                raise JSSyntaxError('unterminated comment')
            line += source[i:end + 2].count('\n')
            i = end + 2
            continue
        start, start_line = i, line
        if c in "\"'`":
            i += 1
            while i < len(source) and source[i] != c:
                if c == '`' and source.startswith('${', i):
                    raise JSSyntaxError('interpolated template needs review')
                if source[i] == '\\':
                    i += 1
                if i < len(source):
                    line += source[i] == '\n'
                i += 1
            if i == len(source):
                raise JSSyntaxError('unterminated string')
            i += 1
            node = JSNode('string', source[start:i], start_line, end_line=line)
        elif c.isalpha() or c in '_$':
            i += 1
            while i < len(source) and (source[i].isalnum() or source[i] in '_$'):
                i += 1
            node = JSNode('word', source[start:i], line)
        elif c.isdigit():
            i += 1
            while i < len(source) and (source[i].isalnum() or source[i] in '._'):
                i += 1
            node = JSNode('number', source[start:i], line)
        elif c in '({[':
            node = JSNode('group', c, line)
            stack[-1].children.append(node)
            stack.append(node)
            i += 1
            continue
        elif c in ')}]':
            if len(stack) == 1 or stack[-1].text != {')': '(', '}': '{', ']': '['}[c]:
                raise JSSyntaxError('unmatched delimiter')
            stack.pop().end_line = line
            i += 1
            continue
        elif c in '/\\' or source.startswith('</', i) or (c == '<' and i + 1 < len(source) and source[i+1].isalpha()):
            raise JSSyntaxError('ambiguous expression syntax needs review')
        else:
            op = next((op for op in ('===', '!==', '=>', '==', '!=', '<=', '>=', '&&', '||', '??', '?.', '++', '--', '**', '...')
                       if source.startswith(op, i)), c)
            i += len(op)
            node = JSNode('punct', op, line)
        stack[-1].children.append(node)
    if len(stack) != 1:
        raise JSSyntaxError('incomplete file / unclosed delimiter')
    return root


def _js_walk(node):
    yield node
    for child in node.children:
        yield from _js_walk(child)


def _js_statements(nodes):
    """Parse statement ownership, including unbraced controls and ASI returns.

    A return inside an if/loop/label is a child statement, never a direct return
    of the containing callback. Unknown compound forms cannot earn an exemption.
    """
    def statement(i):
        if i >= len(nodes):
            raise JSSyntaxError('missing statement')
        start = i
        word = nodes[i].text
        if word in ('if', 'for', 'while', 'with', 'switch'):
            i += 1
            if i < len(nodes) and nodes[i].text == 'await':
                i += 1
            if i >= len(nodes) or nodes[i].text != '(':
                raise JSSyntaxError('invalid control condition')
            i += 1
            if i >= len(nodes):
                raise JSSyntaxError('missing control body')
            _, i = statement(i)
            if word == 'if' and i < len(nodes) and nodes[i].text == 'else':
                _, i = statement(i + 1)
            return ('control', start, i), i
        if word == 'do':
            _, i = statement(i + 1)
            if i + 1 >= len(nodes) or nodes[i].text != 'while' or nodes[i+1].text != '(':
                raise JSSyntaxError('invalid do/while')
            i += 2
            if i < len(nodes) and nodes[i].text == ';':
                i += 1
            return ('control', start, i), i
        if i + 1 < len(nodes) and nodes[i].kind == 'word' and nodes[i+1].text == ':':
            _, i = statement(i + 2)
            return ('label', start, i), i
        if word == '{':
            return ('block', start, i + 1), i + 1
        if word == 'try':
            i += 1
            if i >= len(nodes) or nodes[i].text != '{':
                raise JSSyntaxError('invalid try')
            i += 1
            while i < len(nodes) and nodes[i].text in ('catch', 'finally'):
                i += 1
                if i < len(nodes) and nodes[i].text == '(':
                    i += 1
                if i >= len(nodes) or nodes[i].text != '{':
                    raise JSSyntaxError('invalid handler')
                i += 1
            return ('control', start, i), i
        kind = 'return' if word == 'return' else 'expression'
        i += 1
        while i < len(nodes):
            if nodes[i].text == ';':
                i += 1
                break
            # ASI after return's newline, or before a new declaration/return.
            if nodes[i].line > nodes[i-1].end_line and (
                    (kind == 'return' and i == start + 1) or
                    nodes[i].text in ('return', 'const', 'let', 'var', 'throw', 'if', 'for', 'while')):
                break
            # A new expression on the next line cannot be swallowed into the
            # return's operand (e.g. `return void 0\n expect(...)`). Ambiguous
            # continuations are conservative: only explicit operators/groups join.
            if (nodes[i].line > nodes[i-1].end_line
                    and (nodes[i].kind in ('word', 'number', 'string') or nodes[i].text in ('{', '!', '~', '++', '--'))
                    and (nodes[i-1].kind in ('word', 'number', 'string', 'group'))
                    and nodes[i-1].text not in ('await', 'new', 'void', 'typeof', 'delete', 'instanceof', 'in')):
                break
            # A function declaration ends with its body, without needing ';'.
            if word in ('function', 'async') and nodes[i].text == '{':
                i += 1
                break
            i += 1
        return (kind, start, i), i

    result, i = [], 0
    while i < len(nodes):
        item, i = statement(i)
        result.append(item)
    return result


def _js_callback_bodies(root):
    bodies = set()
    for parent in _js_walk(root):
        nodes = parent.children
        for i, node in enumerate(nodes):
            if node.text != '(' or i == 0:
                continue
            # Only known direct test registration calls can authorize a return.
            j = i - 1
            while j >= 2 and nodes[j-1].text == '.' and nodes[j].text in ('concurrent', 'serial'):
                j -= 2
            if nodes[j].text not in ('it', 'test', 'specify') or (j and nodes[j-1].text in ('.', '?.')):
                continue
            args, arg = [], []
            for child in node.children:
                if child.text == ',':
                    args.append(arg); arg = []
                else:
                    arg.append(child)
            args.append(arg)
            # A named test's second argument is its callback (third may be timeout).
            if len(args) < 2:
                continue
            fn = args[1]
            if fn and fn[0].text == 'async':
                fn = fn[1:]
            if len(fn) == 3 and fn[0].text == '(' and fn[1].text == '=>' and fn[2].text == '{':
                bodies.add(fn[2])
            elif fn and fn[0].text == 'function':
                fn = fn[1:]
                if fn and fn[0].kind == 'word':
                    fn = fn[1:]
                if len(fn) == 2 and fn[0].text == '(' and fn[1].text == '{':
                    bodies.add(fn[1])
    return bodies


def _js_helper_alias_refactors(old, new, old_tree):
    """Recognize only `return y;` -> `const z = y; return z;` in a top-level helper.

    Karen's accepted helper repro is value-preserving. It does not authorize
    arbitrary helper deletion, assertion removal, or new returns in helpers.
    """
    helper_returns = set()
    nodes = old_tree.children
    for i in range(len(nodes) - 3):
        if (nodes[i].text == 'function' and nodes[i+1].kind == 'word'
                and not nodes[i+1].text.lower().startswith(('test', 'spec'))
                and nodes[i+2].text == '(' and nodes[i+3].text == '{'):
            body = nodes[i+3]
            statements = _js_statements(body.children)
            if statements and statements[-1][0] == 'return':
                helper_returns.add(body.children[statements[-1][1]].line)
    removed, returns = set(), set()
    a, b = old.splitlines(), new.splitlines()
    for tag, i, j, k, l in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != 'replace' or j-i != 1 or l-k != 2 or i+1 not in helper_returns:
            continue
        before = _js_parse(a[i]).children
        after = _js_parse('\n'.join(b[k:l])).children
        if (len(before) == 3 and before[0].text == 'return' and before[1].kind == 'word' and before[2].text == ';'
                and len(after) == 8 and after[0].text == 'const' and after[1].kind == 'word'
                and [n.text for n in after[2:]] == ['=', before[1].text, ';', 'return', after[1].text, ';']
                and after[1].text != before[1].text
                and sum(n.kind == 'word' and n.text == after[1].text for n in _js_walk(_js_parse(new))) == 2):
            removed.add(i+1)
            returns.add(k+2)
    return removed, returns


def _js_added(nodes, added):
    return any(n.line in added for node in nodes for n in _js_walk(node))


def _js_binding_reasons(tree, added, path):
    """Inspect binding targets, not RHS uses of the runner/assertion names.

    Destructuring is deliberately conservative: an ambiguous protected name in
    a target needs review. Strings and comments are already separate tokens.
    """
    protected = {'expect', 'it', 'test', 'describe'}
    reasons = []

    def binding(nodes):
        if (_js_added(nodes, added) and
                any(n.kind == 'word' and n.text in protected for node in nodes for n in _js_walk(node))):
            reasons.append(f'rebinds a test/assertion name in {path}')

    for parent in _js_walk(tree):
        nodes = parent.children
        for i, node in enumerate(nodes):
            if node.text in ('const', 'let', 'var'):
                # At this level commas separate declarators, not nested RHS args.
                j = i + 1
                while j < len(nodes):
                    start = j
                    while j < len(nodes) and nodes[j].text not in ('=', ';', ',', 'in', 'of'):
                        if j > start and nodes[j].line > nodes[j-1].end_line:
                            break
                        j += 1
                    binding(nodes[start:j])
                    if j < len(nodes) and nodes[j].text == ',':
                        j += 1
                        continue
                    if j == len(nodes) or nodes[j].text != '=':
                        break
                    j += 1
                    while j < len(nodes) and nodes[j].text not in (';', ','):
                        if nodes[j].line > nodes[j-1].end_line:
                            break
                        j += 1
                    if j == len(nodes) or nodes[j].text != ',':
                        break
                    j += 1
            if node.text in ('function', 'class'):
                j = i + 1
                if j < len(nodes) and nodes[j].text == '*':
                    j += 1
                binding(nodes[j:j+1])
            if node.text == 'import':
                j = i + 1
                while j < len(nodes) and nodes[j].text not in ('from', ';', '='):
                    j += 1
                binding(nodes[i+1:j])
            # Simple and compound assignments; equality operators are single tokens.
            if node.text == '=':
                j = i - 1
                if j >= 0 and nodes[j].text in ('+', '-', '*', '&&', '||', '??', '&', '|', '^', '**'):
                    j -= 1
                if j >= 0:
                    target = nodes[j]
                    if target.text in ('{', '['):
                        binding([target, node])
                    elif target.kind == 'word' and target.text in protected:
                        binding([target, node])
                    # globalThis['it'] = ... (also refuse computed receiver aliases).
                    if target.text == '[' and any(n.kind == 'string' and n.text[1:-1] in protected
                                                  for n in target.children) and _js_added([target, node], added):
                        reasons.append(f'rebinds a global test/assertion name in {path}:{node.line}')
    return reasons


def _js_assertion_function_reasons(tree, added, path):
    """Prove a direct invocation path from module execution to assertion helpers.

    This is a conservative lexical call graph, not general JS execution analysis.
    Only direct calls, known test/hook registrations and IIFEs establish invocation;
    passing a helper to an unknown API or ambiguous duplicate names needs review.
    Recursive calls in an unreachable function cannot make it reachable.
    """
    functions = []
    declarations = set()
    parents = {}
    for parent in _js_walk(tree):
        for child in parent.children:
            parents[child] = parent
        nodes = parent.children
        for i, node in enumerate(nodes):
            body, name = None, None
            if node.text == 'function':
                j = i + 1
                if j < len(nodes) and nodes[j].text == '*':
                    j += 1
                if j < len(nodes) and nodes[j].kind == 'word':
                    name = nodes[j].text
                    declarations.add(nodes[j])
                    j += 1
                if j < len(nodes) and nodes[j].text == '(':
                    j += 1
                    if j < len(nodes) and nodes[j].text == '{':
                        body = [nodes[j]]
                    else:
                        raise JSSyntaxError('function body needs review')
                # A named function expression is invoked through its assignment.
                if i >= 2 and nodes[i-1].text == '=' and nodes[i-2].kind == 'word':
                    name = nodes[i-2].text
            elif node.text == '=>':
                j = i + 1
                if j >= len(nodes):
                    raise JSSyntaxError('missing arrow body')
                if nodes[j].text == '{':
                    body = [nodes[j]]
                else:
                    end = j
                    while end < len(nodes) and nodes[end].text not in (';', ','):
                        end += 1
                    body = nodes[j:end]
                start = i - 1
                if start and nodes[start-1].text == 'async':
                    start -= 1
                if start >= 2 and nodes[start-1].text == '=' and nodes[start-2].kind == 'word':
                    name = nodes[start-2].text
            if body is not None:
                functions.append({'anchor': node, 'body': body, 'name': name,
                                  'generator': node.text == 'function' and nodes[i+1].text == '*',
                                  'tokens': {n for b in body for n in _js_walk(b)}})

    def owner(token):
        candidates = [i for i, fn in enumerate(functions) if token in fn['tokens']]
        return min(candidates, key=lambda i: len(functions[i]['tokens'])) if candidates else None

    def straight_line(token):
        # Conditional/short-circuit calls do not prove invocation. Likewise a
        # call after return cannot rescue an otherwise unreachable helper.
        fn_id = owner(token)
        boundary = functions[fn_id]['body'] if fn_id is not None else [tree]
        child = token
        while child in parents:
            parent = parents[child]
            nodes = parent.children
            if parent.text == '{' or parent.kind == 'root':
                index = nodes.index(child)
                for kind, start, end in _js_statements(nodes):
                    if start <= index < end:
                        if kind != 'expression':
                            return False
                        if any(n.text in ('&&', '||', '??', '?') for n in nodes[start:index]):
                            return False
                        break
                    if kind in ('return', 'control', 'label'):
                        return False
            elif any(n.text in ('&&', '||', '??', '?') for n in nodes[:nodes.index(child)]):
                return False
            if parent in boundary or child in boundary:
                break
            child = parent
        return True

    names = {}
    for i, fn in enumerate(functions):
        if fn['name']:
            names.setdefault(fn['name'], []).append(i)
    edges = []
    registrations = {'it': 1, 'test': 1, 'specify': 1, 'describe': 1,
                     'beforeAll': 0, 'beforeEach': 0, 'afterAll': 0, 'afterEach': 0}
    for parent in _js_walk(tree):
        nodes = parent.children
        for i, node in enumerate(nodes):
            if node.text != '(' or i == 0:
                continue
            callee = nodes[i-1]
            if callee in declarations or not straight_line(callee):
                continue
            direct = i < 2 or nodes[i-2].text not in ('.', '?.', 'function')
            if direct and callee.kind == 'word':
                targets = names.get(callee.text, [])
                if len(targets) == 1:
                    edges.append((owner(callee), targets[0]))
            j = i - 1
            while j >= 2 and nodes[j-1].text == '.' and nodes[j].text in ('concurrent', 'serial'):
                j -= 2
            if nodes[j].text in registrations and (j == 0 or nodes[j-1].text not in ('.', '?.')):
                args, arg = [], []
                for child in node.children:
                    if child.text == ',':
                        args.append(arg); arg = []
                    else:
                        arg.append(child)
                args.append(arg)
                pos = registrations[nodes[j].text]
                if len(args) > pos:
                    callback = args[pos]
                    for target, fn in enumerate(functions):
                        if fn['anchor'] in callback:
                            edges.append((owner(nodes[j]), target))
                    if len(callback) == 1 and len(names.get(callback[0].text, [])) == 1:
                        edges.append((owner(nodes[j]), names[callback[0].text][0]))
            # A parenthesized function immediately followed by an argument list.
            if callee.text == '(':
                for target, fn in enumerate(functions):
                    if fn['anchor'] in callee.children:
                        edges.append((owner(callee), target))

    live = {None}
    while True:
        reached = live | {target for source, target in edges
                          if source in live and not functions[target]['generator']}
        if reached == live:
            break
        live = reached
    reasons = []
    for node in _js_walk(tree):
        if node.kind != 'word' or node.text not in ('expect', 'assert'):
            continue
        fn_id = owner(node)
        if fn_id is None or fn_id in live:
            continue
        changed = node.line in added
        ancestor = fn_id
        while ancestor is not None:
            fn = functions[ancestor]
            changed |= fn['anchor'].line in added or any(b.line in added for b in fn['body'])
            ancestor = owner(fn['anchor'])
        if changed:
            reasons.append(f'assertion in an uncalled function in {path}:{node.line} (invocation needs review)')
    return reasons


def _js_return_reasons(f, contents):
    """Return (findings, safe removed-row indexes) for strict existing JS/TS tests."""
    path = f.new
    if f.status == 'A' or not (_is_test(path) and JS_FILE.search(path)):
        return [], set()
    old, new = contents.get(path, (None, None))
    reasons, removed, helper_returns = [], set(), set()
    try:
        if new is None:
            # Patch-only mode can prove structure only from a contiguous file prefix.
            if not f.new_lines or sorted(f.new_lines) != list(range(1, max(f.new_lines) + 1)):
                raise JSSyntaxError('missing full-file context; use --staged or --range')
            new = '\n'.join(f.new_lines[n] for n in sorted(f.new_lines))
        tree = _js_parse(new)
        reasons.extend(_js_binding_reasons(tree, f.added_lines, path))
        reasons.extend(_js_assertion_function_reasons(tree, f.added_lines, path))
        if old is not None:
            removed, helper_returns = _js_helper_alias_refactors(old, new, _js_parse(old))
        safe_returns = set()
        for body in _js_callback_bodies(tree):
            statements = _js_statements(body.children)
            if statements and statements[-1][0] == 'return':
                safe_returns.add(body.children[statements[-1][1]])
        lines = new.splitlines()
        for node in _js_walk(tree):
            if node.text == '{' and node.end_line in f.added_lines and node.line not in f.added_lines:
                reasons.append(f'added line closes an existing block in {path}:{node.end_line}')
            if node.kind == 'word' and node.text == 'return' and node.line in f.added_lines:
                if node.line in helper_returns:
                    continue
                # Preserve the conservative rule for comments after the return.
                following = node.line
                while following < len(lines) and not lines[following].strip():
                    following += 1
                if node not in safe_returns or (following < len(lines) and lines[following].lstrip().startswith(('//', '/*'))):
                    reasons.append(f'adds an early exit to an existing test file {path}:{node.line} (return must be the last statement of the test callback itself)')
            children = node.children
            for i, child in enumerate(children):
                # Calls may occur anywhere in an expression, or span added lines.
                if i + 2 < len(children) and child.text in ('process', 'jest', 'vi'):
                    call_end = i + 4
                    member = children[i+1:i+3]
                    call = children[i+3] if i + 3 < len(children) else member[1]
                    prop = member[1].text if member[0].text in ('.', '?.') else None
                    if member[0].text == '[' and len(member[0].children) == 1:
                        key = member[0].children[0]
                        prop = key.text[1:-1] if key.kind == 'string' else None
                        call = member[1]
                        call_end = i + 3
                    if call.text == '(' and _js_added(children[i:call_end], f.added_lines):
                        if child.text == 'process' and prop == 'exit':
                            reasons.append(f'adds process.exit in {path}:{child.line}')
                        elif child.text in ('jest', 'vi') and prop == 'mock':
                            reasons.append(f'adds {child.text}.mock in {path}:{child.line} (needs human review)')
                if child.line not in f.added_lines:
                    continue
                if child.text == 'await' and [n.text for n in children[i+1:i+3]] == ['new', 'Promise']:
                    reasons.append(f'adds an awaited constructed Promise in {path}:{child.line} (settlement needs review)')
                # Property access is checked regardless of the receiver, so aliases
                # cannot hide disabled test registration (T = it; S = T.skip).
                if child.text in ('.', '?.') and i+1 < len(children) and children[i+1].text in ('skip', 'only', 'todo', 'fixme', 'skipIf', 'runIf', 'failing', 'fails'):
                    reasons.append(f'adds a skip/only marker through a property/alias in {path}:{child.line}')
                if child.text == '[' and any(n.kind == 'string' and n.text[1:-1] in ('skip', 'only', 'todo', 'fixme', 'skipIf', 'runIf', 'failing', 'fails') for n in child.children):
                    reasons.append(f'adds a computed skip/only marker in {path}:{child.line}')
        return reasons, {f.removed_lines[n] for n in removed if n in f.removed_lines}
    except (JSSyntaxError, RecursionError) as e:
        return [f'cannot establish safe JS/TS structure / early exit in {path}: {e}'], set()


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
    helper_removed = {}
    for f in files:
        if not push:
            js_reasons, safe_removed = _js_return_reasons(f, contents)
            reasons.extend(js_reasons)
            helper_removed[f] = safe_removed
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
    row_indexes = Counter()
    for f, path, sign, line in rows:
        row_index = row_indexes[f]
        row_indexes[f] += 1
        test = _is_test(path)
        if sign == "-" and test:
            if not push:
                if row_index not in helper_removed.get(f, set()):
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
        exit_pattern = EXIT_CALL if not push and JS_FILE.search(path) else EARLY_EXIT
        if exit_pattern.search(line) and f.status != "A" and not py_known:
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
        if not (_is_test(key) or _is_test(f.old)) or not (key.endswith(".py") or JS_FILE.search(key)):
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

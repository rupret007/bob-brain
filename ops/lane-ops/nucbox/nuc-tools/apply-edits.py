#!/usr/bin/env python3
"""apply-edits.py EDITS_FILE [--root DIR] [--check]   (lane-ops v2)

Applies SEARCH/REPLACE edit blocks (the format LLMs produce most reliably; see aider's edit-format
benchmarks and Diff-XYZ) to a git checkout. Format, one or more blocks:

    FILE: relative/path.ext
    <<<<<<< SEARCH
    exact existing lines (empty to create a new file or append to an empty one)
    =======
    replacement lines
    >>>>>>> REPLACE

Matching ladder per block: exact text, then trailing-whitespace-insensitive, then
indentation-insensitive line match. A SEARCH must match exactly once; ambiguous or missing
matches fail the whole run (nothing is written) and name the failing block so the model can repair it.
Paths must stay inside the root (no absolute paths, no "..", no .git/ in any letter case).
lane-ops v3 (arch-review-2 B7): files are written atomically (temp file in the same folder, fsync, os.replace,
original mode kept), and an empty SEARCH is refused for a file that already has content: it used to append
silently, so a model "creating" a file that existed duplicated it. An empty SEARCH still creates a new file or
fills an empty one.
Exit: 0 applied (or would apply with --check), 3 refused/failed, 2 usage.
"""
import os
import re
import sys
import tempfile

BLOCK = re.compile(
    r"^FILE:[ \t]*(?P<path>[^\n]+?)[ \t]*\n(?:```[^\n]*\n)?<{7} SEARCH[ \t]*\n(?P<search>.*?)^={7}[ \t]*\n(?P<replace>.*?)^>{7} REPLACE[ \t]*$",
    re.S | re.M,
)


class EditError(Exception):
    pass


def parse(text):
    blocks = [(m.group("path").strip().strip("`"), m.group("search"), m.group("replace")) for m in BLOCK.finditer(text)]
    if not blocks:
        raise EditError("no SEARCH/REPLACE blocks found")
    return blocks


def safe_path(root, rel):
    if not rel or rel.startswith(("/", "~")) or "\\" in rel:
        raise EditError(f"unsafe path {rel!r}")
    parts = rel.split("/")
    if ".." in parts or any(p.lower() == ".git" for p in parts):
        raise EditError(f"unsafe path {rel!r}")
    full = os.path.realpath(os.path.join(root, rel))
    if not full.startswith(os.path.realpath(root) + os.sep):
        raise EditError(f"path escapes root {rel!r}")
    return full


def _find_lines(hay_lines, needle_lines, norm):
    n = len(needle_lines)
    want = [norm(x) for x in needle_lines]
    hits = []
    for i in range(len(hay_lines) - n + 1):
        if all(norm(hay_lines[i + k]) == want[k] for k in range(n)):
            hits.append(i)
    return hits


def _exact_hits(content, search):
    """Exact matches that start (and, without a trailing newline, end) on a line boundary. Karen #151: a plain
    substring count let "x = 1" match inside "ax = 1" or "x = 10" and edit the middle of another line."""
    hits, i = [], content.find(search)
    while i != -1:
        end = i + len(search)
        if (i == 0 or content[i - 1] == "\n") and (search.endswith("\n") or end == len(content) or content[end] in "\r\n"):
            hits.append(i)
        i = content.find(search, i + 1)
    return hits


def replace_once(content, search, replace, label):
    if search == "":
        if content.strip():
            raise EditError(f"{label}: empty SEARCH on a file that already has content; quote the lines to replace")
        return replace
    hits = _exact_hits(content, search)
    if len(hits) == 1:
        i = hits[0]
        return content[:i] + replace + content[i + len(search):]
    if len(hits) > 1:
        raise EditError(f"{label}: SEARCH matches {len(hits)} places; add more context")
    hay = content.splitlines(keepends=True)
    needle = search.splitlines(keepends=True)
    while needle and needle[-1].strip() == "":
        needle.pop()
    if not needle:
        raise EditError(f"{label}: SEARCH is only blank lines")
    for loose, norm in ((False, lambda s: s.rstrip()), (True, lambda s: s.strip())):
        hits = _find_lines(hay, needle, norm)
        if len(hits) == 1:
            i = hits[0]
            rep = replace
            if loose:  # indentation-insensitive hit: shift the replacement to the file's indentation
                have = hay[i][: len(hay[i]) - len(hay[i].lstrip())]
                gave = needle[0][: len(needle[0]) - len(needle[0].lstrip())]
                rep = "".join(have + l[len(gave):] if l.startswith(gave) else l for l in replace.splitlines(keepends=True))
            if rep and not rep.endswith("\n") and i + len(needle) < len(hay):
                rep += "\n"
            return "".join(hay[:i]) + rep + "".join(hay[i + len(needle):])
        if len(hits) > 1:
            raise EditError(f"{label}: SEARCH matches {len(hits)} places (whitespace-insensitive); add more context")
    first = needle[0].strip()[:70]
    raise EditError(f"{label}: SEARCH not found (first line: {first!r}); copy the lines exactly from the file")


def write_atomic(full, body):
    d = os.path.dirname(full)
    os.makedirs(d, exist_ok=True)
    mode = None
    try:
        mode = os.stat(full).st_mode & 0o7777
    except FileNotFoundError:
        pass
    fd, tmp = tempfile.mkstemp(prefix=".apply-edits-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        else:
            os.chmod(tmp, 0o666 & ~_umask())
        os.replace(tmp, full)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _umask():
    m = os.umask(0)
    os.umask(m)
    return m


def apply(text, root, check=False):
    root = os.path.realpath(root)
    staged = {}
    for idx, (rel, search, replace) in enumerate(parse(text), 1):
        full = safe_path(root, rel)
        label = f"block {idx} ({rel})"
        if full in staged:
            cur = staged[full]
        elif os.path.isfile(full):
            cur = open(full, encoding="utf-8", errors="surrogateescape").read()
        elif search == "":
            cur = ""
        else:
            raise EditError(f"{label}: file does not exist (use an empty SEARCH to create it)")
        staged[full] = replace_once(cur, search, replace, label)
    if not check:
        for full, body in staged.items():
            write_atomic(full, body)
    return sorted(os.path.relpath(p, root) for p in staged)


def main(argv):
    args = [a for a in argv[1:] if a != "--check"]
    check = "--check" in argv
    root = "."
    if "--root" in args:
        i = args.index("--root")
        if i + 1 >= len(args):
            print("usage: apply-edits.py EDITS_FILE [--root DIR] [--check]")
            return 2
        root = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print("usage: apply-edits.py EDITS_FILE [--root DIR] [--check]")
        return 2
    try:
        files = apply(open(args[0], errors="replace").read(), root, check)
    except (EditError, OSError) as e:
        print(f"EDITS failed: {e}")
        return 3
    print(("EDITS ok (check): " if check else "EDITS applied: ") + " ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

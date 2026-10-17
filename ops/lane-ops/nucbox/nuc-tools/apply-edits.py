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
Paths must stay inside the root (no absolute paths, no "..", no .git/).
Exit: 0 applied (or would apply with --check), 3 refused/failed, 2 usage.
"""
import os
import re
import sys

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
    if ".." in parts or ".git" in parts:
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


def replace_once(content, search, replace, label):
    if search == "":
        return content + replace
    c = content.count(search)
    if c == 1:
        return content.replace(search, replace, 1)
    if c > 1:
        raise EditError(f"{label}: SEARCH matches {c} places; add more context")
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
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", errors="surrogateescape") as f:
                f.write(body)
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

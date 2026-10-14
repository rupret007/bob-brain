#!/usr/bin/env python3
"""Linux helper that honors the sandbox-exec argv this repository already emits.

macOS CI uses /usr/bin/sandbox-exec. Ubuntu CI installs this file at that path
and uses bubblewrap so write-deny / allow-list policies are actually enforced.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys


def parse_argv(argv):
    policy = ""
    bindings = {}
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "-p" and index + 1 < len(argv):
            policy = argv[index + 1]
            index += 2
            continue
        if item == "-D" and index + 1 < len(argv):
            key, _, value = argv[index + 1].partition("=")
            bindings[key] = value
            index += 2
            continue
        if item.startswith("-"):
            sys.exit("sandbox-exec: unsupported argument: " + item)
        break
    return policy, bindings, argv[index:]


def expand(policy, bindings):
    for key, value in bindings.items():
        policy = policy.replace('(param "%s")' % key, json.dumps(value))
    return policy


def quoted_strings(text):
    return [json.loads(match) for match in re.findall(r'"(?:\\.|[^"\\])*"', text)]


def allow_write_paths(policy):
    match = re.search(r"\(allow file-write\*(.*)\)\s*$", policy, re.S)
    if not match:
        return []
    return quoted_strings(match.group(1))


def deny_write_paths(policy):
    paths = []
    for match in re.finditer(r"\(deny file-write\*", policy):
        start = match.end()
        depth = 1
        index = start
        while index < len(policy) and depth:
            if policy[index] == "(":
                depth += 1
            elif policy[index] == ")":
                depth -= 1
            index += 1
        block = policy[start:index]
        if block.strip() == ")":
            continue
        paths.extend(quoted_strings(block))
    return paths


def main(argv):
    policy, bindings, command = parse_argv(argv)
    if not command:
        sys.exit("sandbox-exec: missing command")
    policy = expand(policy, bindings)
    bwrap = shutil.which("bwrap")
    if not bwrap:
        sys.exit("sandbox-exec: bubblewrap is required")

    wrapper = [bwrap, "--die-with-parent"]
    if "(deny network*)" in policy:
        wrapper.append("--unshare-net")
    if re.search(r"\(deny file-write\*\)", policy):
        wrapper.extend(["--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev"])
        for path in allow_write_paths(policy):
            if path == "/dev/null":
                continue
            if os.path.exists(path):
                wrapper.extend(["--bind", path, path])
    else:
        wrapper.extend(["--dev-bind", "/", "/", "--proc", "/proc", "--dev", "/dev"])
        for path in deny_write_paths(policy):
            if os.path.exists(path):
                wrapper.extend(["--ro-bind", path, path])
    os.execv(bwrap, wrapper + command)


if __name__ == "__main__":
    main(sys.argv[1:])

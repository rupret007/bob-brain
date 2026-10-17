#!/usr/bin/env python3
"""Linux helper that honors the sandbox-exec argv this repository already emits.

macOS CI uses /usr/bin/sandbox-exec. Ubuntu 24.04 GitHub runners block
unprivileged user namespaces, so bubblewrap cannot set up a uid map.
Deny-list policies are enforced by clearing write bits on the denied
paths for the duration of the command, then restoring them. That still
rejects writes to conductor/core paths while sibling git work stays
possible. Allow-list policies keep using bubblewrap when it works.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
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


def walk_existing(paths):
    items = []
    for path in paths:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            continue
        items.append(path)
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                items.extend(os.path.join(root, name) for name in dirs + files)
    return items


def clear_write_bits(paths):
    saved = []
    for item in walk_existing(paths):
        mode = os.stat(item).st_mode
        saved.append((item, mode))
        os.chmod(item, mode & ~0o222)
    return saved


def restore_modes(saved):
    for item, mode in reversed(saved):
        try:
            os.chmod(item, mode)
        except FileNotFoundError:
            continue


def run_bwrap(policy, command):
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return None
    wrapper = [bwrap, "--die-with-parent"]
    if "(deny network*)" in policy:
        wrapper.append("--unshare-net")
    wrapper.extend(["--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev"])
    for path in allow_write_paths(policy):
        if path == "/dev/null":
            continue
        if os.path.exists(path):
            wrapper.extend(["--bind", path, path])
    try:
        return subprocess.call(wrapper + command)
    except OSError:
        return None


def main(argv):
    policy, bindings, command = parse_argv(argv)
    if not command:
        sys.exit("sandbox-exec: missing command")
    policy = expand(policy, bindings)
    if re.search(r"\(deny file-write\*\)", policy):
        status = run_bwrap(policy, command)
        if status is not None:
            raise SystemExit(status)
        sys.exit("sandbox-exec: allow-list policy requires bubblewrap")

    saved = clear_write_bits(deny_write_paths(policy))
    try:
        raise SystemExit(subprocess.call(command))
    finally:
        restore_modes(saved)


if __name__ == "__main__":
    main(sys.argv[1:])

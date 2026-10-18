#!/usr/bin/env python3
"""Reject sensitive additions without ever displaying their contents.

Scan a pinned Git comparison, not the working tree. Unknown revisions, binary
changes, symlinks and unreadable objects fail closed. This is a publication gate,
not a guarantee that arbitrary prose contains no personal information: reviewers
must still inspect sanitized summaries. Raw runtime evidence stays local.
"""
import argparse
import json
from pathlib import PurePosixPath
import re
import subprocess
import sys


TOKEN = re.compile(r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
ASSIGNMENT = re.compile(r"(?i)[\"']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|authorization)[\"']?\s*[:=]\s*[\"']([^\"'\n]{8,})[\"']")
PHONE = re.compile(r"(?<![\w.])(?:\+?1[ .-]?)?\(?([2-9]\d{2})\)?[ .-]?(\d{3})[ .-]?(\d{4})(?!\w)")
PHONE_FIELD = re.compile(r"(?i)[\"']?(?:phone|phone_number|mobile|telephone)[\"']?\s*[:=]\s*[\"']?(\+?\d{10,15})")
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
PRIVATE_FIELD = re.compile(r'(?i)["\'](?:message|message_body|body|content|text|sender|recipient|full_name|first_name|last_name|home_address|street_address|date_of_birth|dob|ssn|social_security_number)["\']\s*:\s*["\']([^"\'\n]+)["\']')
YAML_PRIVATE = re.compile(r"(?i)^\s*(?:-\s+)?(?:message|message_body|body|content|text|sender|recipient|full_name|first_name|last_name|home_address|street_address|date_of_birth|dob|ssn|social_security_number)\s*:\s*(.+?)\s*$")
ENV_CREDENTIAL = re.compile(r"^\s*(?:export\s+)?(?:[A-Z_]*API_KEY|[A-Z_]*ACCESS_TOKEN|[A-Z_]*SECRET|[A-Z_]*PASSWORD)\s*=\s*([^\s#]+)")
PLACEHOLDERS = {"redacted", "[redacted]", "<redacted>", "placeholder", "example", "test", "dummy", "synthetic", "example-value", "test-value"}
DATA_SUFFIXES = {".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".csv", ".tsv", ".txt", ".md"}


def placeholder(value):
    return value.lower() in PLACEHOLDERS or bool(re.fullmatch(r"\$\{[A-Z_][A-Z0-9_]*\}", value))


def artifact_rule(path):
    p = PurePosixPath(path)
    parts = {part.lower() for part in p.parts}
    if p.name == ".env" or p.name.startswith(".env.") or p.suffix.lower() in {".pem", ".key", ".p12", ".sqlite", ".sqlite3", ".db", ".log", ".jsonl", ".ndjson"}:
        return "private-runtime-artifact"
    if {"user-memory", "chat-history", "transcripts"} & parts:
        return "private-runtime-artifact"
    if "fixtures" not in parts and ({"evidence", "state", "logs"} & parts) and p.suffix.lower() != ".md":
        return "raw-evidence-artifact"
    return None


def line_rules(path, line):
    rules = set()
    if TOKEN.search(line):
        rules.add("credential")
    for match in ASSIGNMENT.finditer(line):
        value = match.group(1)
        if not placeholder(value):
            rules.add("credential-assignment")
    env = ENV_CREDENTIAL.search(line)
    if env and not placeholder(env.group(1).strip("\"'")):
        rules.add("credential-assignment")
    auth = re.search(r"(?i)\b(?:authorization|bearer)\s*[:=]?\s+(?:bearer\s+)?([^\s\"']{8,})", line)
    if auth and not placeholder(auth.group(1)):
        rules.add("authorization-token")
    for match in PHONE.finditer(line):
        # NANPA's explicitly reserved fictional 555-0100 through 555-0199.
        if match.group(2) != "555" or not 100 <= int(match.group(3)) <= 199:
            rules.add("phone-number")
    for match in PHONE_FIELD.finditer(line):
        digits = match.group(1).lstrip("+")
        national = digits[1:] if len(digits) == 11 and digits.startswith("1") else digits
        if len(national) != 10 or national[3:6] != "555" or not 100 <= int(national[6:]) <= 199:
            rules.add("phone-number")
    for match in re.finditer(r"(?<!\w)\+[2-9]\d{9,14}(?!\w)", line):
        rules.add("phone-number")
    if re.search(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)", line):
        rules.add("social-security-number")
    for match in EMAIL.finditer(line):
        domain = match.group(1).lower()
        if domain not in {"example.com", "example.org", "example.net", "example.invalid"} and not domain.endswith((".example", ".invalid", ".test")):
            rules.add("personal-email")
    if PurePosixPath(path).suffix.lower() in DATA_SUFFIXES:
        for match in PRIVATE_FIELD.finditer(line):
            if not placeholder(match.group(1)):
                rules.add("private-message-or-personal-data")
        match = YAML_PRIVATE.search(line)
        if match and not placeholder(match.group(1).strip("\"'")):
            rules.add("private-message-or-personal-data")
    for match in re.finditer(r"(?:/Users/|/home/)([A-Za-z][A-Za-z0-9_.-]+)/", line):
        if match.group(1) not in {"example", "test", "runner", "user"}:
            rules.add("personal-home-path")
    return rules


def git(*args):
    return subprocess.run(["git", *args], input=b"", check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def scan_comparison(base, head):
    changes = git("diff", "--name-status", "-z", "--no-renames", base, head).split(b"\0")
    findings = []
    for index in range(0, len(changes) - 1, 2):
        status, raw_path = changes[index:index + 2]
        if status == b"D":
            continue
        path = raw_path.decode("utf-8", errors="strict")
        entries = git("ls-tree", "-z", head, "--", path).split(b"\t", 1)[0].split()
        if not entries or entries[0] not in {b"100644", b"100755"}:
            findings.append((path, 1, "unscannable-file-mode"))
            continue
        rule = artifact_rule(path)
        if rule:
            findings.append((path, 1, rule))
        data = git("show", head + ":" + path)
        try:
            data.decode("utf-8", errors="strict")
            if b"\0" in data:
                raise ValueError("binary")
        except (UnicodeError, ValueError):
            findings.append((path, 1, "unscannable-binary"))
            continue
        patch = git("diff", "--text", "--no-color", "--no-renames", "--no-ext-diff", "--no-textconv", "--unified=0", base, head, "--", path).decode("utf-8", errors="strict")
        lineno = 0
        in_hunk = False
        for line in patch.splitlines():
            hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk:
                lineno = int(hunk.group(1))
                in_hunk = True
            elif in_hunk and line.startswith("+"):
                findings.extend((path, lineno, rule) for rule in sorted(line_rules(path, line[1:])))
                lineno += 1
            elif in_hunk and not line.startswith(("-", "\\")):
                lineno += 1
    return findings


def scan(base, head):
    # Inspect every newly reachable commit: removing a secret in a later commit
    # does not remove it from the public repository's history.
    base = git("rev-parse", "--verify", "--end-of-options", base + "^{commit}").decode().strip()
    head = git("rev-parse", "--verify", "--end-of-options", head + "^{commit}").decode().strip()
    findings = set(scan_comparison(base, head))
    commits = git("rev-list", "--reverse", base + ".." + head).decode().splitlines()
    for commit in commits:
        ancestry = git("rev-list", "--parents", "-n", "1", commit).decode().split()
        # Imported component histories can legitimately introduce root commits.
        # Every root file is an addition: compare with Git's empty tree, using
        # mktree so this also works with the repository's object hash format.
        parent = ancestry[1] if len(ancestry) > 1 else git("mktree").decode().strip()
        findings.update(scan_comparison(parent, commit))
    return sorted(findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        findings = scan(args.base, args.head)
    except (subprocess.CalledProcessError, UnicodeError, ValueError):
        print("privacy-check: unable to inspect complete pinned comparison", file=sys.stderr)
        return 2
    for path, lineno, rule in findings:
        # JSON escaping prevents crafted names from injecting log annotations.
        safe_path = "<sensitive-path-redacted>" if line_rules("path.md", path) else path
        print("{}:{}:{}".format(json.dumps(safe_path), lineno, rule))
    print("Public privacy check: {} finding(s)".format(len(findings)))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

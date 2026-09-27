"""Identity of this code release, independent of persistent chat/brain data."""
import html
import json
import re
import subprocess
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
STATIC = CODE_ROOT / "webchat/static"


def load_build(code_root=CODE_ROOT):
    manifest = code_root / "webbob-build.json"
    if manifest.is_file():
        value = json.loads(manifest.read_text())
        sha, built_at = value["sha"], value["built_at"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid Web Bob release SHA")
    elif (code_root / ".git").exists():
        def git(*args):
            return subprocess.check_output(["git", "-C", str(code_root), *args], text=True, timeout=5).strip()
        sha, built_at = git("rev-parse", "HEAD"), git("show", "-s", "--format=%cI", "HEAD")
    else:
        # Do not walk up to another project's repository or read BOB-STATE.
        sha, built_at = "unknown", "unknown"
    return dict(name="Web Bob", sha=sha, short_sha=sha[:7], built_at=built_at)


BUILD = load_build()
VERSION_QUESTION = re.compile(
    r"\b(?:what|which)\s+(?:version(?:/build)?|build(?:\s+number)?|sha|commit)\s+"
    r"(?:are you|is (?:this|web\s*bob)|am i (?:using|running))\b|"
    r"\b(?:what(?:['’]s| is)|show(?: me)?)\s+(?:your|web\s*bob['’]s)\s+"
    r"(?:version|build(?:\s+number)?|sha|commit)\b|"
    r"^(?:(?:your|web\s*bob)\s+)?(?:version|build(?:\s+number)?|build/sha)[?!. ]*$", re.I)


def render_page(name):
    value = (STATIC / name).read_text()
    for key, replacement in (("__WEBBOB_SHA__", BUILD["short_sha"]),
                             ("__WEBBOB_BUILT_AT__", BUILD["built_at"])):
        value = value.replace(key, html.escape(replacement, quote=True))
    return value

"""Identity of this code release, independent of persistent chat/brain data."""
import html
import json
import os
import re
import subprocess
from pathlib import Path

# This tracked module lives in <running code>/webchat, including Git worktrees.
# Persistent BOB_ROOT data and deployment manifests never choose its location.
CODE_ROOT = Path(__file__).resolve().parents[1]
STATIC = CODE_ROOT / "webchat/static"


def _git(code_root, *args):
    # An inherited Git override must not identify another checkout as this one.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return subprocess.check_output(["git", "-C", str(code_root), *args], text=True,
                                   stderr=subprocess.DEVNULL, timeout=5, env=env).strip()


def git_checkout_root(code_root=CODE_ROOT):
    """Resolve Git identity only when this code's identity module is committed.

    Supports normal checkouts, linked worktrees and tracked nested layouts.
    An archive under an unrelated parent repository cannot borrow its identity.
    """
    try:
        code_root = Path(code_root).resolve(strict=True)
        module = code_root / "webchat/build_info.py"
        if not module.is_file() or module.resolve(strict=True) != module:
            return None
        checkout = Path(_git(code_root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        relative = module.relative_to(checkout).as_posix()
        if _git(code_root, "cat-file", "-t", "HEAD:" + relative) != "blob":
            return None
        return checkout
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return None


def load_build(code_root=CODE_ROOT):
    manifest = code_root / "webbob-build.json"
    if manifest.is_file():
        value = json.loads(manifest.read_text())
        sha, built_at = value["sha"], value["built_at"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid Web Bob release SHA")
    elif git_checkout_root(code_root) is not None:
        sha, built_at = _git(code_root, "rev-parse", "HEAD"), _git(code_root, "show", "-s", "--format=%cI", "HEAD")
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

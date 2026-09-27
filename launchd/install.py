#!/usr/bin/env python3
"""Install the Mini's one supervisor and watchdog guard with bounded commands."""
import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))
from command import run
from state import CONDUCTOR, ROOT


def install_user_launchers():
    """Copy launchers outside ~/Documents so launchd is not blocked on the plist entrypoint."""
    bindir = Path.home() / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    stubs = CONDUCTOR / "launchd" / "bin-stub"
    bob_root = str(ROOT)
    for source in sorted(stubs.glob("bob-launch-*.sh")):
        target = bindir / source.name
        body = source.read_text().replace("@@BOB_ROOT@@", bob_root)
        target.write_text(body)
        target.chmod(0o755)
    return bindir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webchat-only", action="store_true",
                        help="Install chat without restarting the conductor services")
    args = parser.parse_args()
    install_user_launchers()
    launcher = Path.home() / "bin" / "bob-launch-services.sh"
    webchat_launcher = Path.home() / "bin" / "bob-launch-webchat.sh"
    agents = Path.home() / "Library/LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    retired = CONDUCTOR / "launchd/retired"
    retired.mkdir(exist_ok=True)
    domain = "gui/" + str(os.getuid())
    for label in (() if args.webchat_only else ("com.jeff.mini-conductor", "com.jeff.mini-tick")):
        run(["launchctl", "bootout", domain + "/" + label], capture_output=True, timeout=15)
        old = agents / (label + ".plist")
        if old.exists():
            shutil.copy2(old, retired / old.name)
            old.unlink()
    labels = ("com.jeff.bob-webchat",) if args.webchat_only else (
        "com.jeff.bob-services", "com.jeff.bob-watchdog", "com.jeff.bob-webchat")
    for label in labels:
        source = CONDUCTOR / "launchd" / (label + ".plist")
        target = agents / source.name
        run(["plutil", "-lint", str(source)], capture_output=True, timeout=15, check=True)
        shutil.copy2(source, target)
        run(["launchctl", "bootout", domain + "/" + label], capture_output=True, timeout=15)
        run(["launchctl", "bootstrap", domain, str(target)], capture_output=True, timeout=30, check=True)
        run(["launchctl", "print", domain + "/" + label], capture_output=True, timeout=15, check=True)
        print("Installed and loaded " + label, flush=True)
    if not args.webchat_only:
        run([str(launcher)], timeout=60, check=True)
    run([str(webchat_launcher)], timeout=30, check=True, detach=True)


if __name__ == "__main__":
    main()

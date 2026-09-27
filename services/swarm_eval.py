"""Run the existing Web Bob parity eval strictly against temporary state."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webchat"))
from bob_parity_eval import run_eval, state_ledger


def main():
    with tempfile.TemporaryDirectory(prefix="swarm-eval-") as folder:
        root = Path(folder)
        (root / "conductor/webchat").mkdir(parents=True)
        state_ledger.write_now(root, "Offline evaluation fixture; no live workers")
        result = run_eval(root)
    print(json.dumps(result, indent=2))
    return int(result["passed"] != result["total"])


if __name__ == "__main__":
    raise SystemExit(main())

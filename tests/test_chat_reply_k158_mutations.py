"""Karen kg17k m158k mutants K3, K5, K8 must be killed by chat reply assertions."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MUTATION_FILE = Path("/home/rupret/work/kg17k/m158k.json")
TARGET = REPO_ROOT / "webbob" / "chat_reply.py"
TEST_MODULES = [
    "tests.test_chat_reply",
    "tests.test_chat_reply_karen_repro",
    "tests.test_chat_reply_p158_karen",
]

K3_UNCERTAIN_TO_RETRY = {
    "name": "K3 uncertain -> retry",
    "old": "        except Exception:\n            if effect_may_be_visible:\n                return self._mark_uncertain(reply_id, now)\n            return self._mark_send_timeout(reply_id, attempts, now)",
    "new": "        except Exception:\n            raise ReplyNotSentError()",
}

K8_CHAT_REPLY_RETRY = {
    "name": "K8 ChatReplyError branch terminal-never",
    "old": "        except ChatReplyError:\n            return self._mark_uncertain(reply_id, now)",
    "new": """        except ChatReplyError:
            delay = retry_delay(attempts)
            next_at = now + delay
            state = "failed_retry"
            with self.db() as db:
                db.execute(\"\"\"UPDATE replies SET state=?, receipt=NULL, next_retry_at=?, updated_at=? WHERE id=?\"\"\",
                           (state, next_at, now, reply_id))
                row = self._row(db, reply_id)
            return self._snapshot(row)""",
}


class ChatReplyK158MutationGate(unittest.TestCase):
    def test_k158_mutants_killed(self):
        muts = json.loads(MUTATION_FILE.read_text())
        muts = [m for m in muts if m["name"] == "K5 symlink allowed"]
        muts.extend([K3_UNCERTAIN_TO_RETRY, K8_CHAT_REPLY_RETRY])
        self.assertEqual(len(muts), 3)
        orig = TARGET.read_text()
        survivors = []
        try:
            for mutation in muts:
                count = orig.count(mutation["old"])
                if count != 1:
                    self.fail(f"{mutation['name']}: expected one match, found {count}")
                TARGET.write_text(orig.replace(mutation["old"], mutation["new"], 1))
                proc = subprocess.run(
                    [sys.executable, "-m", "unittest", *TEST_MODULES, "-q"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if proc.returncode == 0:
                    survivors.append(mutation["name"])
        finally:
            TARGET.write_text(orig)
        self.assertEqual(survivors, [], f"surviving mutants: {survivors}")


if __name__ == "__main__":
    unittest.main()

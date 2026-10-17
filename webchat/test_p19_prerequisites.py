"""P19 lane documents blocked status; reply-draft behavior is not shipped here."""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
P19_DOC = REPO_ROOT / "docs" / "P19-PREREQUISITES.md"
WEBCHAT = REPO_ROOT / "webchat"


class P19PrerequisitesTests(unittest.TestCase):
    def test_p19_prerequisites_doc_records_blocked_scope(self):
        self.assertTrue(P19_DOC.is_file(), "expected docs/P19-PREREQUISITES.md on the P19 lane")
        text = P19_DOC.read_text(encoding="utf-8")
        self.assertIn("P19 is not implemented", text)
        self.assertIn("prerequisite check", text.lower())
        self.assertIn("P9", text)
        self.assertIn("reply-draft", text)

    def test_p19_gmail_reply_draft_is_not_present_in_product_code(self):
        """Blocked P19 must not register Gmail reply-draft handlers in webchat."""
        py_files = [p for p in WEBCHAT.glob("*.py") if not p.name.startswith("test_")]
        combined = "\n".join(p.read_text(encoding="utf-8") for p in py_files)
        lowered = combined.lower()
        self.assertNotIn("gmail reply draft", lowered)
        self.assertNotIn("google_gmail", lowered)
        self.assertNotIn("googlegmail", lowered)


if __name__ == "__main__":
    unittest.main()

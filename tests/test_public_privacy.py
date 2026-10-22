import importlib.util
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("public_privacy", Path(__file__).parents[1] / "tools" / "check_public_privacy.py")
privacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(privacy)


class PublicPrivacyTests(unittest.TestCase):
    def test_credentials_never_exempted_by_fixture_path(self):
        token = "sk-" + "a" * 30
        for path in ("app.py", "tests/fixtures/sample.py", "evidence/summary.md"):
            self.assertIn("credential", privacy.line_rules(path, token))
        self.assertIn("credential-assignment", privacy.line_rules("app.py", 'password = "' + "not-a-placeholder" + '"'))

    def test_only_reserved_fictional_phones_are_safe(self):
        self.assertFalse(privacy.line_rules("sample.py", "+1 (202) 555-0100"))
        self.assertFalse(privacy.line_rules("sample.py", "+1-202-555-0199"))
        for last in ("0099", "0200"):
            self.assertIn("phone-number", privacy.line_rules("tests/fixtures/sample.py", "202-555-" + last))
        self.assertIn("phone-number", privacy.line_rules("sample.json", '"phone": "' + "1202867" + "5309" + '"'))

    def test_email_and_structured_private_data(self):
        self.assertFalse(privacy.line_rules("sample.md", "sample" + "@example.invalid"))
        self.assertIn("personal-email", privacy.line_rules("sample.md", "someone" + "@mailhost.org"))
        for field in ("body", "message", "sender", "full_name", "home_address", "date_of_birth"):
            line = '"' + field + '": "' + "Sensitive sample" + '"'
            self.assertIn("private-message-or-personal-data", privacy.line_rules("summary.json", line))
            self.assertFalse(privacy.line_rules("summary.json", '"' + field + '": "[REDACTED]"'))

    def test_raw_evidence_and_private_artifacts(self):
        for path in ("evidence/session.json", "chat-history/session.md", "user-memory/notes.md", "debug.log", "private.key", ".env"):
            self.assertIsNotNone(privacy.artifact_rule(path))
        self.assertIsNone(privacy.artifact_rule("evidence/summary.md"))

    def test_unquoted_and_compact_values_cannot_bypass_detection(self):
        number = "202" + "867" + "5309"
        for value in ("+1" + number, "(" + number[:3] + ")" + number[3:6] + "-" + number[6:]):
            self.assertIn("phone-number", privacy.line_rules("notes.md", value))
        self.assertIn("credential-assignment", privacy.line_rules("sample.txt", "API_KEY=" + "z" * 24))
        self.assertIn("authorization-token", privacy.line_rules("sample.txt", "Authorization: Bearer " + "z" * 24))
        for key in ("message_body", "full_name"):
            self.assertIn("private-message-or-personal-data", privacy.line_rules("sample.yaml", key + ": " + "Sensitive sample"))
        self.assertIn("social-security-number", privacy.line_rules("notes.md", "123" + "-45-" + "6789"))
        self.assertIn("personal-home-path", privacy.line_rules("notes.md", "/home/example/ and /home/" + "private-person" + "/"))

    def test_git_comparison_includes_all_pr_commits_and_never_prints_values(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True).stdout.decode().strip()
            git("init", "-q")
            git("config", "user.email", "ci@example.invalid")
            git("config", "user.name", "Privacy test")
            root = Path(directory)
            (root / "old.txt").write_text("safe\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            secret = "ghp_" + "a" * 30
            (root / "new.txt").write_text("safe\n" + secret + "\n")
            (root / "attributes.txt").write_text("++ " + secret + "\n")
            (root / ".gitattributes").write_text("attributes.txt -diff\n")
            (root / "binary.bin").write_bytes(b"\0hidden")
            git("add", ".")
            git("commit", "-qm", "first")
            (root / "later.txt").write_text("safe\n")
            git("add", ".")
            git("commit", "-qm", "second")
            actual_git = privacy.git
            def in_repo(*args):
                return actual_git("-C", directory, *args)
            with patch.object(privacy, "git", side_effect=in_repo):
                findings = privacy.scan(base, "HEAD")
            self.assertIn(("new.txt", 2, "credential"), findings)
            self.assertIn(("attributes.txt", 1, "credential"), findings)
            self.assertIn(("binary.bin", 1, "unscannable-binary"), findings)
            self.assertNotIn(secret, repr(findings))
            git("mv", "new.txt", "renamed.txt")
            (root / "link.txt").symlink_to("old.txt")
            git("add", ".")
            git("commit", "-qm", "rename")
            with patch.object(privacy, "git", side_effect=in_repo):
                findings = privacy.scan(base, "HEAD")
            self.assertIn(("renamed.txt", 2, "credential"), findings)
            self.assertIn(("link.txt", 1, "unscannable-file-mode"), findings)
            (root / "renamed.txt").unlink()
            git("add", ".")
            git("commit", "-qm", "remove sensitive file")
            with patch.object(privacy, "git", side_effect=in_repo):
                findings = privacy.scan(base, "HEAD")
            self.assertIn(("new.txt", 2, "credential"), findings)

    def test_invalid_base_is_fatal(self):
        with patch.object(privacy, "git", side_effect=subprocess.CalledProcessError(1, "git")):
            with self.assertRaises(subprocess.CalledProcessError):
                privacy.scan("missing", "HEAD")

    def test_report_retains_exact_historical_object_without_source_values(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True).stdout.decode().strip()
            git("init", "-q")
            git("config", "user.email", "ci@example.invalid")
            git("config", "user.name", "Privacy test")
            root = Path(directory)
            path = "sample" + "@mailhost.org" + ".txt"
            (root / path).write_text("safe\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            sensitive = "ghp_" + "c" * 30
            (root / path).write_text(sensitive + "\n")
            git("add", ".")
            git("commit", "-qm", "historical addition")
            introduced = git("rev-parse", "HEAD")
            blob = git("rev-parse", "HEAD:" + path)
            (root / path).write_text("different safe content at the same line\n")
            git("add", ".")
            git("commit", "-qm", "remove sensitive value")
            head = git("rev-parse", "HEAD")
            actual_git = privacy.git
            with patch.object(privacy, "git", side_effect=lambda *args: actual_git("-C", directory, *args)):
                report = privacy.scan_report(base, head)
                tuples = privacy.scan(base, head)
            self.assertEqual(report["base"], base)
            self.assertEqual(report["head"], head)
            self.assertEqual(report["findings"], [{"path": path, "line": 1,
                "rule": "credential", "commit": introduced,
                "comparison_parent": base, "object": blob}])
            self.assertEqual(tuples, [(path, 1, "credential")])
            result = subprocess.run([sys.executable, str(SPEC.origin), "--base", base,
                "--head", head, "--format", "json"], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            published = json.loads(result.stdout)
            self.assertEqual(published["findings"][0]["path"], "<sensitive-path-redacted>")
            self.assertEqual(published["findings"][0]["object"], blob)
            self.assertNotIn(path, result.stdout + result.stderr)
            self.assertNotIn(sensitive, result.stdout + result.stderr)
            self.assertNotIn("different safe content", result.stdout + result.stderr)
            self.assertNotIn(sensitive, repr(report))

    def test_json_cli_keeps_clean_and_unscannable_exit_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True).stdout.decode().strip()
            git("init", "-q")
            git("config", "user.email", "ci@example.invalid")
            git("config", "user.name", "Privacy test")
            (Path(directory) / "safe.txt").write_text("safe\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            for revision, expected in ((base, 0), ("missing", 2)):
                with self.subTest(revision=revision):
                    result = subprocess.run([sys.executable, str(SPEC.origin), "--base", base,
                        "--head", revision, "--format", "json"], cwd=directory, capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected)
                    if expected == 0:
                        self.assertEqual(json.loads(result.stdout)["findings"], [])
                    else:
                        self.assertEqual(result.stdout, "")

    def test_text_redaction_preserves_distinct_finding_count(self):
        paths = ["one" + "@mailhost.org", "two" + "@mailhost.org"]
        report = {"schema_version": 1, "base": "a" * 40, "head": "b" * 40,
                  "findings": [{"path": path, "line": 1, "rule": "credential",
                                "commit": "b" * 40, "comparison_parent": "a" * 40,
                                "object": "c" * 40} for path in paths]}
        output = StringIO()
        with patch.object(privacy, "scan_report", return_value=report), \
                patch.object(sys, "argv", ["privacy", "--base", "HEAD"]), \
                redirect_stdout(output):
            self.assertEqual(privacy.main(), 1)
        self.assertIn("2 finding(s)", output.getvalue())
        self.assertEqual(output.getvalue().count("<sensitive-path-redacted>"), 2)
        for path in paths:
            self.assertNotIn(path, output.getvalue())

    def test_imported_root_history_scans_secrets_removed_before_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True).stdout.decode().strip()
            git("init", "-q")
            git("config", "user.email", "ci@example.invalid")
            git("config", "user.name", "Privacy test")
            root = Path(directory)
            (root / "base.txt").write_text("safe\n")
            git("add", ".")
            git("commit", "-qm", "base")
            branch = git("branch", "--show-current")
            base = git("rev-parse", "HEAD")
            git("checkout", "--orphan", "imported-component")
            git("rm", "-rf", ".")
            secret = "ghp_" + "b" * 30
            (root / "removed.txt").write_text(secret + "\n")
            git("add", ".")
            git("commit", "-qm", "component root")
            git("rm", "removed.txt")
            (root / "component.txt").write_text("safe\n")
            git("add", ".")
            git("commit", "-qm", "remove sensitive component file")
            git("checkout", branch)
            git("merge", "--allow-unrelated-histories", "--no-ff", "-m", "import component", "imported-component")
            actual_git = privacy.git
            def in_repo(*args):
                return actual_git("-C", directory, *args)
            with patch.object(privacy, "git", side_effect=in_repo):
                findings = privacy.scan(base, "HEAD")
            self.assertEqual([("removed.txt", 1, "credential")], findings)


if __name__ == "__main__":
    unittest.main()

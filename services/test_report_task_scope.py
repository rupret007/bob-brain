"""Report templates must preserve the assigned behavior and source boundaries."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import api_worker
import result_acceptance
import workspaces


class ReportTaskScopeTests(unittest.TestCase):
    def test_disk_assignment_does_not_receive_completion_guard_cases(self):
        task = ("Project: Web Bob\nYour independent subtask:\nDraft regression tests for "
                "disk preflight and bounded evidence writes. Include an Action plan.\n"
                "Relevant evidence: services/result_acceptance.py::check_completion_json, "
                "reviews/texting_deploy_record.py")
        contract = api_worker.report_serialization(task, "test-writing")
        self.assertNotIn('"target": "services/result_acceptance.py::check_completion_json"', contract)
        self.assertNotIn("use both supplied narrow guard cases unchanged", contract)
        self.assertIn("Choose targets that exercise the behavior in the assigned task", contract)
        self.assertIn('"target": "[file/symbol]"', contract)
        self.assertFalse(api_worker.completion_guard_task(task))

    def test_explicit_completion_task_gets_optional_examples_and_generic_schema(self):
        contract = api_worker.report_serialization(
            "Project: Web Bob\nDraft tests for check_completion_json rejecting missing output.", "test-writing")
        self.assertIn("Optional completion-JSON guard examples", contract)
        self.assertIn('"target": "services/result_acceptance.py::check_completion_json"', contract)
        self.assertIn('"target": "[file/symbol]"', contract)
        self.assertNotIn("use both supplied narrow guard cases unchanged", contract)

    def test_deploy_source_snapshot_stays_tracked_and_excludes_runtime_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            workspaces.git(repo, "init", "-b", "main")
            files = {
                "reviews/texting_deploy_record.py": "MIN_FREE_BYTES = 5 * 1024 ** 3\n",
                "reviews/deploy_texting_2055.py": "def require_disk_space():\n    pass\n",
                "reviews/test_disk_evidence_2055.py": "def test_shortfall():\n    pass\n",
                "reviews/runtime_receipt.py": "runtime_receipt_must_not_be_sent = True\n",
                "reviews/TEXTING-DEPLOY-2055.json": '{"secret": "receipt-must-not-be-sent"}\n',
                "reviews/keys.env": "KEY=secret-must-not-be-sent\n",
                "reviews/nested/deploy_texting_2055.py": "nested_must_not_be_sent = True\n",
            }
            for name, content in files.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            workspaces.git(repo, "add", ".")
            workspaces.git(repo, "-c", "user.name=Test", "-c", "user.email=test@localhost",
                           "commit", "-m", "Source fixture")
            (repo / "reviews/record_texting_deploy_2055.py").write_text("untracked_must_not_be_sent = True\n")
            task = "Draft Web Bob disk evidence regressions for reviews/texting_deploy_record.py."
            body, metadata = api_worker.evidence(repo, "minimax", task, str, kind="test-writing")
            self.assertIn("MIN_FREE_BYTES = 5 * 1024 ** 3", body)
            self.assertEqual({row["path"] for row in metadata["files"]}, {
                "reviews/texting_deploy_record.py", "reviews/deploy_texting_2055.py",
                "reviews/test_disk_evidence_2055.py"})
            self.assertNotIn("must-not-be-sent", body)
            self.assertNotIn("must_not_be_sent", body)
            self.assertLessEqual(metadata["source_bytes"], 64000)
            (repo / "reviews/deploy_texting_2055.py").unlink()
            (repo / "reviews/deploy_texting_2055.py").symlink_to(repo / "reviews/keys.env")
            self.assertFalse(api_worker.safe_source(repo, "reviews/deploy_texting_2055.py"))

    def test_rendered_findings_reach_review_and_semantic_rejection_stays_binding(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/texting_regression_drafts_1658.json").read_text())
        answer = api_worker.render_report(fixture["prompt"], json.dumps(fixture["complete_report"]), fixture["kind"])
        self.assertIn("\nFindings/limits: ", answer)
        reviewer = Mock(return_value='{"accepted": false, "reason": "Drafts do not test the assigned task."}')
        with self.assertRaisesRegex(result_acceptance.ResultRejected, "Drafts do not test the assigned task"):
            result_acceptance.accept(fixture["prompt"], answer, reviewer, kind=fixture["kind"])
        payload = json.loads(reviewer.call_args.args[0].split("\n\n", 1)[1])
        self.assertEqual(payload["answer"], answer)
        self.assertIn("\nFindings/limits: ", payload["answer"])


if __name__ == "__main__":
    unittest.main()

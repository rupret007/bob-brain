import json
import unittest
from unittest.mock import patch

import pr_evidence


class PullRequestEvidence(unittest.TestCase):
    def setUp(self):
        self.projects = {"WebJam": {"remote": "owner/webjam"}, "AdoptIQ": {"remote": "owner/adoptiq"}}
        self.data = dict(number=161, title="Fix", url="https://github.com/owner/webjam/pull/161",
                         headRefOid="a" * 40, baseRefOid="b" * 40, files=[dict(path="src/app.py")])

    def test_bare_review_resolves_repository_and_supplies_the_actual_diff(self):
        diff = "diff --git a/src/app.py b/src/app.py\n-old\n+new\n"
        with patch.object(pr_evidence, "gh", side_effect=[json.dumps(self.data), None, diff, json.dumps(self.data)]):
            evidence = pr_evidence.load("review PR 161", self.projects)
        self.assertIn(diff, evidence["text"])
        self.assertEqual(evidence["metadata"]["headRefOid"], "a" * 40)
        self.assertEqual(evidence["metadata"]["repo"], "owner/webjam")

    def test_changed_head_or_ambiguous_repository_fails_closed(self):
        with patch.object(pr_evidence, "gh", return_value=json.dumps(self.data)):
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                pr_evidence.load("review PR #161", self.projects)
        after = dict(self.data, headRefOid="c" * 40)
        with patch.object(pr_evidence, "gh", side_effect=[json.dumps(self.data), "diff", json.dumps(after)]):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                pr_evidence.load("review WebJam PR #161", self.projects)

    def test_non_review_never_reads_github(self):
        with patch.object(pr_evidence, "gh") as call:
            self.assertIsNone(pr_evidence.load("Improve WebJam", self.projects))
            call.assert_not_called()

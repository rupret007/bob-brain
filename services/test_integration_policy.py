"""Policy failures must invalidate evidence without touching Git or Web Bob."""
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integration_policy import authorize, digest, policy_id
from leases import LeaseStore
from task_contracts import contract_id, require_current


def contract(task="feature", dependencies=None):
    return dict(schema=1, task=task, version=1, owner="maintainer", goal="Preserve rendering",
                invariants=["Integrated rendering returns 2"], paths=["consumer.py", "producer.py"],
                resources=["test-db"], dependencies=dependencies or {},
                checks={name: digest(name + "-v1") for name in ("tests", "evals", "acceptance")})


class PolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="swarm-policy-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = LeaseStore(self.root, "webbob", self.root)
        self.contract = contract()
        self.current = {"feature": self.contract}
        self.lease = self.store.claim("attempt-one", self.contract["paths"], shared_resources=self.contract["resources"])
        self.author = dict(model="writer-v1", creator="openai", provider="host-a", harness="cursor", harness_version="1")
        self.reviewer = dict(model="reviewer-v1", creator="anthropic", provider="host-b", harness="cli", harness_version="2")
        self.policy = dict(schema=1, version=1, identities=[self.author, self.reviewer],
                           check_issuers=["ci"], review_issuers=["review-service"], review_config=digest("rubric-v1"))
        self.candidate = dict(project="webbob", task="feature", attempt="attempt-one", source_sha="1" * 40,
                              train_sha="2" * 40, sha="3" * 40, tree="4" * 40, contract=contract_id(self.contract),
                              policy=policy_id(self.policy), lease_owner="attempt-one", lease_token=self.lease["token"],
                              authors=[self.author], provenance_complete=True, changed_paths=["producer.py"])
        self.receipts()

    def receipts(self):
        binding = digest(self.candidate)
        self.checks = [dict(binding=binding, check=name, config=config, passed=True, issuer="ci",
                            environment="isolated-ci", artifact="ci/run-1/" + name)
                       for name, config in self.contract["checks"].items()]
        self.review = dict(binding=binding, config=self.policy["review_config"], approved=True,
                           issuer="review-service", identity=self.reviewer, provenance_complete=True)

    def accept(self, **overrides):
        values = dict(contract=self.contract, current_contracts=self.current, policy=self.policy,
                      checks=self.checks, review=self.review, leases=self.store,
                      current_train_sha="2" * 40, current_source_sha="1" * 40)
        return authorize(self.candidate, **dict(values, **overrides))

    def test_accepts_exact_candidate_and_is_vendor_neutral(self):
        self.assertEqual(self.accept(), dict(binding=digest(self.candidate), sha="3" * 40, tree="4" * 40, accepted=True))
        # No hardcoded harness-to-vendor routing table: effective identity controls policy.
        self.reviewer["harness"] = "cursor"
        self.candidate["policy"] = policy_id(self.policy)
        self.receipts()
        self.assertTrue(self.accept()["accepted"])

    def test_any_candidate_input_change_or_moving_refs_invalidates_receipts(self):
        for field in ("sha", "tree", "source_sha", "train_sha"):
            previous = self.candidate[field]
            self.candidate[field] = "5" * 40
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.accept()
            self.candidate[field] = previous
        for field in ("current_train_sha", "current_source_sha"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.accept(**{field: "6" * 40})
        self.policy["version"] += 1
        with self.assertRaises(ValueError):
            self.accept()

    def test_check_configuration_issuers_results_and_complete_coverage_are_mandatory(self):
        original = copy.deepcopy(self.checks)
        for field, value in (("binding", "stale"), ("config", digest("worker-tests")), ("passed", False),
                             ("passed", 1), ("issuer", "worker"), ("artifact", ""), ("environment", None)):
            self.checks = copy.deepcopy(original)
            self.checks[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.accept()
        for checks in ([], original[:-1], [original[0]] * 3, [None] * 3):
            with self.subTest(checks=checks), self.assertRaises(ValueError):
                self.accept(checks=checks)

    def test_nested_authors_resolvers_and_effective_fallbacks_affect_review(self):
        self.candidate["authors"].append(self.reviewer)
        self.receipts()
        with self.assertRaises(ValueError):
            self.accept()
        self.candidate["authors"] = [self.author]
        self.candidate["provenance_complete"] = False
        self.receipts()
        with self.assertRaises(ValueError):
            self.accept()
        self.candidate["provenance_complete"] = True
        self.receipts()
        for field, value in (("identity", self.author), ("identity", dict(self.reviewer, model="unknown-fallback")),
                             ("binding", "stale"), ("approved", 1), ("provenance_complete", False),
                             ("config", digest("old-rubric")), ("issuer", "worker")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.accept(review=dict(self.review, **{field: value}))

    def test_forbidden_vendor_cannot_be_allowlisted_under_any_harness(self):
        for change in ({"creator": "xAI"}, {"provider": "x.ai"}, {"model": "grok-4"}):
            policy = copy.deepcopy(self.policy)
            policy["identities"].append(dict(self.author, **change))
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy_id(policy)

    def test_lease_expiry_reassignment_and_undeclared_rename_sources_block(self):
        with patch("leases.time.time", return_value=self.lease["expires"]):
            with self.assertRaises(ValueError):
                self.accept()
        for paths in (["unowned.py", "producer.py"], [" producer.py"], [".git/config"]):
            self.candidate["changed_paths"] = paths
            self.receipts()
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                self.accept()
        self.candidate["changed_paths"] = ["producer.py"]
        self.receipts()
        self.store.release("attempt-one", self.lease["token"])
        self.store.claim("attempt-one", self.contract["paths"], shared_resources=self.contract["resources"])
        with self.assertRaises(ValueError):
            self.accept()

    def test_changed_contract_or_transitive_dependency_invalidates_old_work(self):
        leaf = contract("api")
        middle = contract("client", {"api": contract_id(leaf)})
        self.contract["dependencies"] = {"client": contract_id(middle)}
        self.current.update(api=leaf, client=middle)
        self.candidate["contract"] = contract_id(self.contract)
        self.receipts()
        self.assertTrue(self.accept()["accepted"])
        leaf["version"] += 1
        with self.assertRaises(ValueError):
            self.accept()
        leaf["version"] -= 1
        self.contract["checks"]["acceptance"] = digest("worker-weakened-suite")
        with self.assertRaises(ValueError):
            self.accept()

    def test_independent_acceptance_catches_disjoint_semantic_incompatibility(self):
        producer, consumer = self.root / "producer.py", self.root / "consumer.py"
        def run_acceptance():
            return subprocess.run([sys.executable, "-c", "from consumer import render; assert render() == 2"],
                                  cwd=self.root, capture_output=True, timeout=10).returncode
        # Each non-overlapping change passes on the base; their combination fails.
        producer.write_text("def value(): return '1'\n")
        consumer.write_text("from producer import value\ndef render(): return int(value()) + 1\n")
        self.assertEqual(run_acceptance(), 0)
        producer.write_text("def value(): return 1\n")
        consumer.write_text("from producer import value\ndef render(): return value() + 1\n")
        self.assertEqual(run_acceptance(), 0)
        producer.write_text("def value(): return '1'\n")
        # Syntax checks remain green; the separately pinned behavioral suite is red.
        compile(producer.read_text(), str(producer), "exec")
        compile(consumer.read_text(), str(consumer), "exec")
        self.checks[-1]["passed"] = run_acceptance() == 0
        self.assertFalse(self.checks[-1]["passed"])
        with self.assertRaisesRegex(ValueError, "acceptance evidence"):
            self.accept()


class ContractTests(unittest.TestCase):
    def test_schema_behavioral_and_acceptance_contracts_are_required(self):
        for change in ({"schema": 2}, {"version": True}, {"invariants": []}, {"paths": ["../escape"]},
                       {"checks": {"tests": digest("tests")}}, {"dependencies": {"api": "mutable-branch"}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract_id(dict(contract(), **change))

    def test_missing_changed_and_self_dependencies_fail_closed(self):
        original = contract()
        self.assertEqual(require_current(original, {"feature": original}), contract_id(original))
        with self.assertRaises(ValueError):
            require_current(original, {})
        changed = dict(original, version=2)
        with self.assertRaises(ValueError):
            require_current(original, {"feature": changed})
        with self.assertRaises(ValueError):
            contract_id(contract(dependencies={"feature": digest("self")}))

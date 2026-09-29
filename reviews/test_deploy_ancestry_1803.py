"""Release-object regressions in temporary Git repositories; no live mutation."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("deploy_texting_1803", HERE / "deploy_texting_1803.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class CleanAncestry(unittest.TestCase):
    def simulated(self, codes, *, fetched="merge", diff=""):
        attempts = iter(codes)

        def command(argv):
            if "rev-parse" in argv:
                return fetched
            if "merge-base" in argv:
                code = next(attempts)
                if code:
                    raise subprocess.CalledProcessError(code, argv, stderr="synthetic Git failure")
            if "diff" in argv:
                return diff
            return ""

        return patch.object(deploy, "run", side_effect=command)

    def test_exit128_refetches_and_retries(self):
        with self.simulated([128, 0]) as run:
            result = deploy.verify_clean_merge(Path("release-repo"), "tip", "merge")
        self.assertTrue(result["retried_missing_object"])
        self.assertEqual(sum("fetch" in c.args[0] for c in run.call_args_list), 2)
        self.assertTrue(result["ancestor"])

    def test_persistent_exit128_is_repository_error(self):
        with self.simulated([128, 128]) as run:
            with self.assertRaisesRegex(RuntimeError, "object/repository error persists after fetch"):
                deploy.verify_clean_merge(Path("release-repo"), "tip", "merge")
        self.assertEqual(sum("fetch" in c.args[0] for c in run.call_args_list), 2)

    def test_nonancestor_is_rejected_without_object_retry(self):
        with self.simulated([1]) as run:
            with self.assertRaisesRegex(RuntimeError, "not an ancestor"):
                deploy.verify_clean_merge(Path("release-repo"), "tip", "merge")
        self.assertEqual(sum("fetch" in c.args[0] for c in run.call_args_list), 1)

    def test_changed_clean_ref_cannot_pass(self):
        with self.simulated([], fetched="unexpected-merge") as run:
            with self.assertRaisesRegex(RuntimeError, "differs from recorded clean merge"):
                deploy.verify_clean_merge(Path("release-repo"), "tip", "merge")
        self.assertFalse(any("merge-base" in c.args[0] for c in run.call_args_list))

    def test_changed_tree_cannot_pass(self):
        with self.simulated([0], diff="product.py"):
            with self.assertRaisesRegex(RuntimeError, "tree differs"):
                deploy.verify_clean_merge(Path("release-repo"), "tip", "merge")

    def test_fetches_merge_into_release_repo_without_feature_object(self):
        def git(repo, *args):
            return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()

        with tempfile.TemporaryDirectory(dir="/private/tmp") as folder:
            root = Path(folder)
            seed, origin, candidate, release = [root / n for n in ("seed", "origin", "candidate", "release")]
            seed.mkdir()
            git(seed, "init")
            git(seed, "config", "user.name", "Release Guard Test")
            git(seed, "config", "user.email", "release-guard@example.invalid")
            (seed / "product.py").write_text("baseline\n")
            git(seed, "add", "product.py")
            git(seed, "commit", "-m", "baseline")
            git(seed, "branch", deploy.CLEAN_BRANCH)
            git(seed, "checkout", "-b", "feature")
            (seed / "product.py").write_text("reviewed\n")
            git(seed, "commit", "-am", "reviewed tip")
            tip = git(seed, "rev-parse", "HEAD")
            git(root, "clone", "--bare", str(seed), str(origin))
            git(root, "clone", "--depth", "1", "--single-branch", "--branch", "feature", origin.as_uri(), str(candidate))
            git(root, "clone", "--single-branch", "--branch", "feature", origin.as_uri(), str(release))
            git(seed, "remote", "add", "origin", str(origin))
            git(seed, "checkout", deploy.CLEAN_BRANCH)
            git(seed, "merge", "--no-ff", "feature", "-m", "regular clean merge")
            merge = git(seed, "rev-parse", "HEAD")
            git(seed, "push", "origin", deploy.CLEAN_BRANCH)
            self.assertEqual(git(candidate, "rev-parse", "--is-shallow-repository"), "true")
            with self.assertRaises(subprocess.CalledProcessError) as missing:
                git(candidate, "merge-base", "--is-ancestor", tip, merge)
            self.assertEqual(missing.exception.returncode, 128)
            result = deploy.verify_clean_merge(release, tip, merge)
            self.assertTrue(result["ancestor"] and result["tree_equal"])
            self.assertEqual(git(release, "rev-parse", "origin/" + deploy.CLEAN_BRANCH), merge)
            self.assertEqual(git(candidate, "rev-parse", "HEAD"), tip)
            with self.assertRaises(subprocess.CalledProcessError):
                git(candidate, "cat-file", "-e", merge)


if __name__ == "__main__":
    unittest.main(verbosity=2)

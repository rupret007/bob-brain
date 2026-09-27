"""Filesystem ownership tests, including independent-process claim races."""
import concurrent.futures
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from leases import LeaseConflict, LeaseStore


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="swarm-leases-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = LeaseStore(self.root, "webbob", self.root)

    def test_claim_is_persistent_idempotent_and_explicitly_released(self):
        row = self.store.claim("cursor-one", ["./webchat//app.py", "services/"])
        self.assertEqual(row["paths"], ["services", "webchat/app.py"])
        self.assertEqual(row, LeaseStore(self.root, "webbob").claim("cursor-one", row["paths"]))
        self.assertFalse(self.store.release("another", row["token"]))
        with self.assertRaises(ValueError):
            self.store.release("cursor-one", "wrong-token")
        self.assertEqual(self.store.list(), [row])
        self.assertTrue(self.store.release("cursor-one", row["token"]))
        self.assertFalse(self.store.release("cursor-one", row["token"]))
        new = self.store.claim("cursor-one", row["paths"])
        with self.assertRaises(ValueError):
            self.store.release("cursor-one", row["token"])
        self.assertNotEqual(new["token"], row["token"])

    def test_ancestor_descendant_exact_root_and_case_alias_overlap(self):
        for owned, proposed in [("webchat", "webchat/app.py"), ("webchat/app.py", "webchat"),
                                ("webchat/app.py", "WEBCHAT/APP.py"), (".", "anywhere"),
                                ("anywhere", "."), ("café", "cafe\u0301/file")]:
            with self.subTest(owned=owned, proposed=proposed):
                row = self.store.claim("one", [owned])
                with self.assertRaises(LeaseConflict):
                    self.store.claim("two", [proposed])
                self.store.release("one", row["token"])

    def test_prefix_siblings_are_parallel_and_multifile_claim_is_all_or_nothing(self):
        self.store.claim("one", ["webchat/app.py"])
        self.store.claim("two", ["webchat/app.py.bak", "webchat2"])
        with self.assertRaises(LeaseConflict):
            self.store.claim("three", ["new.py", "webchat/app.py"])
        self.assertEqual(len(self.store.list()), 2)
        self.store.claim("four", ["new.py"])
        LeaseStore(self.root, "another-project").claim("one", ["webchat/app.py"])

    def test_invalid_and_symlink_paths_never_claim(self):
        (self.root / "alias").symlink_to(self.root, target_is_directory=True)
        for paths in [[], "app.py", ["../a"], ["/tmp/a"], ["a/../b"], ["*.py"], [".git/config"],
                      ["a\\b"], ["a\nfile"], ["alias/file"], [""]]:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                self.store.claim("one", paths)
        for project in ("..", "../webbob", "/root", ""):
            with self.assertRaises(ValueError):
                LeaseStore(self.root, project)
        self.assertEqual(self.store.list(), [])

    def test_corruption_fails_closed(self):
        self.store.path.parent.mkdir(parents=True)
        for text in ("{broken", "[]", '{"version":1,"project":"webbob","leases":[{}]}'):
            self.store.path.write_text(text)
            with self.assertRaises(ValueError):
                self.store.claim("one", ["code"])
            self.assertEqual(self.store.path.read_text(), text)

    def test_transfer_invalidates_author_and_preserves_paths(self):
        row = self.store.claim("author", ["code"])
        resolver = self.store.transfer("author", row["token"], "resolver")
        self.assertEqual(resolver["paths"], row["paths"])
        self.assertNotEqual(resolver["token"], row["token"])
        self.assertFalse(self.store.release("author", row["token"]))
        with self.assertRaises(LeaseConflict):
            self.store.claim("third", ["code"])

    def test_independent_processes_cannot_both_claim_overlapping_paths(self):
        script = Path(__file__).with_name("leases.py")
        def claim(index):
            return subprocess.run([sys.executable, str(script), "--conductor", str(self.root),
                "--project", "webbob", "claim", "worker-" + str(index), "shared/file.py"],
                capture_output=True, text=True, timeout=10)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(claim, range(8)))
        self.assertEqual(sum(r.returncode == 0 for r in results), 1)
        self.assertEqual(len(json.loads(self.store.path.read_text())["leases"]), 1)


if __name__ == "__main__":
    unittest.main()

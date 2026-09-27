"""Real SQLite races, restart recovery and stale authority rejection."""
import concurrent.futures
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from leases import LeaseConflict, LeaseStore


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="swarm-leases-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = LeaseStore(self.root, "webbob", self.root)

    def test_reload_renew_release_and_reacquire_fence(self):
        first = self.store.claim("one", ["./webchat//app.py", "services/"])
        self.assertEqual(first["paths"], ["services", "webchat/app.py"])
        again = LeaseStore(self.root, "webbob", self.root)
        self.assertEqual(again.list(), [first])
        with patch("leases.time.time", return_value=first["heartbeat"] + 1):
            again.renew("one", first["token"], ttl=600)
        self.assertGreater(again.list()[0]["expires"], first["expires"])
        again.release("one", first["token"])
        second = again.claim("one", first["paths"])
        self.assertGreater(second["generation"], first["generation"])
        self.assertNotEqual(second["token"], first["token"])
        for method in (again.release, again.renew):
            with self.assertRaises(ValueError):
                method("one", first["token"])
        with self.assertRaises(ValueError), again.guard("one", first["token"]):
            pass

    def test_overlap_aliases_and_atomic_multiscope_acquisition(self):
        for owned, proposed in [("webchat", "webchat/app.py"), ("webchat/app.py", "webchat"),
                                ("webchat/app.py", "WEBCHAT/APP.py"), (".", "anywhere"),
                                ("anywhere", "."), ("café", "cafe\u0301/file")]:
            with self.subTest(owned=owned, proposed=proposed):
                row = self.store.claim("one", [owned])
                with self.assertRaises(LeaseConflict):
                    self.store.claim("two", ["new.py", proposed])
                self.assertEqual(len(self.store.list()), 1)
                self.store.release("one", row["token"])
        self.store.claim("one", ["code.py"], shared_resources=["test-db"])
        with self.assertRaises(LeaseConflict):
            self.store.claim("two", ["code.py.bak"], shared_resources=["TEST-DB"])
        self.store.claim("two", ["code.py.bak"], shared_resources=["isolated-db"])

    def test_invalid_paths_symlinks_and_ttls_fail_closed(self):
        (self.root / "alias").symlink_to(self.root, target_is_directory=True)
        for paths in [[], "code.py", ["../a"], ["/tmp/a"], ["*.py"], [".git/config"],
                      ["a\\b"], ["a\nfile"], ["alias/file"], [""]]:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                self.store.claim("one", paths)
        for ttl in (0, -1, 3601, float("nan"), float("inf"), True):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                self.store.claim("one", ["code"], ttl=ttl)
        self.assertEqual(self.store.list(), [])

    def test_expired_worker_cannot_renew_submit_release_or_steal_reassignment(self):
        first = self.store.claim("one", ["code"], ttl=1)
        with patch("leases.time.time", return_value=first["expires"]):
            for method in (self.store.renew, self.store.release):
                with self.assertRaises(ValueError):
                    method("one", first["token"])
            with self.assertRaises(ValueError), self.store.guard("one", first["token"]):
                pass
            with self.assertRaises(LeaseConflict):
                self.store.claim("two", ["code"])
            with self.assertRaises(ValueError):
                self.store.recover("one", first["token"], receipt="")
            self.store.recover("one", first["token"], receipt="runner/quarantine-one")
            restarted = LeaseStore(self.root, "webbob", self.root)
            restarted.recover("one", first["token"], receipt="runner/quarantine-one")
            second = restarted.claim("one", ["code"])
            with self.assertRaises(ValueError), restarted.guard("one", first["token"]):
                pass
            self.assertGreater(second["generation"], first["generation"])
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT recovery_receipt FROM leases WHERE token=?", (first["token"],)).fetchone()[0],
                             "runner/quarantine-one")

    def test_guard_rechecks_expiry_and_renewal_has_absolute_deadline(self):
        first = self.store.claim("one", ["code"])
        with patch("leases.time.time", side_effect=[first["heartbeat"], first["expires"]]):
            with self.assertRaises(ValueError), self.store.guard("one", first["token"]):
                pass
        with patch("leases.time.time", return_value=first["heartbeat"]):
            with self.store._transaction() as db:
                db.execute("UPDATE leases SET deadline=?", (first["heartbeat"] + 10,))
            self.store.renew("one", first["token"], ttl=3600)
            self.assertEqual(self.store.list()[0]["expires"], first["heartbeat"] + 10)

    def test_independent_processes_grant_one_owner_and_crash_rolls_back(self):
        script = ("from leases import LeaseStore; import sys; "
                  "LeaseStore(sys.argv[1], 'webbob').claim(sys.argv[2], ['shared'])")
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).parent))
        def claim(index):
            return subprocess.run([sys.executable, "-c", script, str(self.root), "worker-" + str(index)],
                                  env=environment, capture_output=True, timeout=15).returncode
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(claim, range(8))).count(0), 1)
        first = self.store.list()[0]
        script = ("import sqlite3,os,sys; db=sqlite3.connect(sys.argv[1]); "
                  "db.execute('BEGIN IMMEDIATE'); db.execute(\"UPDATE leases SET state='released'\"); os._exit(9)")
        result = subprocess.run([sys.executable, "-c", script, str(self.store.path)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 9)
        self.assertEqual(LeaseStore(self.root, "webbob").list(), [first])

    def test_corrupt_unsupported_and_legacy_state_is_never_replaced(self):
        self.store.path.write_bytes(b"not a SQLite database")
        with self.assertRaises(sqlite3.DatabaseError):
            LeaseStore(self.root, "webbob")
        self.assertEqual(self.store.path.read_bytes(), b"not a SQLite database")
        legacy = self.store.path.with_name("legacy.json")
        legacy.write_text('{"leases": []}')
        with self.assertRaises(ValueError):
            LeaseStore(self.root, "legacy")
        self.assertFalse(legacy.with_suffix(".sqlite3").exists())
        future = LeaseStore(self.root, "future")
        with sqlite3.connect(future.path) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaises(ValueError):
            LeaseStore(self.root, "future")

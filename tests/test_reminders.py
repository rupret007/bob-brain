from datetime import datetime, timedelta
from pathlib import Path
import os
import tempfile
import unittest
from zoneinfo import ZoneInfo

from webbob.reminders import CHICAGO, ReminderError, ReminderStore

UTC = ZoneInfo("UTC")


class ReminderStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "reminders.sqlite"
        self.now = datetime(2026, 3, 7, 12, 0, tzinfo=CHICAGO)
        self.clock = lambda: self.now
        self.store = ReminderStore(self.path, clock=self.clock)

    def test_create_list_and_cancel_pending(self):
        due = datetime(2026, 3, 7, 18, 0, tzinfo=CHICAGO)
        created = self.store.create("Take bins out", due)
        self.assertRegex(created["id"], r"[0-9a-f-]{36}")
        self.assertEqual(created["body"], "Take bins out")
        self.assertEqual(created["state"], "pending")
        self.assertEqual(created["due_chicago"], "2026-03-07T18:00:00-06:00")
        listed = self.store.list()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], created["id"])
        cancelled = self.store.cancel(created["id"])
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertEqual(self.store.list(), [])
        with self.assertRaises(ReminderError):
            self.store.cancel(created["id"])

    def test_spring_forward_due_boundary_uses_chicago_wall_clock(self):
        before = ReminderStore(self.path, clock=lambda: datetime(2026, 3, 8, 1, 44, tzinfo=CHICAGO))
        due = datetime(2026, 3, 8, 1, 45, tzinfo=CHICAGO)
        reminder = before.create("Water plants", due)
        self.assertEqual(before.collect_due(), [])
        self.now = datetime(2026, 3, 8, 1, 45, tzinfo=CHICAGO)
        self.store = ReminderStore(self.path, clock=self.clock)
        fired = self.store.collect_due()
        self.assertEqual([r["id"] for r in fired], [reminder["id"]])
        self.assertEqual(fired[0]["body"], "Water plants")

    def test_fall_back_ambiguous_due_respects_explicit_offset(self):
        # 01:30 occurs twice; -05:00 selects the first occurrence (CDT ended).
        due = datetime.fromisoformat("2026-11-01T01:30:00-05:00")
        reminder = self.store.create("First pass", due)
        expected_utc = due.astimezone(UTC)
        self.now = (expected_utc - timedelta(minutes=1)).astimezone(CHICAGO)
        self.store = ReminderStore(self.path, clock=self.clock)
        self.assertEqual(self.store.collect_due(), [])
        self.now = expected_utc.astimezone(CHICAGO)
        self.store = ReminderStore(self.path, clock=self.clock)
        fired = self.store.collect_due()
        self.assertEqual([r["id"] for r in fired], [reminder["id"]])

    def test_survives_restart(self):
        due = datetime(2026, 3, 7, 13, 0, tzinfo=CHICAGO)
        created = self.store.create("Restart me", due)
        restarted = ReminderStore(self.path, clock=self.clock)
        self.assertEqual(restarted.list()[0]["id"], created["id"])
        self.now = due
        restarted = ReminderStore(self.path, clock=self.clock)
        self.assertEqual([r["id"] for r in restarted.collect_due()], [created["id"]])

    def test_fires_exactly_once(self):
        due = datetime(2026, 3, 7, 12, 0, tzinfo=CHICAGO)
        reminder = self.store.create("Once only", due)
        first = self.store.collect_due()
        second = self.store.collect_due()
        self.assertEqual([r["id"] for r in first], [reminder["id"]])
        self.assertEqual(second, [])
        row = ReminderStore(self.path, clock=self.clock).get(reminder["id"])
        self.assertEqual(row["state"], "fired")

    def test_cancel_prevents_firing(self):
        due = datetime(2026, 3, 7, 12, 30, tzinfo=CHICAGO)
        reminder = self.store.create("Skip me", due)
        self.store.cancel(reminder["id"])
        self.now = due
        self.store = ReminderStore(self.path, clock=self.clock)
        self.assertEqual(self.store.collect_due(), [])

    def test_symlinked_store_path_rejected_for_read_and_write(self):
        real = Path(self.tmp.name) / "real-reminders.sqlite"
        link = Path(self.tmp.name) / "reminders-link.sqlite"
        ReminderStore(real, clock=self.clock).create(
            "seed", datetime(2026, 3, 7, 18, 0, tzinfo=CHICAGO))
        os.symlink(real, link)
        with self.assertRaises(ReminderError):
            ReminderStore(link, clock=self.clock)
        self.store.create("local", datetime(2026, 3, 7, 19, 0, tzinfo=CHICAGO))
        backing = Path(self.tmp.name) / "backing.sqlite"
        self.path.rename(backing)
        os.symlink(backing, self.path)
        with self.assertRaises(ReminderError):
            self.store.list()

    def test_symlinked_ancestor_directory_rejected_for_read_and_write(self):
        real_root = Path(self.tmp.name) / "real-root"
        real_root.mkdir()
        link_root = Path(self.tmp.name) / "link-root"
        os.symlink(real_root, link_root)
        nested = link_root / "nested"
        nested.mkdir()
        path = nested / "reminders.sqlite"
        self.assertFalse(path.parent.is_symlink())
        due = datetime(2026, 3, 7, 18, 0, tzinfo=CHICAGO)
        with self.assertRaises(ReminderError):
            ReminderStore(path, clock=self.clock).create("blocked", due)
        good = real_root / "nested" / "good.sqlite"
        ReminderStore(good, clock=self.clock).create("ok", due)
        alias = link_root / "nested" / "good.sqlite"
        self.assertTrue(alias.exists())
        with self.assertRaises(ReminderError):
            ReminderStore(alias, clock=self.clock).list()

    def test_store_file_mode_is_private(self):
        self.store.create("Private", datetime(2026, 3, 7, 18, 0, tzinfo=CHICAGO))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_naive_clock_rejected(self):
        naive_clock = lambda: datetime(2026, 3, 7, 12, 0)
        store = ReminderStore(self.path, clock=naive_clock)
        due = datetime(2026, 3, 7, 12, 0, tzinfo=CHICAGO)
        store.create("Needs tz clock", due)
        with self.assertRaisesRegex(ReminderError, "timezone-aware clock"):
            store.collect_due()

    def test_naive_due_interpreted_as_chicago_wall_clock(self):
        naive_due = datetime(2026, 3, 7, 18, 0)
        created = self.store.create("Wall clock", naive_due)
        self.assertEqual(created["due_chicago"], "2026-03-07T18:00:00-06:00")
        explicit = self.store.create(
            "Explicit", datetime(2026, 3, 7, 18, 0, tzinfo=CHICAGO))
        self.assertEqual(explicit["due_chicago"], created["due_chicago"])


if __name__ == "__main__":
    unittest.main()

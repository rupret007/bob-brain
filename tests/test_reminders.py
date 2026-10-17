from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zoneinfo import ZoneInfo

from webbob.reminders import CHICAGO, MAX_PENDING_PER_OWNER, ReminderError, ReminderStore

UTC = ZoneInfo("UTC")
OWNER = "jeff"


class ReminderStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "reminders.sqlite"
        self.now = datetime(2026, 3, 7, 12, 0, tzinfo=CHICAGO)
        self.clock = lambda: self.now
        self.store = ReminderStore(self.path, OWNER, clock=self.clock)

    def test_create_list_and_cancel_pending(self):
        due = datetime(2026, 3, 7, 18, 0, tzinfo=CHICAGO)
        created = self.store.create("Take bins out", due)
        self.assertRegex(created["id"], r"[0-9a-f-]{36}")
        self.assertEqual(created["body"], "Take bins out")
        self.assertEqual(created["owner"], OWNER)
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

    def test_naive_due_strings_use_chicago_wall_clock(self):
        created = self.store.create("Naive", "2026-03-07T18:00:00")
        self.assertEqual(created["due_chicago"], "2026-03-07T18:00:00-06:00")

    def test_nonexistent_and_ambiguous_naive_times_rejected(self):
        for due in (
            "2027-03-14T02:30:00",
            "2026-11-01T01:30:00",
            "2026-03-08T02:15:00",
        ):
            with self.assertRaises(ReminderError):
                self.store.create("bad", due)

    def test_ambiguous_wall_time_accepts_explicit_offset(self):
        created = self.store.create("ok", "2026-11-01T01:30:00-06:00")
        self.assertEqual(created["due_chicago"], "2026-11-01T01:30:00-06:00")

    def test_past_due_refused(self):
        with self.assertRaises(ReminderError):
            self.store.create("late", "2020-01-01T00:00:00")

    def test_bad_due_raises_reminder_error_not_builtin(self):
        for due in ("garbage", "9999-12-31T23:59:59"):
            with self.assertRaises(ReminderError) as ctx:
                self.store.create("x", due)
            self.assertNotIsInstance(ctx.exception, OverflowError)
            self.assertIs(type(ctx.exception), ReminderError)

    def test_per_owner_pending_cap(self):
        base = datetime(2027, 1, 1, 9, 0, tzinfo=CHICAGO)
        for i in range(MAX_PENDING_PER_OWNER):
            self.store.create(f"r{i}", base + timedelta(minutes=i))
        with self.assertRaises(ReminderError):
            self.store.create("one too many", base + timedelta(days=1))

    def test_list_and_cancel_scoped_to_owner(self):
        other = ReminderStore(self.path, "other", clock=self.clock)
        created = self.store.create("Jeff private", "2027-01-02T09:00:00")
        self.assertEqual(other.list(), [])
        with self.assertRaises(ReminderError):
            other.cancel(created["id"])
        self.assertEqual(self.store.cancel(created["id"])["state"], "cancelled")

    def test_owner_column_persisted(self):
        self.store.create("x", "2027-01-02T09:00:00")
        cols = [
            row[1]
            for row in sqlite3.connect(self.path).execute("pragma table_info(reminders)")
        ]
        self.assertIn("owner", cols)

    def test_spring_forward_due_boundary_uses_chicago_wall_clock(self):
        before = ReminderStore(
            self.path, OWNER, clock=lambda: datetime(2026, 3, 8, 1, 44, tzinfo=CHICAGO)
        )
        due = datetime(2026, 3, 8, 1, 45, tzinfo=CHICAGO)
        reminder = before.create("Water plants", due)
        self.assertEqual(before.collect_due(), [])
        self.now = datetime(2026, 3, 8, 1, 45, tzinfo=CHICAGO)
        self.store = ReminderStore(self.path, OWNER, clock=self.clock)
        fired = self.store.collect_due()
        self.assertEqual([r["id"] for r in fired], [reminder["id"]])
        self.assertEqual(fired[0]["body"], "Water plants")
        self.store.mark_fired(reminder["id"])

    def test_fall_back_ambiguous_due_respects_explicit_offset(self):
        # 01:30 occurs twice; -05:00 selects the first occurrence (CDT ended).
        due = datetime.fromisoformat("2026-11-01T01:30:00-05:00")
        reminder = self.store.create("First pass", due)
        expected_utc = due.astimezone(UTC)
        self.now = (expected_utc - timedelta(minutes=1)).astimezone(CHICAGO)
        self.store = ReminderStore(self.path, OWNER, clock=self.clock)
        self.assertEqual(self.store.collect_due(), [])
        self.now = expected_utc.astimezone(CHICAGO)
        self.store = ReminderStore(self.path, OWNER, clock=self.clock)
        fired = self.store.collect_due()
        self.assertEqual([r["id"] for r in fired], [reminder["id"]])
        self.store.mark_fired(reminder["id"])

    def test_survives_restart(self):
        due = datetime(2026, 3, 7, 13, 0, tzinfo=CHICAGO)
        created = self.store.create("Restart me", due)
        restarted = ReminderStore(self.path, OWNER, clock=self.clock)
        self.assertEqual(restarted.list()[0]["id"], created["id"])
        self.now = due
        restarted = ReminderStore(self.path, OWNER, clock=self.clock)
        due_rows = restarted.collect_due()
        self.assertEqual([r["id"] for r in due_rows], [created["id"]])
        restarted.mark_fired(created["id"])

    def test_fires_exactly_once_after_delivery_confirmed(self):
        due = datetime(2026, 3, 7, 12, 0, tzinfo=CHICAGO)
        reminder = self.store.create("Once only", due)
        first = self.store.collect_due()
        self.assertEqual(self.store.get(reminder["id"])["state"], "pending")
        second = self.store.collect_due()
        self.assertEqual([r["id"] for r in first], [reminder["id"]])
        self.assertEqual([r["id"] for r in second], [reminder["id"]])
        self.store.mark_fired(reminder["id"])
        self.assertEqual(self.store.collect_due(), [])
        row = ReminderStore(self.path, OWNER, clock=self.clock).get(reminder["id"])
        self.assertEqual(row["state"], "fired")

    def test_cancel_prevents_firing(self):
        due = datetime(2026, 3, 7, 12, 30, tzinfo=CHICAGO)
        reminder = self.store.create("Skip me", due)
        self.store.cancel(reminder["id"])
        self.now = due
        self.store = ReminderStore(self.path, OWNER, clock=self.clock)
        self.assertEqual(self.store.collect_due(), [])

    def test_symlink_store_rejected(self):
        real = Path(self.tmp.name) / "real.sqlite"
        link = Path(self.tmp.name) / "link.sqlite"
        link.symlink_to(real)
        with self.assertRaises(ReminderError):
            ReminderStore(link, OWNER, clock=self.clock)

    def test_naive_clock_rejected(self):
        with self.assertRaises(ReminderError):
            ReminderStore(
                Path(self.tmp.name) / "other.sqlite",
                OWNER,
                clock=lambda: datetime(2026, 3, 7, 12, 0),
            )

    def test_body_length_enforced(self):
        with self.assertRaises(ReminderError):
            self.store.create("x" * 2001, "2027-01-02T09:00:00")

    def test_store_file_permissions(self):
        mode = self.path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_cancelled_reminders_stay_out_of_list(self):
        due = datetime(2026, 3, 7, 14, 0, tzinfo=CHICAGO)
        reminder = self.store.create("gone", due)
        self.store.cancel(reminder["id"])
        self.assertEqual(self.store.list(), [])


if __name__ == "__main__":
    unittest.main()

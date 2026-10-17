from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from webbob.morning_calendar import MorningCalendarError, MorningCalendarRoutine
from webbob.reminders import CHICAGO
from webbob.workspace import NEEDS_JEFF, Workspace, WorkspaceError, WRITE_TOOLS


class MorningCalendarRoutineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "morning-calendar.sqlite"
        self.now = datetime(2026, 3, 7, 7, 0, tzinfo=CHICAGO)
        self.clock = lambda: self.now
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.response = SimpleNamespace(
            isError=False,
            content=[SimpleNamespace(type="text", text="Team standup 9:00")],
            model_dump=lambda **kw: {"receipt": "calendar"},
        )
        self.session = SimpleNamespace(call_tool=AsyncMock(return_value=self.response))
        self.workspace = Workspace(self.session, account="owner@example.org", consent_verified=True)

    async def test_fires_once_per_chicago_morning(self):
        first = await self.routine.run_due(self.workspace)
        second = await self.routine.run_due(self.workspace)
        self.assertIsNotNone(first)
        self.assertEqual(first["chicago_date"], "2026-03-07")
        self.assertTrue(first["ok"])
        self.assertIsNone(second)
        self.now += timedelta(hours=2)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.assertIsNone(await self.routine.run_due(self.workspace))

    async def test_spring_forward_morning_fires_once(self):
        self.now = datetime(2026, 3, 8, 6, 59, tzinfo=CHICAGO)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.assertIsNone(await self.routine.run_due(self.workspace))
        self.now = datetime(2026, 3, 8, 7, 0, tzinfo=CHICAGO)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        fired = await self.routine.run_due(self.workspace)
        self.assertEqual(fired["chicago_date"], "2026-03-08")
        self.now = datetime(2026, 3, 8, 12, 0, tzinfo=CHICAGO)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.assertIsNone(await self.routine.run_due(self.workspace))

    async def test_fall_back_morning_fires_once_for_calendar_day(self):
        self.now = datetime(2026, 11, 1, 6, 59, tzinfo=CHICAGO)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.assertIsNone(await self.routine.run_due(self.workspace))
        self.now = datetime(2026, 11, 1, 7, 0, tzinfo=CHICAGO)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        fired = await self.routine.run_due(self.workspace)
        self.assertEqual(fired["chicago_date"], "2026-11-01")
        self.now = datetime(2026, 11, 1, 23, 0, tzinfo=CHICAGO)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.assertIsNone(await self.routine.run_due(self.workspace))

    async def test_lists_todays_events_read_only(self):
        result = await self.routine.run_due(self.workspace)
        self.assertTrue(result["ok"])
        self.assertEqual(result["calendar"]["source_tool"], "get_events")
        self.assertEqual(result["calendar"]["text"], "Team standup 9:00")
        self.assertFalse(result["calendar"]["execution_authority"])
        tool, args = self.session.call_tool.call_args.args
        self.assertEqual(tool, "get_events")
        self.assertEqual(args["calendar_id"], "primary")
        self.assertEqual(args["time_min"], "2026-03-07T00:00:00-06:00")
        self.assertEqual(args["time_max"], "2026-03-08T00:00:00-06:00")

    async def test_empty_calendar_day_is_honest(self):
        self.response.content[0].text = ""
        result = await self.routine.run_due(self.workspace)
        self.assertTrue(result["ok"])
        self.assertEqual(result["calendar"]["text"], "")
        self.assertNotIn("invented", result["calendar"]["text"].lower())

    async def test_calendar_error_is_honest_without_invented_events(self):
        self.session.call_tool.side_effect = TimeoutError("offline")
        result = await self.routine.run_due(self.workspace)
        self.assertFalse(result["ok"])
        self.assertEqual(result["calendar"], None)
        self.assertIn("unavailable", result["error"].lower())
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.assertIsNone(await self.routine.run_due(self.workspace))

    async def test_no_write_or_send_tools_reachable(self):
        await self.routine.run_due(self.workspace)
        tools = {call.args[0] for call in self.session.call_tool.call_args_list}
        self.assertEqual(tools, {"get_events"})
        self.assertNotIn("draft_gmail_message", tools)
        self.assertNotIn("manage_event", tools)
        self.assertEqual(set(WRITE_TOOLS.values()), {"draft_gmail_message", "manage_event"})

    async def test_cancel_stops_routine(self):
        self.routine.cancel()
        self.assertIsNone(await self.routine.run_due(self.workspace))
        self.session.call_tool.assert_not_awaited()
        self.now = datetime(2026, 3, 8, 7, 0, tzinfo=CHICAGO)
        self.routine = MorningCalendarRoutine(self.path, clock=self.clock)
        self.assertIsNone(await self.routine.run_due(self.workspace))

    async def test_oauth_pending_surfaces_needs_jeff_without_invented_events(self):
        workspace = Workspace(self.session, account="owner@example.org")
        result = await self.routine.run_due(workspace)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], NEEDS_JEFF)
        self.assertIsNone(result["calendar"])
        self.session.call_tool.assert_not_awaited()


class MorningCalendarRoutineStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "morning-calendar.sqlite"

    def test_unavailable_store_rejected(self):
        bad = Path(self.tmp.name) / "missing" / "morning.sqlite"
        with self.assertRaises(MorningCalendarError):
            MorningCalendarRoutine(bad)


if __name__ == "__main__":
    unittest.main()

"""Real Chromium, authenticated loopback M1 flow with no model or host effects."""
import json
import os
from pathlib import Path
import subprocess
import threading
from unittest.mock import Mock

from app import Server
from shared_chat import SharedChatContext
from skill_runtime import SkillRuntime
from storypool_actions import StoryPoolActions
from test_ui_browser import CODE, playwright_module
from test_webchat import Fixture


class PhoneAcceptanceTests(Fixture):
    def test_authenticated_memory_status_and_declined_action_at_phone_widths(self):
        for name in ('MONITOR.md', 'NEEDS_JEFF.md', 'conductor/digest-2026-10-18-am.md'):
            source = self.root / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('Offline acceptance fixture; no production observation.\n')
            source.chmod(0o600)
            os.utime(source, (1000, 1000))
        self.chat.shared_context = SharedChatContext(
            self.root / 'chat', source_folder=self.root,
            fetch_engine=lambda machine: ('{}', False))
        self.chat.shared_context.append(event_id='trial', actor='webbob', summary='Offline phone fixture')
        self.chat.skills = SkillRuntime(storypool_read=lambda: dict(files=[], needs_jeff=[],
            dashboard=dict(state='unavailable', freshness='unknown')))
        effects = Mock(side_effect=AssertionError('Declined action must never execute'))
        self.chat.storypool_actions = StoryPoolActions(self.folder, execute=effects)
        server = Server(('127.0.0.1', 0), self.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = self.root / 'phone-config.json'
        screenshots = os.environ.get('BOB_M1_SCREENSHOT_DIR')
        if screenshots:
            Path(screenshots).mkdir(mode=0o700, parents=True, exist_ok=True)
        config.write_text(json.dumps(dict(url='http://127.0.0.1:' + str(server.server_port),
            password=self.chat.password, screenshots=screenshots)))
        config.chmod(0o600)
        try:
            subprocess.run(['node', str(CODE / 'browser_m1_acceptance.cjs'), str(config)],
                check=True, timeout=90, env=dict(os.environ, BOB_PLAYWRIGHT_MODULE=playwright_module(CODE)))
            effects.assert_not_called()
            self.assertFalse(self.fake.calls, 'All trial responses must be deterministic and offline')
            self.assertIn('copper sailboat', (self.folder / 'memory/profile.md').read_text())
            receipts = json.loads((self.folder / 'storypool-actions/receipts.json').read_text())
            self.assertEqual([row['state'] for row in receipts.values()], ['cancelled'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

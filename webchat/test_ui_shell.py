"""Static shell contract for the polished phone-first Web Bob UI."""
from pathlib import Path
import unittest

from build_info import STATIC


class UiShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.css = (STATIC / "style.css").read_text(encoding="utf-8")
        cls.app = (STATIC / "app.js").read_text(encoding="utf-8")

    def test_removed_song_ui_stays_out_of_phone_shell(self):
        for needle in ('id="view-song"', 'data-bottom="song"', "Write a song", "Songs</span>"):
            self.assertNotIn(needle, self.index)

    def test_chat_composer_and_build_header_present(self):
        for needle in ('id="composer"', "composer-dock", 'id="attach-plus"', 'id="attach-input"', 'id="live-call"', "waveform", 'class="build-sha"'):
            self.assertIn(needle, self.index)
        self.assertIn(".composer-dock", self.css)
        self.assertIn(".job-llm", self.css)

    def test_jobs_page_structure(self):
        self.assertIn("jobs-page-header", self.index)
        self.assertIn('id="live-jobs"', self.index)
        self.assertIn("job-llm-row", self.app)


if __name__ == "__main__":
    unittest.main()

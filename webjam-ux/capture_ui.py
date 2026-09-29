#!/usr/bin/env python3
"""Offscreen layout evidence, with isolated settings and no external launches."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'repo'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from core.settings import AppSettings
from core.secret_store import NoSecretStore, set_default_secret_store
from webjam_qt.theme.qss_loader import load_stylesheet
from webjam_qt.windows.launch_dialog import LaunchDialog
from webjam_qt.windows.simple_settings import SimpleSettingsDialog


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else 'before'
    folder = ROOT / 'screenshots' / tag
    folder.mkdir(parents=True, exist_ok=True)
    set_default_secret_store(NoSecretStore('UI evidence; do not access credentials'))
    app = QApplication([])
    app.setStyleSheet(load_stylesheet())
    settings = AppSettings(config_file=str(folder / 'settings.json'),
                           last_creator_profile_key='music', musician_name='Sam')
    door = LaunchDialog(settings)
    door.show()
    app.processEvents()
    door.grab().save(str(folder / 'music-door.png'))
    door.show_join()
    app.processEvents()
    door.grab().save(str(folder / 'music-join.png'))
    door._join()
    app.processEvents()
    door.grab().save(str(folder / 'empty-invite.png'))
    door.close()
    prefs = SimpleSettingsDialog(settings, webex_opener=lambda _url: False)
    prefs.show()
    app.processEvents()
    prefs.grab().save(str(folder / 'settings.png'))
    prefs.close()
    print(folder)


if __name__ == '__main__':
    main()

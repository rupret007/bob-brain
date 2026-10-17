"""Home-prefix aliases must not weaken the local file boundary."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import chat_intent
from local_tasks import LocalFiles, LocalTasks, LocalTaskError


class HomeAliasTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.parent = self.root / 'real-parent'
        self.canonical_home = self.parent / 'home'
        self.documents = self.canonical_home / 'Documents'
        self.documents.mkdir(parents=True)
        (self.documents / 'note.txt').write_text('original home note')
        self.alias = self.root / 'home-parent-alias'
        self.alias.symlink_to(self.parent, target_is_directory=True)
        self.home = self.alias / 'home'
        self.files = LocalFiles(self.home)

    def test_absolute_alias_and_canonical_home_read_the_same_file(self):
        for home in (self.home, self.canonical_home):
            with self.subTest(home=str(home)):
                reply = self.files.execute(dict(kind='read', path=str(home / 'Documents/note.txt')))
                self.assertIn('original home note', reply)

    def test_alias_does_not_hide_user_symlinks_or_traversal(self):
        (self.canonical_home / 'shortcut').symlink_to(self.documents, target_is_directory=True)
        (self.documents / 'linked-note.txt').symlink_to(self.documents / 'note.txt')
        for suffix in ('shortcut/note.txt', 'Documents/linked-note.txt',
                       'Documents/../Documents/note.txt', '.private/note.txt'):
            with self.subTest(suffix=suffix):
                with self.assertRaises((LocalTaskError, OSError)):
                    self.files.execute(dict(kind='read', path=str(self.home / suffix)))

    def test_excluded_and_dynamic_protected_trees_reject_alias_paths(self):
        files = LocalFiles(self.home, excluded=(self.home / 'Documents/excluded',),
                           protected=lambda: (self.canonical_home / 'Documents/protected',))
        for home in (self.home, self.canonical_home):
            for suffix in ('Documents/excluded/note.txt', 'Documents/protected/note.txt',
                           'DOCUMENTS/EXCLUDED/note.txt', 'DOCUMENTS/PROTECTED/note.txt'):
                with self.subTest(home=str(home), suffix=suffix):
                    with self.assertRaisesRegex(LocalTaskError, 'outside the local file allowlist'):
                        files.parts(str(home / suffix))

    def test_worker_preserves_alias_and_keeps_canonical_home_when_alias_retargets(self):
        with patch('pathlib.Path.home', return_value=self.home):
            actions = LocalTasks(self.root / 'state', root=self.root / 'runtime')
        state = chat_intent.new_state()
        command = 'read file ' + str(self.home / 'Documents/note.txt')
        first = actions.handle(command, 'chat', str(uuid.uuid4()), state)
        self.assertIn('original home note', first)

        replacement_parent = self.root / 'replacement-parent'
        replacement_documents = replacement_parent / 'home/Documents'
        replacement_documents.mkdir(parents=True)
        (replacement_documents / 'note.txt').write_text('replacement home note')
        self.alias.unlink()
        self.alias.symlink_to(replacement_parent, target_is_directory=True)

        reply = actions.handle(command, 'chat', str(uuid.uuid4()), state)
        self.assertIn('original home note', reply)
        self.assertNotIn('replacement home note', reply)
        self.assertEqual(actions.files.home, self.canonical_home)

    def test_worker_refuses_canonical_home_replaced_by_symlink(self):
        with patch('pathlib.Path.home', return_value=self.home):
            actions = LocalTasks(self.root / 'state', root=self.root / 'runtime')
        moved_home = self.root / 'moved-home'
        self.canonical_home.rename(moved_home)
        self.canonical_home.symlink_to(moved_home, target_is_directory=True)

        reply = actions.handle('read file ' + str(self.home / 'Documents/note.txt'),
                               'chat', str(uuid.uuid4()), chat_intent.new_state())
        self.assertNotIn('File read:', reply)
        self.assertNotIn('original home note', reply)


if __name__ == '__main__':
    unittest.main()

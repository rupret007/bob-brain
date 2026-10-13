"""GitHub inbox reads: fake gh only, no live network, tokens, or mutations."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

from app import Chat, hard_rule_refusal
import chat_intent
from github_read import (
    AUTH, DISPLAY_LIMIT, FAILED, FETCH_LIMIT, GitHubRead, GitHubReadError, HELP,
    INVALID, JSON_FIELDS, NEED_REPO, READ_ONLY, TIMEOUT_MSG, TRUNCATED,
    UNAVAILABLE, UNALLOWLISTED, issue_argv, parse, pr_argv, run_gh,
)
from providers import KEY
from task_dispatch import parse_work, task_queue
from texting import Texting
from texting_fixture import OfflineProviders


ALLOWED = 'owner/allowed'
OTHER = 'evil/not-listed'


def item(kind, repo, number, title='Fix login', state='OPEN'):
    path = 'issues' if kind == 'issues' else 'pull'
    return dict(title=title, state=state, url=f'https://github.com/{repo}/{path}/{number}')


class FakeGh:
    def __init__(self):
        self.calls = []
        self.stdout = '[]'
        self.stderr = ''
        self.returncode = 0
        self.error = None
        self.payloads = {}

    def __call__(self, argv, timeout=None):
        self.calls.append(list(argv))
        if self.error:
            raise self.error
        key = tuple(argv)
        stdout = self.payloads.get(key, self.stdout)
        return subprocess.CompletedProcess(list(argv), self.returncode, stdout, self.stderr)


class GitHubFixture(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh()
        self.state = chat_intent.new_state()
        self.actions = GitHubRead(allowlist=[ALLOWED], runner=self.gh)
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.real_popen = patch('subprocess.Popen', side_effect=AssertionError('Real gh spawn forbidden'))
        self.real_popen.start()
        self.addCleanup(self.real_popen.stop)

    def say(self, text):
        return self.actions.handle(text, self.state)


class ParseAndAllowlistTests(GitHubFixture):
    def test_allowlisted_repo_only_and_exact_read_only_argv(self):
        self.gh.stdout = json.dumps([item('issues', ALLOWED, 1)])
        reply = self.say('list issues for ' + ALLOWED)
        self.assertIn('Fix login', reply)
        self.assertIn('https://github.com/owner/allowed/issues/1', reply)
        self.assertEqual(self.gh.calls, [issue_argv(ALLOWED)])
        self.assertEqual(self.gh.calls[0], [
            'gh', 'issue', 'list', '--repo', ALLOWED, '--limit', str(FETCH_LIMIT),
            '--json', JSON_FIELDS])
        self.gh.stdout = json.dumps([item('pulls', ALLOWED, 2, 'Draft inbox')])
        reply = self.say('list PRs for ' + ALLOWED)
        self.assertIn('Draft inbox', reply)
        self.assertEqual(self.gh.calls[1], [
            'gh', 'pr', 'list', '--repo', ALLOWED, '--limit', str(FETCH_LIMIT),
            '--json', JSON_FIELDS])
        self.assertEqual(self.gh.calls[1], pr_argv(ALLOWED))

    def test_unallowlisted_repo_never_spawns(self):
        self.assertEqual(self.say('list issues for ' + OTHER), UNALLOWLISTED)
        self.assertEqual(self.say('gh issue list --repo ' + OTHER), UNALLOWLISTED)
        self.assertFalse(self.gh.calls)

    def test_default_allowlist_is_owner_repo_only(self):
        actions = GitHubRead(runner=self.gh)
        self.assertIsNone(actions.resolve(OTHER))
        self.assertEqual(actions.resolve('rupret007/bob-brain'), 'rupret007/bob-brain')
        self.gh.stdout = json.dumps([item('issues', 'rupret007/bob-brain', 3)])
        self.assertIn('issues/3', actions.handle(
            'list issues for Rupret007/Bob-Brain', self.state))
        self.assertEqual(self.gh.calls, [issue_argv('rupret007/bob-brain')])

    def test_env_allowlist_rejects_injection_fragments(self):
        with patch.dict(os.environ, BOB_GITHUB_REPOS='friend/ok,evil/repo;rm'):
            actions = GitHubRead(runner=self.gh)
        self.assertEqual(actions.resolve('friend/ok'), 'friend/ok')
        self.assertIsNone(actions.resolve('evil/repo;rm'))

    def test_command_injection_is_rejected_without_spawn(self):
        for text in (
            'list issues for ' + ALLOWED + '; rm -rf /',
            'list issues for ' + ALLOWED + ' && gh issue comment 1',
            'list issues for ' + ALLOWED + ' | cat',
            'list issues for $(whoami)/repo',
            'list issues for ' + ALLOWED + ' --search "inject"',
            'gh issue list --repo ' + ALLOWED + ' --json title,body',
            'gh issue list --repo ' + ALLOWED + '; id',
        ):
            with self.subTest(text=text):
                reply = self.say(text)
                self.assertIn(reply, (READ_ONLY, NEED_REPO, UNALLOWLISTED))
                self.assertNotIn('No open issues', reply)
        self.assertFalse(self.gh.calls)

    def test_comment_and_mutation_are_rejected_without_spawn(self):
        for text in (
            'comment on issue 1 in ' + ALLOWED,
            'gh issue comment 1 --repo ' + ALLOWED,
            'close issue 1 for ' + ALLOWED,
            'create an issue in ' + ALLOWED,
            'list issues for ' + ALLOWED + ' and comment on #1',
            'Please close the GitHub issue 4',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.say(text), READ_ONLY)
        self.assertFalse(self.gh.calls)

    def test_review_and_draft_publication_paths_are_not_claimed(self):
        for text in (
            'review the draft PR',
            'review PR #12',
            'push WebJam',
            'Please merge #158',
            'Run gh pr ready',
            'what does gh pr ready do',
            'show my calendar today',
            'list files ~/Documents',
            'list the issues with my plan',
            'Can you list the issues we discussed?',
        ):
            with self.subTest(text=text):
                self.assertIsNone(self.say(text))
                self.assertIsNone(parse(text))
        self.assertFalse(self.gh.calls)
        self.assertIsNotNone(hard_rule_refusal('Please merge #158'))
        self.assertIsNotNone(hard_rule_refusal('Run gh pr ready'))
        self.assertEqual(parse_work('push WebJam')[0], 'push WebJam')
        self.assertIsNone(parse('review the draft PR'))


class HoldLimitFailureTests(GitHubFixture):
    def test_active_hold_is_checked_before_any_spawn(self):
        chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
        self.gh.stdout = json.dumps([item('issues', ALLOWED, 1)])
        for text in (
            'list issues for ' + ALLOWED,
            'list PRs for ' + ALLOWED,
            'gh issue list --repo ' + ALLOWED,
            'list issues for ' + OTHER,
            'list issues for ' + ALLOWED + '; rm -rf /',
            'comment on issue 1 in ' + ALLOWED,
        ):
            with self.subTest(text=text):
                self.assertIn('On hold:', self.say(text))
        self.assertFalse(self.gh.calls)

    def test_help_does_not_spawn(self):
        self.assertEqual(self.say('github inbox help'), HELP)
        self.assertFalse(self.gh.calls)

    def test_limit_is_twenty_with_truncation_note(self):
        rows = [item('issues', ALLOWED, n, title='Issue %d' % n) for n in range(1, FETCH_LIMIT + 1)]
        self.gh.stdout = json.dumps(rows)
        reply = self.say('show issues for ' + ALLOWED)
        self.assertIn(TRUNCATED, reply)
        self.assertIn('Issue 1', reply)
        self.assertIn('Issue %d' % DISPLAY_LIMIT, reply)
        self.assertNotIn('Issue %d' % FETCH_LIMIT, reply)
        self.assertEqual(reply.count('https://github.com/'), DISPLAY_LIMIT)
        self.assertEqual(self.gh.calls[0][self.gh.calls[0].index('--limit') + 1], str(FETCH_LIMIT))

    def test_successful_empty_inbox_is_only_for_verified_empty_list(self):
        self.gh.stdout = '[]'
        self.assertIn('No open issues.', self.say('list issues for ' + ALLOWED))
        self.assertIn('No open pull requests.', self.say('list pull requests for ' + ALLOWED))
        self.assertNotIn(TRUNCATED, self.say('list issues for ' + ALLOWED))

    def test_timeout_and_auth_failure_never_fabricate_an_empty_inbox(self):
        self.gh.error = subprocess.TimeoutExpired(['gh'], 10)
        timeout = self.say('list issues for ' + ALLOWED)
        self.assertEqual(timeout, TIMEOUT_MSG)
        self.assertNotIn('No open issues', timeout)
        self.assertNotIn('No open pull requests', timeout)
        self.gh.error = None
        self.gh.returncode = 1
        self.gh.stderr = 'authentication required: missing GH_TOKEN ghp_' + 'a' * 30
        self.gh.stdout = '[]'
        auth = self.say('list PRs for ' + ALLOWED)
        self.assertEqual(auth, AUTH)
        self.assertNotIn('No open', auth)
        self.gh.stderr = 'boom'
        failed = self.say('list issues for ' + ALLOWED)
        self.assertEqual(failed, FAILED)
        self.assertNotIn('No open issues', failed)

    def test_invalid_or_missing_payload_is_not_an_empty_inbox(self):
        for payload in ('', '{', 'null', '{"title":"x"}', json.dumps([{'title': 1, 'state': 'OPEN', 'url': 'https://github.com/owner/allowed/issues/1'}])):
            self.gh.stdout = payload
            reply = self.say('list issues for ' + ALLOWED)
            self.assertEqual(reply, INVALID)
            self.assertNotIn('No open issues', reply)

    def test_output_redaction_strips_tokens_from_titles(self):
        secret = 'ghp_' + 'b' * 30
        self.gh.stdout = json.dumps([item('issues', ALLOWED, 9, title='leak ' + secret)])
        reply = self.say('list issues for ' + ALLOWED)
        self.assertNotIn(secret, reply)
        self.assertIn('[secret removed]', reply)
        self.assertTrue(KEY.search('leak ' + secret))
        extra = GitHubRead(allowlist=[ALLOWED], runner=self.gh, redact=lambda text: text.replace('VISIBLE-SECRET', '[secret removed]'))
        self.gh.stdout = json.dumps([item('issues', ALLOWED, 10, title='note VISIBLE-SECRET')])
        redacted = extra.handle('list issues for ' + ALLOWED, self.state)
        self.assertNotIn('VISIBLE-SECRET', redacted)
        self.assertIn('[secret removed]', redacted)

    def test_runner_oserror_is_unavailable_not_empty(self):
        self.gh.error = OSError('missing gh')
        reply = self.say('list issues for ' + ALLOWED)
        self.assertEqual(reply, UNAVAILABLE)
        self.assertNotIn('No open issues', reply)

    def test_supported_grammar_does_not_require_model(self):
        self.gh.stdout = json.dumps([item('issues', ALLOWED, 1)])
        for text in (
            'Please list issues for ' + ALLOWED,
            'Could you show GitHub issues for ' + ALLOWED + '?',
            'list issue inbox for repo ' + ALLOWED,
            'gh issue list --repo ' + ALLOWED,
            'github inbox for ' + ALLOWED,
        ):
            with self.subTest(text=text):
                self.assertIn('Fix login', self.say(text))


class SpawnBoundaryTests(unittest.TestCase):
    def test_run_gh_uses_argv_list_and_maps_timeout(self):

        class FakeProcess:
            def __init__(self):
                self.kill_called = False

            def communicate(self, timeout=None):
                if timeout is not None:
                    raise subprocess.TimeoutExpired(['gh'], timeout)
                return b'', b''

            def kill(self):
                self.kill_called = True

        hung = FakeProcess()
        with patch('subprocess.Popen', return_value=hung) as popen:
            with self.assertRaises(GitHubReadError) as error:
                run_gh(['gh', 'issue', 'list'], timeout=0.01)
        self.assertEqual(str(error.exception), TIMEOUT_MSG)
        self.assertTrue(hung.kill_called)
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ['gh', 'issue', 'list'])
        self.assertNotEqual(popen.call_args.kwargs.get('stdin'), None)
        with patch('subprocess.Popen', side_effect=FileNotFoundError('gh')):
            with self.assertRaises(GitHubReadError) as error:
                run_gh(['gh', 'issue', 'list'])
        self.assertEqual(str(error.exception), UNAVAILABLE)
        with patch('subprocess.Popen') as popen:
            process = Mock()
            process.communicate.return_value = (b'[]', b'')
            process.returncode = 0
            popen.return_value = process
            result = run_gh(issue_argv(ALLOWED))
        self.assertEqual(result.stdout, '[]')
        self.assertEqual(popen.call_args.args[0], issue_argv(ALLOWED))


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gh = FakeGh()
        self.actions = GitHubRead(allowlist=[ALLOWED], runner=self.gh)
        self.providers = OfflineProviders()
        self.chat = Chat(self.root / 'chat', self.root, self.providers, texting=Texting(Mock(), Mock()),
                         reminder_notifier=Mock(), github_read=self.actions)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def submit(self, text):
        with patch('app.parse_work', side_effect=AssertionError('Entered generic queue')):
            return self.chat.submit(self.cid, text, str(uuid.uuid4()), actor='owner')['messages'][-1]

    def test_inbox_lists_are_direct_before_model_or_coding(self):
        self.gh.stdout = json.dumps([item('issues', ALLOWED, 4, 'Direct path')])
        response = self.submit('list issues for ' + ALLOWED)
        self.assertEqual(response['provider'], 'github')
        self.assertIn('Direct path', response['content'])
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.gh.stdout = json.dumps([item('pulls', ALLOWED, 5, 'PR card')])
        response = self.submit('list PRs for ' + ALLOWED)
        self.assertEqual(response['provider'], 'github')
        self.assertIn('PR card', response['content'])

    def test_saved_hold_blocks_chat_inbox_before_spawn(self):
        self.chat.submit(self.cid, 'Hold all work', str(uuid.uuid4()))
        before = copy.deepcopy(self.chat.get(self.cid)['intent_state'])
        self.gh.stdout = json.dumps([item('issues', ALLOWED, 1)])
        result = self.submit('list issues for ' + ALLOWED)
        self.assertIn('On hold:', result['content'])
        self.assertEqual(self.chat.get(self.cid)['intent_state'], before)
        self.assertFalse(self.gh.calls)
        self.assertFalse(self.providers.calls)

    def test_existing_review_and_publication_paths_still_reach_their_handlers(self):
        merge = self.chat.submit(self.cid, 'Please merge #158', str(uuid.uuid4()), actor='owner')['messages'][-1]
        self.assertIn("won't merge", merge['content'])
        self.assertFalse(self.gh.calls)
        ready = self.chat.submit(self.cid, 'Run gh pr ready', str(uuid.uuid4()), actor='owner')['messages'][-1]
        self.assertIn('Drafts only', ready['content'])
        self.assertFalse(self.gh.calls)
        self.assertIsNone(self.actions.handle('push WebJam', chat_intent.new_state()))
        self.assertIsNone(self.actions.handle('review the draft PR', chat_intent.new_state()))


if __name__ == '__main__':
    unittest.main()

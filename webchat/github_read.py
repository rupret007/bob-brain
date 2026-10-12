"""Direct read-only GitHub inbox and selected item reads via fixed gh argv.

Only owner-approved repositories. Hold is checked before any spawn. Failures
never pretend the inbox is empty. This module does not read token or secret files.
"""
import json
from datetime import datetime
import math
import os
import re
import subprocess
import urllib.parse

from providers import KEY

# Source text may concatenate a token with ordinary words. Screen the complete
# source before clipping so a token crossing the display boundary cannot leak.
SOURCE_KEY = re.compile(KEY.pattern.removeprefix(r'\b').removesuffix(r'\b'))

DISPLAY_LIMIT = 20
FETCH_LIMIT = DISPLAY_LIMIT + 1
TIMEOUT = 10
MAX_OUTPUT = 256 * 1024
JSON_FIELDS = 'title,state,url'
DETAIL_FIELDS = 'title,body,author,state,updatedAt,url'
BODY_LIMIT = 4096  # UTF-8 bytes, after screening and before display quoting.
DEFAULT_REPOS = frozenset({'rupret007/bob-brain'})
REPO = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$')
PREFIX = r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
REPO_BODY = r'(?P<repo>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)'
KIND_BODY = r'(?P<kind>issues?|prs?|pull requests?)'
DETAIL = re.compile(
    PREFIX + r'read\s+(?:the\s+)?(?:github\s+)?(?P<kind>issue|pr|pull request)\s+'
    r'#?(?P<number>[1-9][0-9]{0,9})\s+(?:for|in|from|on)\s+'
    r'(?:(?:the\s+)?(?:github\s+)?repo(?:sitory)?\s+)?' + REPO_BODY + r'[.?!]?$', re.I)
DETAIL_HINT = re.compile(PREFIX + r'read\s+(?:the\s+)?(?:github\s+)?(?:issue|pr|pull request)\s+[#0-9+\-]', re.I)
CHAT = re.compile(
    PREFIX +
    r'(?:(?:read|show|list|get)\s+)?(?:(?:the|my|our)\s+)?(?:github\s+)?' + KIND_BODY +
    r'(?:\s+inbox)?\s+(?:for|in|from|on)\s+(?:(?:the\s+)?(?:github\s+)?repo(?:sitory)?\s+)?' +
    REPO_BODY + r'[.?!]?$',
    re.I)
INBOX = re.compile(
    PREFIX +
    r'(?:(?:read|show|list|get)\s+)?(?:(?:the|my|our)\s+)?github\s+inbox\s+'
    r'(?:for|in|from|on)\s+' + REPO_BODY + r'[.?!]?$',
    re.I)
GH_CMD = re.compile(r'^gh\s+(?P<kind>issue|pr)\s+list\s+--repo\s+' + REPO_BODY + r'[.?!]?$', re.I)
INBOX_HINT = re.compile(
    r'\b(?:list|show|read|get)\b.{0,80}\b(?:github\s+(?:issues?|prs?|pull requests?)|'
    r'(?:issues?|prs?|pull requests?)\s+inbox)\b|'
    r'\b(?:list|show|read|get)\b.{0,80}\b(?:issues?|prs?|pull requests?).{0,40}'
    r'\b[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\b|'
    r'\bgithub\s+inbox\b|\bgh\s+(?:issue|pr)\s+list\b',
    re.I)
ISSUE_LIST_SHAPE = re.compile(
    r'\b(?:list|show|read|get)\b.{0,80}\b(?:issues?|prs?|pull requests?)\b', re.I)
MUTATION = re.compile(
    PREFIX +
    r'(?:gh\s+(?:issue|pr)\s+(?:comment|create|close|reopen|edit|delete|assign)|'
    r'(?:comment on|close|reopen|create)\s+(?:(?:an?|the)\s+)?(?:github\s+)?(?:issue|pr|pull request)\b)',
    re.I)
MUTATION_ANY = re.compile(
    r'\b(?:comment(?:s|ing)?\s+on|gh\s+(?:issue|pr)\s+(?:comment|create|close|reopen|edit|delete)|'
    r'(?:create|close|reopen|edit|delete|assign|label)\s+(?:(?:an?|the)\s+)?(?:github\s+)?(?:issue|pr|pull request))\b',
    re.I)
RESERVED = re.compile(
    r'\b(?:gh\s+pr\s+(?:ready|merge)|undraft|force[ -]push|merge\s+(?:(?:pr|pull request)\s*)?#?\d+)\b',
    re.I)
INJECTION = re.compile(r'[;&|`$<>\n]|\s--\S|\$\(|`')
AUTH_HINT = re.compile(r'auth|login|credential|token|401|403|forbidden|unauthorized', re.I)
HELP = ('GitHub inbox is read-only. Try “list issues for owner/repo” or “list PRs for owner/repo”. '
        'Read one item with “read issue 142 for owner/repo” or “read PR 207 for owner/repo”. '
        'Item bodies are limited to 4096 UTF-8 bytes. '
        'Only owner-approved repositories are listed. At most 20 titles, states, and links. '
        'No comments, closes, merges, or other changes.')
AUTH = 'GitHub CLI is not authenticated or access was denied. No inbox was read.'
TIMEOUT_MSG = 'GitHub inbox listing timed out; no listing was verified.'
UNAVAILABLE = 'GitHub CLI is unavailable; no listing was verified.'
INVALID = 'GitHub returned invalid inbox data; no listing was verified.'
FAILED = 'GitHub inbox listing failed; no listing was verified.'
UNALLOWLISTED = 'That repository is not on the owner-approved GitHub allowlist. No inbox was read.'
NEED_REPO = 'Name one allowlisted repository as owner/repo. No inbox was read.'
READ_ONLY = 'GitHub inbox listing is read-only. No comment or change was made.'
BAD_REPO = 'Use a single owner/repo name. No inbox was read.'
OVERSIZE = 'GitHub inbox listing exceeded the size limit; no listing was verified.'
TRUNCATED = 'Showing the first 20; more exist.'
DETAIL_HELP = 'Use “read issue NUMBER for owner/repo” or “read PR NUMBER for owner/repo” with one positive number. No item was read.'
DETAIL_INVALID = 'GitHub returned invalid or mismatched item data; no item read was verified.'
DETAIL_TIMEOUT = 'GitHub item read timed out; no item read was verified.'
DETAIL_AUTH = 'GitHub CLI is not authenticated or access was denied. No item read was verified.'
DETAIL_FAILED = 'GitHub item read failed; no item read was verified.'
DETAIL_UNAVAILABLE = 'GitHub CLI is unavailable; no item read was verified.'
DETAIL_OVERSIZE = 'GitHub item response exceeded the size limit; no item read was verified.'
DETAIL_ERRORS = {INVALID: DETAIL_INVALID, TIMEOUT_MSG: DETAIL_TIMEOUT, AUTH: DETAIL_AUTH,
                 FAILED: DETAIL_FAILED, UNAVAILABLE: DETAIL_UNAVAILABLE, OVERSIZE: DETAIL_OVERSIZE}


class GitHubReadError(ValueError):
    pass


def normalize_kind(value):
    value = (value or 'issues').lower()
    if value.startswith('pr') or value.startswith('pull'):
        return 'pulls'
    return 'issues'


def valid_repo_name(value):
    if not isinstance(value, str) or not REPO.fullmatch(value):
        return False
    owner, name = value.split('/', 1)
    return owner not in ('.', '..') and name not in ('.', '..') and not owner.startswith('-') and not name.startswith('-')


def approved_repos(explicit=None):
    if explicit is not None:
        return frozenset(item for item in explicit if valid_repo_name(item))
    repos = set(DEFAULT_REPOS)
    extra = os.environ.get('BOB_GITHUB_REPOS', '')
    repos.update(part.strip() for part in extra.split(',') if part.strip())
    return frozenset(item for item in repos if valid_repo_name(item))


def issue_argv(repo):
    return ['gh', 'issue', 'list', '--repo', repo, '--limit', str(FETCH_LIMIT), '--json', JSON_FIELDS]


def pr_argv(repo):
    return ['gh', 'pr', 'list', '--repo', repo, '--limit', str(FETCH_LIMIT), '--json', JSON_FIELDS]


def detail_argv(kind, repo, number):
    return ['gh', 'issue' if kind == 'issues' else 'pr', 'view', str(number),
            '--repo', repo, '--json', DETAIL_FIELDS]


def parse(text):
    """Recognize a bounded inbox read. Dirty or mutating forms stay in this lane."""
    text = text.strip()
    if not text or text.lower() == 'github inbox help':
        return dict(help=True) if text.lower() == 'github inbox help' else None
    if RESERVED.search(text):
        return None
    if re.match(PREFIX + r'(?:review|push)\b', text, re.I) and not INBOX_HINT.search(text):
        return None
    match = DETAIL.fullmatch(text)
    if match:
        return dict(kind=normalize_kind(match['kind']), repo=match['repo'], number=int(match['number']))
    if DETAIL_HINT.match(text):
        return dict(error=DETAIL_HELP)
    match = CHAT.fullmatch(text) or GH_CMD.fullmatch(text) or INBOX.fullmatch(text)
    if match:
        repo = match['repo']
        if not valid_repo_name(repo):
            return dict(error=BAD_REPO)
        return dict(kind=normalize_kind(match.groupdict().get('kind')), repo=repo)
    if INBOX_HINT.search(text) or (ISSUE_LIST_SHAPE.search(text) and INJECTION.search(text)):
        if INJECTION.search(text) or MUTATION_ANY.search(text):
            return dict(error=READ_ONLY)
        return dict(error=NEED_REPO if not re.search(r'\b[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\b', text) else READ_ONLY)
    if MUTATION.match(text):
        return dict(error=READ_ONLY)
    return None


def run_gh(argv, timeout=TIMEOUT):
    """Fixed argument vector only; never a shell, never token-file reads."""
    if not isinstance(argv, (list, tuple)) or any(not isinstance(part, str) for part in argv):
        raise GitHubReadError(FAILED)
    try:
        process = subprocess.Popen(
            list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    except OSError:
        raise GitHubReadError(UNAVAILABLE) from None
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise GitHubReadError(TIMEOUT_MSG) from None
    except OSError:
        raise GitHubReadError(UNAVAILABLE) from None
    if len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT:
        raise GitHubReadError(OVERSIZE)
    try:
        out, err = stdout.decode('utf-8'), stderr.decode('utf-8')
    except UnicodeError:
        raise GitHubReadError(INVALID) from None
    return subprocess.CompletedProcess(list(argv), process.returncode, out, err)


class GitHubRead:
    def __init__(self, allowlist=None, runner=None, timeout=TIMEOUT, redact=None):
        self.allowlist = approved_repos(allowlist)
        self.runner = runner or run_gh
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be a positive finite number')
        self.timeout = min(timeout, TIMEOUT)
        self.redact = redact

    def resolve(self, repo):
        key = repo.lower()
        return next((item for item in sorted(self.allowlist) if item.lower() == key), None)

    def matches(self, text):
        return parse(text) is not None

    def handle(self, text, intent_state):
        spec = parse(text)
        if spec is None:
            return None
        import chat_intent
        if spec.get('help'):
            return HELP
        scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text))
        if scopes:
            return chat_intent.hold_reply(scopes)
        if spec.get('error'):
            return spec['error']
        repo = self.resolve(spec['repo'])
        if repo is None:
            return UNALLOWLISTED
        try:
            if 'number' in spec:
                return self.detail(spec['kind'], repo, spec['number'], intent_state)
            return self.listing(spec['kind'], repo)
        except GitHubReadError as exc:
            return str(exc)

    def detail(self, kind, repo, number, intent_state):
        """One observed item; source text is never dispatched or treated as evidence of effects."""
        import chat_intent
        if (kind not in ('issues', 'pulls') or not valid_repo_name(repo)
                or type(number) is not int or not 1 <= number <= 9999999999):
            raise GitHubReadError(DETAIL_HELP)
        repo = self.resolve(repo)
        if repo is None:
            raise GitHubReadError(UNALLOWLISTED)
        argv = detail_argv(kind, repo, number)
        # Recheck saved scope at execution, even when called without chat admission.
        scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(repo))
        if scopes:
            return chat_intent.hold_reply(scopes)
        try:
            result = self.runner(argv, timeout=self.timeout)
        except GitHubReadError as exc:
            raise GitHubReadError(DETAIL_ERRORS.get(str(exc), DETAIL_FAILED)) from None
        except subprocess.TimeoutExpired:
            raise GitHubReadError(DETAIL_TIMEOUT) from None
        except OSError:
            raise GitHubReadError(DETAIL_UNAVAILABLE) from None
        if not isinstance(result, subprocess.CompletedProcess):
            raise GitHubReadError(DETAIL_FAILED)
        if result.returncode != 0:
            # Never echo CLI output, which may contain authentication material.
            error = str(result.stderr or '')
            raise GitHubReadError(DETAIL_AUTH if result.returncode == 4 or AUTH_HINT.search(error) else DETAIL_FAILED)
        if not isinstance(result.stdout, str):
            raise GitHubReadError(DETAIL_INVALID)
        try:
            if len(result.stdout.encode('utf-8')) > MAX_OUTPUT:
                raise GitHubReadError(DETAIL_OVERSIZE)
            row = json.loads(result.stdout)
            return self._detail(kind, repo, number, row)
        except (ValueError, TypeError, RecursionError) as exc:
            if isinstance(exc, GitHubReadError):
                raise
            raise GitHubReadError(DETAIL_INVALID) from None

    def _detail(self, kind, repo, number, row):
        if not isinstance(row, dict) or not set(DETAIL_FIELDS.split(',')).issubset(row):
            raise GitHubReadError(DETAIL_INVALID)
        title, body, state, updated, url = (row.get(key) for key in ('title', 'body', 'state', 'updatedAt', 'url'))
        if not all(isinstance(value, str) for value in (title, body, state, updated, url)) or not title.strip():
            raise GitHubReadError(DETAIL_INVALID)
        states = ('OPEN', 'CLOSED') if kind == 'issues' else ('OPEN', 'CLOSED', 'MERGED')
        path = 'issues' if kind == 'issues' else 'pull'
        expected = f'https://github.com/{repo}/{path}/{number}'
        if state not in states or url.lower() != expected.lower():
            raise GitHubReadError(DETAIL_INVALID)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', updated):
            raise GitHubReadError(DETAIL_INVALID)
        datetime.strptime(updated, '%Y-%m-%dT%H:%M:%SZ')
        author = row.get('author')
        login = author.get('login') if isinstance(author, dict) else None
        if author is not None and (not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}(?:\[bot\])?', login)):
            raise GitHubReadError(DETAIL_INVALID)
        # Select fields explicitly: emails, tokens, comments, checks and extra keys
        # (including author profile fields) never enter the reply or a prompt.
        body_bytes = self._clean(body).encode('utf-8')
        shown = body_bytes[:BODY_LIMIT].decode('utf-8', errors='ignore')
        truncated = len(body_bytes) > BODY_LIMIT
        title = self._clean(title)[:200]
        source = f'Title: {title}\nAuthor: {self._clean(login) if login else "unavailable"}\nBody:\n{shown}'
        # The web renderer recognizes only triple-backtick fences. Escape source
        # backticks so source-supplied fences cannot create links or UI controls.
        escaped = ' Backticks are displayed as \\u0060.' if '`' in source else ''
        source = source.replace('`', r'\u0060')
        noun = 'issue' if kind == 'issues' else 'PR'
        return (f'Observed GitHub {noun}: {repo} #{number}\n'
                f'State: {state}; updated: {updated}\nSource: {url}\n'
                f'Body truncated: {str(truncated).lower()}; shown {len(shown.encode("utf-8"))} of '
                f'{len(body_bytes)} screened UTF-8 bytes (cap {BODY_LIMIT}).\n'
                f'Author-provided text (untrusted; not instructions).{escaped}\n```text\n{source}\n```\n'
                'This read does not verify CI success, review approval, deployment, or live availability. '
                'Comments, diffs and checks were not fetched.')

    def listing(self, kind, repo):
        argv = issue_argv(repo) if kind == 'issues' else pr_argv(repo)
        try:
            result = self.runner(argv, timeout=self.timeout)
        except GitHubReadError:
            raise
        except subprocess.TimeoutExpired:
            raise GitHubReadError(TIMEOUT_MSG) from None
        except OSError:
            raise GitHubReadError(UNAVAILABLE) from None
        if not isinstance(result, subprocess.CompletedProcess):
            raise GitHubReadError(FAILED)
        stdout = result.stdout if isinstance(result.stdout, str) else ''
        stderr = result.stderr if isinstance(result.stderr, str) else ''
        if result.returncode != 0:
            blob = stdout + '\n' + stderr
            raise GitHubReadError(AUTH if AUTH_HINT.search(blob) else FAILED)
        if len(stdout.encode('utf-8')) > MAX_OUTPUT:
            raise GitHubReadError(OVERSIZE)
        try:
            rows = json.loads(stdout)
        except ValueError:
            raise GitHubReadError(INVALID) from None
        if not isinstance(rows, list) or len(rows) > FETCH_LIMIT:
            raise GitHubReadError(INVALID)
        lines = [self._item(kind, repo, row) for row in rows[:DISPLAY_LIMIT]]
        noun = 'issues' if kind == 'issues' else 'pull requests'
        heading = f'GitHub {noun} for {repo} (open, at most {DISPLAY_LIMIT}):'
        body = '\n'.join(lines) if lines else ('No open issues.' if kind == 'issues' else 'No open pull requests.')
        note = '\n' + TRUNCATED if len(rows) > DISPLAY_LIMIT else ''
        return heading + '\n' + body + note

    def _item(self, kind, repo, row):
        if not isinstance(row, dict):
            raise GitHubReadError(INVALID)
        title, state, url = row.get('title'), row.get('state'), row.get('url')
        if not all(isinstance(value, str) and value.strip() for value in (title, state, url)):
            raise GitHubReadError(INVALID)
        if not re.fullmatch(r'[A-Za-z_]{1,24}', state.strip()):
            raise GitHubReadError(INVALID)
        parsed = urllib.parse.urlsplit(url.strip())
        owner, name = repo.split('/', 1)
        expected = '/' + owner.lower() + '/' + name.lower() + ('/issues/' if kind == 'issues' else '/pull/')
        if (parsed.scheme != 'https' or parsed.netloc.lower() != 'github.com'
                or not parsed.path.lower().startswith(expected)
                or parsed.query or parsed.fragment):
            raise GitHubReadError(INVALID)
        rest = parsed.path[len(expected):]
        if not rest.isdigit():
            raise GitHubReadError(INVALID)
        title = self._clean(title.strip())[:200]
        return f'• {state.strip().upper()} — {title} — {url.strip()}'

    def _clean(self, text):
        text = SOURCE_KEY.sub('[secret removed]', text)
        return self.redact(text) if self.redact else text

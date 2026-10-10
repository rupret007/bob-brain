"""Direct read-only GitHub issue/PR inbox listing via fixed gh argv.

Only owner-approved repositories. Hold is checked before any spawn. Failures
never pretend the inbox is empty. This module does not read token or secret files.
"""
import json
import os
import re
import subprocess
import urllib.parse

from providers import KEY

DISPLAY_LIMIT = 20
FETCH_LIMIT = DISPLAY_LIMIT + 1
TIMEOUT = 10
MAX_OUTPUT = 256 * 1024
JSON_FIELDS = 'title,state,url'
DEFAULT_REPOS = frozenset({'rupret007/bob-brain'})
REPO = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$')
PREFIX = r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
REPO_BODY = r'(?P<repo>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)'
KIND_BODY = r'(?P<kind>issues?|prs?|pull requests?)'
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
    r'\b(?:list|show|read|get)\b.{0,80}\b(?:github\s+)?(?:issues?|prs?|pull requests?)(?:\s+inbox)?\b|'
    r'\bgithub\s+inbox\b|\bgh\s+(?:issue|pr)\s+list\b',
    re.I)
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


def parse(text):
    """Recognize a bounded inbox read. Dirty or mutating forms stay in this lane."""
    text = text.strip()
    if not text or text.lower() == 'github inbox help':
        return dict(help=True) if text.lower() == 'github inbox help' else None
    if RESERVED.search(text):
        return None
    if re.match(PREFIX + r'(?:review|push)\b', text, re.I) and not INBOX_HINT.search(text):
        return None
    match = CHAT.fullmatch(text) or GH_CMD.fullmatch(text) or INBOX.fullmatch(text)
    if match:
        repo = match['repo']
        if not valid_repo_name(repo):
            return dict(error=BAD_REPO)
        return dict(kind=normalize_kind(match.groupdict().get('kind')), repo=repo)
    if INBOX_HINT.search(text):
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
            list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        self.timeout = timeout
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
            return self.listing(spec['kind'], repo)
        except GitHubReadError as exc:
            return str(exc)

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
        text = KEY.sub('[secret removed]', text)
        return self.redact(text) if self.redact else text

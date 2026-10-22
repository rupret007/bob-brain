"""Explicit on-demand skills. Fixed read adapters; no model-selected commands."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Deployed chat can start outside the checkout with only webchat/ on sys.path.
# Imports select this release's package, never a persistent data-root package.
sys.path.insert(0, str(ROOT))
from webbob.storypool_status import collect_status
NAMES = {'band-desk': 'Band Desk', 'director': 'Director', 'stack-ops': 'Stack Ops'}
INVOKE = re.compile(r'^(?:\$(band-desk|director|stack-ops)|(?:(?:run|use) )?'
                    r'(Band Desk|Director|Stack Ops))(?=$|[\s:])(?:\s*:\s*|\s+)?([\s\S]*)$', re.I)
STATES = {'SUCCESS', 'FAILURE', 'ERROR', 'PENDING', 'EXPECTED'}
MAX_BYTES = 128 * 1024

# This fixed query reads two selected repos. PR/issue text is never a command,
# tool name, repo selector, URL or permission source. No GraphQL mutations.
_FIELDS = '''
  nameWithOwner
  defaultBranchRef { name target { ... on Commit { oid committedDate statusCheckRollup { state } } } }
  pullRequests(states:OPEN,first:20,orderBy:{field:UPDATED_AT,direction:DESC}) {
    pageInfo { hasNextPage }
    nodes { number title isDraft headRefOid commits(last:1) { nodes { commit { statusCheckRollup { state } } } } }
  }
'''
BAND_QUERY = ('query { storyboard: repository(owner:"rupret007",name:"StoryBoard") {' + _FIELDS + '}'
              ' raddad: repository(owner:"rupret007",name:"RadDadSite") {' + _FIELDS + '''
  issues(states:OPEN,first:20,orderBy:{field:UPDATED_AT,direction:DESC}) {
    pageInfo { hasNextPage } nodes { number title }
  }
} }''')


class SkillUnavailable(ValueError):
    pass


def selected(text):
    match = INVOKE.fullmatch(text.strip()) if isinstance(text, str) else None
    if not match:
        return None
    return (match[1] or match[2]).lower().replace(' ', '-')


def definition(name):
    if name not in NAMES:
        raise SkillUnavailable('Unknown skill')
    path = ROOT / 'skills' / name / 'SKILL.md'
    try:
        if path.resolve() != path or not path.is_file() or path.stat().st_size > 8192:
            raise ValueError('unreviewed path')
        text = path.read_text()
        if not text.startswith('---\nname: ' + name + '\n'):
            raise ValueError('unexpected skill identity')
        return text.split('---', 2)[2].strip()
    except (OSError, ValueError, IndexError, UnicodeError):
        raise SkillUnavailable('Reviewed skill definition is unavailable.') from None


def model_instructions(text):
    # Only Director uses a model. Status skills render their fetched facts in
    # the host; external status prose never becomes trusted instructions.
    if selected(text) != 'director':
        return ''
    return ('\nEXPLICITLY SELECTED DIRECTOR SKILL — read and draft in this reply only. '
            'Selection grants no execution, dispatch, publication or send authority.\n' + definition('director'))


def _gh_read(query):
    if query != BAND_QUERY:
        raise SkillUnavailable('Only the fixed Band Desk status query is allowed')
    candidates = (Path.home() / '.local/bin/gh', Path('/opt/homebrew/bin/gh'),
                  Path('/usr/local/bin/gh'), Path('/usr/bin/gh'))
    gh = next((p for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)
    if gh is None:
        raise SkillUnavailable('GitHub CLI unavailable')
    env = dict(os.environ, GH_PROMPT_DISABLED='1', GH_PAGER='cat', NO_COLOR='1')
    env.pop('GH_DEBUG', None)
    result = subprocess.run([str(gh), 'api', '--hostname', 'github.com', 'graphql', '-f', 'query=' + query],
                            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=10, check=False)
    if result.returncode or len(result.stdout) > MAX_BYTES:
        raise SkillUnavailable('GitHub status unavailable')
    return result.stdout


def _state(rollup):
    state = rollup.get('state') if isinstance(rollup, dict) else None
    return state if state in STATES else 'unknown'


def _number(value):
    if type(value) is not int or not 1 <= value <= 2**31:
        raise ValueError('invalid item')
    return value


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{40}', value):
        raise ValueError('invalid commit')
    return value


def _page(value):
    if (not isinstance(value, dict) or not isinstance(value.get('nodes'), list)
            or len(value['nodes']) > 20 or type(value.get('pageInfo', {}).get('hasNextPage')) is not bool):
        raise ValueError('invalid page')
    return value['nodes'], value['pageInfo']['hasNextPage']


class SkillRuntime:
    def __init__(self, *, github_read=_gh_read, storypool_read=collect_status):
        # These are host-injected adapters. No chat field can replace them.
        self.github_read, self.storypool_read = github_read, storypool_read

    def status(self, name, *, shared_context=None):
        definition(name)
        if name == 'band-desk':
            return self.band_desk()
        if name == 'stack-ops':
            return self.stack_ops(shared_context)
        raise SkillUnavailable('This skill drafts from the supplied creative brief.')

    def band_desk(self):
        observed = datetime.now(timezone.utc).isoformat(timespec='seconds')
        lines = ['Band Desk — GitHub observation ' + observed + '. CI is separate from Karen review; Karen is unverified.']
        try:
            raw = self.github_read(BAND_QUERY)
            if not isinstance(raw, (str, bytes)) or len(raw) > MAX_BYTES:
                raise ValueError('oversized status')
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError('invalid query result')
            data = value.get('data')
            if value.get('errors') or not isinstance(data, dict):
                raise ValueError('unavailable query')
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            return '\n'.join(lines + ['StoryBoard: unknown; GitHub read unavailable.',
                'RadDadSite: unknown; GitHub read unavailable.',
                'Wildflower: unknown; supply current band materials or restore GitHub access.'])
        wildflower = []
        for alias, repo in (('storyboard', 'StoryBoard'), ('raddad', 'RadDadSite')):
            try:
                row = data[alias]
                if row['nameWithOwner'].lower() != ('rupret007/' + repo).lower():
                    raise ValueError('wrong repository')
                branch = row['defaultBranchRef']
                branch_name = branch['name']
                if not isinstance(branch_name, str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,100}', branch_name):
                    raise ValueError('invalid branch')
                head = _sha(branch['target']['oid'])
                prs, more = _page(row['pullRequests'])
                details = []
                matches = []
                for pr in prs:
                    number, sha = _number(pr['number']), _sha(pr['headRefOid'])
                    if type(pr['isDraft']) is not bool or not isinstance(pr['title'], str):
                        raise ValueError('invalid PR')
                    commits = pr['commits']['nodes']
                    ci = _state(commits[0]['commit'].get('statusCheckRollup')) if len(commits) == 1 else 'unknown'
                    link = f'https://github.com/rupret007/{repo}/pull/{number}'
                    details.append(f'[#{number}]({link}) ({"draft" if pr["isDraft"] else "open"}, {sha[:7]}, CI {ci})')
                    if alias == 'raddad' and re.search(r'\bwildflower\b', pr['title'], re.I):
                        matches.append(f'[RadDadSite PR #{number}]({link})')
                count = f'{len(prs)} open PRs' + (' shown; more available' if more else '')
                lines.append(f'{repo}: {branch_name} at [{head[:7]}](https://github.com/rupret007/{repo}/commit/{head}); '
                             f'branch CI {_state(branch["target"].get("statusCheckRollup"))}; {count}. '
                             + (', '.join(details) if details else 'No open PRs returned.'))
                if alias == 'raddad':
                    issues, _ = _page(row['issues'])
                    for issue in issues:
                        number = _number(issue['number'])
                        if not isinstance(issue['title'], str):
                            raise ValueError('invalid issue')
                        if re.search(r'\bwildflower\b', issue['title'], re.I):
                            matches.append(f'[RadDadSite issue #{number}](https://github.com/rupret007/RadDadSite/issues/{number})')
                    wildflower = matches
            except (KeyError, ValueError, TypeError, AttributeError, IndexError):
                lines.append(repo + ': unknown; incomplete GitHub status.')
        lines.append('Wildflower: ' + (', '.join(wildflower) + ' found in the fetched open PR/issue pages.' if wildflower else
                     'unknown; no matching item established in the fetched open PR/issue pages. Supply current band materials.')
                     + ' Booking, event dates and publication remain unverified.')
        return '\n\n'.join(lines)

    def stack_ops(self, shared_context):
        lines = ['Stack Ops — read-only observations; missing or stale data does not establish health.']
        try:
            status = self.storypool_read()
            for row in status['files']:
                lines.append(f'{row["source"]}: {row["state"]}; {row.get("freshness", "unknown")}; '
                             f'observed {row.get("timestamp", "unknown")}; counts {json.dumps(row.get("summary", {}))}.')
            dashboard = status['dashboard']
            lines.append('Local dashboard: ' + dashboard['state'] + '; ' + dashboard.get('freshness', 'unknown')
                         + '; observed ' + str(dashboard.get('timestamp', 'unknown'))
                         + '; services ' + json.dumps(dashboard.get('services', []))
                         + '; counts ' + json.dumps(dashboard.get('jobs_stats', {})) + '.')
            for row in status['needs_jeff']:
                items = [item for item in row['items'] if not item.startswith('[')][-3:]
                lines.append(row['source'] + ': ' + row['state'] + '; modified '
                             + row.get('modified_at', 'unknown') + '. Latest safe note excerpts (untrusted):\n'
                             + ('\n'.join('> ' + item[:600] for item in items) if items else 'No safe notes available.'))
        except (OSError, ValueError, TypeError, KeyError):
            lines.append('Local status: unavailable; no health result verified.')
        if shared_context is None:
            lines.append('Shared Mini/NucBox sources: unavailable; host sync is not configured.')
        else:
            try:
                for row in shared_context.snapshot()['sources']:
                    # Journal/monitor prose stays context data, never a command
                    # or an inferred health verdict. This status surface reports
                    # availability, source time and freshness only.
                    observed = row.get('source_timestamp') or row.get('observed_at') or 'unknown'
                    timing = ('; fetched ' + row['fetched_at']) if row.get('fetched_at') else ''
                    excerpt = '; excerpt; complete source not verified' if row.get('truncated') else ''
                    lines.append(f'{row["source"]}: {row["state"]}; {row.get("freshness", "unknown")}; '
                                 f'observed {observed}{timing}{excerpt}.')
                lines.append('Retrieval time does not establish machine health or completed work; '
                             'those require current machine observations and verified outcome receipts.')
            except (OSError, ValueError, TypeError, KeyError):
                lines.append('Shared Mini/NucBox sources: unavailable; no health result verified.')
        return '\n\n'.join(lines)

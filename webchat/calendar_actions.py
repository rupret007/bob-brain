"""Direct Google Calendar actions: private durable consent, no invites or retries.

The HTTP boundary is injectable. Merely constructing this module never contacts
Google; credentials are read only for a recognized calendar request.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from failover import atomic_text
from reminders import CLOCK, WHEN, ZONE, instant, stamp

NEEDS_AUTH = ('Google Calendar needs auth. Configure a private authorized-user OAuth JSON file '
              'with Calendar access using BOB_GOOGLE_CALENDAR_CREDENTIALS '
              '(or ~/.config/webbob/google-calendar.json). No calendar action was performed.')
HELP = ('Try “create a calendar event Dentist tomorrow at 2pm for 30 minutes”, '
        '“create a calendar event for 2am to go to bed”, or “show my calendar today”. '
        'Default: primary calendar, America/Chicago, one hour, no recurrence, invitations, or event alerts. '
        'Creation requires the draft’s exact yes wbcal-… message.')
UNCERTAIN = ('Calendar creation is unconfirmed. Check Google Calendar before making another draft. '
             'This confirmation will not submit another create request.')
PREFIX = r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
CREATE = re.compile(PREFIX + r'(?:create|add|set(?:\s+up)?|schedule)\s+(?:an?\s+)?(?:google\s+)?calendar\s+event\b\s*(.*)$', re.I | re.S)
READ = re.compile(PREFIX + r'(?:(?:read|show|list)\s+|what(?:\x27s| is) on\s+)?(?:my\s+)?(?:google\s+)?calendar(?:\s+events)?(?:\s+(today|tomorrow|this week|next 7 days|on \d{4}-\d{2}-\d{2}))?[.?!]?$', re.I)
CONTROL = re.compile(r'^(yes|cancel)\s+(wbcal-[a-f0-9]{32})$', re.I)


class CalendarError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise CalendarError('Google Calendar redirected the request; its result is unconfirmed.')


def request_json(url, *, data=None, headers=None, form=False):
    """Fixed Google hosts, no proxies, redirects or automatic retries."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc not in ('oauth2.googleapis.com', 'www.googleapis.com'):
        raise CalendarError('Invalid Calendar endpoint.')
    body = (urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
    request = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json', **(headers or {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('large response')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError('invalid response')
        return result
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403) or form and exc.code == 400:
            raise CalendarError('Google Calendar needs auth: authorization expired or Calendar access was denied.') from None
        raise CalendarError('Google Calendar rejected the request; no success was verified.') from None
    except (OSError, ValueError, UnicodeError):
        raise CalendarError('Google Calendar is unavailable or returned invalid data; no success was verified.') from None


class GoogleCalendar:
    def __init__(self, credentials=None, transport=None):
        self.credentials = credentials
        self.transport = transport or request_json

    def configured(self):
        self._credentials()

    def _credentials(self):
        configured = self.credentials or os.environ.get('BOB_GOOGLE_CALENDAR_CREDENTIALS')
        candidates = [Path(configured).expanduser()] if configured else [
            Path.home() / '.config/webbob/google-calendar.json',
            Path.home() / '.config/gcloud/application_default_credentials.json']
        path = next((p for p in candidates if p.exists() or p.is_symlink()), candidates[0])
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd) as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 24000:
                    raise ValueError('private credentials required')
                value = json.load(handle)
            if not isinstance(value, dict) or value.get('type', 'authorized_user') != 'authorized_user':
                raise ValueError('authorized user required')
            if any(not isinstance(value.get(k), str) or not value[k].strip() for k in ('client_id', 'client_secret', 'refresh_token')):
                raise ValueError('missing OAuth credentials')
            return value
        except (OSError, ValueError, UnicodeError):
            raise CalendarError(NEEDS_AUTH) from None

    def _headers(self):
        cfg = self._credentials()
        token = self.transport('https://oauth2.googleapis.com/token', form=True,
                               data={k: cfg[k] for k in ('client_id', 'client_secret', 'refresh_token')} |
                               {'grant_type': 'refresh_token'})
        access = token.get('access_token')
        if not isinstance(access, str) or not access or any(c.isspace() for c in access):
            raise CalendarError('Google Calendar needs auth: OAuth did not return an access token.')
        return {'Authorization': 'Bearer ' + access}

    def create(self, event):
        return self.transport('https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=none',
                              data=event, headers=self._headers())

    def listing(self, start, end):
        query = urllib.parse.urlencode(dict(timeMin=start, timeMax=end, singleEvents='true',
                                           orderBy='startTime', maxResults=100, timeZone='America/Chicago'))
        return self.transport('https://www.googleapis.com/calendar/v3/calendars/primary/events?' + query,
                              headers=self._headers())


def iso(seconds):
    return datetime.fromtimestamp(seconds, ZONE).isoformat()


def event_spec(text, now):
    clause = CREATE.fullmatch(text.strip())[1].strip().rstrip('.?!')
    duration = 3600
    length = re.search(r'\s+for\s+(\d+)\s+(minutes?|hours?)$', clause, re.I)
    if length:
        duration = int(length[1]) * (60 if length[2].lower().startswith('minute') else 3600)
        clause = clause[:length.start()]
    if not 60 <= duration <= 86400:
        raise CalendarError('Choose an event duration between 1 minute and 24 hours.')
    match = re.fullmatch(r'(?:for\s+)?(' + WHEN + r')\s+(?:to|for)\s+(.+)', clause, re.I | re.S)
    if match:
        when, title = match[1], match[2]
    else:
        match = re.fullmatch(r'(.+?)\s+(' + WHEN + r')', clause, re.I | re.S)
        if not match:
            raise CalendarError('I need an event title and a clear date/time. ' + HELP)
        title, when = match[1], match[2]
    title = title.strip()
    quoted_title = len(title) >= 2 and title.startswith('"') and title.endswith('"')
    if not quoted_title and re.search(
            r'\b(?:today|tomorrow|tonight|yesterday|morning|afternoon|evening|noon|midnight|'
            r'monday|tuesday|wednesday|thursday|friday|saturday|sunday|UTC|GMT|CST|CDT|EST|EDT|PST|PDT)\b|'
            r'\b(?:next|this)\s+(?:week|month|year|day)\b|\b\d{4}-\d{2}-\d{2}\b|'
            r'\b\d{1,2}/\d{1,2}\b|\b(?:on|at)\s+\d|\bfor\s+\d+\s+(?:minutes?|hours?)\b|'
            r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d|'
            r'\b' + CLOCK + r'\b', title, re.I):
        raise CalendarError('I could not resolve the full event time. Use a clear date/time; '
                            'put a title containing time or date words in double quotes. ' + HELP)
    title = title[1:-1] if quoted_title else title
    if not 1 <= len(title) <= 500:
        raise CalendarError('Keep the event title between 1 and 500 characters.')
    # Extra scheduling clauses must never quietly become a different schedule.
    if re.search(r'\b(?:every|recurring|repeat|invite|attendees?|send|email)\b', clause, re.I):
        raise CalendarError('This Calendar action supports a single private event only. No invitations were sent. ' + HELP)
    try:
        due = instant(when, now)
    except ValueError as exc:
        raise CalendarError('Calendar time needs clarification: ' + str(exc)) from None
    return dict(summary=title, start={'dateTime': iso(due), 'timeZone': 'America/Chicago'},
                end={'dateTime': iso(due + duration), 'timeZone': 'America/Chicago'},
                reminders={'useDefault': False}, visibility='private')


def verified(result, event):
    if not isinstance(result, dict) or result.get('id') != event['id'] or result.get('status') != 'confirmed':
        return False
    try:
        return (result.get('summary') == event['summary'] and not result.get('attendees') and
                all(datetime.fromisoformat(result[key]['dateTime'].replace('Z', '+00:00')) ==
                    datetime.fromisoformat(event[key]['dateTime']) for key in ('start', 'end')))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


class CalendarActions:
    def __init__(self, folder, client=None, clock=time.time):
        self.folder = Path(folder) / 'calendar'
        self.client = client if client is not None else GoogleCalendar()
        self.clock = clock

    @contextmanager
    def locked(self):
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.folder.is_symlink():
            raise CalendarError('Calendar storage must be a private directory.')
        self.folder.chmod(0o700)
        path = self.folder / 'receipts.json'
        fd = os.open(self.folder / 'receipts.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'r+') as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise CalendarError('Calendar storage must use regular files.')
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if path.is_symlink() or path.exists() and (not path.is_file() or path.stat().st_size > 2 * 1024 * 1024):
                    raise CalendarError('Calendar storage needs repair; no request submitted.')
                rows = json.loads(path.read_text()) if path.exists() else {}
                if not isinstance(rows, dict):
                    raise CalendarError('Calendar storage needs repair; no request submitted.')
                yield rows
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save(self, rows):
        atomic_text(self.folder / 'receipts.json', json.dumps(rows, ensure_ascii=False))

    def matches(self, text):
        text = text.strip()
        return bool(CREATE.fullmatch(text) or READ.fullmatch(text) or
                    re.match(r'^(?:yes|cancel)\s+wbcal-', text, re.I) or text.lower() == 'calendar help')

    def handle(self, text, cid, request_id, intent_state):
        if not self.matches(text):
            return None
        import chat_intent
        try:
            control = CONTROL.fullmatch(text.strip())
            if control:
                return self.control(control[1].lower(), control[2].lower(), cid, request_id, intent_state)
            if re.match(r'^(?:yes|cancel)\s+wbcal-', text, re.I):
                return 'Use the exact yes wbcal-… or cancel wbcal-… message from the draft. Nothing created.'
            if text.lower() == 'calendar help':
                return HELP
            if CREATE.fullmatch(text):
                scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text))
                if scopes:
                    return chat_intent.hold_reply(scopes)
                return self.draft(text, cid, request_id)
            return self.read(READ.fullmatch(text)[1])
        except CalendarError as exc:
            return str(exc)
        except (OSError, ValueError, TypeError, KeyError):
            return 'Calendar request could not finish. If you approved a draft, ' + UNCERTAIN

    def draft(self, text, cid, request_id):
        # Retry identity precedes time parsing: a retry must not roll to tomorrow.
        with self.locked() as rows:
            old = next((r for r in rows.values() if r['cid'] == cid and r['request_id'] == request_id), None)
            if old:
                if old['text'] != text:
                    return 'That calendar request ID belongs to a different draft. Nothing created.'
                return self.receipt(old)
            event = event_spec(text, self.clock())
            self.client.configured()  # Local credential check only; no OAuth/network yet.
            if len(rows) >= 1000:
                raise CalendarError('Calendar receipt storage is full. Nothing created.')
            token = 'wbcal-' + uuid.uuid4().hex
            event['id'] = hashlib.sha256(token.encode()).hexdigest()
            for row in rows.values():
                if row['cid'] == cid and row['state'] == 'draft':
                    row['state'] = 'replaced'
            row = dict(cid=cid, request_id=request_id, text=text, event=event, token=token,
                       state='draft', expires=self.clock() + 3600)
            rows[token] = row
            self.save(rows)
            return self.receipt(row)

    @staticmethod
    def receipt(row):
        if row['state'] == 'created':
            return row['receipt']
        if row['state'] in ('claimed', 'unconfirmed'):
            return (row.get('error', '') + ' ' + UNCERTAIN).strip()
        if row['state'] != 'draft':
            return 'That calendar draft was cancelled, replaced, or expired. Nothing created by this request.'
        event = row['event']
        return (f'Calendar draft (not created): {event["summary"]}. '
                f'{stamp(datetime.fromisoformat(event["start"]["dateTime"]).timestamp())} to '
                f'{stamp(datetime.fromisoformat(event["end"]["dateTime"]).timestamp())}. '
                f'Primary calendar; America/Chicago; no invitations or event alerts. '
                f'Within one hour reply exactly “yes {row["token"]}” to create, or “cancel {row["token"]}”.')

    def control(self, command, token, cid, request_id, intent_state):
        import chat_intent
        with self.locked() as rows:
            row = rows.get(token)
            if not row or row['cid'] != cid:
                return 'No matching calendar draft in this conversation. Nothing created.'
            if row['state'] != 'draft':
                return self.receipt(row)
            if command == 'cancel':
                row['state'] = 'cancelled'
                self.save(rows)
                return 'Calendar draft cancelled. Nothing created.'
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(row['text']))
            if scopes:
                return chat_intent.hold_reply(scopes)
            if request_id == row['request_id']:
                return 'Review the calendar draft and confirm in a separate message. Nothing created.'
            if self.clock() >= row['expires'] or datetime.fromisoformat(row['event']['start']['dateTime']).timestamp() <= self.clock():
                row['state'] = 'expired'
                self.save(rows)
                return 'Calendar draft expired. Make a fresh draft. Nothing created.'
            self.client.configured()
            row.update(state='claimed', approved_request_id=request_id)
            self.save(rows)  # Persist consumed consent BEFORE any OAuth or create call.
            try:
                result = self.client.create(row['event'])
                if verified(result, row['event']):
                    row.update(state='created', receipt=f'Google Calendar confirmed event created: {row["event"]["summary"]}. '
                               f'{row["event"]["start"]["dateTime"]} to {row["event"]["end"]["dateTime"]} '
                               f'(America/Chicago). Event ID: {result["id"]}. No invitations requested.')
                else:
                    row['state'] = 'unconfirmed'
            except CalendarError as exc:
                row.update(state='unconfirmed', error=str(exc))
            except Exception:
                row['state'] = 'unconfirmed'
            self.save(rows)
            return self.receipt(row)

    def read(self, period):
        self.client.configured()
        now = datetime.fromtimestamp(self.clock(), ZONE)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period = (period or 'next 7 days').lower()
        if period == 'tomorrow':
            start += timedelta(days=1)
        elif period.startswith('on '):
            try:
                start = datetime.strptime(period[3:], '%Y-%m-%d').replace(tzinfo=ZONE)
            except ValueError:
                raise CalendarError('Choose a valid calendar date in YYYY-MM-DD format.') from None
        end = start + timedelta(days=7 if period in ('this week', 'next 7 days') else 1)
        if period == 'this week':
            start -= timedelta(days=start.weekday())
            end = start + timedelta(days=7)
        result = self.client.listing(start.isoformat(), end.isoformat())
        items = result.get('items')
        if not isinstance(items, list) or len(items) > 100:
            raise CalendarError('Google Calendar returned invalid event data; no listing was verified.')
        lines = []
        try:
            for item in items:
                if item.get('status') == 'cancelled':
                    continue
                title = item.get('summary') or '(untitled event)'
                if not isinstance(title, str):
                    raise ValueError('invalid title')
                date = item['start']
                if 'dateTime' in date:
                    parsed = datetime.fromisoformat(date['dateTime'].replace('Z', '+00:00'))
                    if parsed.tzinfo is None:
                        raise ValueError('missing offset')
                    when = stamp(parsed.timestamp())
                else:
                    when = datetime.strptime(date['date'], '%Y-%m-%d').strftime('%b %d, %Y') + ' (all day)'
                lines.append(f'• {when}: {title[:500]}')
        except (KeyError, TypeError, ValueError, AttributeError):
            raise CalendarError('Google Calendar returned invalid event data; no listing was verified.') from None
        heading = f'Google Calendar, primary: {start.date()} through {end.date()} (end exclusive), America/Chicago.'
        return heading + '\n' + ('\n'.join(lines) if lines else 'No events returned for this window.') + (
            '\nMore events exist; showing the first page (up to 100).' if result.get('nextPageToken') else '')

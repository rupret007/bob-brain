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
        '“create a calendar event for 2am to go to bed”, “show my calendar today”, '
        'or “cancel calendar event EVENT_ID”. '
        'Default: primary calendar, America/Chicago, one hour, no recurrence, invitations, or event alerts. '
        'Creation and cancellation require that draft’s exact yes wbcal-… message. '
        'Only one non-recurring, attendee-free event can be cancelled.')
UNCERTAIN = ('Calendar creation is unconfirmed. Check Google Calendar before making another draft. '
             'This confirmation will not submit another create request.')
UNCERTAIN_CANCEL = ('Calendar cancellation is unconfirmed. Check Google Calendar before making another request. '
                    'This confirmation will not submit another cancel request.')
PREFIX = r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
CREATE = re.compile(PREFIX + r'(?:create|add|set(?:\s+up)?|schedule)\s+(?:an?\s+)?(?:google\s+)?calendar\s+event\b\s*(.*)$', re.I | re.S)
READ = re.compile(PREFIX + r'(?:(?:read|show|list)\s+|what(?:\x27s| is) on\s+)?(?:my\s+)?(?:google\s+)?calendar(?:\s+events)?(?:\s+(today|tomorrow|this week|next 7 days|on \d{4}-\d{2}-\d{2}))?[.?!]?$', re.I)
CANCEL_EVENT = re.compile(
    PREFIX + r'(?:cancel|delete|remove)\s+(?:the\s+)?(?:google\s+)?calendar\s+event\b\s+'
    r'([A-Za-z0-9_=.-]{5,1024})\s*$', re.I)
CONTROL = re.compile(r'^(yes|cancel)\s+(wbcal-[a-f0-9]{32})$', re.I)


class CalendarError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise CalendarError('Google Calendar redirected the request; its result is unconfirmed.')


def request_json(url, *, data=None, headers=None, form=False, method=None, allow_missing=False):
    """Fixed Google hosts, no proxies, redirects or automatic retries."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc not in ('oauth2.googleapis.com', 'www.googleapis.com'):
        raise CalendarError('Invalid Calendar endpoint.')
    body = (urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json', **(headers or {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('large response')
        if not raw:
            return {}
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError('invalid response')
        return result
    except urllib.error.HTTPError as exc:
        if allow_missing and exc.code in (404, 410):
            return None
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

    def event_url(self, event_id, *, query=''):
        ident = urllib.parse.quote(event_id, safe='')
        url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events/' + ident
        return url + query

    def get(self, event_id, *, allow_missing=False):
        result = self.transport(self.event_url(event_id), headers=self._headers(), allow_missing=True)
        if result is None:
            if allow_missing:
                return None
            raise CalendarError('No matching calendar event was found. Nothing was cancelled.')
        return result

    def delete(self, event_id):
        return self.transport(self.event_url(event_id, query='?sendUpdates=none'),
                              method='DELETE', headers=self._headers())


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


def observed_version(item):
    if not isinstance(item, dict):
        return None
    etag = item.get('etag') if isinstance(item.get('etag'), str) else ''
    updated = item.get('updated') if isinstance(item.get('updated'), str) else ''
    if not etag.strip() and not updated.strip():
        return None
    return dict(etag=etag.strip(), updated=updated.strip())


def versions_match(stored, current):
    if not isinstance(stored, dict) or not isinstance(current, dict):
        return False
    if stored.get('etag') and current.get('etag'):
        return stored['etag'] == current['etag']
    if stored.get('updated') and current.get('updated'):
        return stored['updated'] == current['updated']
    return False


def simple_cancel_refusal(item):
    if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip():
        return 'Google Calendar returned invalid event data; nothing was cancelled.'
    if item.get('status') == 'cancelled':
        return 'That calendar event is already cancelled. Nothing was changed.'
    attendees = item.get('attendees')
    if isinstance(attendees, list) and attendees:
        return 'This Calendar action cancels one private event only. Events with attendees were not changed.'
    if item.get('recurrence') or item.get('recurringEventId'):
        return 'This Calendar action cancels one non-recurring event only. Recurring series were not changed.'
    if observed_version(item) is None:
        return 'That calendar event has no observed version. Nothing was cancelled.'
    return None


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
        return bool(CREATE.fullmatch(text) or READ.fullmatch(text) or CANCEL_EVENT.fullmatch(text) or
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
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text))
            if scopes:
                return chat_intent.hold_reply(scopes)
            if CREATE.fullmatch(text):
                return self.draft(text, cid, request_id)
            cancel = CANCEL_EVENT.fullmatch(text)
            if cancel:
                return self.draft_cancel(text, cancel[1], cid, request_id)
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

    def draft_cancel(self, text, event_id, cid, request_id):
        with self.locked() as rows:
            old = next((r for r in rows.values() if r['cid'] == cid and r['request_id'] == request_id), None)
            if old:
                if old.get('text') != text or old.get('kind') != 'cancel':
                    return 'That calendar request ID belongs to a different draft. Nothing was cancelled.'
                return self.receipt(old)
            self.client.configured()
            item = self.client.get(event_id)
            if item.get('id') != event_id:
                raise CalendarError('Google Calendar returned a different event; nothing was cancelled.')
            refusal = simple_cancel_refusal(item)
            if refusal:
                raise CalendarError(refusal)
            if len(rows) >= 1000:
                raise CalendarError('Calendar receipt storage is full. Nothing was cancelled.')
            token = 'wbcal-' + uuid.uuid4().hex
            for row in rows.values():
                if row['cid'] == cid and row['state'] == 'draft':
                    row['state'] = 'replaced'
            row = dict(cid=cid, request_id=request_id, text=text, kind='cancel', token=token,
                       event_id=event_id, version=observed_version(item), preview=item,
                       state='draft', expires=self.clock() + 3600)
            rows[token] = row
            self.save(rows)
            return self.receipt(row)

    @staticmethod
    def receipt(row):
        if row['state'] in ('created', 'deleted'):
            return row['receipt']
        uncertain = UNCERTAIN_CANCEL if row.get('kind') == 'cancel' else UNCERTAIN
        if row['state'] in ('claimed', 'unconfirmed'):
            return (row.get('error', '') + ' ' + uncertain).strip()
        if row['state'] != 'draft':
            if row.get('kind') == 'cancel':
                return 'That calendar cancel draft was cancelled, replaced, or expired. Nothing was cancelled by this request.'
            return 'That calendar draft was cancelled, replaced, or expired. Nothing created by this request.'
        if row.get('kind') == 'cancel':
            item = row.get('preview') or {}
            title = item.get('summary') if isinstance(item.get('summary'), str) and item['summary'] else '(untitled event)'
            version = row.get('version') or {}
            mark = version.get('etag') or version.get('updated') or 'unknown'
            return (f'Calendar cancel draft (not cancelled): {title[:500]}. '
                    f'Event ID: {row["event_id"]}. Observed version: {mark}. '
                    f'Primary calendar; one non-recurring private event; no attendees. '
                    f'Within one hour reply exactly “yes {row["token"]}” to cancel, or “cancel {row["token"]}”.')
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
                if row and row.get('kind') == 'cancel':
                    return 'No matching calendar cancel draft in this conversation. Nothing was cancelled.'
                return 'No matching calendar draft in this conversation. Nothing created.'
            if row['state'] != 'draft':
                return self.receipt(row)
            if command == 'cancel':
                row['state'] = 'cancelled'
                self.save(rows)
                if row.get('kind') == 'cancel':
                    return 'Calendar cancel draft dismissed. Nothing was cancelled.'
                return 'Calendar draft cancelled. Nothing created.'
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(row['text']))
            if scopes:
                return chat_intent.hold_reply(scopes)
            if request_id == row['request_id']:
                if row.get('kind') == 'cancel':
                    return 'Review the calendar cancel draft and confirm in a separate message. Nothing was cancelled.'
                return 'Review the calendar draft and confirm in a separate message. Nothing created.'
            expired = self.clock() >= row['expires']
            if row.get('kind') != 'cancel':
                expired = expired or datetime.fromisoformat(row['event']['start']['dateTime']).timestamp() <= self.clock()
            if expired:
                row['state'] = 'expired'
                self.save(rows)
                if row.get('kind') == 'cancel':
                    return 'Calendar cancel draft expired. Make a fresh cancel request. Nothing was cancelled.'
                return 'Calendar draft expired. Make a fresh draft. Nothing created.'
            self.client.configured()
            row.update(state='claimed', approved_request_id=request_id)
            self.save(rows)  # Persist consumed consent BEFORE any OAuth or write.
            if row.get('kind') == 'cancel':
                return self.finish_cancel(rows, row)
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

    def finish_cancel(self, rows, row):
        try:
            current = self.client.get(row['event_id'])
            refusal = simple_cancel_refusal(current)
            if refusal:
                row.update(state='unconfirmed', error=refusal)
            elif current.get('id') != row['event_id'] or not versions_match(row.get('version'), observed_version(current)):
                row.update(state='unconfirmed',
                           error='That calendar event changed since the draft. Nothing was cancelled.')
            else:
                self.client.delete(row['event_id'])
                observed = self.client.get(row['event_id'], allow_missing=True)
                if observed is None or observed.get('status') == 'cancelled':
                    title = row.get('preview', {}).get('summary') if isinstance(row.get('preview'), dict) else ''
                    title = title if isinstance(title, str) and title.strip() else '(untitled event)'
                    row.update(state='deleted',
                               receipt=f'Google Calendar confirmed event cancelled: {title[:500]}. '
                                       f'Event ID: {row["event_id"]}.')
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

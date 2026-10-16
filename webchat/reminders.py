"""Private, durable chat reminders with best-effort local macOS notifications."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from zoneinfo import ZoneInfo

from failover import atomic_text
from actions_intent import reminder_request, routine_request, routine_intent
from approval_language import approval_requested, leading_approval_request
import chat_intent

ZONE = ZoneInfo('America/Chicago')
HELP = ('Try “remind me to check the oven in 10 minutes”, “remind me to call Sam on 2026-10-01 at 14:00”, '
        '“remind me every 2 hours to stretch”, “my reminders”, or “cancel reminder ID”. '
        'You can also say “create a reminder for 2am to go to bed” or “set a timer for 10 minutes”. '
        'Explicit “remind me to … in …” and “remind me every …” interval requests save personal reminders directly. '
        'Other valid requests produce a draft; confirm its exact token in a separate message to schedule it. '
        'Times use America/Chicago; a clock time without a date means its next occurrence. '
        'Reminders appear here and in Jobs while Web Bob is running; overdue reminders arrive when it returns. '
        'Local macOS notifications require owner opt-in and notification permission. '
        'Reminders never send texts or emails or start work.')
ROUTINE_HELP = ('Try “every morning do read file ~/Documents/notes.txt”, '
                '“every morning at 8am do search the web for Chicago weather”, or '
                '“every morning remind me to stretch”. Morning defaults to 9am America/Chicago. '
                'Read-only routines run in this chat while Web Bob is running; one overdue run catches up after restart. '
                'Use “my routines” and “cancel routine ID”. Writes, deletes and sends cannot run unattended.')
UNITS = {'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400}
DURATION = r'\d+\s+(?:seconds?|minutes?|hours?|days?)'
# "Confirm when unsure" (Jeff, 2026-10-15): a direct interval reminder saves
# immediately only when the whole request is plain ASCII and the reminder body
# is ASCII letters/digits separated by single spaces, contains no
# single-letter runs (spelled-out words) and no action/approval/prohibition
# word. Everything else goes to the exact-token confirmation draft.
_PLAIN_BODY = re.compile(r'[A-Za-z0-9]+(?: [A-Za-z0-9]+)*')
_PLAIN_REQUEST = re.compile(r'[A-Za-z0-9 :]+[.!?]?')
# Joined words ("reviewfirst", "pleaseapprove") still carry these roots.
_CONTROL_ROOTS = re.compile(r'schedul|approv|consent|confirm|permi|draft|preview|review|proofread|prohibit|forbid|'
                            r'disabl|authori|signoff|beforehand|condition|contingent|hypothetic|simulat|execut|decid|'
                            r'agree|concur|suppos|provid|unless|greenlight|goahead|sav(?:e|ing)|creat|disallow|barred|suspend|later|'
                            r'nix|veto|embargo|freez|frozen|withh[oe]ld|postpon|deferr|delay|halt|block|forbid|ban(?:ned|s)?\\b|'
                            r'alert|notif|timer|setting|allow|permit|restrict|prevent|cancel|abort|revok|rescind', re.I)
_CONTROL_WORDS = re.compile(
    r'(?:schedul|approv|approval|consent|confirm|agree|concur|permi|permission|allow|authori|'
    r'draft|preview|review|proofread|check|verify|sign|signoff|signal|green|light|ok|okay|yes|'
    r'go|ahead|wait|hold|pause|defer|pend|later|until|unless|after|before|beforehand|first|once|'
    r'when|if|provid|suppos|should|assum|condition|contingent|depend|only|just|not|no|never|dont|'
    r'don|stop|halt|cancel|disabl|prohibit|forbid|forbidden|ban|block|deny|denied|refus|reject|veto|'
    r'avoid|skip|without|test|dry|simulat|pretend|hypothetic|maybe|perhaps|might|may|decid|'
    r'decision|think|ask|let|show|see|look|act|execut|run|send|text|email|call|follow)\w*', re.I)


_WORDLIST_PATH = Path(__file__).resolve().parent / 'data' / 'scowl-en-50.txt'


def _load_words():
    # Pinned in-repo SCOWL list (see data/README-wordlist.md). A missing or
    # unreadable list fails closed: no reminder saves instantly.
    try:
        return frozenset(_WORDLIST_PATH.read_text(encoding='ascii').split())
    except (OSError, UnicodeError):
        return frozenset()


_DICTIONARY = _load_words()
_TIME_UNITS = frozenset(('second', 'seconds', 'minute', 'minutes', 'min', 'mins',
                         'hour', 'hours', 'hr', 'hrs', 'day', 'days'))


def _dictionary_token(word):
    word = word.lower()
    if any(char.isdigit() for char in word) or word in _TIME_UNITS:
        return True  # numbers, IDs and time units
    if word in _DICTIONARY:
        return True
    for suffix in ('es', 's', 'ed', 'ing', 'd'):
        stem = word[:-len(suffix)]
        if word.endswith(suffix) and len(stem) >= 3 and (
                stem in _DICTIONARY or stem + 'e' in _DICTIONARY or
                (len(stem) > 3 and stem[-1] == stem[-2] and stem[:-1] in _DICTIONARY)):
            return True
    return False


def plain_interval_reminder(text, body):
    text = text.strip()
    if not (text.isascii() and _PLAIN_REQUEST.fullmatch(text) and _PLAIN_BODY.fullmatch(body.strip())):
        return False
    words = body.split()
    if any(len(word) == 1 and word.lower() not in ('a',) for word in words):
        return False
    if not all(_dictionary_token(word) for word in words):
        return False
    return not any(_CONTROL_WORDS.fullmatch(word) or _CONTROL_ROOTS.search(word) for word in words)


PERSONAL_INTERVAL_REQUEST = re.compile(
    r'^(?:please\s+)*remind me (?:to [\s\S]+? in \d+\s+'
    r'(?:seconds?|minutes?|mins?|hours?|hrs?|days?)|'
    r'every \d+\s+(?:minutes?|hours?|days?) to [\s\S]+?)[.!?]*$', re.I)
CLOCK = r'\d{1,2}(?::\d{2}\s*(?:am|pm)?|\s*(?:am|pm))'
WHEN = (r'(?:(?:in\s+)?' + DURATION + r'|(?:on\s+)?(?:\d{4}-\d{2}-\d{2}|today|tomorrow)'
        r'(?:\s+at)?\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|'
        r'(?:at\s+)?\d{4}-\d{2}-\d{2}t\S+|(?:at\s+)?' + CLOCK + r')')
TIMEZONE = re.compile(r'\b(?:UTC|GMT|[ECMP][SD]T|'
                      r'(?:America|Europe|Asia|Africa|Australia|Pacific|Atlantic|Indian|Etc)/[\w/+-]+|'
                      r'(?:eastern|central|mountain|pacific)\s+(?:(?:standard|daylight)\s+)?time)\b', re.I)


def notify_macos(body):
    """Submit an OS alert, without shell/source interpolation or a display claim."""
    if sys.platform != 'darwin':
        return False
    script = 'on run argv\n display notification (item 1 of argv) with title "Web Bob reminder"\nend run'
    try:
        result = subprocess.run(['/usr/bin/osascript', '-e', script, '--', body],
                                capture_output=True, timeout=3, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class ReminderError(ValueError):
    pass


class ExtractionNeeded(Exception):
    """Ask the normal, budgeted reply worker for extraction, never execution."""


WEEKDAYS = 'monday tuesday wednesday thursday friday saturday sunday'.split()
WEEKDAY = '|'.join(WEEKDAYS)


def natural_request(text, now):
    """Normalize only resolved schedule syntax; the consent guard still scans it."""
    request = reminder_request(text)
    if not request:
        return text, None, ''
    clause = request['clause']
    clause = re.sub(r'\b(\d+)\s+(mins?|hrs?)\b',
                    lambda m: m[1] + (' minutes' if m[2].lower().startswith('min') else ' hours'), clause, flags=re.I)
    assumption = ''
    clause, count = re.subn(r'\b((?:today|tomorrow) at \d{1,2})(?=\s+to\b|$)', r'\1am', clause, flags=re.I)
    if count:
        assumption = 'Assuming AM for the clock time. '
    weekly = re.fullmatch(r'(every |(?:on )?)(' + WEEKDAY + r')(?:\s+at)?\s+(night|\d{1,2}(?::\d{2})?\s*(?:am|pm)?) to (.+)', clause, re.I)
    recurrence = None
    if weekly:
        clock = weekly[3].lower()
        if clock == 'night':
            return 'remind me ' + clause, None, ''
        elif re.fullmatch(r'\d{1,2}', clock):
            clock += 'am'
            assumption = 'Assuming AM for the clock time. '
        local = datetime.fromtimestamp(now, ZONE)
        date = local.date() + timedelta(days=(WEEKDAYS.index(weekly[2].lower()) - local.weekday()) % 7)
        if date == local.date():
            try:
                instant(f'{date} at {clock}', now)
            except ReminderError as exc:
                if 'already passed' not in str(exc):
                    raise
                date += timedelta(days=7)
        clause = f'on {date} at {clock} to {weekly[4]}'
        if weekly[1].lower() == 'every ':
            recurrence = dict(day=WEEKDAYS.index(weekly[2].lower()), clock=clock)
    return ('remind me ' if request['kind'] == 'reminder' else 'set a ' + request['kind'] + ' ') + clause, recurrence, assumption


def next_weekday(now, schedule):
    local = datetime.fromtimestamp(now, ZONE)
    date = local.date() + timedelta(days=(schedule['day'] - local.weekday()) % 7)
    try:
        return instant(f"{date} at {schedule['clock']}", now)
    except ReminderError as exc:
        if 'already passed' not in str(exc):
            raise
        return instant(f"{date + timedelta(days=7)} at {schedule['clock']}", now)


def extraction_prompt(text):
    return ('Extract a reminder request as JSON only: {"body": string|null, "when": string|null}. '
            'Copy body and when verbatim from the request. Do not invent dates, event times, '
            'offsets, or facts. Null for missing fields. This is extraction for a draft, '
            'never permission to schedule or execute. Request: ' + json.dumps(text))


def instant(text, now):
    """Small explicit grammar; never invent a date for an ambiguous request."""
    value = text.strip().casefold()
    relative = re.fullmatch(r'in (\d+) (seconds?|minutes?|hours?|days?)', value)
    if relative:
        seconds = int(relative[1]) * UNITS[relative[2].rstrip('s')]
        if not 1 <= seconds <= 366 * 86400:
            raise ReminderError('Choose a delay between 1 second and 366 days.')
        return now + seconds
    local_now = datetime.fromtimestamp(now, ZONE)
    clock = re.fullmatch(r'(?:at\s+)?(' + CLOCK + r')', value)
    if clock:
        # Resolve the next local occurrence explicitly; DST gaps/folds still
        # fail closed below, and explicit dates never silently roll forward.
        clock_parts = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', clock[1])
        hour, minute = int(clock_parts[1]), int(clock_parts[2] or 0)
        if clock_parts[3]:
            if not 1 <= hour <= 12:
                raise ReminderError('Use an hour from 1 to 12 with am or pm.')
            hour = hour % 12 + (12 if clock_parts[3] == 'pm' else 0)
        candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        date = (local_now + timedelta(days=1)).date() if candidate <= local_now else local_now.date()
        value = f'{date.isoformat()} at {hour:02d}:{minute:02d}'
    day = re.fullmatch(r'(?:on )?(\d{4}-\d{2}-\d{2}|today|tomorrow)(?: at)? (\d{1,2})(?::(\d{2}))?\s*(am|pm)?', value)
    if day:
        date = (local_now + timedelta(days=1 if day[1] == 'tomorrow' else 0)).date() if day[1] in ('today', 'tomorrow') else datetime.strptime(day[1], '%Y-%m-%d').date()
        hour, minute = int(day[2]), int(day[3] or 0)
        if day[4]:
            if not 1 <= hour <= 12:
                raise ReminderError('Use an hour from 1 to 12 with am or pm.')
            hour = hour % 12 + (12 if day[4] == 'pm' else 0)
        naive = datetime.combine(date, datetime.min.time()).replace(hour=hour, minute=minute)
        first, second = naive.replace(tzinfo=ZONE, fold=0), naive.replace(tzinfo=ZONE, fold=1)
        if first.utcoffset() != second.utcoffset() or datetime.fromtimestamp(first.timestamp(), ZONE).replace(tzinfo=None) != naive:
            raise ReminderError('That local time falls in a daylight-saving clock change. Use an ISO date/time with an explicit UTC offset.')
        due = first.timestamp()
    else:
        try:
            parsed = datetime.fromisoformat(re.sub(r'^at\s+', '', value).replace('z', '+00:00'))
        except ValueError:
            raise ReminderError('I need a clear date and time. ' + HELP) from None
        if parsed.tzinfo is None:
            raise ReminderError('Use a local date with “at HH:MM”, or an ISO date/time with an explicit UTC offset.')
        due = parsed.timestamp()
    if due <= now:
        raise ReminderError('That time has already passed. Choose a future time.')
    if due - now > 366 * 86400:
        raise ReminderError('Choose a time within the next 366 days.')
    return due


def parse(text, now):
    stripped = text.strip().rstrip('.?!')
    # Constraints anywhere in a recognized request apply before any schedule
    # variant (including recurring reminders) is allowed to create a row.
    if approval_requested(text):
        raise ReminderError('Nothing was saved. Send a new reminder request when you want it scheduled.')
    if TIMEZONE.search(stripped):
        raise ReminderError('The reminder timezone needs clarification. Nothing was saved. '
                            'Use America/Chicago local clock times without a timezone qualifier, '
                            'or an ISO date/time with an explicit UTC offset.')
    morning = routine_request(text)
    if morning:
        clock = morning_clock(morning['clock'])
        return reminder_body(morning['body']), next_morning(now, clock), 86400
    request = reminder_request(stripped)
    if request:
        clause = request['clause'].strip()
        default_body = request['kind'].capitalize()
    else:
        legacy = re.fullmatch(r'(?:remind me|set (?:a )?routine)\s+([\s\S]+)', stripped, re.I)
        if not legacy:
            return None
        clause, default_body = legacy[1], 'Reminder'
    # The old interval grammar retains its limits and catch-up semantics.
    stripped = 'remind me ' + clause
    recurring = re.fullmatch(r'(?:remind me|set (?:a )?routine) every (\d+) (minutes?|hours?|days?) to ([\s\S]+)', stripped, re.I)
    if recurring:
        interval = int(recurring[1]) * UNITS[recurring[2].lower().rstrip('s')]
        if not 60 <= interval <= 366 * 86400:
            raise ReminderError('Repeat intervals must be between 1 minute and 366 days.')
        return reminder_body(recurring[3]), now + interval, interval
    match = re.fullmatch(r'to ([\s\S]+?)\s+(' + WHEN + r')', clause, re.I)
    if match:
        return reminder_body(match[1]), instant(_when(match[2]), now), None
    clause = re.sub(r'^for\s+', '', clause, flags=re.I)
    match = re.fullmatch(r'(' + WHEN + r')(?:\s+(?:to|for)\s+([\s\S]+))?', clause, re.I)
    if match:
        return reminder_body(match[2] or default_body), instant(_when(match[1]), now), None
    return None


def reminder_body(value):
    # A second time/date in the body may qualify or conflict with the matched
    # schedule. Ask before saving instead of silently treating it as prose.
    month = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|'
             r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)')
    # Recognize quantity phrases conservatively without guessing their value
    # (e.g. "two", "twenty-one", "a couple of"). Ask for one explicit schedule.
    relative = r'in\s+(?:[\w-]+\s+)+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)'
    if re.search(r'\b(?:today|tomorrow|tonight|yesterday|noon|midnight|'
                 r'monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
                 r'next\s+(?:week|month|year)|every\s+\w+|\d{4}-\d{2}-\d{2}|'
                 + month + r'\.?\s+\d{1,2}|\d{1,2}\s+' + month + r'|'
                 r'\d{1,2}/\d{1,2}(?:/\d{2,4})?|'
                 r'at\s+\d{1,2}\b|' + relative + r'|' + CLOCK + r')\b', value, re.I):
        raise ReminderError('The reminder has an extra date or time clause. Nothing was saved. '
                            'Please use one schedule, such as “create a reminder for tomorrow at 2am to go to bed”.')
    return value.strip()


def _when(value):
    return 'in ' + value if re.fullmatch(DURATION, value, re.I) else value


def morning_clock(value):
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', value or '9am', re.I)
    if not match:
        raise ReminderError('Choose a morning clock time. ' + ROUTINE_HELP)
    hour, minute, meridiem = int(match[1]), int(match[2] or 0), (match[3] or '').lower()
    if meridiem:
        if not 1 <= hour <= 12:
            raise ReminderError('Use an hour from 1 to 12 with am or pm.')
        hour = hour % 12 + (12 if meridiem == 'pm' else 0)
    # A morning window also avoids ambiguous/nonexistent US DST hours.
    if not 3 <= hour < 12 or not 0 <= minute < 60:
        raise ReminderError('Morning routines support 3:00am through 11:59am America/Chicago.')
    return f'{hour:02d}:{minute:02d}'


def next_morning(now, clock):
    hour, minute = map(int, clock.split(':'))
    local = datetime.fromtimestamp(now, ZONE)
    due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due <= local:
        due += timedelta(days=1)
    return due.timestamp()


def repeat_description(row):
    if row.get('weekly_time'):
        return ' Repeats every ' + WEEKDAYS[row['weekly_time']['day']].capitalize() + ' at ' + row['weekly_time']['clock'] + ' America/Chicago.'
    if row.get('daily_time'):
        return ' Repeats every morning at ' + row['daily_time'] + ' America/Chicago.'
    return f" Repeats every {row['interval_seconds'] // 60} minutes." if row['interval_seconds'] else ''


def stamp(seconds):
    local = datetime.fromtimestamp(seconds, ZONE)
    return local.strftime('%b %d, %Y at %I:%M:%S %p %Z' if local.second else '%b %d, %Y at %I:%M %p %Z')


class Reminders:
    def __init__(self, folder, clock=time.time):
        self.folder = Path(folder) / 'reminders'
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.folder.is_symlink():
            raise ReminderError('Reminder storage must be a private directory.')
        self.folder.chmod(0o700)
        self.path = self.folder / 'items.json'
        self.clock = clock

    @contextmanager
    def locked(self):
        if self.path.is_symlink() or (self.folder / 'items.lock').is_symlink():
            raise ReminderError('Reminder storage must use private regular files.')
        with (self.folder / 'items.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if self.path.exists() and self.path.stat().st_size > 2 * 1024 * 1024:
                    raise ReminderError('Reminder storage is full. Nothing changed.')
                rows = json.loads(self.path.read_text()) if self.path.exists() else []
                if not isinstance(rows, list):
                    raise ReminderError('Reminder storage needs repair. Nothing changed.')
                yield rows
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save(self, rows):
        atomic_text(self.path, json.dumps(rows, ensure_ascii=False))
        self.path.chmod(0o600)

    def save_change(self, rows, before):
        """Read back under the lock: an atomic write can fail after replacement."""
        try:
            self.save(rows)
        except OSError:
            try:
                current = json.loads(self.path.read_text())
            except FileNotFoundError:
                current = []
            except (OSError, ValueError):
                current = None
            if current == before:
                raise ReminderError('Reminder storage failed. The requested change was not saved.') from None
            raise ReminderError('Reminder storage update is unconfirmed; the change may already be saved. '
                                'Check “my reminders” before trying again.') from None

    def create(self, cid, request_id, body, due, interval=None, *, daily_time=None, action=None, weekly_time=None):
        if not 1 <= len(body) <= 1000:
            raise ReminderError('Keep a reminder between 1 and 1,000 characters.')
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, 'webbob-reminder:' + cid + ':' + request_id).hex[:16]
        with self.locked() as rows:
            existing = next((r for r in rows if r['id'] == identifier), None)
            if existing:
                return existing
            if sum(r['state'] == 'pending' for r in rows) >= 200:
                raise ReminderError('The reminder limit is reached. Cancel active reminders before adding more.')
            before = list(rows)
            if len(rows) >= 400:
                pending = [r for r in rows if r['state'] == 'pending']
                completed = sorted((r for r in rows if r['state'] != 'pending'), key=lambda r: r['created_at'])[-199:]
                rows[:] = pending + completed
            row = dict(id=identifier, conversation_id=cid, body=body, due_at=due, interval_seconds=interval,
                       state='pending', created_at=self.clock(), occurrences=0)
            if weekly_time:
                row['weekly_time'] = weekly_time
            if daily_time:
                row['daily_time'] = daily_time
            if action:
                row['action'] = action
            rows.append(row)
            self.save_change(rows, before)
            return row

    def listing(self):
        with self.locked() as rows:
            return (sorted((r for r in rows if r['state'] == 'pending'), key=lambda r: r['due_at']) +
                    sorted((r for r in rows if r['state'] != 'pending'), key=lambda r: r.get('last_fired_at', r['created_at']), reverse=True))

    def cancel(self, identifier):
        with self.locked() as rows:
            row = next((r for r in rows if r['id'] == identifier), None)
            if not row:
                raise ReminderError('No reminder with that ID was found.')
            if row['state'] == 'fired':
                return 'That reminder already appeared in chat.'
            before = [dict(r) for r in rows]
            row['state'] = 'cancelled'
            self.save_change(rows, before)
        return 'Reminder cancelled.'

    def deliver_due(self, deliver, notify=None):
        """Persist chat and firing state before a best-effort OS notification.

        Chat retries deduplicate by notice ID. A crash after the firing-state
        write can lose an OS alert; we never replay that alert on restart.
        """
        notifications = []
        with self.locked() as rows:
            changed = False
            now = self.clock()
            for row in rows:
                if row['state'] != 'pending' or row['due_at'] > now:
                    continue
                notice = uuid.uuid5(uuid.NAMESPACE_URL, 'reminder-notice:' + row['id'] + ':' + str(row['occurrences'])).hex
                if not deliver(row, notice):
                    continue
                # Action output remains private in chat; never expose file or
                # lookup results in an OS alert or claim a routine was a reminder.
                if not row.get('action'):
                    notifications.append(dict(row))
                row['occurrences'] += 1
                row['last_fired_at'] = now
                if row.get('weekly_time'):
                    row['due_at'] = next_weekday(now, row['weekly_time'])
                elif row.get('daily_time'):
                    row['due_at'] = next_morning(now, row['daily_time'])
                elif row['interval_seconds']:
                    # One catch-up notice, never a burst after downtime.
                    elapsed = int((now - row['due_at']) // row['interval_seconds']) + 1
                    row['due_at'] += elapsed * row['interval_seconds']
                else:
                    row['state'] = 'fired'
                changed = True
            if changed:
                self.save(rows)
        if notify:
            for row in notifications:
                try:
                    notify(row['body'])
                except Exception:
                    pass  # OS failure must not undo or block durable chat delivery.

    @contextmanager
    def draft_lock(self):
        # Drafts are not scheduled items and cannot be delivered. Serialize
        # confirmation separately so create() can take its normal item lock.
        path = self.folder / 'drafts.json'
        lock_path = self.folder / 'drafts.lock'
        if path.is_symlink() or lock_path.is_symlink():
            raise ReminderError('Reminder draft storage must use private regular files.')
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if path.exists() and path.stat().st_size > 2 * 1024 * 1024:
                    raise ReminderError('Reminder draft storage is full. Nothing was saved.')
                drafts = json.loads(path.read_text()) if path.exists() else {}
                if not isinstance(drafts, dict):
                    raise ReminderError('Reminder draft storage needs repair. Nothing was saved.')
                yield drafts
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save_drafts(self, drafts):
        path = self.folder / 'drafts.json'
        atomic_text(path, json.dumps(drafts, ensure_ascii=False))
        path.chmod(0o600)

    def draft_receipt(self, row):
        if row['state'] == 'done':
            return row['receipt']
        if row['state'] == 'needs_time':
            return f"Draft reminder: {row['body']} — {row['when']}. {row['question']}"
        if row['state'] != 'draft':
            return ('That reminder draft is ' + row['state'] +
                    '. Check “my reminders” before making a fresh request.')
        when = stamp(row['due'])
        lead = f"Draft reminder: {row['body']} — "
        request = reminder_request(row['text'])
        relative = re.search(r'\bin (\d+)\s+(seconds?|minutes?|mins?|hours?|hrs?|days?)\b',
                             request['clause'], re.I) if request else None
        if relative and not row['interval'] and not row.get('weekly_time') and not row['daily_time']:
            unit = relative[2].lower().rstrip('s')
            unit = {'min': 'minute', 'hr': 'hour'}.get(unit, unit)
            delay = relative[1] + ' ' + unit + ('s' if int(relative[1]) != 1 else '')
            when = 'in ' + delay
            lead = f"Draft reminder: {row['body']} "
        preview = (row.get("assumption", "") + lead + when + repeat_description(dict(
                    interval_seconds=row['interval'], daily_time=row['daily_time'], weekly_time=row.get('weekly_time'))) +
                (f" Read-only action: {row['action']}." if row['action'] else '')).rstrip('.')
        return (preview +
                (". OK to set it? It isn't running yet—use a phone or oven timer if you need it counting now." if relative else '.') +
                f"\nReply `yes {row['token']}` to set.")

    def draft(self, text, cid, request_id, actor, body, due, interval, daily_time, action, *, weekly_time=None, assumption=''):
        if not 1 <= len(body) <= 1000:
            raise ReminderError('Keep a reminder between 1 and 1,000 characters.')
        with self.draft_lock() as drafts:
            existing = next((r for r in drafts.values() if r['cid'] == cid and
                             r['request_id'] == request_id), None)
            if existing:
                return (self.draft_receipt(existing) if existing['text'] == text and
                        existing['actor'] == actor else 'Request ID already used for another reminder.')
            if len(drafts) >= 1000:
                raise ReminderError('Reminder draft limit reached. Nothing was saved.')
            for old in drafts.values():
                if old['cid'] == cid and old['state'] in ('draft', 'needs_time'):
                    old['state'] = 'replaced'
            token = 'wbrem-' + uuid.uuid4().hex
            row = dict(token=token, text=text, cid=cid, request_id=request_id,
                       actor=actor, body=body, due=due, interval=interval,
                       daily_time=daily_time, action=action, weekly_time=weekly_time, assumption=assumption, state='draft',
                       expires=self.clock() + 3600)
            drafts[token] = row
            self.save_drafts(drafts)
            return self.draft_receipt(row)

    def control(self, command, token, cid, request_id, actor, intent_state, local_tasks):
        with self.draft_lock() as drafts:
            row = drafts.get(token)
            if not row or row['cid'] != cid or row['actor'] != actor:
                return 'No matching reminder draft in this conversation.'
            if row['state'] != 'draft':
                return self.draft_receipt(row)
            if command == 'cancel':
                row['state'] = 'cancelled'
                self.save_drafts(drafts)
                return 'Reminder draft cancelled. Nothing was saved to your reminders.'
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(row['text']), action_text=row['text'])
            if scopes:
                return chat_intent.hold_reply(scopes)
            if request_id == row['request_id']:
                return 'Confirm the reminder in a separate message.'
            if self.clock() >= min(row['expires'], row['due']):
                row['state'] = 'expired'
                self.save_drafts(drafts)
                return self.draft_receipt(row)
            if row['action']:
                if local_tasks is None:
                    return 'Local routine actions are unavailable. Nothing was saved.'
                from local_tasks import LocalTaskError
                try:
                    local_tasks.validate_routine(row['action'])
                except LocalTaskError as exc:
                    return str(exc)
            # Persist consumed consent BEFORE create. An interrupted or uncertain
            # attempt must never run again on replay, even across a restart.
            row.update(state='unconfirmed', approved_request_id=request_id)
            self.save_drafts(drafts)
            created = self.create(cid, row['request_id'], row['body'], row['due'], row['interval'],
                                  daily_time=row['daily_time'], action=row['action'], weekly_time=row.get('weekly_time'))
            row.update(state='done', receipt=self.created_receipt(created))
            self.save_drafts(drafts)
            return row['receipt']

    def created_receipt(self, row):
        repeat = repeat_description(row)
        if row.get('action'):
            return (f"Read-only routine saved: {row['body']} — {stamp(row['due_at'])}.{repeat} ID {row['id']}. "
                    'Results will appear in this chat while Web Bob is running, with one catch-up run after restart. '
                    'Saved holds are checked before each run. No job or message to another person will be sent.')
        return f"Reminder saved: {row['body']} — {stamp(row['due_at'])}.{repeat} ID {row['id']}. It will appear in this chat while Web Bob is running (or when it restarts); macOS alerts require owner opt-in; no text, email or job will be sent."

    def incomplete(self, text, cid, request_id, actor, body, when, question):
        with self.draft_lock() as drafts:
            for old in drafts.values():
                if old['cid'] == cid and old['request_id'] == request_id:
                    return self.draft_receipt(old)
                if old['cid'] == cid and old['state'] in ('draft', 'needs_time'):
                    old['state'] = 'replaced'
            if len(drafts) >= 1000:
                raise ReminderError('Reminder draft limit reached. Nothing was saved.')
            token = 'wbrem-' + uuid.uuid4().hex
            row = dict(token=token, cid=cid, request_id=request_id, actor=actor, text=text,
                       body=body, when=when, question=question, state='needs_time')
            drafts[token] = row
            self.save_drafts(drafts)
            return self.draft_receipt(row)

    def extracted(self, output, text, cid, request_id, actor, intent_state):
        # Model text is untrusted. Only literal spans can become draft operands;
        # deterministic parsing and the unchanged consent detector still apply.
        try:
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text), action_text=text)
            if scopes:
                return chat_intent.hold_reply(scopes)
            value = json.loads(output)
            body, when = value['body'], value['when']
            if not isinstance(body, str) or not body.strip() or body not in text:
                raise ValueError()
            if when is not None and (not isinstance(when, str) or when not in text):
                raise ValueError()
            if approval_requested(text):
                return 'Nothing was saved. Send a new reminder request when you want it scheduled.'
            if when:
                normalized, weekly, assumption = natural_request(f'remind me {when} to {body}', self.clock())
                missing = self.missing_clock(normalized, text, cid, request_id, actor)
                if missing:
                    return missing
                parsed = parse(normalized, self.clock())
                if parsed:
                    morning = routine_request(normalized)
                    daily_time = morning_clock(morning['clock']) if morning else None
                    if morning and not morning['clock']:
                        assumption = 'Assuming morning means 9am America/Chicago. '
                    return self.draft(text, cid, request_id, actor, *parsed, daily_time, None,
                                      weekly_time=weekly, assumption=assumption)
            return self.incomplete(text, cid, request_id, actor, body, when or 'time needed',
                                   'What date and time should I use?')
        except (ValueError, TypeError, KeyError):
            return 'I need a clear time for your reminder. What date and time should I use?'

    def missing_clock(self, normalized, text, cid, request_id, actor):
        # Every-morning requests retain the documented 9am default in parse().
        match = re.fullmatch(r'remind me (every |(?:on )?)(' + WEEKDAY +
                            r')(?: (morning|afternoon|evening|night))? to (.+)', normalized.rstrip('.?!'), re.I)
        if not match or approval_requested(text):
            return None
        when = match[1] + match[2].capitalize() + (' ' + match[3] if match[3] else '')
        defaults = {'morning': '9 AM', 'afternoon': '2 PM', 'evening': '8 PM', 'night': '8 PM'}
        suggestion = defaults.get((match[3] or '').lower(), '9 AM')
        return self.incomplete(text, cid, request_id, actor, reminder_body(match[4]), when,
                               f'I suggest {suggestion} Central (America/Chicago), pending your OK. '
                               'What time should I use?')

    def handle(self, text, cid, request_id, *, local_tasks=None, intent_state=None, actor='owner', allow_model=False):
        try:
            return self._handle(text, cid, request_id, local_tasks=local_tasks,
                                intent_state=intent_state or chat_intent.new_state(), actor=actor, allow_model=allow_model)
        except ReminderError as exc:
            return str(exc)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return ('Reminder storage is unavailable; no successful change was verified. '
                    'Check “my reminders” once storage is available before trying again.')

    def _handle(self, text, cid, request_id, *, local_tasks=None, intent_state=None, actor='owner', allow_model=False):
        if leading_approval_request(text, reminder_request):
            return 'Nothing was saved. Send a new reminder request when you want it scheduled.'
        control = re.fullmatch(r'(yes|cancel) (wbrem-[0-9a-f]{32})', text.strip())
        if control:
            return self.control(control[1], control[2], cid, request_id, actor, intent_state or chat_intent.new_state(), local_tasks)
        if re.match(r'^(?:yes|cancel)\s+wbrem-', text.strip(), re.I):
            return 'Use the exact confirmation message from the reminder draft. Nothing was saved.'
        clock = re.fullmatch(r'(?:at )?(' + CLOCK + r')[.! ]*', text.strip(), re.I)
        if clock:
            with self.draft_lock() as drafts:
                waiting = [r for r in drafts.values() if r['cid'] == cid and r['actor'] == actor
                           and r['state'] == 'needs_time']
            if len(waiting) == 1:
                row = waiting[0]
                schedule = re.fullmatch(r'(every |(?:on )?)(' + WEEKDAY +
                                       r')(?: (?:morning|afternoon|evening|night))?', row['when'], re.I)
                when = schedule[1] + schedule[2] if schedule else row['when']
                if schedule or when == 'every morning':
                    return self._handle(f"remind me {when} at {clock[1]} to {row['body']}", cid, request_id,
                                        local_tasks=local_tasks, intent_state=intent_state, actor=actor,
                                        allow_model=allow_model)
        command = text.strip().casefold().rstrip('.?!')
        if command in ('reminders', 'my reminders', 'list reminders', 'show reminders', 'routines', 'my routines',
                       'timers', 'my timers', 'alarms', 'my alarms'):
            rows = [r for r in self.listing() if r['state'] == 'pending']
            return ('Your reminders (America/Chicago):\n' + '\n'.join(
                f"• {'Read-only routine: ' if r.get('action') else ''}{r['body']} — {stamp(r['due_at'])}" + repeat_description(r) + f" · ID {r['id']}"
                for r in rows)) if rows else 'You have no pending reminders. ' + HELP
        cancel = re.fullmatch(r'cancel (?:reminder|routine|timer|alarm) ([0-9a-f]{16})', command)
        if cancel:
            return self.cancel(cancel[1])
        if reminder_request(text) or routine_intent(text) or re.match(r'^(?:remind me|set (?:a )?routine|cancel (?:reminder|routine|timer|alarm)|reminder help)\b', command):
            try:
                normalized, weekly, assumption = natural_request(text, self.clock())
                missing = self.missing_clock(normalized, text, cid, request_id, actor)
                if missing:
                    return missing
                event = re.fullmatch(r'remind me before (.+?) to (.+)', normalized, re.I)
                # An unresolved event has no due time or approvable token. Asking
                # for its time is safe even when words like "rehearsal" trigger
                # the conservative consent detector. Scheduling still goes
                # through parse() and a separate exact-token confirmation.
                if event and re.fullmatch(r'[\w \'’-]{1,80}', event[1]):
                    return self.incomplete(text, cid, request_id, actor, event[2], 'before ' + event[1],
                                           'When is ' + event[1] + '? I suggest an hour before; '
                                           'I’ll wait for your OK before scheduling.')
                parsed = parse(normalized, self.clock())
                if not parsed:
                    body_only = re.fullmatch(r'remind me to (.+)', normalized, re.I)
                    if body_only:
                        return self.incomplete(text, cid, request_id, actor, body_only[1], 'time needed',
                                               'What date and time should I use? Try “tomorrow at 9am”.')
                    if reminder_request(text) and allow_model:
                        raise ExtractionNeeded()
                    return ROUTINE_HELP if routine_intent(text) else 'What should I remind you about, and when?'
                body, due, interval = parsed
                morning = routine_request(text)
                daily_time = morning_clock(morning['clock']) if morning else None
                if morning and not morning['clock']:
                    assumption = 'Assuming morning means 9am America/Chicago. '
                action = None
                if (morning and morning['mode'].lower() == 'do' and not morning['remind']
                        and (morning['kind'] or 'routine').lower() == 'routine'):
                    if local_tasks is None:
                        return 'Local routine actions are unavailable. ' + ROUTINE_HELP
                    action = local_tasks.validate_routine(body)
                scopes = chat_intent.blocked_scopes(intent_state or chat_intent.new_state(), chat_intent.projects(text), action_text=text)
                if scopes:
                    return chat_intent.hold_reply(scopes)
                # A complete, explicit request to remind the speaker authorizes
                # this local reminder. Inspect the original wording: normalized
                # requests and model extractions are not fresh authorization.
                # Parsing above still rejects approval clauses and ambiguity.
                if action is None and not assumption and PERSONAL_INTERVAL_REQUEST.fullmatch(text.strip()):
                    # Check both the original request and extracted reminder
                    # text for either interval grammar. Detection normalization
                    # must never strip constraints or rewrite the saved body.
                    if approval_requested(text) or approval_requested(body):
                        raise ReminderError('Nothing was saved. Send a new reminder request when you want it scheduled.')
                    if not plain_interval_reminder(text, body):
                        # Confirm when unsure: anything but plain ASCII words
                        # goes to the separate exact-token confirmation step.
                        return self.draft(text, cid, request_id, actor, body, due, interval, daily_time, action,
                                          weekly_time=weekly, assumption=assumption)
                    with self.draft_lock() as drafts:
                        changed = False
                        for old in drafts.values():
                            if old['cid'] == cid and old['state'] in ('draft', 'needs_time'):
                                old['state'] = 'replaced'
                                changed = True
                        if changed:
                            self.save_drafts(drafts)
                        row = self.create(cid, request_id, body, due, interval,
                                          daily_time=daily_time, action=action, weekly_time=weekly)
                    return self.created_receipt(row)
                return self.draft(text, cid, request_id, actor, body, due, interval, daily_time, action, weekly_time=weekly, assumption=assumption)
            except (UnicodeError, json.JSONDecodeError):
                raise  # Storage corruption is not a date/time parsing error.
            except ValueError as exc:
                from local_tasks import LocalTaskError
                return str(exc) if isinstance(exc, (ReminderError, LocalTaskError)) else 'That date or time is invalid. ' + HELP
        return None

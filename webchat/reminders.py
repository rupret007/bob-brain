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
from actions_intent import reminder_request

ZONE = ZoneInfo('America/Chicago')
HELP = ('Try “remind me to check the oven in 10 minutes”, “remind me to call Sam on 2026-10-01 at 14:00”, '
        '“remind me every 2 hours to stretch”, “my reminders”, or “cancel reminder ID”. '
        'You can also say “create a reminder for 2am to go to bed” or “set a timer for 10 minutes”. '
        'Times use America/Chicago; a clock time without a date means its next occurrence. '
        'Reminders appear here and in Jobs while Web Bob is running; overdue reminders arrive when it returns. '
        'Local macOS notifications are best effort and require notification permission. '
        'Reminders never send texts or emails or start work.')
UNITS = {'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400}
DURATION = r'\d+\s+(?:seconds?|minutes?|hours?|days?)'
CLOCK = r'\d{1,2}(?::\d{2}\s*(?:am|pm)?|\s*(?:am|pm))'
WHEN = (r'(?:(?:in\s+)?' + DURATION + r'|(?:on\s+)?(?:\d{4}-\d{2}-\d{2}|today|tomorrow)'
        r'(?:\s+at)?\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|'
        r'(?:at\s+)?\d{4}-\d{2}-\d{2}t\S+|(?:at\s+)?' + CLOCK + r')')


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
        return recurring[3].strip(), now + interval, interval
    match = re.fullmatch(r'to ([\s\S]+?)\s+(' + WHEN + r')', clause, re.I)
    if match:
        return match[1].strip(), instant(_when(match[2]), now), None
    clause = re.sub(r'^for\s+', '', clause, flags=re.I)
    match = re.fullmatch(r'(' + WHEN + r')(?:\s+(?:to|for)\s+([\s\S]+))?', clause, re.I)
    if match:
        return (match[2] or default_body).strip(), instant(_when(match[1]), now), None
    return None


def _when(value):
    return 'in ' + value if re.fullmatch(DURATION, value, re.I) else value


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

    def create(self, cid, request_id, body, due, interval=None):
        if not 1 <= len(body) <= 1000:
            raise ReminderError('Keep a reminder between 1 and 1,000 characters.')
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, 'webbob-reminder:' + cid + ':' + request_id).hex[:16]
        with self.locked() as rows:
            existing = next((r for r in rows if r['id'] == identifier), None)
            if existing:
                return existing
            if sum(r['state'] == 'pending' for r in rows) >= 200:
                raise ReminderError('The reminder limit is reached. Cancel active reminders before adding more.')
            if len(rows) >= 400:
                pending = [r for r in rows if r['state'] == 'pending']
                completed = sorted((r for r in rows if r['state'] != 'pending'), key=lambda r: r['created_at'])[-199:]
                rows[:] = pending + completed
            row = dict(id=identifier, conversation_id=cid, body=body, due_at=due, interval_seconds=interval,
                       state='pending', created_at=self.clock(), occurrences=0)
            rows.append(row)
            self.save(rows)
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
            row['state'] = 'cancelled'
            self.save(rows)
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
                notifications.append(dict(row))
                row['occurrences'] += 1
                row['last_fired_at'] = now
                if row['interval_seconds']:
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

    def handle(self, text, cid, request_id):
        command = text.strip().casefold().rstrip('.?!')
        if command in ('reminders', 'my reminders', 'list reminders', 'show reminders', 'routines', 'my routines',
                       'timers', 'my timers', 'alarms', 'my alarms'):
            rows = [r for r in self.listing() if r['state'] == 'pending']
            return ('Your reminders (America/Chicago):\n' + '\n'.join(
                f"• {r['body']} — {stamp(r['due_at'])}" + (f"; repeats every {r['interval_seconds'] // 60} minutes" if r['interval_seconds'] else '') + f" · ID {r['id']}"
                for r in rows)) if rows else 'You have no pending reminders. ' + HELP
        cancel = re.fullmatch(r'cancel (?:reminder|routine|timer|alarm) ([0-9a-f]{16})', command)
        if cancel:
            return self.cancel(cancel[1])
        if reminder_request(text) or re.match(r'^(?:remind me|set (?:a )?routine|cancel (?:reminder|routine|timer|alarm)|reminder help)\b', command):
            try:
                parsed = parse(text, self.clock())
                if not parsed:
                    return HELP
                body, due, interval = parsed
                row = self.create(cid, request_id, body, due, interval)
                repeat = f" Repeats every {row['interval_seconds'] // 60} minutes." if row['interval_seconds'] else ''
                return f"Reminder saved: {row['body']} — {stamp(row['due_at'])}.{repeat} ID {row['id']}. It will appear in this chat while Web Bob is running (or when it restarts); macOS notification is best effort; no text, email or job will be sent."
            except ValueError as exc:
                return str(exc) if isinstance(exc, ReminderError) else 'That date or time is invalid. ' + HELP
        return None

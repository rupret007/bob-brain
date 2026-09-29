"""Private, durable reminders. The only notification is a Web Bob chat message."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
from pathlib import Path
import re
import time
import uuid
from zoneinfo import ZoneInfo

from failover import atomic_text

ZONE = ZoneInfo('America/Chicago')
HELP = ('Try “remind me to check the oven in 10 minutes”, “remind me to call Sam on 2026-10-01 at 14:00”, '
        '“remind me every 2 hours to stretch”, “my reminders”, or “cancel reminder ID”. '
        'Times use America/Chicago. Reminders appear here and in Jobs while Web Bob is running; overdue reminders arrive when it returns. '
        'They never send messages outside Web Bob or start work.')
UNITS = {'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400}


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
    stripped = text.strip()
    recurring = re.fullmatch(r'(?:remind me|set (?:a )?routine) every (\d+) (minutes?|hours?|days?) to ([\s\S]+)', stripped, re.I)
    if recurring:
        interval = int(recurring[1]) * UNITS[recurring[2].lower().rstrip('s')]
        if not 60 <= interval <= 366 * 86400:
            raise ReminderError('Repeat intervals must be between 1 minute and 366 days.')
        return recurring[3].strip(), now + interval, interval
    match = re.fullmatch(r'remind me to ([\s\S]+?) ((?:in |on |today |tomorrow |at \d{4}-)[\s\S]+)', stripped, re.I)
    if match:
        return match[1].strip(), instant(match[2], now), None
    return None


def stamp(seconds):
    return datetime.fromtimestamp(seconds, ZONE).strftime('%b %d, %Y at %I:%M %p %Z')


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

    def deliver_due(self, deliver):
        """Persist chat first. A stable notification ID makes a retry harmless."""
        with self.locked() as rows:
            changed = False
            now = self.clock()
            for row in rows:
                if row['state'] != 'pending' or row['due_at'] > now:
                    continue
                notice = uuid.uuid5(uuid.NAMESPACE_URL, 'reminder-notice:' + row['id'] + ':' + str(row['occurrences'])).hex
                if not deliver(row, notice):
                    continue
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

    def handle(self, text, cid, request_id):
        command = text.strip().casefold().rstrip('.?!')
        if command in ('reminders', 'my reminders', 'list reminders', 'show reminders', 'routines', 'my routines'):
            rows = [r for r in self.listing() if r['state'] == 'pending']
            return ('Your reminders (America/Chicago):\n' + '\n'.join(
                f"• {r['body']} — {stamp(r['due_at'])}" + (f"; repeats every {r['interval_seconds'] // 60} minutes" if r['interval_seconds'] else '') + f" · ID {r['id']}"
                for r in rows)) if rows else 'You have no pending reminders. ' + HELP
        cancel = re.fullmatch(r'cancel (?:reminder|routine) ([0-9a-f]{16})', command)
        if cancel:
            return self.cancel(cancel[1])
        if re.match(r'^(?:remind me|set (?:a )?routine|cancel (?:reminder|routine)|reminder help)\b', command):
            try:
                parsed = parse(text, self.clock())
                if not parsed:
                    return HELP
                body, due, interval = parsed
                row = self.create(cid, request_id, body, due, interval)
                repeat = f" Repeats every {interval // 60} minutes." if interval else ''
                return f"Reminder saved: {row['body']} — {stamp(row['due_at'])}.{repeat} ID {row['id']}. It will appear in this chat; no text, email or job will be sent."
            except ValueError as exc:
                return str(exc) if isinstance(exc, ReminderError) else 'That date or time is invalid. ' + HELP
        return None

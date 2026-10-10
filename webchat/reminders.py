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

ZONE = ZoneInfo('America/Chicago')
HELP = ('Try “remind me to check the oven in 10 minutes”, “remind me to call Sam on 2026-10-01 at 14:00”, '
        '“remind me every 2 hours to stretch”, “my reminders”, or “cancel reminder ID”. '
        'You can also say “create a reminder for 2am to go to bed” or “set a timer for 10 minutes”. '
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
    if re.search(r"\b(?:do\s+not|don't|don’t|never)\s+(?:(?:actually|ever|just|yet|really)\s+)*(?:save|create|schedule|set|add|execute)\b|"
                 r'\b(?:ask|confirm|check)(?:\s+with)?\s+me\s+(?:first|before)|'
                 r'\b(?:ask(?:\s+me)?|wait)\s+for\s+(?:my\s+)?(?:approval|confirmation|permission)\b|'
                 r'\b(?:get|pending|after)\s+my\s+(?:approval|confirmation)\b|'
                 r'\b(?:if|unless|until|after|once|when)\s+I\s+(?:confirm|approve|say)\b|'
                 r'\b(?:wait|hold off)\s+(?:until|before)|\b(?:before|without)\s+my\s+(?:approval|confirmation)',
                 stripped, re.I):
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
    if re.search(r'\b(?:today|tomorrow|tonight|yesterday|noon|midnight|'
                 r'monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
                 r'next\s+(?:week|month|year)|every\s+\w+|\d{4}-\d{2}-\d{2}|'
                 + month + r'\.?\s+\d{1,2}|\d{1,2}\s+' + month + r'|'
                 r'\d{1,2}/\d{1,2}(?:/\d{2,4})?|'
                 r'at\s+\d{1,2}\b|in\s+' + DURATION + r'|' + CLOCK + r')\b', value, re.I):
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

    def create(self, cid, request_id, body, due, interval=None, *, daily_time=None, action=None):
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
                if row.get('daily_time'):
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

    def handle(self, text, cid, request_id, *, local_tasks=None):
        try:
            return self._handle(text, cid, request_id, local_tasks=local_tasks)
        except ReminderError as exc:
            return str(exc)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return ('Reminder storage is unavailable; no successful change was verified. '
                    'Check “my reminders” once storage is available before trying again.')

    def _handle(self, text, cid, request_id, *, local_tasks=None):
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
                parsed = parse(text, self.clock())
                if not parsed:
                    return ROUTINE_HELP if routine_intent(text) else HELP
                body, due, interval = parsed
                morning = routine_request(text)
                daily_time = morning_clock(morning['clock']) if morning else None
                action = None
                if (morning and morning['mode'].lower() == 'do' and not morning['remind']
                        and (morning['kind'] or 'routine').lower() == 'routine'):
                    if local_tasks is None:
                        return 'Local routine actions are unavailable. ' + ROUTINE_HELP
                    action = local_tasks.validate_routine(body)
                row = self.create(cid, request_id, body, due, interval, daily_time=daily_time, action=action)
                repeat = repeat_description(row)
                if row.get('action'):
                    return (f"Read-only routine saved: {row['body']} — {stamp(row['due_at'])}.{repeat} ID {row['id']}. "
                            'Results will appear in this chat while Web Bob is running, with one catch-up run after restart. '
                            'Saved holds are checked before each run. No job or message to another person will be sent.')
                return f"Reminder saved: {row['body']} — {stamp(row['due_at'])}.{repeat} ID {row['id']}. It will appear in this chat while Web Bob is running (or when it restarts); macOS alerts require owner opt-in; no text, email or job will be sent."
            except (UnicodeError, json.JSONDecodeError):
                raise  # Storage corruption is not a date/time parsing error.
            except ValueError as exc:
                from local_tasks import LocalTaskError
                return str(exc) if isinstance(exc, (ReminderError, LocalTaskError)) else 'That date or time is invalid. ' + HELP
        return None

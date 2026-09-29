"""Natural task acceptance over isolated local data; never invokes a real worker."""
import json
from pathlib import Path
import uuid

from instinct_fixture import InstinctFixture
from task_dispatch import task_queue
from texting import Texting


def run_eval():
    cases = []
    def check(name, passed):
        cases.append(dict(name='Remaining: ' + name, **{'pass': bool(passed)}))
    with InstinctFixture() as f:
        f.chat.reminders.clock = lambda: f.now
        rid = str(uuid.uuid4())
        first = f.answer('remind me to check the oven in 10 minutes', request_id=rid)
        check('create structured reminder without model', first['provider'] == 'reminders' and not f.providers.calls)
        check('receipt states delivery scope', 'no text, email or job' in first['content'])
        check('private durable reminder store', f.chat.reminders.path.is_file() and f.chat.reminders.path.stat().st_mode & 0o777 == 0o600)
        f.answer('remind me to check the oven in 10 minutes', request_id=rid)
        check('duplicate request creates one reminder', len(f.chat.reminders.listing()) == 1)
        check('list finds pending reminder', 'check the oven' in f.answer('my reminders')['content'])
        f.chat.deliver_reminders()
        check('future reminder does not fire early', f.chat.reminders.listing()[0]['state'] == 'pending')
        f.now += 600
        f.chat.deliver_reminders()
        check('due notification arrives in chat', f.chat.history(f.identifier)['messages'][-1]['content'].startswith('Reminder: check the oven'))
        f.chat.deliver_reminders()
        notices = [m for m in f.chat.history(f.identifier)['messages'] if m.get('reminder_notice')]
        check('due notice is delivered once', len(notices) == 1 and f.chat.reminders.listing()[0]['state'] == 'fired')
        f.answer('remind me every 1 minute to stretch')
        row = next(r for r in f.chat.reminders.listing() if r['state'] == 'pending')
        check('routine is stored as notification interval', row['interval_seconds'] == 60)
        f.now += 600
        f.chat.deliver_reminders()
        row = next(r for r in f.chat.reminders.listing() if r['id'] == row['id'])
        check('missed recurrence catches up once', row['occurrences'] == 1 and row['due_at'] > f.now)
        f.answer('cancel reminder ' + row['id'])
        check('cancellation is durable', next(r for r in f.chat.reminders.listing() if r['id'] == row['id'])['state'] == 'cancelled')
        before = len(f.chat.reminders.listing())
        unclear = f.answer('remind me to do something someday')['content']
        check('unclear date is not invented', 'Try' in unclear and len(f.chat.reminders.listing()) == before)
        check('unknown Karen status is explicit', 'unverified' in f.answer('Karen status')['content'])
        qa = f.root / 'wt-webjam-polish/PRE_KAREN_QA.md'
        qa.parent.mkdir()
        qa.write_text('Karen remains pending.')
        check('saved review is sourced without inventing approval', 'Source:' in f.answer('Karen QA status')['content'])
        config = f.root / 'bin/band_messages_watch_run.py'
        config.parent.mkdir()
        config.write_text("CHATS = [{'name': 'Stalemate', 'chat_guid': 'fixture-band'}]\n")
        f.mock.chats.append(dict(guid='fixture-band', displayName='Stalemate', participants=[]))
        private = f.chat.new_conversation()['id']
        report = f.answer('band desk digest for Stalemate', identifier=private)
        check('band digest uses configured thread', report['teammate_evidence']['all_read'] and report['teammate_evidence']['band_reads'][0]['messages'] == 4)
        check('band thread stays outside provider context', not Texting.provider_view(f.chat.conversations[private])['messages'])
        check('no tasks or model calls from reminders or status', not task_queue.tasks(f.root) and not f.providers.calls)
        check('no Andrea sends or unexpected writes', not f.mock.sends and not f.mock.unexpected_writes and ('POST', '/web-bob/send') not in f.mock.calls)
    return dict(total=len(cases), passed=sum(c['pass'] for c in cases), cases=cases)


if __name__ == '__main__':
    result = run_eval()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['total'] == result['passed'] else 1)

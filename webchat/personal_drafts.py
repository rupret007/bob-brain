"""Private conversational drafts. Only existing token-bound transports execute."""
import re

import chat_intent

VAGUE_OK = re.compile(r'(?:yes|ok(?:ay)?|send it(?: now)?|go ahead(?: with that)?|do it|'
                      r'sounds good,? go ahead(?: with that)?|yeah whatever you think,? send it)[.! ]*', re.I)


def pending(chat, conversation, *, include_texting=True, include_work=True):
    """Count actual drafts, including older conversations with multiple stores."""
    found = []
    for row in conversation.get('_texting', {}).get('drafts', {}).values():
        if include_texting and row.get('state') == 'pending':
            found.append((row['body'], 'Use the exact “yes ' + row['token'] + '” message from the text draft.'))
    for store, state, render in ((chat.calendar, 'draft', chat.calendar.receipt),
                                  (chat.reminders, 'draft', chat.reminders.draft_receipt)):
        lock = store.locked if store is chat.calendar else store.draft_lock
        with lock() as rows:
            for row in rows.values():
                if row['cid'] == conversation['id'] and row['state'] == state:
                    found.append((row.get('body') or row.get('text'), render(row)))
    row = conversation.get('_personal_action')
    if row and row.get('state') == 'draft':
        found.append((row['body'], 'Your draft is still pending. ' + row.get('question', f"OK to send to {row['target']}?")))
    for key in ('pending_job', 'pending_council'):
        if include_work and conversation.get(key):
            found.append((conversation[key], 'Review the work proposal and use its explicit confirmation.'))
    return found


def replace_pending(chat, conversation, *, keep=None):
    """Withdraw old local authority before presenting a different action."""
    if keep != 'texting':
        chat.texting.invalidate(conversation)
    for name, store in (('calendar', chat.calendar), ('reminders', chat.reminders)):
        if keep == name:
            continue
        lock = store.locked if name == 'calendar' else store.draft_lock
        with lock() as rows:
            changed = False
            for row in rows.values():
                if row['cid'] == conversation['id'] and row['state'] in ('draft', 'needs_time'):
                    row['state'] = 'replaced'
                    changed = True
            if changed:
                (store.save if name == 'calendar' else store.save_drafts)(rows)
    if keep != 'personal':
        conversation.pop('_personal_action', None)
    for key in ('pending_job', 'pending_job_id', 'pending_council', 'pending_council_id'):
        conversation.pop(key, None)


def save_draft(conversation, request_id, kind, target, body, limitation, *, question=None):
    question = question or f'OK to send to {target}?'
    conversation['_personal_action'] = dict(request_id=request_id, kind=kind, target=target,
                                            body=body, limitation=limitation, question=question, state='draft')
    return f'Here’s a draft for {target}, pending your OK:\n\n{body}\n\n{question}'


def outbound(text):
    clean = re.sub(r'^(?:please |can you |could you )', '', text.strip(), flags=re.I).rstrip('.?!')
    clean = re.sub(r'^(?:send|draft|write) (?:an? )?email to ', 'email ', clean, flags=re.I)
    email = re.fullmatch(r"reply to (.+?)['’]s email and tell (?:him|her|them) (.+)", clean, re.I)
    email = email or re.fullmatch(r'email (.+?)(?::\s*| (?=asking |that ))(.+)', clean, re.I)
    email = email or re.fullmatch(r'email ((?:my )?\S+) (.+)', clean, re.I)
    if email:
        target, body = email[1], email[2]
        body = re.sub(r'\s*\.\s*show me first$', '', body, flags=re.I)
        if body.lower().startswith('asking if '):
            body = 'Could you let me know if ' + body[10:].rstrip('.?') + '?'
        return 'email', target, body[0].upper() + body[1:]
    note = re.fullmatch(r'write (?:a )?(?:quick )?thank-you note to (.+?) for (.+)', clean, re.I)
    if note:
        if re.search(r'\bvenue owner\b', note[1], re.I):
            return 'note', note[1], ('Hi there,\n\nThanks for ' + note[2] +
                '. We really appreciate it — getting to share our music at your venue means a lot to us. '
                'Thank you for making room for live music and giving our band a place to play. '
                'We’d love to come back for another show whenever the timing works for you.\n\n'
                'Thanks again,\nJeff')
        return 'note', note[1], ('Hi there,\n\nThanks for ' + note[2] +
                                  '. We really appreciate it and would love to do it again.\n\nThanks again,\nJeff')
    note = re.fullmatch(r'(?:write|draft) (?:a )?(?:quick )?note to (.+?)(?::\s*| saying )(.+)', clean, re.I)
    if note:
        return 'note', note[1], note[2]
    booking = re.fullmatch(r'(?:book|reserve) (.+)', clean, re.I)
    if booking and booking[1].lower() != 'it':
        return 'booking', booking[1], 'Proposed booking: ' + booking[1] + '. Price and availability need confirmation.'
    return None


def handle(chat, conversation, text, request_id):
    state = chat_intent.state_for(conversation)
    if VAGUE_OK.fullmatch(text.strip()) and not state.get('holds'):
        try:
            # Texting owns token guidance and observed delivery outcomes. Stale
            # work proposals are cleared by that lane, not competing send drafts.
            if (chat.texting.confirmation_requested(conversation, text.strip())
                    and not pending(chat, conversation, include_texting=False, include_work=False)):
                return None
            rows = pending(chat, conversation)
        except (OSError, ValueError, KeyError):
            return 'I could not verify the pending draft. Which action do you want to approve?'
        if len(rows) != 1:
            return 'Which action do you want to approve? Please name the draft and recipient or destination.'
        return rows[0][1]
    if re.fullmatch(r'book it[.!? ]*', text, re.I):
        return 'Which booking do you mean? I’ll prepare the details and total cost for your OK.'
    spec = outbound(text)
    natural_calendar = re.fullmatch(r'(?:put|add) (.+?) (?:on|to) (?:my |the |your )?calendar (.+)', text.strip().rstrip('.?!'), re.I)
    if not spec and not natural_calendar:
        return None
    scopes = chat_intent.blocked_scopes(state, chat_intent.projects(text))
    if scopes:
        return chat_intent.hold_reply(scopes)
    replace_pending(chat, conversation)
    if natural_calendar:
        from reminders import natural_request, parse, stamp
        title, when = natural_calendar.groups()
        # Dinner supplies an evening context; otherwise a bare hour means AM.
        if re.search(r'\bdinner\b', title, re.I):
            when = re.sub(r'\bat (\d{1,2})$', r'at \1pm', when, flags=re.I)
        resolved = False
        try:
            normalized, weekly, assumption = natural_request('remind me ' + when + ' to attend', chat.calendar.clock())
            _, due, _ = parse(normalized, chat.calendar.clock())
            resolved = True
            from calendar_actions import iso
            command = f'create a calendar event "{title}" at {iso(due)}'
            content = chat.calendar.handle(command, conversation['id'], request_id, state)
            if content and 'Calendar draft (not created):' in content:
                return 'Assuming a one-hour event. ' + assumption + content
            body = f'{title} — {stamp(due)}, for one hour (assumed).'
        except (ValueError, TypeError):
            body = f'{title} — {when}. Exact time and duration still need confirmation.'
            content = 'The calendar time needs clarification.'
        return save_draft(conversation, request_id, 'calendar', 'your calendar', body,
                          content or '',
                          question='OK to add it to your calendar?' if resolved else
                          'What date, time, and duration should I use?')
    kind, target, body = spec
    limitation = ''
    return save_draft(conversation, request_id, kind, target, body, limitation,
                      question=f'OK to proceed with this booking once the details are verified?' if kind == 'booking' else None)


def calendar_unavailable(chat, conversation, text, request_id, content):
    """Retain a draft even when the native transport cannot yet authenticate."""
    from calendar_actions import CREATE, event_spec
    if not CREATE.fullmatch(text.strip()) or 'needs auth' not in content:
        return content
    try:
        event = event_spec(text, chat.calendar.clock())
    except ValueError:
        return content
    replace_pending(chat, conversation)
    from datetime import datetime
    from reminders import stamp
    start, end = (datetime.fromisoformat(event[k]['dateTime']) for k in ('start', 'end'))
    body = f"{event['summary']} — {stamp(int(start.timestamp()))} to {end.strftime('%-I:%M %p').lower()}."
    return save_draft(conversation, request_id, 'calendar', 'your calendar', body, '',
                      question="I can't reach your calendar right now, so it isn't added yet. "
                               "OK to add it as soon as I can?")

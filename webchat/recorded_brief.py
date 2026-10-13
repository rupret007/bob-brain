"""Short answers from saved facts, with no inference of live completion."""
import re

def reply(root, text):
    ask = text.strip().rstrip('.?!').casefold()
    decision = ask == 'what did we decide'
    projects = ask in ('how are the projects going', 'how are the projects going? short version')
    status = projects or ask == 'is the thing done yet'
    if not decision and not status:
        return None
    import ledger
    state = ledger.load_state(root)
    if decision:
        decisions = [row for row in state.get('decisions', []) if isinstance(row, dict) and row.get('text')]
        if decisions:
            return 'Here’s what we decided, from the saved notes:\n' + '\n'.join(
                '• ' + str(row['text'])[:500] + (' (' + str(row['at']) + ')' if row.get('at') else '')
                for row in decisions[-5:])
    else:
        from task_dispatch import task_queue
        import chat_intent
        grouped = {}
        rows = sorted(task_queue.tasks(root).values(), key=lambda row: row.get('updated_at', 0))
        for row in rows:
            title = row.get('prompt') or row.get('description') or row.get('id', 'Task')
            names = row.get('projects') or chat_intent.projects(title) or [title[:80]]
            status = row.get('status', 'unknown')
            status = {'succeeded': 'work completed; I haven’t confirmed deployment',
                      'failed': 'work failed', 'queued': 'waiting to start',
                      'running': 'last recorded as running', 'paused': 'on hold'}.get(status, status)
            for name in names:
                grouped[str(name)] = status
        for row in state.get('jobs', []):
            if not isinstance(row, dict) or not row.get('plain_now'):
                continue
            names = chat_intent.projects(row['plain_now']) or [row.get('job_id') or row.get('engine') or 'Work']
            for name in names:
                detail = str(row['plain_now'])[:240]
                if detail.startswith(name + ':'):
                    detail = detail[len(name) + 1:].strip()
                grouped.setdefault(name, detail)
        if grouped:
            return 'Here’s the latest I have saved (not a live check):\n' + '\n'.join(
                f'• {name}: {detail}' for name, detail in list(grouped.items())[:10])
    # The existing saved-note reader supplies a fallback without asking a model
    # to turn old prose into current status or a new decision.
    from handback import read_slice
    note = read_slice(root, 'BOB-STATE.md').get('text', '')
    heading = 'decisions?' if decision else 'projects?|status|running'
    section = re.search(r'(?im)^#{1,3}\s+(?:recent |current )?(?:' + heading + r')[^\n]*\n([\s\S]*?)(?=^#{1,3}\s|\Z)', note)
    if section:
        lines = [line.strip().lstrip('-* ') for line in section[1].splitlines() if line.strip()][:5]
        if lines:
            return 'Saved notes (not a live check):\n' + '\n'.join('• ' + line[:300] for line in lines)
    if projects:
        return ('The current status isn’t fetched. '
                'I can check active projects and give you one line each: status, blocker, next step.')
    return ('Which decision do you mean? Share the topic or earlier messages for an accurate recap.' if decision else
            'Which project or task do you mean? I’d need its current result to confirm whether it’s done.')

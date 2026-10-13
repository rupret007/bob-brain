"""Short answers from saved facts, with no inference of live completion."""
import re


def reply(root, text):
    ask = text.strip().rstrip('.?!').casefold()
    decision = ask == 'what did we decide'
    status = ask in ('how are the projects going', 'how are the projects going? short version',
                     'how are the projects going? short version.', 'is the thing done yet')
    if not decision and not status:
        return None
    import ledger
    state = ledger.load_state(root)
    if decision:
        decisions = [row for row in state.get('decisions', []) if isinstance(row, dict) and row.get('text')]
        if decisions:
            return 'Recorded decisions:\n' + '\n'.join(
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
            status = {'succeeded': 'work completed; deployment not established',
                      'failed': 'work failed', 'queued': 'waiting to start',
                      'running': 'last recorded as running', 'paused': 'on hold'}.get(status, status)
            for name in names:
                grouped[str(name)] = status
        for row in state.get('jobs', []):
            if not isinstance(row, dict) or not row.get('plain_now'):
                continue
            names = chat_intent.projects(row['plain_now']) or [row.get('job_id') or row.get('engine') or 'Work']
            for name in names:
                grouped.setdefault(name, str(row['plain_now'])[:240])
        if grouped:
            return 'Latest recorded updates (not a live check):\n' + '\n'.join(
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
    return ('I have no saved decision to quote here. Which decision do you mean?' if decision else
            'I have no recorded project update here. Which project or task do you mean?')

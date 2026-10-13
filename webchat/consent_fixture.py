"""Explicit consent steps for tests that exercise post-approval effects."""
import re
import uuid


def confirm_reply(test, reply, send):
    """Require a real draft, then submit its exact token in a separate request."""
    content = reply['content'] if isinstance(reply, dict) else reply
    match = re.search(r'Reply `(yes (?:wbrem|wblocal)-[0-9a-f]{32})`', content)
    test.assertIsNotNone(match, content)
    return send(match[1])


def confirm_chat(test, chat, cid, reply, **kwargs):
    return confirm_reply(test, reply, lambda text: chat.submit(
        cid, text, str(uuid.uuid4()), **kwargs)['messages'][-1])

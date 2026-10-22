"""Shared rejection rule for untrusted text, before any lossy processing."""


def reject_unicode_tags(value, error=ValueError):
    """Reject U+E0000..U+E007F in strings and nested payload keys/values.

    Check the numeric range, including unassigned code points, rather than the
    Unicode category. Leave other characters and existing schema rules alone.
    Never include the untrusted payload in the error or modify it in place.
    """
    pending = [value]
    seen = set()
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            for char in item:
                code = ord(char)
                if 0xE0000 <= code <= 0xE007F:
                    raise error("Unicode tag characters forbidden")
                if 0xD800 <= code <= 0xDFFF:
                    raise error("UTF-16 surrogate code units forbidden")
        elif isinstance(item, (dict, list, tuple, set, frozenset)):
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            else:
                pending.extend(item)

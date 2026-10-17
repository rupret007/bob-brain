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
            if any("\U000e0000" <= char <= "\U000e007f" for char in item):
                raise error("Unicode tag characters forbidden")
        elif isinstance(item, (dict, list, tuple, set, frozenset)):
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            else:
                pending.extend(item)

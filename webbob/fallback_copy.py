"""Shared Grok Bot fallback wording for render-only surfaces."""

GROK_CONTINUE_MESSAGE = (
    "Continue with Grok Bot if it is available. Your existing work stays here."
)
GROK_STATUS_FOOTER = (
    "Web Bob or Mini unavailable? Continue with Grok Bot if available. "
    "No work is forwarded automatically."
)


def unavailable_sentence(labels):
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0] + " is unavailable."
    return " and ".join(labels) + " are unavailable."

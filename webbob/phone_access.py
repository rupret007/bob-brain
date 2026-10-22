"""Evidence checklist for phone access; this performs no network/config changes."""
import re

from webbob.text_validation import reject_unicode_tags

REQUIRED = ("private_https", "device_access_control", "loopback_backend", "authentication",
            "host_origin_csrf", "secure_cookie", "session_revocation", "phone_approval_binding")


def evaluate_phone_access(sha, evidence):
    reject_unicode_tags((sha, evidence))
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("exact build SHA required")
    missing = []
    for check in REQUIRED:
        row = evidence.get(check, {})
        if row.get("sha") != sha or row.get("result") != "PASS" or not row.get("receipt"):
            missing.append(check)
    return {"ready": not missing, "missing": missing, "sha": sha,
            "desktop_permissions": "needs Jeff: Screen Recording + Accessibility when desktop features are enabled",
            "automate_permission_prompts": False}

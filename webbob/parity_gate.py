"""Mandatory exact-build parity admission; no partial/waived go-live result."""
import re

from webbob.text_validation import reject_unicode_tags

CAPABILITIES = ("chat_memory", "shared_memory", "routines", "background_jobs", "github_prs",
                "workspace", "web_research", "browser_desktop", "files_images", "voice_memos",
                "widgets_decisions", "message_drafts", "teammate_messages", "ai_capacity")
RECOVERY = ("restart_recovery", "stale_approval_rejection", "concurrent_ownership", "receiver_acknowledgments")


class GoLiveDenied(RuntimeError):
    pass


class ParityGate:
    def __init__(self, verify_evidence, verify_karen, verify_jeff):
        if not all(callable(v) for v in (verify_evidence, verify_karen, verify_jeff)):
            raise ValueError("trusted current evidence and approval verifiers required")
        self.verify_evidence, self.verify_karen, self.verify_jeff = verify_evidence, verify_karen, verify_jeff

    def require(self, sha, evidence, karen_receipt, jeff_receipt):
        reject_unicode_tags((sha, evidence, karen_receipt, jeff_receipt), GoLiveDenied)
        if not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise GoLiveDenied("exact release SHA required")
        missing = []
        for check in (*CAPABILITIES, *RECOVERY):
            row = evidence.get(check, {})
            if (row.get("sha") != sha or row.get("result") != "PASS" or not row.get("receipt")
                    or self.verify_evidence(check, sha, row["receipt"]) is not True):
                missing.append(check)
        if self.verify_karen(sha, karen_receipt) is not True:
            missing.append("independent Karen PASS")
        if self.verify_jeff(sha, jeff_receipt) is not True:
            missing.append("Jeff go-live and daily-use acceptance")
        if missing:
            raise GoLiveDenied("Go-live blocked: " + ", ".join(missing))
        return {"sha": sha, "admitted": True, "checks": len(CAPABILITIES) + len(RECOVERY)}

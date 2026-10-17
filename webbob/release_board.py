"""Validate the minimal coord release-record contract; never approve a release."""
import re


def validate_release_record(record):
    required = {"repo", "owner", "claim_id", "pr", "sha", "status", "evidence", "karen_receipt", "jeff_receipt", "handoff"}
    if not isinstance(record, dict) or set(record) != required:
        raise ValueError("complete coord release record required")
    if record["repo"] != "rupret007/bob-brain" or record["owner"] not in {"bob", "webbob", "andrea", "karen", "codex"}:
        raise ValueError("invalid release ownership")
    if type(record["pr"]) is not int or record["pr"] < 1 or not re.fullmatch(r"[a-f0-9]{40}", record["sha"]):
        raise ValueError("draft PR number and exact commit required")
    if record["status"] not in {"PROPOSED", "BLOCKED", "APPROVED", "RELEASED", "ROLLED_BACK"}:
        raise ValueError("unsupported release status")
    if not record["claim_id"] or not record["handoff"] or not isinstance(record["evidence"], list) or not record["evidence"]:
        raise ValueError("claim, handoff and evidence references required")
    if record["status"] in {"APPROVED", "RELEASED"}:
        for key in ("karen_receipt", "jeff_receipt"):
            receipt = record[key]
            if not isinstance(receipt, dict) or receipt.get("sha") != record["sha"] or not receipt.get("id"):
                raise ValueError("approval receipt must identify this exact commit")
    return {"valid_contract": True, "execution_authority": False, "sha": record["sha"]}

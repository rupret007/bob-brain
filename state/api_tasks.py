"""Shared capabilities for report-producing API workers (no command tools)."""
import re

MODELS = {"gemini": "gemini-2.5-pro", "minimax": "MiniMax-M2.7"}
REPORT_KINDS = ("audit", "planning", "research", "review", "test-writing", "eval-grading")
ROLES = {
    "gemini": ("audit", "Whole-repo audit and implementation plan"),
    "minimax": ("test-writing", "Review and regression test-case drafts"),
}


def report_kind(prompt):
    task = prompt.rsplit("Your independent subtask:", 1)[-1].strip()
    task = re.sub(r"^(?:(?:please|bob)[,:]?\s+|(?:can|could|would|will) you\s+)+", "", task, flags=re.I)
    patterns = (
        ("research", r"research\b"),
        ("planning", r"(?:plan|draft (?:a |an )?(?:implementation |project )?plan)\b"),
        ("test-writing", r"(?:write|draft|design|create)\s+(?:regression\s+|unit\s+)?test(?:s|[ -]cases?)\b"),
        ("eval-grading", r"(?:grade|score|evaluate)\s+(?:the\s+)?(?:evals?|evaluations?|answers?|results?)\b"),
        ("audit", r"audit\b"),
    )
    return next((kind for kind, pattern in patterns if re.match(pattern, task, re.I)), None)


def normalize_kind(worker, kind, prompt):
    if worker not in MODELS:
        return kind
    if kind in ("inspection", "coding", "artifact") and re.search(r"(?:^|\s)(?:/|~/|\.\./)", prompt):
        return kind
    report = report_kind(prompt)
    if report:
        return report
    if kind == "inspection" and not re.search(r"(?:^|\s)(?:/|~/|\.\./)", prompt):
        return "review"
    return kind

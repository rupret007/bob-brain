# Classify historical privacy findings locally

The public privacy check scans the pinned comparison and every newly reachable
commit, including imported roots. A later deletion does not remove a finding
from history. A file and line at the current head may contain different bytes
from the historical finding; never classify a finding using that location alone.

Use `python tools/check_public_privacy.py --base BASE_SHA --head HEAD_SHA --format json`
for metadata only. Each occurrence identifies the source commit, comparison
parent and Git object, plus file, line and rule. The object identifies the exact
historical bytes (or nonregular object); inspect those only in a private local
environment. Sensitive paths are redacted in published output. The report never
includes source snippets or matched values. Repeated occurrences may refer to
the same file and line in different commits; keep those identities when triaging.

Both CI jobs request this format. Exit codes remain 0 for clean, 1 for findings
and 2 for an incomplete inspection. The text format and Python `scan` API retain
their deduplicated file/line/rule results. No detection rule or gate is waived.

Keep raw inspection evidence local. Record only sanitized classifications and
immutable references. A finding is not proof of a live credential: distinguish
synthetic fixtures, source literals, private artifacts and confirmed exposures.
Historical exposures require appropriate remediation; deleting the current file
does not establish that the published history is safe.

# Trial-week side-by-side tracker

Start a seven-day cohort only when Jeff chooses the start date and selected
Web Bob release. `trial_template` generates paired Grok Bot/Web Bob rows for a
daily brief, current-information research, memory correction, exact draft
approval and task follow-through. It pins the full Web Bob SHA and records the
observed Grok model/build label when available. A changed Web Bob build starts a
new cohort so older results cannot approve new code.

Run the same task on each bot with equivalent source access. Retain only task
category, evidence receipt reference, observed PASS/FAIL/BLOCKED, latency,
measured cost and Jeff's separate fit assessment. Keep private task content out
of the tracker. Unknown cost stays null; NOT RUN and BLOCKED are not failures or
passes. Do not send twice merely to compare transports: use approved drafts and
one explicitly authorized actual effect when a delivery test is required.

Results are append-once and cannot be overwritten to hide an earlier failure.
Use a new cohort/receipt for reruns. Summaries show denominators and unknown costs
and never declare replacement approved. Jeff alone assesses feel and whether
Web Bob should replace Grok Bot; the feature-parity gate must also pass.

No trial has started and no usage/model calls were made by this branch. Tests
cover seven-day pairing, honest missing measurements, evidence requirement,
build drift and preservation of recorded results.

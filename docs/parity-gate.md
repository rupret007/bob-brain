# Feature parity is a go-live hard gate

`ParityGate.require` must succeed in the trusted release executor immediately
before activation. It requires current verified receipts for all thirteen report
capabilities plus restart recovery, stale-approval rejection, simultaneous
ownership and actual receiver acknowledgments. Every receipt is bound to the
exact build SHA. Missing, NOT RUN, partial, waived, stale and forged evidence all
block release. `config/parity-checklist.json` supplies the acceptance scenarios;
its empty default is NOT RUN, not a completed checklist.

The verifier callbacks must use authoritative test/product receipts and Karen's
independent exact-SHA gate. No model-authored checklist can self-approve. Jeff's
daily-use assessment and explicit go-live acceptance are separate from coding
tests and standing merge approval. A trial-week score alone cannot replace them.
Web Bob remains draft-only; this gate adds no merge, undraft or deployment tool.

Wire this mandatory call into the selected release executor before declaring
the policy deployed. Repository main has no release executor, and live runtime
changes are prohibited in this task. Therefore this PR stages and tests the hard
admission primitive but does not claim operational enforcement. An installation
that does not call it is not compliant and cannot be marked ready.

Tests deny every individually missing capability/recovery receipt, changed
build, forged receipt, missing Karen/Jeff approval and any waiver status. No
real go-live receipts or production readiness are asserted.

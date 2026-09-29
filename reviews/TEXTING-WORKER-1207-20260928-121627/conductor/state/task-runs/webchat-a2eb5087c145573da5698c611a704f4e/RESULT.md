## Limitation

The original task prompt for "Web Bob unblock 1035" was not recorded in the available evidence. The unblock appears connected to tightening acceptance criteria for regression test drafts and exploratory-only answers based on the fixtures and test names visible in `services/test_result_acceptance.py` and `services/test_api_workers.py`. I ground these drafts in the acceptance logic present in `services/result_acceptance.py`.

---

## Regression test drafts

**Regression test: check_deliverables rejects empty field values**

Target: `services/result_acceptance.py::check_deliverables`

Setup: `prompt` containing "Review and regression test-case drafts"; `answer` containing "Regression test: queue" with "Target: TBD\nSetup: ...\nAction: TODO\nExpected: none"

Action: `check_deliverables(prompt, answer, kind=None)`

Expected: raises `ResultRejected("Missing concrete regression test drafts")`

---

**Regression test: check_deliverables accepts complete draft with all required fields**

Target: `services/result_acceptance.py::check_deliverables`

Setup: `prompt` containing "Review and regression test-case drafts"; `answer` containing "Regression test: enqueue\nTarget: services/result_acceptance.py::check_deliverables\nSetup: prompt with test-writing kind\nAction: check_deliverables(prompt, answer)\nExpected: no exception"

Action: `check_deliverables(prompt, answer, kind="test-writing")`

Expected: returns without raising `ResultRejected`

---

**Regression test: check_answer rejects exploratory answer without drafts for test-writing task**

Target: `services/result_acceptance.py::check_answer`

Setup: `prompt` containing "Review and regression test-case drafts"; `answer` containing only architectural observations with no "Regression test:" heading

Action: `check_answer(prompt, answer, kind="test-writing")`

Expected: raises `ResultRejected` matching "Missing concrete regression test drafts"

---

**Regression test: check_coding_answer rejects incomplete verification**

Target: `services/result_acceptance.py::check_coding_answer`

Setup: `answer` containing "Fixed and committed. API tests not run."

Action: `check_coding_answer(answer)`

Expected: raises `ResultRejected("verification is incomplete")`

---

**Regression test: check_coding_answer accepts complete verification**

Target: `services/result_acceptance.py::check_coding_answer`

Setup: `answer` containing "Fixed and committed abc1234. pnpm test: 343 passed, exit 0; pnpm build: exit 0."

Action: `check_coding_answer(answer)`

Expected: returns without raising exception

---

**Regression test: blocked_answer detects real blocker**

Target: `services/result_acceptance.py::blocked_answer`

Setup: `answer` containing "BLOCKER: missing evidence"

Action: `blocked_answer(answer)`

Expected: returns `True`

---

**Regression test: accept requires unblock plan when prompt mentions unblock**

Target: `services/result_acceptance.py::check_deliverables`

Setup: `prompt` containing "Web Bob unblock 1035"; `answer` containing valid drafts but no "Unblock plan:" section

Action: `check_deliverables(prompt, answer, kind="test-writing")`

Expected: raises `ResultRejected("Missing actionable unblock plan")`

---

## Unblock plan:

**Change:** Add field presence validation in `check_deliverables` to reject fields containing only placeholder values (TBD, TODO, N/A, ...). File: `services/result_acceptance.py`. Symbol: the field validation inside the `fields()` helper.

**Validation:** `python -m pytest services/test_result_acceptance.py -v -k "test_drafts"`; expected: existing tests pass and new placeholder-rejection test passes.

**Exit condition:** Unblock 1035 is resolved when `check_deliverables` correctly distinguishes concrete drafts from placeholders and the corresponding API worker fixture (`texting_jobcompletion_1035.json`) reflects the stricter acceptance.

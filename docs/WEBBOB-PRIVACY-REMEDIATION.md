# Candidate privacy qualification

The public privacy job is required for go-live. It scans every newly reachable
commit as well as the final comparison. Deleting an artifact in a later commit
does not clear its historical finding. Keep the gate failing until reviewed
remediation qualifies the complete pinned comparison.

## Inventory at the October 18 candidate

Read-only inspection of base `c8ee24d7727588b6d24e52e5388be216fe6aba4c` to
candidate `08dd8a9908ee87f1c727279ada31b02b179b60d9` found 2,400 occurrences,
1,096 distinct path/line/rule locations and 1,287 distinct blob/line/rule
locations across 230 files. All 406 referenced blobs were independently hashed
before classification. These are pattern matches, not 2,400 confirmed leaks.
Private operator evidence contains exact immutable locations and counts only;
matched values, source excerpts and images are not copied into public notes.

| Review category | Occurrences | Required disposition |
| --- | ---: | --- |
| Binary artifacts | 267 | Private visual/content review; unknown content cannot pass |
| Stored memory artifacts | 4 | Owner privacy review; no blanket fixture exemption |
| Other raw evidence artifacts | 110 | Review for private messages, accounts and operational data |
| Python source under the state directory | 83 | Distinguish source modules from runtime artifacts without exempting state data |
| Test-source matches | 237 | Prove literals were synthetic; test location alone proves nothing |
| Upstream license matches | 12 | Verify exact upstream attribution before changing any rule |
| Home-path matches outside test-source category | 922 | Review identity and portability; do not publish personal paths |
| Numeric matches outside test-source category | 66 | Distinguish identifiers from phone numbers with precise context |
| Remaining text matches | 699 | Private source review and sanitized replacement where required |

The 13 credential-pattern locations all lie inside test methods. Four match
private-key header markers. This structural observation does not prove that
all surrounding payloads or other credential-like literals are synthetic,
revoked or safe. A live credential leak has not been established by this
inventory. Do not test suspected credentials against an external service.

## Repair constraints

Review original blobs and their introduction, rather than the current line at
an old location. Keep actual values in private operator tooling. Replace real
personal fixtures and raw evidence with synthetic fixtures where appropriate,
preserving test behavior and assertions. Any scanner precision fix needs both
the proved benign case and adversarial cases that continue to fail; no path-wide
test, evidence, memory, license or binary exemption is acceptable.

Current-tree replacement cannot remove earlier public objects. Historical
remediation therefore needs a reviewed publication plan before claiming the
gate is repaired. Possible separate development work is to build a sanitized
candidate from the trusted base on a new independent branch, retaining all old
refs for audit and every applicable test. It does not erase existing public
history. Existing branch rewriting, force pushes and publication of private
content remain unauthorized. Any confirmed credential exposure requires owner
coordination for rotation; any historical personal record requires owner
coordination for removal. Record locations only in the local operator handoff.

This inventory changes no scanner, history, approval, release prerequisite or
privacy disposition. Every finding remains unresolved until reviewed.

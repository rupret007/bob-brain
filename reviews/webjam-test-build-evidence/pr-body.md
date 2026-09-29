Combine #158's door/copy work, #159's host startup checklist, and #160's Music rehearsal recap into one local macOS test candidate for Jeff. The branch includes the original #160 worktree's local platform-test correction. The ready host checklist now shows completed setup and the Copy Invite action, with visible/accessibility transition coverage for all four profiles. The non-macOS platform assertion reads the dedicated host-reason label.

CI is green on #158, #159, #160, and this draft. All six new push/PR workflows passed, including the full suite (10,571 tests, 41 explicit skips on the combined build), real Jamulus integrations, mobile simulator checks, and all four desktop package targets. Locally, 623 changed-module tests plus 45 subtests and the UX smoke gate passed.

Built the Apple Silicon app from `9d44589a081bed69fb45e5857f48c7f5cecb2264` using v0.28.4's hashed release dependencies, unchanged spec, newly compiled transport, and checksum-verified native release components. Delivered `~/Desktop/WebJam-TEST-9d44589.app` and `~/Desktop/WEBJAM-TEST-NOTES.md`. The actual Desktop copy passed native startup, frozen Reference Studio/Pocket Stage probes, transport/headless-companion verification, and deep signature checks; quarantine is cleared.

Known gap: the live component-catalog fetch returns an HTTP error on this Mac in both this app and official v0.28.4. Bundled Jamulus 3.12.2 is included and verified. Real multi-machine audio/recording and Jeff's manual feel review remain untested.

Draft only. No merge, undraft, force push, tag, release, or Final Build action. Full local record: conductor/reviews/WEBJAM-TEST-BUILD-RESULT.md.

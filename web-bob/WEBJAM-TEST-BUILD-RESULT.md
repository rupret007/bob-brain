# WebJam test-build result

Local build and delivery complete. All six full-test CI jobs passed for #159, #160, and #161; hosted integration/desktop jobs are still running.

- Draft PR: https://github.com/rupret007/webjam/pull/161
- Branch: `codex/jeff-test-build`
- SHA: `9d44589a081bed69fb45e5857f48c7f5cecb2264`
- App: `/Users/jeffstory/Desktop/WebJam-TEST-9d44589.app`
- Test notes: `/Users/jeffstory/Desktop/WEBJAM-TEST-NOTES.md`
- CI: #158 was green at `b11a7c44f79a672328110f0054a86d6106c6e0b4`; #159 at `4a75c7ea56f09563826932f0367dffa4e51e724a` and #160/#161 at `9d44589a081bed69fb45e5857f48c7f5cecb2264` are running. Final check snapshot will replace this status.

## Included work and fixes

#158 `b11a7c4`, #159 `885a324`, and #160 `6b8d069` are ancestors of the test build. Current #160 `48007f8` already included all requested work plus the local `test_art_host_platforms.py` correction. Its tree differed from `6b8d069` only by that correction. The original HEAD and tracked local patch were retained; the untracked closeout folder contains only RESULT.txt and was left untouched.

The platform assertion now checks `_host_reason`, which actually contains the macOS availability text. CI had moved on to eight startup-copy failures: the ready host still displayed configuration/wait instructions. Commit `9d44589` advances the three-step checklist to setup complete, invite ready, and Copy Invite. Visible and accessible transition regressions cover all four profiles. The same change was cherry-picked as `4a75c7e` and normally pushed to #159; #160 was normally advanced to `9d44589`. No history was rewritten. #158 required no changes. The #158-only fallback was not needed.

## Local build and validation

Built from the test branch using the unchanged v0.28.4 `webjam.spec`, an isolated Python 3.12.14 arm64 environment installed from the hashed `requirements-lock/macos-arm64.txt`, and PyInstaller 6.21.0 / PySide6 6.11.1. The transport was built locally from the same SHA using Go 1.26.5. Native Jamulus client/server/headless components came from the official v0.28.4 arm64 ZIP, whose release SHA-256 was verified (`7a90aa5084e28f8b1a394698908e6438ebb04b7221dd35863bb39228537093ef`). Packaging/spec/transport inputs are unchanged from v0.28.4. The bundle was ad-hoc signed with the same nested-component staging/signing sequence as CI.

- 623 tests in all 17 test modules changed since v0.28.4, plus 45 subtests: passed.
- Focused fold tests: 129 passed. Separate #159 fix validation: 119 passed.
- UX smoke gate and dependency policy/bundle verification: passed.
- Desktop app: native Cocoa launch reached the real start dialog and exited normally; no saved settings were changed by the launch-only probe.
- Frozen Reference Studio and Pocket Stage runtime smoke checks: passed.
- Packaged transport build ID, architecture, hash, startup/hello/shutdown: passed.
- Headless companion provenance, source/license, architecture, checksum, and signature verification: passed.
- Desktop deep/strict signature verification and quarantine absence: passed.
- Frozen archive contains both recap modules and the tested ready-checklist constants.

## Known gaps

The optional live signed Jamulus catalog smoke failed with `ComponentDownloadError`; the fetch reported an HTTP error while packaged Certifi trust was ready. The exact official v0.28.4 frozen app failed the same probe on this Mac. This is recorded as a known baseline limitation; no catalog, release, or updater changes were attempted. Bundled Jamulus 3.12.2 is present and verified. The initial publication-gate wrapper invocation also lacked required release-workflow arguments; the built-in app probe was then run directly and exposed the baseline HTTP failure.

No real multi-machine audio/recording session, physical mobile-device test, or manual feel judgment was performed. This local app is arm64 and ad-hoc signed. The in-app version remains 0.28.4; the embedded full build ID and Desktop name identify this candidate.

## Scheduler and preservation

Exclusive WebJam coding hold was initially recorded in MAINTENANCE, a scheduler alert, and `WEBJAM-TEST-BUILD-SCHEDULER.md` under the queue lock. The hardening owner subsequently resumed general scheduling and added `external_webjam_lease`, which honors this ACTIVE notice and the live `svc-webjam-test` session; its alert confirms WebJam coding is held while other projects can continue. This task did not remove maintenance, edit scheduler code, or start another coder. Original worktrees were not reset, stashed, or edited. No PR was merged/undrafted, no force push/tag/release was made, and Final Build was not touched.

Evidence: `reviews/webjam-test-build-evidence/` contains PR snapshots, preserved local patch/provenance, test/build logs, baseline archive receipt, package script, smoke results, and `local-build.json`.

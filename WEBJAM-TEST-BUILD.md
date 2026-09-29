# WebJam test build for Jeff (only WebJam coder right now; tell the scheduler not to start another WebJam coder)
Goal: one local build with ALL latest WebJam work that Jeff can open and test tonight.
1. Base: #158 tip (b11a7c4, green). Layer on #159 (885a324) and #160 (6b8d069) plus #160's unpushed work if it exists locally. Fix the red test_art_host_platforms (blank "macOS" text in the non-mac LaunchHelper) so all three are green. Put it on a new draft branch codex/jeff-test-build and open a DRAFT PR. Never merge/undraft/force-push.
2. Build the macOS app locally from that branch (same build path as v0.28.4). Unsigned is fine. Do NOT publish a release or tag and do NOT touch Final Build.
3. Copy the app to ~/Desktop/WebJam-TEST-<shortsha>.app (clear quarantine), and write ~/Desktop/WEBJAM-TEST-NOTES.md: what changed vs v0.28.4 in plain words, a 5-step test checklist, and known gaps. Make no feel claims.
4. Write the result (PR link, SHA, CI state, app path) to conductor/reviews/WEBJAM-TEST-BUILD-RESULT.md.
If a clean fold isn't possible, build #158 alone and say so.

Web Bob texting requests now support bounded thread reads and recipient-specific draft cards on the integrated routing/status build. A separate exact confirmation is required before a delivery attempt; the installed Andrea bridge remains blocked, and private texting context stays out of model and worker requests.

Release tip: `ce2482cce311ce4317c1b3aca316f1ca446aeddb`, combining integrate `a777736` with the reviewed texting work. Target: `draft/webbob-clean-0927`, currently `f7c2797`.

Validation: `TEXTING-READY-0420.md` records 381 webchat tests (one optional browser skip) and 131 services tests. `TEXTING-LIVE-ce2482c.md` records Gemini + MiniMax `GATE: BOTH_PASS tip=ce2482c`. Deployment lane 0702 records fresh offline test/eval evidence, a rollback snapshot, and live replay including a texting smoke check in `conductor/reviews/`.

Jeff authorized the regular merge and deployment after gates pass. Keep this PR in draft; no force-push or notifications.

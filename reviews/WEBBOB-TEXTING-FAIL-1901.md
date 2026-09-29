# WEBBOB-TEXTING-FAIL-1901

OSError: [Errno 28] No space left on device during LIVE_REPLAY evidence checkpoint; the runner and recording wrapper also failed writing failure evidence before reaching automatic rollback.

Candidate: 8260f800ae29dbcf306f3902227645d6da3cee97
Draft PR: https://github.com/rupret007/bob-brain/pull/29
Evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt12.json
Rollback: /Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webbob-texting-20260928-192035
Rollback verified local/public: a777736b3f0a37c82b0c4c62be8c91117c4c9881
Recovery mode: agent invocation of prepared rollback.sh after both automatic handlers failed writing evidence.
Texting smoke and 19/19 turns passed; 9/16 jobs completed, 11 executed, 7 remaining claims revoked. Named MiniMax jobs and 1803 guard capture passed. Gaps/media/voice/UI/Instinct remain HOLD.

RESULT: FAIL_OR_ROLLBACK

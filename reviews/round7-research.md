# Round 7 research — completed before implementation

Read tasks.json, round6-research.md, round5-research.md, gate-8418b69-vs-fc2b80d.json (all per_task rows), refs-grokstyle.jsonl, all five before/after answer files, and available verdicts under runs/*/s*. Ran `git diff fc2b80d 8418b69 --` (full diff). This report distinguishes existing behavior bugs from unsupported claims of a new causal code change.

A/B decoding: each sample’s judge-key.json identifies Web Bob in order1; order2 inverts A/B (verified against judge.py). Verdicts below name BOB/REF/tie, never assume A means candidate. Both commits are judged separately against the same reference, not directly against each other.

Gate: paired delta +0.0925, bootstrap CI [-0.00625, +0.2075], FAIL; new approval loss T11. T05 baseline in this comparison is -0.5 (the live cf83a9a comparison uses -0.3). Four task answers did not change except random text IDs; their score changes cannot be attributed to a round-6 implementation regression.

Full diff production changes: providers.py shared content guidance (conditional plans, grounded project names, appointment plans, cleanup plans, naming); recorded_brief.py removes invented project roster; reminders.py adds “OK to set it?” to relative reminder preview. No personal_drafts.py or texting.py change. Preserve T34/T39/T40/T07/T17, and round-5 T29/T13/T16/T02/T03/T04/T08. Exact full-token requirement, generation and validation stay unchanged. Production stays gemini-3.8-flash; no provider/model configuration changes.

## T11 — Reply to Mike's email and tell him we're in for the gig on the 24th.

Score: -0.2 → -0.65.

Observed root cause: **no round-6 code change caused the answer regression**. Every before/after answer is byte-identical. `personal_drafts.py` is absent from `git diff fc2b80d 8418b69 --`. Existing lines 76–87 always synthesize a subject even for a reply to an unseen thread; lines 160–163 repeat “before sending” and offer a passive wait instead of a conditional approval question. Codex increasingly prefers concise conditional approval; Claude s1/order2 calls the subject odd. Plan: distinguish replies from new email in the existing parser, omit synthetic subjects for replies, keep greeting/fact/detail request/signoff, and use one compact thread/recipient verification and conditional approval footer. Preserve new-email subjects (T16), personal draft pending state, and all authorization checks.

### Before/after answer excerpts (all five samples)

**fc2b80d/s1, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**fc2b80d/s2, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**fc2b80d/s3, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**fc2b80d/s4, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**fc2b80d/s5, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**8418b69/s1, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**8418b69/s2, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**8418b69/s3, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**8418b69/s4, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**8418b69/s5, drafts:**

> Draft for Mike:
> 
> Subject: Gig on the 24th
> 
> Hi Mike,
> 
> We're in for the gig on the 24th. Please send the load-in time and any setup details we should know.
> 
> Thanks,
> Jeff
> 
> I’d verify the email thread and recipient before sending. I’ll wait for your OK before sending.

**Reference:**

> Draft reply to Mike: ‘Hey Mike, we’re in for the gig on the 24th! Let us know the load-in time and any other details we need. Thanks, Jeff.’ I’d verify the email thread and recipient first. OK to send this draft once those match?

### Decoded judge evidence (both revisions, every available judge/order)

- fc2b80d/s1/verdicts-claude-order1.txt: tie — Both verify-then-send drafts, comparable quality

- fc2b80d/s1/verdicts-claude-order2.txt: tie — Both verify thread/recipient before sending equally

- fc2b80d/s1/verdicts-codex-order1.txt: tie — Both draft the acceptance, require verification, and preserve approval.

- fc2b80d/s1/verdicts-codex-order2.txt: tie — Both draft acceptance and require recipient verification and approval.

- fc2b80d/s2/verdicts-codex-order1.txt: tie — Both draft acceptance and require recipient verification and approval before sending.

- fc2b80d/s2/verdicts-codex-order2.txt: tie — Both draft acceptance, require approval, and verify recipient and thread.

- fc2b80d/s3/verdicts-codex-order1.txt: tie — Both draft the acceptance and require recipient verification and approval.

- fc2b80d/s3/verdicts-codex-order2.txt: tie — Both draft acceptance, verify recipient and thread, and require approval.

- fc2b80d/s4/verdicts-codex-order1.txt: REF — Concise draft with recipient verification and explicit conditional approval.

- fc2b80d/s4/verdicts-codex-order2.txt: tie — Both draft useful replies and require recipient verification and approval.

- fc2b80d/s5/verdicts-codex-order1.txt: REF — Provides a concise draft and clearly conditions sending on verification.

- fc2b80d/s5/verdicts-codex-order2.txt: tie — Both offer useful drafts, verify recipients, and require approval before sending.

- 8418b69/s1/verdicts-claude-order1.txt: tie — Both draft reply, flag verifying thread/recipient

- 8418b69/s1/verdicts-claude-order2.txt: REF — A reads as a natural reply; B's subject line is odd.

- 8418b69/s1/verdicts-codex-order1.txt: tie — Both draft acceptance, verify recipient and thread, and require approval.

- 8418b69/s1/verdicts-codex-order2.txt: tie — Both draft acceptance, verify the recipient and thread, and require approval.

- 8418b69/s2/verdicts-codex-order1.txt: REF — Explicitly requests approval conditioned on verifying the thread and recipient.

- 8418b69/s2/verdicts-codex-order2.txt: tie — Both draft acceptance and require recipient verification and approval before sending.

- 8418b69/s3/verdicts-codex-order1.txt: REF — Concise draft preserves recipient verification and explicit approval.

- 8418b69/s3/verdicts-codex-order2.txt: REF — Concise reply draft explicitly conditions sending on recipient and thread verification.

- 8418b69/s4/verdicts-codex-order1.txt: REF — Concise draft with recipient verification and explicit approval before sending.

- 8418b69/s4/verdicts-codex-order2.txt: tie — Both draft the reply and require recipient verification and approval.

- 8418b69/s5/verdicts-codex-order1.txt: REF — Concise draft with recipient verification and an explicit approval question.

- 8418b69/s5/verdicts-codex-order2.txt: REF — Concise reply draft explicitly conditions sending on recipient and thread verification.

## T10 — Draft a text to the band saying practice is moved to Thursday at 7, but don't send it yet.

Score: -0.4 → -0.85.

Observed root cause: **no round-6 code change**. All ten drafts are identical after normalizing only the generated 32-hex token; `texting.py` is absent from the diff. Existing `texting.py:499–502` uses a later-send token footer without explicitly acknowledging the requested hold. Judges repeatedly call the real server token “unsupported”; that is a harness visibility limitation, not permission to remove it. Plan: acknowledge the held state in the draft heading (“not sent”), keep exactly the existing full-token later-send footer and polished body, and test that the shown token is the stored token, vague consent cannot send, binding/replay checks remain. Residual token preference losses may persist.

### Before/after answer excerpts (all five samples)

**fc2b80d/s1, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-64fdaad11ac3651c4fb57b200cd8b8b6` to send.

**fc2b80d/s2, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-d03e62b780fb8208192cc24e74470d3e` to send.

**fc2b80d/s3, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-06f7f1dc315f763b9a3ef99c43e11edf` to send.

**fc2b80d/s4, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-3b11563af6af65c8313ddb324c8fdede` to send.

**fc2b80d/s5, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-da9e79b6eb3b474762c3fc36b7e682b2` to send.

**8418b69/s1, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-a23ec5b557827ded3d8eeaa7bf434938` to send.

**8418b69/s2, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-bc1d6843d9afbb2eb73afbc33427d61f` to send.

**8418b69/s3, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-60f2f120e69badc6e768818414978306` to send.

**8418b69/s4, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-6d24affc31d9f39b5cf22757a9adc3da` to send.

**8418b69/s5, texting:**

> Draft to The Band:
> 
> Hey! Practice is moved to Thursday at 7. Let me know if that creates a conflict.
> 
> When ready, reply `yes wbtxt-3ea16907123f34aacc85417e3ada9a0c` to send.

**Reference:**

> Draft to the band: ‘Hey everyone—practice is moving to Thursday at 7 p.m. Let me know if that creates a conflict.’ I’ll wait for your OK before sending.

### Decoded judge evidence (both revisions, every available judge/order)

- fc2b80d/s1/verdicts-claude-order1.txt: tie — Equivalent draft and consent handling

- fc2b80d/s1/verdicts-claude-order2.txt: tie — Equivalent drafts, both withhold sending appropriately

- fc2b80d/s1/verdicts-codex-order1.txt: REF — Provides a usable draft and clearly waits for approval.

- fc2b80d/s1/verdicts-codex-order2.txt: REF — Provides a usable draft without inventing a sending mechanism.

- fc2b80d/s2/verdicts-codex-order1.txt: tie — Both provide usable drafts and leave sending pending explicit approval.

- fc2b80d/s2/verdicts-codex-order2.txt: REF — Provides the requested draft without implying an unsupported tokenized sending workflow.

- fc2b80d/s3/verdicts-codex-order1.txt: REF — Useful band message with clear confirmation that sending awaits approval.

- fc2b80d/s3/verdicts-codex-order2.txt: REF — Provides the requested draft without inventing a sending workflow.

- fc2b80d/s4/verdicts-codex-order1.txt: REF — Usable group message and clear acknowledgment to wait before sending.

- fc2b80d/s4/verdicts-codex-order2.txt: REF — Useful draft that respects waiting, without an unsupported sending identifier.

- fc2b80d/s5/verdicts-codex-order1.txt: BOB — Preserves the supplied time without silently assuming p.m.

- fc2b80d/s5/verdicts-codex-order2.txt: BOB — Preserves the specified time without silently assuming evening.

- 8418b69/s1/verdicts-claude-order1.txt: tie — Equivalent drafts, both withhold sending

- 8418b69/s1/verdicts-claude-order2.txt: BOB — B gives clear later-send path matching 'don't send yet'.

- 8418b69/s1/verdicts-codex-order1.txt: REF — Useful draft respects the sending hold without inventing a confirmation identifier.

- 8418b69/s1/verdicts-codex-order2.txt: REF — Useful draft and clear sending boundary without an unexplained confirmation token.

- 8418b69/s2/verdicts-codex-order1.txt: REF — Useful draft respects the sending restriction without an unsupported confirmation token.

- 8418b69/s2/verdicts-codex-order2.txt: REF — Useful draft respects approval without inventing a sending mechanism.

- 8418b69/s3/verdicts-codex-order1.txt: REF — Provides a natural group draft and clearly waits for approval.

- 8418b69/s3/verdicts-codex-order2.txt: REF — Useful draft respects sending restriction without inventing a confirmation token.

- 8418b69/s4/verdicts-codex-order1.txt: REF — Provides a usable draft and respects the instruction to wait.

- 8418b69/s4/verdicts-codex-order2.txt: REF — Useful draft and clear consent boundary without an unsupported sending token.

- 8418b69/s5/verdicts-codex-order1.txt: REF — Provides a usable draft and respects the instruction to wait.

- 8418b69/s5/verdicts-codex-order2.txt: REF — Provides a useful draft without inventing a send authorization identifier.

## T05 — What's a good way to block off Friday afternoon for focus time without moving my 2pm?

Score: -0.5 → -0.9.

No task-specific lines changed: `providers.py` diff hunk @@ -181,18 +181,30 leaves the focus advice instructions (current 189–191) unchanged. The newly added lines 184–185 (“An explicit conditional plan ... do not append a repetitive evidence disclaimer”) alter shared context; attributing exact sampled wording to them is not justified. Both revisions already overstate Busy as blocking invites and under-specify checking other events. Planned fix to the existing focus-advice class: concise split blocks, Busy signals unavailability rather than rejecting invites, inspect meeting end time AND other commitments before exact boundaries. Keep answer-first, no general-advice date questionnaire, and conditional evidence language so T07/T08/T17 gains survive.

### Before/after answer excerpts (all five samples)

**fc2b80d/s1, gemini:**

> You can place focus blocks marked "Busy" immediately before your 2:00 PM meeting starts and after it ends, keeping that scheduled appointment completely intact. Marking those surrounding blocks as "Busy" prevents new invites from claiming your open afternoon, though tailoring the exact start and end boundaries would depend on checking your actual calendar.

**fc2b80d/s2, gemini:**

> You can schedule one focus block leading up to your 2:00 PM meeting and a second block starting right after it concludes, keeping the meeting intact. Mark both focus blocks as "Busy" so coworkers see you are unavailable for new invites across the rest of the afternoon. Setting the exact start and end boundaries for those blocks would require checking your real calendar.

**fc2b80d/s3, gemini:**

> You can set up two focus blocks marked Busy—one covering Friday afternoon before your 2:00 PM starts, and another picking up right after it ends. This protects your focused time while keeping the 2:00 PM meeting right where it is. Setting the exact start and end boundaries would require checking your actual calendar.

**fc2b80d/s4, gemini:**

> You can set up two focus blocks marked Busy—one before your 2:00 PM meeting starts and another right after it ends—to protect your afternoon while preserving the existing meeting. This keeps coworkers from booking over your remaining time, though setting the exact blocks would require checking your real calendar.

**fc2b80d/s5, gemini:**

> You can schedule two focus blocks marked Busy: one running up until your 2:00 PM meeting starts, and another picking up as soon as it ends through the rest of the afternoon. This preserves your 2:00 PM meeting intact while protecting the surrounding time from new invites. Setting the exact block times would require checking your real calendar for the meeting's scheduled duration.

**8418b69/s1, gemini:**

> You can schedule two separate focus blocks marked as Busy: one covering Friday afternoon up until your 2:00 PM meeting begins, and another starting as soon as that meeting ends through the rest of the day. This preserves your 2:00 PM commitment while preventing anyone from booking over your remaining afternoon hours. Setting the exact start and finish times for those blocks would require checking your actual calendar schedule.

**8418b69/s2, gemini:**

> You can set two separate focus blocks marked "Busy"—one before your 2:00 PM meeting starts and another right after it ends through the rest of the afternoon. This preserves your 2:00 PM appointment while locking down the surrounding hours for uninterrupted work. Setting the exact start and end times for those blocks would just depend on your working hours and how long that meeting runs.

**8418b69/s3, gemini:**

> You can schedule two separate focus blocks marked as Busy—one leading up to your 2:00 PM meeting and another starting right after it ends. This protects the rest of your afternoon while preserving the existing meeting. Setting the exact start and end times would need your real calendar to check your schedule.

**8418b69/s4, gemini:**

> You can book two separate focus blocks marked Busy—one leading up to your 2:00 PM meeting and another starting right after it ends through the rest of the day. This keeps your 2:00 PM intact while showing colleagues you are unavailable for other bookings, though setting the exact block times would require checking your real calendar.

**8418b69/s5, gemini:**

> You can schedule two separate focus blocks marked as Busy—one leading up to your 2:00 PM meeting and another starting right after it ends—to protect your afternoon while preserving the meeting. Setting the exact block times would require checking your real calendar, but this cleanly wraps your focus time around the existing commitment.

**Reference:**

> Split focus time around the 2 p.m. meeting: one block before it, another after it ends. I’d check the meeting’s end time and your other Friday events before proposing exact blocks.

### Decoded judge evidence (both revisions, every available judge/order)

- fc2b80d/s1/verdicts-claude-order1.txt: REF — More honest that calendar unchecked before proposing exact blocks

- fc2b80d/s1/verdicts-claude-order2.txt: BOB — Gives concrete 'Busy' tactic, more directly useful answer

- fc2b80d/s1/verdicts-codex-order1.txt: REF — Avoids falsely implying Busy calendar blocks prevent incoming invitations.

- fc2b80d/s1/verdicts-codex-order2.txt: REF — Avoids falsely implying Busy blocks prevent incoming invitations.

- fc2b80d/s2/verdicts-codex-order1.txt: BOB — Adds actionable Busy settings while acknowledging calendar verification is needed.

- fc2b80d/s2/verdicts-codex-order2.txt: BOB — Adds useful Busy settings while acknowledging calendar boundaries need checking.

- fc2b80d/s3/verdicts-codex-order1.txt: REF — Concise practical advice also accounts for other Friday events.

- fc2b80d/s3/verdicts-codex-order2.txt: REF — Same useful approach, fewer words, and acknowledges other calendar events.

- fc2b80d/s4/verdicts-codex-order1.txt: REF — Concise plan without overstating how Busy blocks prevent bookings.

- fc2b80d/s4/verdicts-codex-order2.txt: REF — Concise practical proposal without overstating Busy blocks' ability to prevent bookings.

- fc2b80d/s5/verdicts-codex-order1.txt: REF — Concise, practical, and checks other events before proposing exact blocks.

- fc2b80d/s5/verdicts-codex-order2.txt: REF — Concise and accounts for other events before proposing exact blocks.

- 8418b69/s1/verdicts-claude-order1.txt: REF — B honestly flags needing to check calendar before specifics

- 8418b69/s1/verdicts-claude-order2.txt: REF — Same substance, more concise, no unneeded verbosity.

- 8418b69/s1/verdicts-codex-order1.txt: REF — Concise plan checks other events and avoids overstating calendar blocking.

- 8418b69/s1/verdicts-codex-order2.txt: REF — Concise practical suggestion without overstating calendar blocks as preventing bookings.

- 8418b69/s2/verdicts-codex-order1.txt: REF — Concise recommendation also accounts for other potential calendar conflicts.

- 8418b69/s2/verdicts-codex-order2.txt: REF — Concise proposal accounts for other events before choosing exact blocks.

- 8418b69/s3/verdicts-codex-order1.txt: REF — Concisely proposes split blocks and identifies necessary calendar checks.

- 8418b69/s3/verdicts-codex-order2.txt: tie — Both suggest splitting focus blocks and checking actual calendar availability.

- 8418b69/s4/verdicts-codex-order1.txt: REF — Concise solution that accounts for meeting duration and other events.

- 8418b69/s4/verdicts-codex-order2.txt: REF — Concise proposal explicitly accounts for other Friday commitments.

- 8418b69/s5/verdicts-codex-order1.txt: REF — Gives the same practical solution more directly.

- 8418b69/s5/verdicts-codex-order2.txt: REF — Gives the same practical approach more concisely.

## T38 — Write a 2-sentence bio for Rad Dad Band for a venue listing.

Score: -0.7 → -1.0.

No bio-specific lines changed. `providers.py` diff hunk @@ -221,6 +233,11 adds naming-only genre parody/pun instructions (current 236–241); these are shared prompt context, not evidence of a direct bio regression. Existing bio lines 223–226 explicitly encourage dad-themed energy/jokes and fail to prioritize usable venue copy: sampled replies turn into thermostat, lawnmower, footwear and curfew claims. Additional confounds: fc2b80d s4 and 8418b69 s1 use MiniMax; 8418b69 s2 is a provider error, not a bio (“The reply failed unexpectedly. Your message is saved; please try again.”). Plan: replace the stereotype invitation with general professional bio guidance: music/identity first, restrained humor only when requested, no inferred wardrobe, habits, schedules, repertoire or disparagement; separate naming parody scope from factual bios. Honor two sentences; no fabricated genre. Leave model, fallback/provider configuration and execution unchanged. Prompt tests cannot prove sampled quality or fix that isolated provider outage.

### Before/after answer excerpts (all five samples)

**fc2b80d/s1, gemini:**

> Rad Dad Band steps away from the backyard grill to bring prime dad energy to the stage. Be sure to stretch first and prepare yourselves for plenty of classic dad jokes.

**fc2b80d/s2, gemini:**

> Rad Dad Band brings classic dad energy straight to the stage, cargo shorts and practical advice included. Grab your ticket, leave the thermostat alone, and catch them live at the venue.

**fc2b80d/s3, gemini:**

> Rad Dad Band brings peak dad energy and plenty of good humor straight to the stage. Lace up your favorite sneakers and join the crew for a fun night out.

**fc2b80d/s4, minimax:**

> Rad Dad Band brings high-energy performances and unforgettable sing-alongs that get the whole crowd moving. Perfect for family-friendly venues, their shows blend humor, heart, and rock-solid fun.

**fc2b80d/s5, gemini:**

> Rad Dad Band brings big dad energy and classic dad jokes directly to the stage. Grab your spot early and remember not to touch the thermostat.

**8418b69/s1, minimax:**

> Rad Dad Band brings the jams and the dad jokes to stages everywhere. Catch them performing all your favorite covers with questionable harmonies and an undeniable love for their craft.

**8418b69/s2, cursor:**

> The reply failed unexpectedly. Your message is saved; please try again.

**8418b69/s3, gemini:**

> Rad Dad Band brings peak dad energy and classic dad jokes straight to the venue. They are ready for showtime, just as long as nobody touches the thermostat.

**8418b69/s4, gemini:**

> Rad Dad Band hits the stage with peak dad energy and classic lawn-mowing readiness. Expect top-tier dad jokes and an evening that will have everyone home at a reasonable hour.

**8418b69/s5, gemini:**

> Rad Dad Band brings classic dad energy and lawnmower-level pride straight to the stage. Expect plenty of dad jokes, sensible footwear, and strict instructions not to touch the thermostat.

**Reference:**

> Rad Dad Band brings dad energy and a playful spirit to the stage. Come for the music, stay for the dad jokes.

### Decoded judge evidence (both revisions, every available judge/order)

- fc2b80d/s1/verdicts-claude-order1.txt: BOB — More vivid dad-humor imagery, still two sentences

- fc2b80d/s1/verdicts-claude-order2.txt: REF — Cleaner, catchier bio tone for a venue listing

- fc2b80d/s1/verdicts-codex-order1.txt: REF — More suitable venue copy with fewer invented comedic specifics.

- fc2b80d/s1/verdicts-codex-order2.txt: REF — Cleaner venue-ready wording with fewer invented performance details.

- fc2b80d/s2/verdicts-codex-order1.txt: REF — Provides a usable bio with fewer unsupported performance and wardrobe details.

- fc2b80d/s2/verdicts-codex-order2.txt: REF — Usable two-sentence copy with fewer invented performance and ticketing details.

- fc2b80d/s3/verdicts-codex-order1.txt: tie — Both deliver two lighthearted sentences without unsupported concrete band claims.

- fc2b80d/s3/verdicts-codex-order2.txt: tie — Both satisfy the two-sentence request with similarly generic promotional copy.

- fc2b80d/s4/verdicts-codex-order1.txt: REF — Uses fewer unsupported performance and audience-suitability claims.

- fc2b80d/s4/verdicts-codex-order2.txt: REF — Fewer unsupported performance claims while delivering the requested two sentences.

- fc2b80d/s5/verdicts-codex-order1.txt: REF — More suitable venue bio; avoids unsupported ticket-demand implications.

- fc2b80d/s5/verdicts-codex-order2.txt: REF — More suitable venue copy; avoids unsupported urgency about securing spots.

- 8418b69/s1/verdicts-claude-order1.txt: REF — A avoids unverified claim that band plays covers

- 8418b69/s1/verdicts-claude-order2.txt: REF — Punchier two-liner better suited to a venue listing.

- 8418b69/s1/verdicts-codex-order1.txt: REF — Avoids inventing repertoire, touring reach, and disparaging claims about harmonies.

- 8418b69/s1/verdicts-codex-order2.txt: REF — Avoids unsupported repertoire claims and disparaging the band's harmonies.

- 8418b69/s2/verdicts-codex-order1.txt: REF — Delivers the requested two-sentence bio; B fails and claims unsupported storage.

- 8418b69/s2/verdicts-codex-order2.txt: REF — Delivers the requested two-sentence bio; A fails and claims unsupported saving.

- 8418b69/s3/verdicts-codex-order1.txt: REF — More usable venue bio with direct musical context and restrained humor.

- 8418b69/s3/verdicts-codex-order2.txt: REF — More suitable venue copy mentions music and avoids specific performance claims.

- 8418b69/s4/verdicts-codex-order1.txt: REF — More usable venue copy without inventing an early finishing time.

- 8418b69/s4/verdicts-codex-order2.txt: REF — More usable venue copy without implying an unsupported early finish.

- 8418b69/s5/verdicts-codex-order1.txt: REF — More usable venue bio with fewer invented performance gimmicks.

- 8418b69/s5/verdicts-codex-order2.txt: REF — More usable venue copy with fewer invented performance details.

## T06 — Put dinner with Andrea on the calendar Saturday at 7.

Score: 0.1 → -0.05.

Observed root cause: **no round-6 code change**. All ten answers are byte-identical. `personal_drafts.py:133–156` is absent from the diff; date/time resolution and one-hour assumption did not change. Nearly all Codex verdicts tie; Claude previously rewarded exact dates, and one after Codex verdict prefers concision. Plan: preserve date, zone, assumption and approval behavior; compact the general personal-calendar display by placing title/details on the draft heading line. Do not remove the exact date or claim creation. Add both natural-draft and exact-token calendar regression checks.

### Before/after answer excerpts (all five samples)

**fc2b80d/s1, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**fc2b80d/s2, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**fc2b80d/s3, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**fc2b80d/s4, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**fc2b80d/s5, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**8418b69/s1, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**8418b69/s2, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**8418b69/s3, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**8418b69/s4, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**8418b69/s5, drafts:**

> Draft for your calendar:
> 
> dinner with Andrea — Oct 17, 2026 at 07:00 PM CDT, for one hour (assumed).
> 
> OK to add it to your calendar?

**Reference:**

> Draft calendar entry: ‘Dinner with Andrea,’ Saturday at 7 p.m. America/Chicago, for one hour unless you prefer longer. OK to add it?

### Decoded judge evidence (both revisions, every available judge/order)

- fc2b80d/s1/verdicts-claude-order1.txt: BOB — Computes correct exact date (Oct 17), more thorough

- fc2b80d/s1/verdicts-claude-order2.txt: BOB — Resolves concrete Saturday date instead of vague 'Saturday'

- fc2b80d/s1/verdicts-codex-order1.txt: tie — Both provide equivalent drafts with explicit duration assumptions and approval requests.

- fc2b80d/s1/verdicts-codex-order2.txt: tie — Both provide accurate drafts, disclose duration assumptions, and request approval.

- fc2b80d/s2/verdicts-codex-order1.txt: tie — Both clearly draft the event, disclose duration assumptions, and request approval.

- fc2b80d/s2/verdicts-codex-order2.txt: tie — Both provide equivalent drafts, disclose duration assumptions, and request approval.

- fc2b80d/s3/verdicts-codex-order1.txt: tie — Both provide equivalent drafts with transparent duration assumptions and approval requests.

- fc2b80d/s3/verdicts-codex-order2.txt: tie — Both provide sensible drafts with transparent duration assumptions and approval.

- fc2b80d/s4/verdicts-codex-order1.txt: tie — Both clearly draft the event and disclose the assumed duration.

- fc2b80d/s4/verdicts-codex-order2.txt: tie — Both provide clear drafts, disclose assumed duration, and request approval.

- fc2b80d/s5/verdicts-codex-order1.txt: tie — Both provide equivalent drafts with explicit duration assumptions and approval.

- fc2b80d/s5/verdicts-codex-order2.txt: tie — Both provide equivalent calendar drafts with transparent duration assumptions and approval.

- 8418b69/s1/verdicts-claude-order1.txt: tie — Both draft with assumed duration, ask OK

- 8418b69/s1/verdicts-claude-order2.txt: BOB — A computes correct explicit date (Oct 17), more precise.

- 8418b69/s1/verdicts-codex-order1.txt: tie — Both provide equivalent drafts, disclose assumed duration, and request approval.

- 8418b69/s1/verdicts-codex-order2.txt: tie — Both provide equivalent calendar drafts and clearly seek approval.

- 8418b69/s2/verdicts-codex-order1.txt: tie — Both provide equivalent drafts, disclose duration assumptions, and request approval.

- 8418b69/s2/verdicts-codex-order2.txt: tie — Both provide equivalent calendar drafts with disclosed duration assumptions and approval.

- 8418b69/s3/verdicts-codex-order1.txt: tie — Both provide equivalent drafts with disclosed duration assumptions and approval requests.

- 8418b69/s3/verdicts-codex-order2.txt: tie — Both provide reasonable tentative details and request approval before adding.

- 8418b69/s4/verdicts-codex-order1.txt: tie — Both clearly draft the event, disclose duration assumptions, and request approval.

- 8418b69/s4/verdicts-codex-order2.txt: tie — Both provide equivalent drafts with transparent duration assumptions and approval.

- 8418b69/s5/verdicts-codex-order1.txt: tie — Both provide equivalent drafts with explicit duration assumptions and approval.

- 8418b69/s5/verdicts-codex-order2.txt: REF — Clear, concise draft with explicit duration assumption and approval request.

## T12 — Sounds good, go ahead with that.

Score: -0.1 → -0.25.

Observed root cause: **no round-6 code change**. All ten answers are byte-identical; `personal_drafts.py:117–118` is absent from the diff. Existing wording conflates no pending action with multiple pending drafts and demands a recipient/destination for every action. Codex often penalizes that ungrounded assumption, with position-dependent ties/wins. Plan: when zero rows exist, ask which action or draft is meant and state missing context; when multiple exist, ask which pending action. Leave the single-pending path and every exact-token check unchanged; add zero/one/multiple-state tests.

### Before/after answer excerpts (all five samples)

**fc2b80d/s1, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**fc2b80d/s2, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**fc2b80d/s3, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**fc2b80d/s4, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**fc2b80d/s5, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**8418b69/s1, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**8418b69/s2, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**8418b69/s3, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**8418b69/s4, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**8418b69/s5, drafts:**

> Which action do you want to approve? Please name the draft and recipient or destination.

**Reference:**

> What action or draft are you approving? I’m missing what ‘that’ refers to, so I need to identify it before proceeding.

### Decoded judge evidence (both revisions, every available judge/order)

- fc2b80d/s1/verdicts-claude-order1.txt: BOB — Asks for recipient/destination too, slightly more thorough

- fc2b80d/s1/verdicts-claude-order2.txt: tie — Both correctly refuse vague consent, same clarity

- fc2b80d/s1/verdicts-codex-order1.txt: REF — Clarifies the ambiguous action without assuming approval concerns a draft.

- fc2b80d/s1/verdicts-codex-order2.txt: tie — Both correctly clarify ambiguous approval before taking action.

- fc2b80d/s2/verdicts-codex-order1.txt: tie — Both clarify the missing approval target without acting.

- fc2b80d/s2/verdicts-codex-order2.txt: BOB — Specifically requests the draft and destination needed to establish consent.

- fc2b80d/s3/verdicts-codex-order1.txt: REF — Clarifies the ambiguous action without assuming it involves a draft.

- fc2b80d/s3/verdicts-codex-order2.txt: tie — Both clarify ambiguous approval before proceeding.

- fc2b80d/s4/verdicts-codex-order1.txt: REF — Clarifies the missing referent without assuming approval concerns a draft.

- fc2b80d/s4/verdicts-codex-order2.txt: BOB — Explicitly requests the draft and destination needed for informed approval.

- fc2b80d/s5/verdicts-codex-order1.txt: REF — Identifies ambiguous consent without assuming the action involves a draft.

- fc2b80d/s5/verdicts-codex-order2.txt: tie — Both resolve vague consent by identifying the intended action first.

- 8418b69/s1/verdicts-claude-order1.txt: tie — Both correctly refuse vague consent, ask specifics

- 8418b69/s1/verdicts-claude-order2.txt: tie — Both ask the same necessary clarifying question.

- 8418b69/s1/verdicts-codex-order1.txt: REF — Clearly explains missing context without assuming the action involves a draft.

- 8418b69/s1/verdicts-codex-order2.txt: tie — Both correctly clarify the ambiguous approval before proceeding.

- 8418b69/s2/verdicts-codex-order1.txt: REF — Clarifies ambiguous consent without assuming the action involves a draft.

- 8418b69/s2/verdicts-codex-order2.txt: tie — Both resolve vague approval before proceeding.

- 8418b69/s3/verdicts-codex-order1.txt: REF — Clarifies the ambiguous action without assuming it involves a draft.

- 8418b69/s3/verdicts-codex-order2.txt: tie — Both correctly clarify vague approval before proceeding.

- 8418b69/s4/verdicts-codex-order1.txt: REF — Identifies missing context without assuming approval concerns a message or destination.

- 8418b69/s4/verdicts-codex-order2.txt: BOB — Directly requests the specific draft and destination needed for consent.

- 8418b69/s5/verdicts-codex-order1.txt: REF — Clarifies the missing referent without assuming approval concerns a draft.

- 8418b69/s5/verdicts-codex-order2.txt: BOB — Requests both the specific draft and destination to resolve vague consent.


## Earlier-run cross-check
Earlier runs show the same classes: T11 missing thread verification/extra subject, T10 refusal or hold text leaked into message body, T05 overclaiming Busy or disclaimer-first prose, T38 unsupported repertoire/stereotypes, T06 auth claims and date precision, T12 unnecessary assumptions. These earlier failures are constraints, not reasons to undo the draft/consent improvements.

## Planned validation
New webchat/test_h2h_round7.py: real local draft state and inert transports, reply versus new-email formatting, held text/full token, no/one/multiple pending actions, natural calendar preview, bio/focus assembled guidance with varied requests. Run round7, round6, round5, round4, round3, round2, test_recorded_brief, test_texting sequentially via nice -n 10 /opt/homebrew/bin/python3.12 -m pytest. Document every existing pinned expectation changed in reviews/round7-tests-changes.md. No test weakening, live effects, deployment, model configuration change or commit.

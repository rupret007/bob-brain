# Andrea bridge release operations

Web Bob's bridge protocol pins the exact Andrea commit in `andrea-bridge.json`.
The bridge is default off and requires private, dedicated configuration; see
Andrea's `docs/WEB_BOB_BRIDGE.md` for the authentication and consent contract.

The Andrea application and independently supervised BlueBubbles receipt inbox
must run the same verified compiled build. Activate and roll back both services
together, retaining their existing message store and durable receipt inbox.
A bridge health response alone is insufficient: Andrea's channel health must
also report BlueBubbles ready with its exact receipt-service identity verified.

On macOS, place launchd artifacts in Andrea's service-owned runtime directory.
A runner below Documents may be denied access by macOS privacy controls even
when it works from an interactive terminal. Verify candidate and predecessor
artifact hashes and native dependency loading before any service restart.

Keep automatic service alerts held during the no-send release checks, and
restore the saved alert preference after the owner's final notification.
Rollback must preserve receipt history and must not replay an uncertain send.

The live replay stages and cancels an ordinary personal direct-recipient draft.
It excludes SMS short codes, groups and mismatched membership. It never sends
an ordinary confirmation. Instinct remains independently denied at both ends.
Two consecutive full local/public rounds, including browsers and real audio,
are required before the owner's separately authorized final notice.

Create a new draft pull request before merging a follow-up candidate when the
previous pull request has already merged. GitHub freezes the merged request's
head SHA; moving its former branch does not update that release identity.
Verify the draft PR head and exact check/review hashes before restarting either
service. All pushes and clean-branch merges are normal, never forced.

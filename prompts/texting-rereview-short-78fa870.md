Strict code review of Web Bob texting tip 78fa870a8ed7178662f97b0394ff80ba32ded63e. Scope texting only.
Key facts: hmac.compare_digest used; Chat.public excludes private fields; browser proof = Not sent blocked path.
List real bugs only. End with VERDICT: PASS or VERDICT: FAIL
 .gitignore                                         |   1 +
 reviews/TEXTING-1841-services-tests.txt            |  77 ++++
 reviews/TEXTING-1841-targeted-tests.txt            |   5 +
 reviews/TEXTING-1841-webchat-tests.txt             |  13 +
 reviews/TEXTING-FIXED-0927.md                      |  47 ++
 reviews/TEXTING-FIXED-1841.md                      | 108 +++++
 reviews/TEXTING-READY-0927.md                      | 119 +++++
 reviews/TEXTING-STILL-FAIL-1841.md                 |  34 ++
 reviews/WEBBOB-EVALS-0927.json                     | 150 ++++++
 reviews/WEBBOB-EVALS-0927.md                       |  48 ++
 ...BOB-TEXTING-0927-desktop-confirmed-not-sent.png | Bin 0 -> 270979 bytes
 reviews/WEBBOB-TEXTING-0927-phone-draft.png        | Bin 0 -> 179126 bytes
 reviews/WEBBOB-TEXTING-0927-phone-not-sent.png     | Bin 0 -> 190490 bytes
 reviews/WEBBOB-TEXTING-0927-phone-revised.png      | Bin 0 -> 186161 bytes
 reviews/WEBBOB-TEXTING-0927-phone-summary.png      | Bin 0 -> 189782 bytes
 reviews/WEBBOB-TEXTING-0927.browser.txt            |   1 +
 reviews/WEBBOB-TEXTING-0927.evidence.json          | 113 +++++
 reviews/WEBBOB-TEXTING-0927.md                     |  83 ++++
 reviews/WEBBOB-TEXTING-0927.services-tests.txt     |  77 ++++
 reviews/WEBBOB-TEXTING-0927.webchat-tests.txt      |  13 +
 webchat/README.md                                  |  63 +++
 webchat/app.py                                     |  24 +-
 webchat/browser_texting.cjs                        |  95 ++++
 webchat/providers.py                               |   4 +
 webchat/static/app.js                              |  81 +++-
 webchat/static/index.html                          |   5 +
 webchat/static/style.css                           |  12 +
 webchat/test_texting.py                            | 502 +++++++++++++++++++++
 webchat/test_texting_e2e.py                        | 107 +++++
 webchat/test_webchat.py                            |  16 +
 webchat/texting.py                                 | 394 ++++++++++++++++
 webchat/texting_fixture.py                         | 133 ++++++
 webchat/texting_proof.py                           |  92 ++++
 33 files changed, 2410 insertions(+), 7 deletions(-)
        identifier = secrets.token_hex(8)
        draft = dict(id=identifier, conversation_id=conversation["id"], recipient=target, body=body,
                     revision=len(state["drafts"]) + 1, state="pending", token="wbtxt-" + secrets.token_hex(16),
                     created_at=self.clock(), expires_at=self.clock() + CONFIRM_SECONDS, epoch=self.epoch,
                     actor=actor, request_id=request_id)
        draft["fingerprint"] = fingerprint(draft)
        state["drafts"][identifier] = draft
        state["active"] = identifier
        conversation["messages"][-1]["text_draft_id"] = identifier
        return "Draft ready for review. Nothing sent."

    def confirm(self, conversation, text, actor, request_id, persist):
        state = conversation.get("_texting", {})
        draft = state.get("drafts", {}).get(state.get("active"))
        match = re.fullmatch(r"yes (wbtxt-[0-9a-f]{32})", text, re.I)
        if not draft or not match:
            if text.lower().startswith("yes wbtxt-"):
                self.invalidate(conversation)
            return "Nothing sent. Review a fresh text draft and send its exact ‘yes wbtxt-…’ message separately in this chat."
        if draft["state"] != "pending":
            return "Nothing sent. That text confirmation was already used, cancelled, or replaced. Review a fresh draft."
        if draft["epoch"] != self.epoch or self.clock() >= draft["expires_at"]:
            draft.update(state="expired", token=None)
            return "Nothing sent. That text confirmation expired. Review a fresh draft."
        if (not actor or not hmac.compare_digest(actor, draft["actor"]) or
                request_id == draft["request_id"] or draft["conversation_id"] != conversation["id"] or
                not hmac.compare_digest(match[1], draft["token"]) or
                not hmac.compare_digest(fingerprint(draft), draft["fingerprint"])):
            return "Nothing sent. This yes does not match the exact draft and login that presented it. Review a fresh draft."
        # Save consumed consent before any handoff. Never replay on restart/error.
        draft.update(state="delivery_unconfirmed", token=None, approved_at=self.clock())
        audit = {"event": "owner_confirmed_delivery_unconfirmed", "actor": actor,
                 "conversation_id": conversation["id"], "draft_id": draft["id"], "revision": draft["revision"],
                 "recipient": copy.deepcopy(draft["recipient"]), "body": draft["body"],
                 "fingerprint": draft["fingerprint"], "at": self.clock(), "request_id": request_id}
        state["audit"].append(audit)
        conversation["messages"][-1].update(status="done", provider="texting", content=DELIVERY_UNCONFIRMED)
        persist(conversation)
        if self.andrea.deliver(draft["recipient"]["guid"], draft["body"]):
            draft["state"] = "sent"
            audit["event"] = "owner_sent_via_andrea"
            content = SENT_VIA_ANDREA
        else:
            draft["state"] = "confirmed_not_sent"
            audit["event"] = "owner_confirmed_not_sent"
            content = BRIDGE_BLOCKED
        return content

    def handle(self, conversation, text, actor, request_id, persist, redact):
        state = conversation.get("_texting", {})
        active = state.get("drafts", {}).get(state.get("active"))
        clean = re.sub(r"^(?:please |can you |could you )", "", text, flags=re.I).strip()
        # A worker/job prefix is not a way around the texting gate. Only matching
        # texting commands use this stripped value; other work keeps normal routing.
        clean = re.sub(r"^(?:(?:ask|have|tell|use) (?:codex|claude|cursor|gemini|minimax|mini)(?: to)?\s+|"
                       r"start (?:a )?job:\s*|(?:codex|claude|cursor|gemini|minimax|mini):\s*)", "", clean, flags=re.I)
        command = clean.casefold().rstrip(".?!")
        text_context = active and (active["state"] in ("pending", "editing") or
            len(conversation["messages"]) >= 3 and conversation["messages"][-3].get("texting"))
        confirmation = re.match(r"^yes\s+wbtxt-", clean, re.I) or (text_context and command in ("yes", "ok", "send it", "send it now", "send now", "go", "do it"))
        edit = re.fullmatch(r"(edit|cancel) text draft ([0-9a-f]{16})", clean, re.I)
        replace = re.fullmatch(r"replace text draft ([0-9a-f]{16}) to (.+?):\s*([\s\S]+)", clean, re.I)
        compose = re.fullmatch(r"(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)(?: reply)? to (.+?)(?::\s*| saying )([\s\S]+)", clean, re.I)
        compose = compose or re.fullmatch(r"text (.+?):\s*([\s\S]+)", clean, re.I)
        read = re.fullmatch(r"(read|show|summari[sz]e) (?:the )?(?:recent )?(?:texts?|messages?|imessages?|sms|thread) (?:from |with |in |for )?(.+)", clean, re.I)
        listing = command in ("texts", "list texts", "show texts", "recent texts", "show recent texts", "list recent texts", "summarize recent texts", "summarize texts")
        # Incomplete texting commands only — not colloquial chat like “text me when you're free”.
        help_request = command in ("texting", "texting help", "texting status") or re.match(
            r"^(?:draft|write|compose|send) (?:a )?(?:text|reply|sms|message)\b", clean, re.I
        )
        cancel = active and command in ("cancel text", "cancel text draft", "never mind", "cancel")
            return self.public(value)

    def public(self, value):
        excluded = {"codex_thread_id", "retry_prompt", "pending_job", "pending_job_id", "held_job"}
        # Extensions never see core-private state or mutable conversation objects.
        filtered = {k: copy.deepcopy(v) for k, v in value.items() if k not in excluded}
        return {k: v for k, v in self.texting.public(filtered).items() if k not in excluded}

    def intent_reply(self, conversation, content, provider="dispatcher"):
        conversation["messages"][-1].update(status="done", provider=provider, content=content)
        self.save(conversation)
        self.conversations[conversation["id"]] = conversation
        return self.public(conversation)

    def get(self, identifier):
        if not isinstance(identifier, str) or not UUID.fullmatch(identifier) or identifier not in self.conversations:
            raise RequestError(404, "Conversation not found.")
        return self.conversations[identifier]

    def history(self, identifier):
        with self.lock:
            self.reconcile_tasks()
            return self.public(self.get(identifier))

    def worker_info(self, identifier):
        return self.workers.get(identifier)

    def reply_deadline(self):
        timeouts = getattr(self.providers, "timeouts", {})
        values = list(timeouts.values()) or [180]
        return sum(values[:4]) + 60

    def sweep_stuck(self):

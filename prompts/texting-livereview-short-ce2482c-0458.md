Strict LIVE code review of combined texting+integrate tip:
SHA ce2482cce311ce4317c1b3aca316f1ca446aeddb on draft/webbob-texting-onto-a777736.
Parents: integrate a777736 + texting 9751346.

Must retain BOTH:
1) integrate: status_reply, reply_authority, worker_assignment, pending_job routing
2) texting: Texting.handle/confirm, delivery_unconfirmed, public/private-context, persist_texting clears pending_*

Do NOT reuse BOTH_PASS from 9751346 or a777736 alone. No Twilio/voice/media scope.
Cite real symbols only. End with VERDICT: PASS or VERDICT: FAIL

## confirm+handle
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
        # The draft-creation request cannot also authorize delivery: the owner
        # must review the card and submit its exact token in a later request.
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
        delivered = self.andrea.deliver(draft["recipient"]["guid"], draft["body"])
        if delivered is True:
            draft["state"] = "sent"
            audit["event"] = "owner_sent_via_andrea"
            content = SENT_VIA_ANDREA
        elif delivered is False:
            draft["state"] = "confirmed_not_sent"
            audit["event"] = "owner_confirmed_not_sent"
            content = BRIDGE_BLOCKED
        else:
            content = DELIVERY_UNCONFIRMED
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
        # Bare approvals are routed here for token guidance only; confirm() still
        # requires the entire message to match the exact yes + token format.
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
        if not any((confirmation, edit, replace, compose, read, listing, help_request, cancel)):
            # An intervening turn also withdraws consent, including unsupported edits.
            self.invalidate(conversation)
            return False
        conversation["messages"][-2]["texting"] = True
        answer = conversation["messages"][-1]
        answer.update(texting=True, provider="texting", status="done")
        try:
            if confirmation:
                # The chat turn itself must be yes + token, never a command prefix
                # or quoted/embedded approval extracted from another request.
                content = self.confirm(conversation, text, actor, request_id, persist)
            elif cancel:
                self.invalidate(conversation, "cancelled")
                content = "Text draft cancelled. Nothing sent."
            elif edit:
                draft = state.get("drafts", {}).get(edit[2])
                if not draft or state.get("active") != draft["id"] or draft["state"] not in ("pending", "expired", "editing", "confirmed_not_sent"):
                    raise TextingError("That draft is no longer current. Prepare a fresh text draft.")
                draft.update(state="editing" if edit[1].lower() == "edit" else "cancelled", token=None)
                content = "Confirmation cleared. Edit the draft card, then review it again." if draft["state"] == "editing" else "Text draft cancelled. Nothing sent."
            elif replace or compose:
                # Even a failed/ambiguous edit withdraws the previous confirmation.
                self.invalidate(conversation)
                if replace:
                    if not active or replace[1] != active["id"]:
                        raise TextingError("That draft is no longer current. Prepare a fresh text draft.")
                    query, body = replace[2], replace[3]
                else:
                    query, body = compose[1], compose[2]
                target = recipient(self.resolve(query.strip()))
                if redact(json.dumps(target, ensure_ascii=False)) != json.dumps(target, ensure_ascii=False):
                    raise TextingError("The thread details contain sensitive credentials; no draft was prepared.")
                content = self.draft(conversation, target, body, actor, request_id)
            else:
                self.invalidate(conversation)
                if listing:
                    chats = self.bluebubbles.chats()[:20]
                    content = "Recent text threads (up to 20):\n" + ("\n".join(
                        f"• {label(c)} — {c.get('guid', '?')}\n  {str((c.get('lastMessage') if isinstance(c.get('lastMessage'), dict) else {}).get('text') or '[No text preview]')[:180]}"
                        for c in chats) or "No recent threads.")
                elif read:
                    chat = self.resolve(read[2].strip())
                    messages = sorted(self.bluebubbles.messages(chat["guid"]), key=timestamp)
                    content = f"{label(chat)} — {chat['guid']}\n"
                    if not messages:
                        content += "No recent messages in this thread."
                    elif read[1].lower().startswith("summari"):
                        incoming = sum(m.get("isFromMe") is not True for m in messages)
                        content += (f"Recent thread summary: {len(messages)} messages, {incoming} incoming and "
                                    f"{len(messages) - incoming} from you.\n"
                                    f"Window: {time_label(messages[0])} – {time_label(messages[-1])}.\n"
                                    "Latest messages:\n")
                        content += "\n".join(self.message_line(m, 400) for m in messages[-4:])
                    else:
                        content += "Last 30 messages at most, oldest first:\n" + "\n".join(self.message_line(m, 1200) for m in messages)
                elif command == "texting status":
                    content = self.andrea.status() + " Web Bob delivery is blocked: Andrea requires approval in its registered owner chat."
                else:
                    content = HELP
        except TextingError as exc:
            content = str(exc)
        answer["content"] = redact(content)
        # Every handled turn is saved once here. Confirmations also persist consumed
        # consent before delivery so an interrupted receipt cannot authorize a replay.
        persist(conversation)
## app hooks
                 "provider": None, "attempts": [], "created_at": time.time()},
            ]
            if conversation["title"] == "New conversation":
                conversation["title"] = text[:65]
            if VERSION_QUESTION.search(text):
                return self.intent_reply(conversation, BUILD["short_sha"])
            # Text intent and confirmations never enter generic job/provider routing.
            def persist_texting(value):
                for key in ("pending_job", "pending_job_id", "pending_council", "pending_council_id"):
                    value.pop(key, None)
                self.save(value)
                self.conversations[identifier] = copy.deepcopy(value)
            if self.texting.handle(conversation, text, actor, request_id, persist_texting, self.redact):
                return self.public(conversation)
            from reply_authority import correcting_status
            if correcting_status(text, conversation):
                return self.status_reply(conversation, text)
            transition = chat_intent.apply_turn(intent_state, text, request_id)
            if transition == "hold":
                held_work, held_worker = followup_work(conversation)
                if held_work:
                    conversation["held_job"] = dict(prompt=held_work, worker=held_worker)
                return self.intent_reply(conversation, chat_intent.hold_reply(chat_intent.blocked_scopes(intent_state, [])))
            if transition == "priorities":
                conversation["pending_job"] = "Improve " + ", ".join(intent_state["project_order"])
                conversation["pending_job_id"] = request_id
                return self.intent_reply(conversation, "Priority order: " + ", ".join(intent_state["project_order"]) + ".")
            from worker_assignment import requested_workers
            assignments = requested_workers(text, conversation)
            if assignments:
                return self.submit_worker_assignment(conversation, text, request_id, assignments)
            from worker_assignment import issue_followup
            fix = issue_followup(self.root, conversation, text)
            if fix:
                return self.submit_task(conversation, fix, request_id)
            work, route = parse_work(text)
            if transition == "resume" and not work:
                work_text = re.sub(r"^(?:go(?:\s+ahead)?|resume)(?:\s+and)?[\s,:!]+", "", chat_intent.command(text), flags=re.I)
                work, route = parse_work(work_text)
            started = parse_start(text)
            inbox_task = state_ledger.parse_inbox_message(text)
    def status_reply(self, conversation, text):
        from reply_authority import operational_reply
        from status_observation import bind_observation
        conversation = copy.deepcopy(conversation)
        observation = {}
        content = operational_reply(self.ledger_root(conversation["id"]), "server", text,
                                    observation=observation, redact=self.redact)
        conversation["messages"][-1]["status_observation"] = bind_observation(observation, conversation)
        # The reply and its exact rendering input share the existing private,
        # fsynced atomic conversation write. Retries/restarts keep both intact.
        return self.intent_reply(conversation, self.redact(content), provider="state")

    def get(self, identifier):
        if not isinstance(identifier, str) or not UUID.fullmatch(identifier) or identifier not in self.conversations:
            raise RequestError(404, "Conversation not found.")
        return self.conversations[identifier]

    def history(self, identifier):
        with self.lock:

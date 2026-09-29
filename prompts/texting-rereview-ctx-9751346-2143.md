# Strict LIVE re-review draft/webbob-texting-0927 @9751346 (97513468016488ebe42ca1919e507db99fc0a15f)

SCOPE: TEXTING ONLY (webchat/texting.py, texting_*.py, test_texting*.py, app.py texting hooks, static texting card).
Do NOT fail for missing voice/media/iPhone. Do NOT fail for baseline services/draft_publish.py or dispatch_worker.py unless this tip changed them.
No Twilio. Cite only real symbols that exist in the provided sources.
Prior MiniMax FAILs on request_id equality / bare-yes / IndentationError were triaged as false or intentional; see TEXTING-FIXED-2014.md dispositions.
Focus on NEW tip changes since 78fa870 (lost Andrea reply → delivery_unconfirmed).
End with exactly: VERDICT: PASS or VERDICT: FAIL

## git log
9751346 Clarify texting consent and preserve uncertain delivery receipts
## diffstat vs live dff84e3
 webchat/README.md           |  63 +++++
 webchat/app.py              |  24 +-
 webchat/browser_texting.cjs |  95 ++++++++
 webchat/providers.py        |   4 +
 webchat/static/app.js       |  81 +++++-
 webchat/static/index.html   |   5 +
 webchat/static/style.css    |  12 +
 webchat/test_texting.py     | 582 ++++++++++++++++++++++++++++++++++++++++++++
 webchat/test_texting_e2e.py | 111 +++++++++
 webchat/test_webchat.py     |  16 ++
 webchat/texting.py          | 408 +++++++++++++++++++++++++++++++
 webchat/texting_fixture.py  | 137 +++++++++++
 webchat/texting_proof.py    |  92 +++++++
 13 files changed, 1623 insertions(+), 7 deletions(-)
## diff 78fa870..HEAD webchat (texting-focused)
diff --git a/webchat/test_texting.py b/webchat/test_texting.py
index 22dafbe..a709653 100644
--- a/webchat/test_texting.py
+++ b/webchat/test_texting.py
@@ -15,7 +15,7 @@ from unittest.mock import patch
 
 from app import Chat, RequestError, Server
 from task_dispatch import task_queue
-from texting import Andrea, BlueBubbles, Texting, TextingError, SENT_VIA_ANDREA, local_url
+from texting import Andrea, BlueBubbles, Texting, TextingError, DELIVERY_UNCONFIRMED, SENT_VIA_ANDREA, local_url
 from texting_fixture import MockMessaging, OfflineProviders
 
 
@@ -99,13 +99,52 @@ class TextingTests(unittest.TestCase):
         self.assertIn("I can read recent texts", incomplete["content"])
 
     def test_send_request_is_only_a_draft_and_separate_yes_is_required(self):
+        self.mock.enable_web_bob_send = True
         draft = self.draft("send a text to Alex Morgan: yes, send it now")
         self.assertEqual(draft["body"], "yes, send it now")
         self.assertEqual(draft["state"], "pending")
         self.assertEqual(self.private()["audit"], [])
-        for phrase in ("yes", "ok", "send it", "send it now", "go", "do it"):
-            self.assertIn("Nothing sent", self.say(phrase)["messages"][-1]["content"])
-        self.assertEqual(self.private()["audit"], [])
+        for phrase in ("yes", "ok", "send it", "send it now", "send now", "go", "do it"):
+            with self.subTest(phrase=phrase):
+                self.assertIn("Nothing sent", self.say(phrase)["messages"][-1]["content"])
+                self.assertEqual(self.private()["drafts"][draft["id"]]["state"], "pending")
+                self.assertEqual(self.private()["audit"], [])
+                self.assertEqual(self.mock.sends, [])
+                self.assertNotIn(("POST", "/web-bob/send"), self.mock.calls)
+        self.assertEqual(self.providers.calls, [])
+        self.assertEqual(task_queue.tasks(self.root), {})
+        self.assertEqual(self.say(draft["confirm_message"])["messages"][-1]["content"], SENT_VIA_ANDREA)
+        self.assertEqual(len(self.mock.sends), 1)
+
+    def test_same_request_cannot_confirm_draft(self):
+        self.mock.enable_web_bob_send = True
+        draft = self.draft()
+        conversation = copy.deepcopy(self.chat.conversations[self.identifier])
+        pending = conversation["_texting"]["drafts"][draft["id"]]
+        draft_request = pending["request_id"]
+        with patch.object(self.chat, "save", wraps=self.chat.save) as saved:
+            with self.assertRaises(RequestError) as error:
+                self.say(draft["confirm_message"], request_id=draft_request)
+            self.assertEqual(error.exception.status, 409)
+            # Exercise the consent guard itself, beyond Chat.submit's replay check.
+            content = self.texting.confirm(conversation, draft["confirm_message"],
+                                          self.actor, draft_request, self.chat.save)
+            self.assertIn("does not match", content)
+            saved.assert_not_called()
+        self.assertEqual(pending["state"], "pending")
+        self.assertEqual("yes " + pending["token"], draft["confirm_message"])
+        self.assertEqual(conversation["_texting"]["audit"], [])
+        self.assertEqual(self.mock.sends, [])
+        self.assertNotIn(("POST", "/web-bob/send"), self.mock.calls)
+
+        later_request = str(uuid.uuid4())
+        value = self.say(draft["confirm_message"], request_id=later_request)
+        self.assertEqual(value["messages"][-1]["content"], SENT_VIA_ANDREA)
+        self.assertEqual(self.private()["drafts"][draft["id"]]["state"], "sent")
+        self.assertEqual(len(self.private()["audit"]), 1)
+        self.assertEqual(self.private()["audit"][0]["request_id"], later_request)
+        self.assertEqual(self.mock.sends, [{"chatGuid": draft["recipient"]["guid"], "text": draft["body"]}])
+        self.assertEqual(self.mock.calls.count(("POST", "/web-bob/send")), 1)
 
     def test_worker_routing_cannot_bypass_text_draft_gate(self):
         for request in ("ask Codex to send a text to Alex Morgan: Hello",
@@ -317,6 +356,43 @@ class TextingTests(unittest.TestCase):
         finally:
             restored.close()
 
+    def test_lost_andrea_reply_keeps_delivery_unconfirmed_and_cannot_replay(self):
+        self.mock.enable_web_bob_send = True
+        self.mock.drop_send_response = True
+        draft = self.draft()
+        value = self.say(draft["confirm_message"])
+        self.assertEqual(len(self.mock.sends), 1)
+        self.assertEqual(value["messages"][-1]["content"], DELIVERY_UNCONFIRMED)
+        self.assertEqual(self.private()["drafts"][draft["id"]]["state"], "delivery_unconfirmed")
+        self.assertIsNone(self.private()["drafts"][draft["id"]]["token"])
+        self.assertEqual(self.private()["audit"][0]["event"], "owner_confirmed_delivery_unconfirmed")
+        self.say(draft["confirm_message"])
+        restored = Chat(self.folder, self.root, self.providers,
+                       texting=Texting(BlueBubbles(self.mock.config_db), Andrea(self.mock.base, self.mock.token)))
+        try:
+            history = restored.history(self.identifier)
+            cards = [m["text_draft"] for m in history["messages"] if m.get("text_draft")]
+            self.assertEqual(cards[-1]["state"], "delivery_unconfirmed")
+            self.assertIsNone(cards[-1]["confirm_message"])
+            restored.submit(self.identifier, draft["confirm_message"], str(uuid.uuid4()), actor=self.actor)
+        finally:
+            restored.close()
+        self.assertEqual(len(self.mock.sends), 1)
+        self.assertEqual(self.mock.calls.count(("POST", "/web-bob/send")), 1)
+
+    def test_invalid_andrea_receipts_do_not_claim_sent_or_not_sent(self):
+        for receipt in ({}, {"ok": False}, {"ok": True}, {"ok": True, "messageGuid": ""},
+                        {"ok": True, "messageGuid": " "}, {"ok": True, "messageGuid": 1}):
+            with self.subTest(receipt=receipt):
+                draft = self.draft()
+                with patch("texting.request_json", return_value=receipt) as requested:
+                    value = self.say(draft["confirm_message"])
+                    self.assertEqual(value["messages"][-1]["content"], DELIVERY_UNCONFIRMED)
+                    self.assertEqual(self.private()["drafts"][draft["id"]]["state"], "delivery_unconfirmed")
+                    self.assertIsNone(self.private()["drafts"][draft["id"]]["token"])
+                    self.say(draft["confirm_message"])
+                    self.assertEqual(requested.call_count, 1)
+
     def test_texting_persists_each_turn_and_clears_pending_work(self):
         for text in ("texts", "draft reply to Alex Morgan: Hello", "yes", "cancel text draft"):
             with self.subTest(text=text):
@@ -419,18 +495,22 @@ class TextingTests(unittest.TestCase):
         secret_path = "/private/fixture-andrea/config.env"
         self.mock.andrea_error_body = (f"{self.mock.base}/web-bob/send?password={self.mock.password} "
                                        f"Bearer {self.mock.token} {secret_path}")
-        for status in (401, 403, 500):
+        for status in (401, 403, 404, 405, 500):
             with self.subTest(status=status):
                 self.mock.andrea_error_status = status
                 draft = self.draft()
                 value = self.say(draft["confirm_message"])
-                self.assertTrue(value["messages"][-1]["content"].startswith("Not sent."))
+                if status == 500:
+                    self.assertEqual(value["messages"][-1]["content"], DELIVERY_UNCONFIRMED)
+                else:
+                    self.assertTrue(value["messages"][-1]["content"].startswith("Not sent."))
                 disk = (self.chat.state / (self.identifier + ".json")).read_text()
                 for secret in (self.mock.base, self.mock.password, self.mock.token, secret_path, "password="):
                     self.assertNotIn(secret, json.dumps(value))
                     self.assertNotIn(secret, disk)
                 self.assertEqual(self.mock.sends, [])
-                self.assertEqual(self.private()["drafts"][draft["id"]]["state"], "confirmed_not_sent")
+                expected_state = "delivery_unconfirmed" if status == 500 else "confirmed_not_sent"
+                self.assertEqual(self.private()["drafts"][draft["id"]]["state"], expected_state)
                 self.assertIsNone(self.private()["drafts"][draft["id"]]["token"])
 
     def test_read_allowlist_and_loopback_no_proxy(self):
diff --git a/webchat/test_texting_e2e.py b/webchat/test_texting_e2e.py
index e5b57e1..e1bae00 100644
--- a/webchat/test_texting_e2e.py
+++ b/webchat/test_texting_e2e.py
@@ -70,9 +70,13 @@ class TextingE2ETest(unittest.TestCase):
         self.assertEqual(card["body"], "Charts at 7 tonight.")
         self.assertIn("+15550101010", json.dumps(card["recipient"]))
         self.assertEqual(self.mock.sends, [])
-        _, bare = self.post("yes")
-        self.assertIn("Nothing sent", bare["messages"][-1]["content"])
-        self.assertEqual(self.mock.sends, [])
+        for phrase in ("yes", "ok", "send it"):
+            with self.subTest(phrase=phrase):
+                status, bare = self.post(phrase)
+                self.assertEqual(status, 202)
+                self.assertIn("Nothing sent", bare["messages"][-1]["content"])
+                self.assertEqual(self.mock.sends, [])
+                self.assertNotIn(("POST", "/web-bob/send"), self.mock.calls)
         status, confirmed = self.post(card["confirm_message"])
         self.assertEqual(status, 202)
         self.assertTrue(confirmed["messages"][-1]["content"].startswith("Sent via Andrea"))
diff --git a/webchat/texting.py b/webchat/texting.py
index c7576e6..67cd4cf 100644
--- a/webchat/texting.py
+++ b/webchat/texting.py
@@ -42,6 +42,10 @@ DELIVERY_UNCONFIRMED = ("Confirmation recorded; delivery is unconfirmed. Check t
 class TextingError(Exception):
     """A safe, owner-facing error; never include response bodies or credential URLs."""
 
+    def __init__(self, message, *, status=None):
+        super().__init__(message)
+        self.status = status
+
 
 class NoRedirect(urllib.request.HTTPRedirectHandler):
     def redirect_request(self, *_args, **_kwargs):
@@ -81,8 +85,8 @@ def request_json(base, path, *, data=None, headers=None):
         raise
     except urllib.error.HTTPError as exc:
         if exc.code in (401, 403):
-            raise TextingError("Local messaging authentication failed. Nothing was sent.") from None
-        raise TextingError("The local messaging service rejected the request. Nothing was sent.") from None
+            raise TextingError("Local messaging authentication failed. Nothing was sent.", status=exc.code) from None
+        raise TextingError("The local messaging service rejected the request. Nothing was sent.", status=exc.code) from None
     except (OSError, ValueError, UnicodeError):
         raise TextingError("Local messaging is unavailable or returned invalid data. Nothing was sent.") from None
 
@@ -142,16 +146,19 @@ class Andrea:
                  "Its BlueBubbles channel is unavailable."))
 
     def deliver(self, chat_guid, body):
-        """Owner-approved send through Andrea when the control service exposes Web Bob delivery."""
+        """Return True for delivery, False for rejection, or None for an unknown outcome."""
         if not self.token or not isinstance(chat_guid, str) or not chat_guid or not isinstance(body, str) or not body.strip():
             return False
         try:
             result = request_json(self.base, "/web-bob/send",
                                   data={"chatGuid": chat_guid, "text": body},
                                   headers={"Authorization": "Bearer " + self.token})
-        except TextingError:
-            return False
-        return result.get("ok") is True and isinstance(result.get("messageGuid"), str)
+        except TextingError as exc:
+            # Auth or an absent endpoint rejects the handoff. A lost response or
+            # server error may follow delivery, so it cannot prove "not sent".
+            return False if exc.status in (401, 403, 404, 405) else None
+        guid = result.get("messageGuid")
+        return True if result.get("ok") is True and isinstance(guid, str) and guid.strip() else None
 
 
 def fingerprint(draft):
@@ -271,6 +278,8 @@ class Texting:
         if draft["epoch"] != self.epoch or self.clock() >= draft["expires_at"]:
             draft.update(state="expired", token=None)
             return "Nothing sent. That text confirmation expired. Review a fresh draft."
+        # The draft-creation request cannot also authorize delivery: the owner
+        # must review the card and submit its exact token in a later request.
         if (not actor or not hmac.compare_digest(actor, draft["actor"]) or
                 request_id == draft["request_id"] or draft["conversation_id"] != conversation["id"] or
                 not hmac.compare_digest(match[1], draft["token"]) or
@@ -285,14 +294,17 @@ class Texting:
         state["audit"].append(audit)
         conversation["messages"][-1].update(status="done", provider="texting", content=DELIVERY_UNCONFIRMED)
         persist(conversation)
-        if self.andrea.deliver(draft["recipient"]["guid"], draft["body"]):
+        delivered = self.andrea.deliver(draft["recipient"]["guid"], draft["body"])
+        if delivered is True:
             draft["state"] = "sent"
             audit["event"] = "owner_sent_via_andrea"
             content = SENT_VIA_ANDREA
-        else:
+        elif delivered is False:
             draft["state"] = "confirmed_not_sent"
             audit["event"] = "owner_confirmed_not_sent"
             content = BRIDGE_BLOCKED
+        else:
+            content = DELIVERY_UNCONFIRMED
         return content
 
     def handle(self, conversation, text, actor, request_id, persist, redact):
@@ -306,6 +318,8 @@ class Texting:
         command = clean.casefold().rstrip(".?!")
         text_context = active and (active["state"] in ("pending", "editing") or
             len(conversation["messages"]) >= 3 and conversation["messages"][-3].get("texting"))
+        # Bare approvals are routed here for token guidance only; confirm() still
+        # requires the entire message to match the exact yes + token format.
         confirmation = re.match(r"^yes\s+wbtxt-", clean, re.I) or (text_context and command in ("yes", "ok", "send it", "send it now", "send now", "go", "do it"))
         edit = re.fullmatch(r"(edit|cancel) text draft ([0-9a-f]{16})", clean, re.I)
         replace = re.fullmatch(r"replace text draft ([0-9a-f]{16}) to (.+?):\s*([\s\S]+)", clean, re.I)
diff --git a/webchat/texting_fixture.py b/webchat/texting_fixture.py
index 1c545ca..708ee5b 100644
--- a/webchat/texting_fixture.py
+++ b/webchat/texting_fixture.py
@@ -28,6 +28,7 @@ class MockMessaging:
     def __init__(self, folder):
         self.calls, self.unexpected_writes, self.sends = [], [], []
         self.enable_web_bob_send = False
+        self.drop_send_response = False
         self.andrea_error_status = None
         self.andrea_error_body = None
         self.chats, self.messages = copy.deepcopy(CHATS), copy.deepcopy(MESSAGES)
@@ -58,6 +59,9 @@ class MockMessaging:
                     fixture.sends.append({"chatGuid": guid, "text": text})
                     # Andrea hands off to BlueBubbles on the same loopback fixture.
                     fixture.calls.append(("POST", "/api/v1/message/text"))
+                    if fixture.drop_send_response:
+                        self.close_connection = True
+                        return
                     return self.respond(200, {"ok": True, "messageGuid": "mock-" + secrets.token_hex(8)})
                 if self.command == "POST" and url.path == "/api/v1/message/text":
                     if not fixture.enable_web_bob_send:
--- texting.py confirm/handle ---
    def draft(self, conversation, target, body, actor, request_id):
        if not actor:
            raise TextingError("Log in again before preparing a confirmation-bound text draft.")
        if not body.strip() or len(body) > 4000:
            raise TextingError("Write a text body between 1 and 4,000 characters.")
        state = conversation.setdefault("_texting", {"drafts": {}, "audit": []})
        self.invalidate(conversation)
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
--- test names ---
55:    def test_reads_summaries_and_no_jobs_or_model_calls(self):
65:    def test_ambiguous_names_and_duplicate_transports_require_exact_target(self):
76:    def test_empty_missing_and_unverifiable_thread(self):
83:    def test_colloquial_text_phrasing_is_not_texting_help(self):
101:    def test_send_request_is_only_a_draft_and_separate_yes_is_required(self):
119:    def test_same_request_cannot_confirm_draft(self):
149:    def test_worker_routing_cannot_bypass_text_draft_gate(self):
158:    def test_embedded_approval_is_not_a_separate_yes(self):
164:    def test_texting_does_not_clear_holds_or_capture_later_resume(self):
174:    def test_worker_prefixed_texting_still_respects_holds(self):
182:    def test_separate_yes_sends_via_mock_andrea_bluebubbles_path(self):
194:    def test_separate_yes_success_message_content(self):
206:    def test_token_comparison_timing_safe(self):
222:    def test_exact_confirmation_consumed_once_and_truthfully_blocked(self):
239:    def test_wrong_conversation_login_or_token_cannot_confirm(self):
249:    def test_expiry_restart_and_replay_never_authorize(self):
264:    def test_edit_start_and_recipient_or_body_edit_reset_confirmation(self):
278:    def test_failed_ambiguous_edit_also_withdraws_consent(self):
284:    def test_intervening_message_cancel_new_draft_and_combined_yes_edit(self):
293:    def test_payload_tampering_invalidates_binding(self):
300:    def test_concurrent_yes_has_one_durable_audit_record(self):
308:    def test_duplicate_draft_request_never_rotates_consent(self):
318:    def test_disk_failure_does_not_claim_confirmation(self):
329:    def test_receipt_save_failure_keeps_consent_consumed_after_restart(self):
359:    def test_lost_andrea_reply_keeps_delivery_unconfirmed_and_cannot_replay(self):
383:    def test_invalid_andrea_receipts_do_not_claim_sent_or_not_sent(self):
396:    def test_texting_persists_each_turn_and_clears_pending_work(self):
411:    def test_confirmation_persists_before_handoff_and_once_for_receipt(self):
430:    def test_private_storage_and_public_projection(self):
441:    def test_core_exclusions_are_applied_before_texting_projection(self):
466:    def test_thread_instructions_are_inert_and_private_from_providers(self):
481:    def test_transport_errors_are_safe_and_reads_never_follow_redirects(self):
493:    def test_andrea_errors_do_not_leak_secrets(self):
516:    def test_read_allowlist_and_loopback_no_proxy(self):
527:    def test_andrea_authenticated_health_and_missing_bridge_honesty(self):
536:    def test_http_auth_csrf_and_session_bound_confirmation(self):
--- FIXED-2014 summary ---
# Texting triage and fixes — 2014

Result: local validation PASS; committed and regularly pushed for fresh review.

- Branch: `draft/webbob-texting-0927` on `brain`.
- Parent: `78fa870a8ed7178662f97b0394ff80ba32ded63e`.
- New review SHA: `97513468016488ebe42ca1919e507db99fc0a15f`.
- Commit: `Clarify texting consent and preserve uncertain delivery receipts`.
- Validation date: September 27, 2026 America/Chicago (September 28 UTC).

The task supplied Gemini PASS on `78fa870` and MiniMax FAIL in
`LIVE-MINIMAX-draft_webbob-texting-0927-78fa870-rereview.md`. That report is not
present inside the permitted worktree. This triage checks the three claims
quoted in the task against the actual source; it does not claim to have read
an external report or obtained a fresh external verdict.

## MiniMax claim dispositions

| Claim | Actual code and evidence | Disposition |
| --- | --- | --- |
| Rejecting `request_id == draft["request_id"]` is wrong | `webchat/texting.py:281` now explains that draft creation cannot authorize its own delivery. `test_same_request_cannot_confirm_draft` in `webchat/test_texting.py:119` exercises both the chat replay rejection (409) and the consent guard directly, verifies no save, audit, or bridge call, then succeeds once with the same exact token in a later request. The mock delivery bridge is enabled. | Intentional invariant; equality check preserved. |
| Cancellation has an `IndentationError` | AST parsing passes for `texting.py` and `app.py` at both `78fa870` and the final source. The cancellation regression and full webchat suite pass. | False; no cancellation syntax change. |
| Bare yes/ok with `text_context` can send | `Texting.confirm()` still requires `re.fullmatch(r"yes (wbtxt-[0-9a-f]{32})", ...)`. A comment explains that tokenless phrases route to guidance. The strengthened test at `webchat/test_texting.py:101` checks all seven routed bare phrases with a working mock bridge, zero sends, zero handoffs, no consent consumption, and no model/job routing. The HTTP test at `webchat/test_texting_e2e.py:73` separately checks `yes`, `ok`, and `send it`, then confirms with the exact token. | False; unit and HTTP coverage strengthened. |

## Reproduced texting bug fixed

An Andrea delivery could succeed while its HTTP response was lost. Previously,
`Andrea.deliver()` converted any transport error into `False`, so the draft
became `confirmed_not_sent` and the owner was told “Not sent.”

The synthetic fixture now supports recording a delivery and closing the
connection without returning a receipt. The regression first failed against
the original runtime after asserting one mock delivery; its captured failure
is in [TEXTING-2014-lost-reply-before.txt](TEXTING-2014-lost-reply-before.txt).

`Andrea.deliver()` now distinguishes a confirmed delivery, a known rejection,
and an unknown outcome. Missing or invalid receipts, server errors, and lost
responses preserve `delivery_unconfirmed` and the consumed confirmation.
Only an affirmative receipt with a nonblank message GUID produces `sent`.
Authentication rejection and an absent endpoint (401/403/404/405) retain the
blocked receipt. Error handling retains only safe messages and HTTP status,
without exposing response bodies or credentials.

The lost-response test verifies the uncertain receipt, consumed token, audit
state, persisted state after restart, and exactly one bridge call despite
replays. Additional tests cover invalid acknowledgments and error redaction.
All deliveries in validation are synthetic fixture records.

## Validation on the committed source

| Check | Result | Evidence |
| --- | --- | --- |
| Seven focused consent, cancellation, receipt, and HTTP tests | 7 passed | [Targeted tests](TEXTING-2014-targeted-tests.txt) |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | 295 passed, 0 skipped, 44.760 s; includes the isolated browser proof | [Webchat suite](TEXTING-2014-webchat-tests.txt) |
| `python3 -m unittest discover -s services -p 'test_*.py'` | 121 passed, 0 skipped, 3.509 s in the identical source snapshot described below | [Services suite](TEXTING-2014-services-tests.txt) |
| AST parsing at the parent and final source; `node --check webchat/static/app.js` | PASS | [Syntax checks](TEXTING-2014-syntax-checks.txt) |
| `git diff --check` | PASS before commit | Four texting files committed |
| Regular push and exact remote SHA comparison | PASS; local and remote both `97513468016488ebe42ca1919e507db99fc0a15f` | [Tip and source verification](TEXTING-2014-tip-check.txt), [push log](TEXTING-2014-push.txt) |

### Services fixture location

To honor the worktree-only restriction, `TMPDIR` was set to
`reviews/.texting-proof-2014-tmp`. The initial services run completed 121 tests
with one error: `test_coding_boundary_allows_real_commit_and_normal_push`.
Its macOS sandbox denies writes under the module's source checkout, which
also covered the nested fixture repository. The full initial log is retained
in [TEXTING-2014-services-in-worktree.txt](TEXTING-2014-services-in-worktree.txt).

The entire services suite was rerun from a temporary source snapshot inside
this worktree, with fixture directories beside that snapshot. Its 169 tracked
files from `services/`, `state/`, `webchat/`, and `bootstrap.py` were copied
byte-for-byte from the working tree. The sandbox rules and all tests were
unchanged. The real sandboxed fixture commit/push and all 120 other tests
passed. Temporary source and fixture data were cleaned up afterward.

[The source hash manifest](TEXTING-2014-services-source-sha256.txt) was rechecked
after commit: all 169 files still match, including the four changed files.
The final tip verification also compares each changed file against its committed
bytes. Historical 0927 proof artifacts remain historical evidence; their source
hashes are not represented as evidence for this new SHA.

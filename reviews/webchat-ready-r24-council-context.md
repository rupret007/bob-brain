# Round 24 Web Bob diff context
**Focus:** status snapshot TTL (speed), ops snapshot age on dashboard, self-improve schedule visibility, chord relative-minor (--), mobile link styling.
**Baseline:** R13 final 021c527. Handback r24×2 + ts.net drill required.
diff --git a/conductor/webchat/bob_parity_eval.py b/conductor/webchat/bob_parity_eval.py
index 57416f3..d40c1c3 100644
--- a/conductor/webchat/bob_parity_eval.py
+++ b/conductor/webchat/bob_parity_eval.py
@@ -70,6 +70,10 @@ def run_eval(root: Path | None = None) -> dict:
         "music chord progression scan",
         "chord progression scan" in prog.lower() and "Roman sketch" in prog and "C" in prog,
     ))
+    rows.append(_case(
+        "music relative minor hint",
+        "relative minor" in prog.lower() and "am" in prog.lower(),
+    ))
 
     with tempfile.TemporaryDirectory() as tmp:
         troot = Path(tmp)
diff --git a/conductor/webchat/evidence/handback-drill.json b/conductor/webchat/evidence/handback-drill.json
index a80a3c6..7e648bb 100644
--- a/conductor/webchat/evidence/handback-drill.json
+++ b/conductor/webchat/evidence/handback-drill.json
@@ -1,46 +1,46 @@
 {
-  "started_at": 1790508140.948252,
+  "started_at": 1790508533.4089322,
   "rounds": [
     {
       "ledger": {
-        "tag": "r23-1",
-        "fixture_id": "6bde90fe-fc3f-4ded-ae76-02b1ffc6081a",
+        "tag": "r13-1",
+        "fixture_id": "dc421bc7-4e45-407a-aedd-8e111f46e3b5",
         "ledger_ok": true,
         "bob_pickup_ok": true,
         "summary_chars": 967
       },
       "live": {
-        "tag": "r23-1",
+        "tag": "r13-1",
         "status": "done",
         "provider": "state",
-        "elapsed_seconds": 0.044,
+        "elapsed_seconds": 0.052,
         "mentions_running": true,
-        "snippet": "Running: handback drill screen `drill-r23-1`",
+        "snippet": "Running: handback drill screen `drill-r13-1`",
         "live_ok": true
       },
-      "fixture_id": "6bde90fe-fc3f-4ded-ae76-02b1ffc6081a",
+      "fixture_id": "dc421bc7-4e45-407a-aedd-8e111f46e3b5",
       "reverse_handback_ok": true,
       "events_ok": true,
       "pass": true
     },
     {
       "ledger": {
-        "tag": "r23-2",
-        "fixture_id": "1103e992-8eec-47b4-877d-d1b5339c1c3c",
+        "tag": "r13-2",
+        "fixture_id": "d0238180-9a02-4851-bbcd-bc2af7cfab6d",
         "ledger_ok": true,
         "bob_pickup_ok": true,
         "summary_chars": 967
       },
       "live": {
-        "tag": "r23-2",
+        "tag": "r13-2",
         "status": "done",
         "provider": "state",
-        "elapsed_seconds": 0.045,
+        "elapsed_seconds": 0.054,
         "mentions_running": true,
-        "snippet": "Running: handback drill screen `drill-r23-2`",
+        "snippet": "Running: handback drill screen `drill-r13-2`",
         "live_ok": true
       },
-      "fixture_id": "1103e992-8eec-47b4-877d-d1b5339c1c3c",
+      "fixture_id": "d0238180-9a02-4851-bbcd-bc2af7cfab6d",
       "reverse_handback_ok": true,
       "events_ok": true,
       "pass": true
@@ -48,7 +48,7 @@
   ],
   "isolated": true,
   "prod_unchanged": true,
-  "finished_at": 1790508141.2832031,
+  "finished_at": 1790508533.784657,
   "result": "PASS",
   "drill_commit_marker": "drill0001"
 }
diff --git a/conductor/webchat/evidence/ready-drill.json b/conductor/webchat/evidence/ready-drill.json
index 90f151f..9846da3 100644
--- a/conductor/webchat/evidence/ready-drill.json
+++ b/conductor/webchat/evidence/ready-drill.json
@@ -7,7 +7,7 @@
       "text": "Reply with exactly: drill A1",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.002,
+      "elapsed_seconds": 0.943,
       "busy_in_attempts": false
     },
     {
@@ -15,7 +15,7 @@
       "text": "Reply with exactly: drill B1",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 0.98,
+      "elapsed_seconds": 1.014,
       "busy_in_attempts": false
     },
     {
@@ -23,7 +23,7 @@
       "text": "Reply with exactly: drill A2",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.011,
+      "elapsed_seconds": 0.963,
       "busy_in_attempts": false
     },
     {
@@ -31,7 +31,7 @@
       "text": "Reply with exactly: drill B2",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.018,
+      "elapsed_seconds": 0.666,
       "busy_in_attempts": false
     },
     {
@@ -39,7 +39,7 @@
       "text": "Reply with exactly: drill A3",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.021,
+      "elapsed_seconds": 0.656,
       "busy_in_attempts": false
     },
     {
@@ -47,7 +47,7 @@
       "text": "Reply with exactly: drill B3",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.291,
+      "elapsed_seconds": 0.686,
       "busy_in_attempts": false
     },
     {
@@ -55,7 +55,7 @@
       "text": "Reply with exactly: drill A4",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.031,
+      "elapsed_seconds": 0.697,
       "busy_in_attempts": false
     },
     {
@@ -63,7 +63,7 @@
       "text": "Reply with exactly: drill B4",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.019,
+      "elapsed_seconds": 0.704,
       "busy_in_attempts": false
     },
     {
@@ -71,7 +71,7 @@
       "text": "Reply with exactly: drill A5",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 1.01,
+      "elapsed_seconds": 0.699,
       "busy_in_attempts": false
     },
     {
@@ -79,18 +79,18 @@
       "text": "Reply with exactly: drill B5",
       "status": "done",
       "provider": "gemini",
-      "elapsed_seconds": 0.999,
+      "elapsed_seconds": 0.996,
       "busy_in_attempts": false
     }
   ],
-  "started_at": 1790508141.4210072,
+  "started_at": 1790508429.6953669,
   "locks": [
     "codex: drill holds background lock",
     "cursor: drill holds background lock",
     "gemini: drill holds background lock",
     "minimax: drill holds background lock"
   ],
-  "p50_seconds": 1.015,
+  "p50_seconds": 0.702,
   "via_tsnet": true,
   "merge_refusal": {
     "ok": true,
@@ -100,6 +100,6 @@
     "duplicate_messages": 2,
     "idempotent_refusal": true
   },
-  "finished_at": 1790508151.9042199,
+  "finished_at": 1790508437.805533,
   "result": "PASS"
 }
diff --git a/conductor/webchat/music_notebook.py b/conductor/webchat/music_notebook.py
index dde1ff6..17d9750 100644
--- a/conductor/webchat/music_notebook.py
+++ b/conductor/webchat/music_notebook.py
@@ -272,6 +272,16 @@ def analyze_chord_progression(text: str) -> str | None:
             numerals.append(f"{degree}{'m' if minor else ''}")
     roman = " – ".join(numerals)
     loop = " – ".join(symbols)
+    vi_step = 9
+    rel_idx = (tonic + vi_step) % 12
+    inv_major = {v: k for k, v in major_map.items()}
+    rel_root = inv_major.get(rel_idx)
+    relative_minor = f"{rel_root}m" if rel_root else None
+    rel_line = (
+        f"Relative minor: {relative_minor} (vi of {symbols[0]} major).\n"
+        if relative_minor
+        else ""
+    )
     if numerals[:4] == ["I", "V", "vi", "IV"] or numerals[:4] == ["I", "V", "VI", "IV"]:
         tip = "Classic pop loop — try swapping vi for a minor iv on the pre-chorus for a darker lift."
     elif all(n in ("I", "IV", "V", "vi") for n in numerals if n != "?"):
@@ -282,6 +292,7 @@ def analyze_chord_progression(text: str) -> str | None:
         f"Chord progression scan ($0, key of {symbols[0]}):\n"
         f"Loop: {loop}\n"
         f"Roman sketch: {roman}\n"
+        f"{rel_line}"
         f"{tip} Save each pass in Songs → versions for Bob handback."
     )
 
diff --git a/conductor/webchat/static/app.js b/conductor/webchat/static/app.js
index cf3b081..a5d0b47 100644
--- a/conductor/webchat/static/app.js
+++ b/conductor/webchat/static/app.js
@@ -50,7 +50,7 @@ if ($("login-form")) {
       return `<pre class="code-block" tabindex="0"><button type="button" class="copy-code" aria-label="Copy code">Copy</button><code>${inner}</code></pre>`;
     });
     html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
-    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" rel="noopener noreferrer" target="_blank">$1</a>');
+    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a class="md-link" href="$2" rel="noopener noreferrer" target="_blank">$1</a>');
     html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
     html = html.replace(/^### (.+)$/gm, "<h4 class=\"md-h\">$1</h4>");
     html = html.replace(/^## (.+)$/gm, "<h3 class=\"md-h\">$1</h3>");
@@ -1088,6 +1088,15 @@ if ($("login-form")) {
       return raw.replace("T", " ").replace("+00:00", " UTC");
     }
   }
+  function formatOpsSnapshotAge(iso) {
+    if (!iso) return "—";
+    const parsed = Date.parse(iso);
+    if (Number.isNaN(parsed)) return "—";
+    const secs = Math.max(0, Math.round((Date.now() - parsed) / 1000));
+    if (secs < 60) return `${secs}s ago`;
+    if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
+    return `${Math.round(secs / 3600)}h ago`;
+  }
   function renderOpsDetail(ops, hostId = "ops-detail") {
     const host = $(hostId);
     if (!host) return;
@@ -1112,6 +1121,7 @@ if ($("login-form")) {
       ["Scheduler queue", typeof ops.queue_ready_count === "number" ? `${ops.queue_ready_count} ready` : "—"],
       ["Live jobs", jobs.length ? `${jobs.length} on screen` : "none on screen"],
       ["Scores updated", ops.scores_measured_at ? ops.scores_measured_at.replace("T", " ").slice(0, 19) + " UTC" : "Unknown (no READY RESULT yet)"],
+      ["Ops snapshot", ops.generated_at ? formatOpsSnapshotAge(ops.generated_at) : "—"],
       ["Focus area", ops.scores_weakest?.area ? `${ops.scores_weakest.area} (${ops.scores_weakest.value})` : "—"],
       ["Bob catch-up", (ops.bob_catchup_preview || []).length ? (ops.bob_catchup_preview || []).join(" · ") : "—"],
     ];
@@ -1431,7 +1441,7 @@ if ($("login-form")) {
       const needBootstrap = si.launchd_loaded === false || (si.install_ready && si.launchd_loaded !== true);
       const bootstrapCmd = si.bootstrap_command || (si.bootstrap_script ? `bash ${si.bootstrap_script}` : "");
       lastBootstrapCommand = bootstrapCmd;
-      const siHeadline = [siShort, streak, logFresh].filter(Boolean).join(" · ");
+      const siHeadline = [siShort, streak, logFresh, schedule].filter(Boolean).join(" · ");
       $("self-improve-status").textContent = siHeadline || health;
       const details = $("self-improve-details");
       const extraHost = $("self-improve-extra");
@@ -1443,7 +1453,7 @@ if ($("login-form")) {
       const detailParts = [
         loaded,
         roundShip,
-        schedule && !si.loop_ready ? schedule : "",
+        schedule,
         needBootstrap && bootstrap ? bootstrap : "",
       ].filter(Boolean);
       if (details && extraHost) {
diff --git a/conductor/webchat/static/style.css b/conductor/webchat/static/style.css
index 3f465cb..8c2a01f 100644
--- a/conductor/webchat/static/style.css
+++ b/conductor/webchat/static/style.css
@@ -238,7 +238,8 @@ select option { background: var(--surface-2); color: var(--text); }
 .message.user { margin-left: auto; max-width: 83%; }
 .message .body { white-space: pre-wrap; overflow-wrap: anywhere; }
 .message.assistant .body { white-space: normal; }
-.message.assistant .body a { color: var(--accent); text-decoration: underline; }
+.message.assistant .body a { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
+.message.user .body a.md-link { color: #0a4d8c; text-decoration: underline; text-underline-offset: 2px; word-break: break-word; }
 .message.assistant .body code {
   font: 0.92em ui-monospace, SFMono-Regular, Menlo, monospace;
   padding: 2px 6px;
diff --git a/conductor/webchat/test_webchat.py b/conductor/webchat/test_webchat.py
index e00dab1..61a3212 100644
--- a/conductor/webchat/test_webchat.py
+++ b/conductor/webchat/test_webchat.py
@@ -924,6 +924,25 @@ class HandbackJobTests(Fixture):
         self.assertIsNotNone(reply)
         self.assertIn("real Jeff", reply or "")
 
+    def test_status_snapshot_cache_avoids_repeat_load(self):
+        ledger_dir = Path(__file__).resolve().parent.parent / "state"
+        if str(ledger_dir) not in sys.path:
+            sys.path.insert(0, str(ledger_dir))
+        import ledger as state_ledger
+
+        calls = {"n": 0}
+        real_load = state_ledger.load_state
+
+        def counting_load(root):
+            calls["n"] += 1
+            return real_load(root)
+
+        with patch.object(state_ledger, "load_state", side_effect=counting_load):
+            state_ledger._status_snapshot_cache.clear()
+            state_ledger.try_status_reply(self.root, "status")
+            state_ledger.try_status_reply(self.root, "quick status")
+        self.assertEqual(calls["n"], 1)
+
     def test_panel_round_changelog(self):
         reviews = self.root / "conductor/reviews"
         reviews.mkdir(parents=True, exist_ok=True)
@@ -1136,6 +1155,8 @@ class HandbackJobTests(Fixture):
         self.assertIsNotNone(prog)
         self.assertIn("Roman sketch", prog)
         self.assertIn("C", prog)
+        self.assertIn("Relative minor", prog)
+        self.assertIn("Am", prog)
 
     def test_self_improve_schedule_hint_from_plist(self):
         plist = self.root / "conductor/launchd/com.jeff.bob-webchat-self-improve.plist"
@@ -1284,7 +1305,7 @@ class HandbackJobTests(Fixture):
 
         result = run_eval(Path(__file__).resolve().parents[2])
         self.assertEqual(result["passed"], result["total"])
-        self.assertEqual(result["total"], 28)
+        self.assertEqual(result["total"], 29)
 
     def test_catchup_event_ack_cursor(self):
         ledger_dir = Path(__file__).resolve().parent.parent / "state"

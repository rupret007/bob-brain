#!/usr/bin/env python3
"""Test recovery, isolation, spending and process death without live model calls."""
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import api,budget,command,jobs,lanes,runtime,state,worker,workspaces


class ServicesTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='harden-test-')
        self.root=Path(self.tmp.name);self.core=self.root/'conductor';self.core.mkdir()
        self.patches=[]
        for module in (api,budget,jobs,lanes,runtime,state,worker,workspaces):
            for name,value in [('ROOT',self.root),('CONDUCTOR',self.core)]:
                if hasattr(module,name):self.patches.append(patch.object(module,name,value))
        self.patches += [patch.object(runtime,'HEARTBEATS',self.core/'heartbeats'),patch.object(runtime,'SERVICES',self.core/'services'),patch.dict(os.environ,{'BOB_ROOT':str(self.root)})]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def folder(self):
        p=self.root/'job';p.mkdir();return p
    def recover(self):
        with patch.object(runtime,'screen_sessions',return_value={}):jobs.recover()
    def test_journal_tail_repair_preserves_blocked_job(self):
        state.job_event('a','running',attempts=1)
        with (self.core/'jobs.jsonl').open('ab') as f:f.write(b'{partial')
        state.job_event('a','blocked',outcome='blocked')
        self.assertEqual(state.jobs()['a']['attempts'],1)
        self.assertTrue((self.core/'jobs.jsonl.interrupted-tail').exists())
    def test_middle_corruption_is_visible(self):
        state.job_event('a','running');p=self.core/'jobs.jsonl';p.write_text('bad\n'+p.read_text())
        with self.assertRaises(ValueError):state.jobs()
    def test_terminal_results_cannot_reopen_but_legacy_blockers_can(self):
        state.job_event('a','harvested',outcome='result')
        with self.assertRaises(ValueError):state.job_event('a','running')
        state.job_event('b','harvested',outcome='blocked');jobs.import_legacy()
        self.assertEqual(state.jobs()['b']['state'],'blocked')
    def test_blocker_is_never_harvested_or_closed(self):
        folder=self.folder();(folder/'BLOCKER.txt').write_text('unfinished')
        state.job_event('a','running',job_dir=str(folder));self.recover()
        self.assertIsNone(jobs.closeout(folder));self.assertEqual(state.jobs()['a']['state'],'blocked')
        self.assertGreater(state.jobs()['a']['retry_at'],time.time())
    def test_legacy_orphan_is_retained_without_replay(self):
        state.write_json(self.root/'local-cursor-job-watch-state.json',{'jobs':{'lost':{'running':True}}})
        jobs.import_legacy();self.assertEqual(state.jobs()['lost']['state'],'blocked')
        self.assertTrue((self.root/'lost/ORPHAN_WARNING.txt').exists())
    def test_three_failures_escalate(self):
        state.job_event('a','running',attempts=3);jobs.blocked(state.jobs()['a'],'failure')
        self.assertTrue(state.jobs()['a']['escalated'])
        self.assertIn('job-a',state.read_json(self.core/'alerts.json'))
    def test_verified_result_harvest_is_idempotent(self):
        folder=self.folder();(folder/'RESULT.txt').write_text('evidence')
        state.job_event('a','running',job_dir=str(folder),managed=True,verified=True)
        self.recover();self.recover();self.assertEqual(state.jobs()['a']['state'],'harvested')
        self.assertEqual(len(list((self.root/'next-prompts/_inbox').glob('*'))),1)
    def test_unverified_result_stays_unfinished(self):
        folder=self.folder();(folder/'RESULT.txt').write_text('claim')
        state.job_event('a','running',job_dir=str(folder),managed=True);self.recover()
        self.assertEqual(state.jobs()['a']['state'],'blocked')
    def test_live_writer_is_not_harvested(self):
        folder=self.folder();(folder/'RESULT.txt').write_text('still writing')
        state.job_event('a','running',job_dir=str(folder))
        with patch.object(runtime,'screen_sessions',return_value={'a':'1.a'}):jobs.recover()
        self.assertEqual(state.jobs()['a']['state'],'running')
    def test_alert_only_updates_json(self):
        (self.core/'STATUS.md').write_text('runtime owns this');state.alert('a','failure')
        self.assertEqual((self.core/'STATUS.md').read_text(),'runtime owns this')
    def test_runtime_renders_notes_and_login_state(self):
        (self.core/'status').mkdir();(self.core/'status/notes-cursor.md').write_text('real observation')
        state.write_json(self.core/'lanes.json',{'cursor':{'state':'needs_login'}})
        with patch.object(runtime,'screen_sessions',return_value={}):runtime.status_report()
        text=(self.core/'STATUS.md').read_text();self.assertIn('real observation',text);self.assertIn('cursor=needs_login',text)
    def test_concurrent_budget_reservations_cannot_cross_cap(self):
        def reserve(_):
            try:budget.reserve('minimax','x',1_000_000);return True
            except budget.BudgetExceeded:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:results=list(pool.map(reserve,range(50)))
        self.assertLess(sum(results),50);self.assertLessEqual(budget.totals('minimax')['committed_usd'],48)
    def test_response_usage_settles_unknown_retains_reservation(self):
        row=budget.reserve('minimax','x',1000);budget.settle('minimax',row,{'usage':{'prompt_tokens':100,'completion_tokens':200}})
        self.assertAlmostEqual(budget.totals('minimax')['spent_usd'],.00027)
        row=budget.reserve('minimax','x',1000);budget.settle('minimax',row,{})
        self.assertAlmostEqual(budget.totals('minimax')['reserved_usd'],row['reserved_usd'])
    def test_import_spend_once(self):
        p=self.core/'webjam-ux/spend.log';p.parent.mkdir();p.write_text('{"pass":"one","cost_usd":2}\n')
        budget.import_ux_ledger();budget.import_ux_ledger();self.assertEqual(budget.totals('minimax')['spent_usd'],2)
    def test_cap_stops_transport(self):
        state._append(budget.path('minimax'),{'call_id':'old','cost_usd':48})
        with patch.object(api,'run') as transport:
            with self.assertRaises(budget.BudgetExceeded):api.http_json('https://example.invalid',lane='minimax',prompt='x',max_tokens=1)
        transport.assert_not_called()
    def test_http_secret_file_and_retry(self):
        calls=[]
        def transport(cmd,**kw):
            config=Path(cmd[cmd.index('--config')+1]);self.assertIn('fixture-secret',config.read_text())
            self.assertEqual(config.stat().st_mode & 0o777,0o600);self.assertNotIn('fixture-secret',' '.join(cmd));self.assertNotIn('input',kw)
            calls.append(cmd);Path(cmd[cmd.index('-o')+1]).write_text('{"ok":true}')
            return NS(returncode=0,stdout='503' if len(calls)==1 else '200')
        with patch.object(api,'run',side_effect=transport),patch.object(api.time,'sleep'):
            self.assertTrue(api.http_json('https://example.invalid',headers={'Authorization':'fixture-secret'})['ok'])
        self.assertEqual(len(calls),2)
    def test_cursor_login_auto_activation(self):
        binary=self.root/'cursor';binary.touch()
        for output,expected in [('Not logged in','needs_login'),('Logged in','ready')]:
            with patch.object(lanes,'CURSOR',binary),patch.object(lanes,'run',return_value=NS(returncode=0,stdout=output,stderr='')):
                self.assertEqual(lanes.refresh()['cursor']['state'],expected)
    def test_lane_lease_shared_with_council_and_reviews(self):
        with state.lock('lane-cursor'),patch.object(lanes,'cli') as cli:
            with self.assertRaises(BlockingIOError):lanes.ask('cursor','prompt')
        cli.assert_not_called()
    def test_scheduler_limits(self):
        health={n:{'state':'ready'} for n in lanes.LANES};coder={'kind':'coding','project':'WebJam'}
        active=[dict(coder,engine='codex')]
        self.assertFalse(jobs.can_assign(coder,'cursor',active,health));self.assertFalse(jobs.can_assign(coder,'gemini',[],health))
        self.assertTrue(jobs.can_assign(dict(coder,kind='non-coding'),'gemini',active,health))
        self.assertFalse(jobs.can_assign(coder,'cursor',[{'engine':str(i)} for i in range(5)],health))
    def test_project_and_ci_priority(self):
        p=self.core/'services';p.mkdir();state.write_json(p/'backlog.json',[{'id':'feature','project':'WebJam','priority':20},{'id':'sb','project':'StoryBoard','priority':0},{'id':'ci','project':'WebJam','priority':0}])
        self.assertEqual([r['id'] for r in jobs.queue_specs()],['ci','feature','sb'])
    def test_worktrees_separate_and_main_push_denied(self):
        repo=self.root/'repo';repo.mkdir();workspaces.git(repo,'init','-b','main')
        workspaces.git(repo,'-c','user.name=Test','-c','user.email=test@localhost','commit','--allow-empty','-m','fixture')
        for name in ('a','b'):
            workspaces.prepare({'repo':str(repo),'worktree':str(self.root/name),'branch':'draft/'+name,'job_dir':str(self.root/('job-'+name))})
        self.assertNotEqual(workspaces.git(self.root/'a','branch','--show-current'),workspaces.git(self.root/'b','branch','--show-current'))
        result=subprocess.run([str(self.root/'job-a/hooks/pre-push')],input='refs/heads/draft/a abc refs/heads/main 0000000000000000000000000000000000000000\n',text=True,capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
    def test_codex_has_commit_push_configuration(self):
        response='{"type":"item.completed","item":{"type":"agent_message","text":"evidence"}}\n'
        with patch.object(lanes,'run',return_value=NS(returncode=0,stdout=response,stderr='')) as call,patch.object(lanes,'sandbox_command',side_effect=lambda cmd,cwd,**kwargs:cmd):lanes.cli('codex','task',self.root,True,100)
        self.assertEqual(call.call_args.kwargs['cwd'],str(self.root));self.assertIn('--dangerously-bypass-approvals-and-sandbox',call.call_args.args[0])
    def test_watchdog_caps_restarts(self):
        now=time.time();runtime.HEARTBEATS.mkdir();sessions={'svc-'+n:'1.svc-'+n for n in runtime.INTERVALS}
        for n in runtime.INTERVALS:(runtime.HEARTBEATS/n).touch()
        state.write_json(self.core/'supervisor.json',{n:{'ever_started':True,'started_at':now} for n in runtime.INTERVALS})
        with patch.object(runtime,'screen_sessions',return_value=sessions),patch.object(runtime,'run',return_value=NS(returncode=0)),patch.object(runtime,'start_screen',return_value=True),patch.object(runtime,'service_lock_held',return_value=False):
            for _ in range(4):
                data=state.read_json(self.core/'supervisor.json');data['reviewer']['started_at']=now-4000;state.write_json(self.core/'supervisor.json',data)
                os.utime(runtime.HEARTBEATS/'reviewer',(now-4000,now-4000));runtime.ensure_services(True,'watchdog')
        self.assertEqual(len(state.read_json(self.core/'supervisor.json')['reviewer']['restarts']),3)
    def test_timeout_kills_grandchild(self):
        path=self.root/'child.pid';child="import os,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);open(%r,'w').write(str(os.getpid()));time.sleep(60)"%str(path)
        parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',%r]);time.sleep(60)"%child
        start=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):command.run([sys.executable,'-c',parent],timeout=.5,capture_output=True)
        self.assertLess(time.monotonic()-start,3)
        probe=command.run(['ps','-p',path.read_text(),'-o','stat='],capture_output=True,text=True,timeout=5)
        self.assertTrue(not probe.stdout.strip() or probe.stdout.strip().startswith('Z'),probe.stdout)
    def test_devnull_and_core_write_boundary(self):
        result=command.run([sys.executable,'-c','import sys;print(repr(sys.stdin.read()))'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.stdout.strip(),"''")
        target=self.core/'PROMPT.md';target.write_text('protected')
        argv=[sys.executable,'-c',"from pathlib import Path;Path(%r).write_text('bad')"%str(target)]
        result=command.run(workspaces.sandbox_command(argv,self.root),capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0);self.assertEqual(target.read_text(),'protected')
    def test_git_rollback_before_import_and_chmod(self):
        shutil.copy2(HERE.parent/'bootstrap.py',self.core/'bootstrap.py');(self.core/'services').mkdir();(self.core/'PROMPT.md').write_text('rules')
        p=self.core/'services/example.py';p.write_text('VALUE = 1\n')
        workspaces.git(self.core,'init','-b','draft/test');workspaces.git(self.core,'add','.')
        workspaces.git(self.core,'-c','user.name=Test','-c','user.email=test@localhost','commit','-m','good');workspaces.git(self.core,'tag','last-good')
        p.write_text('def broken(:\n')
        workspaces.git(self.core,'add','services/example.py')
        workspaces.git(self.core,'-c','user.name=Test','-c','user.email=test@localhost','commit','-m','broken committed release')
        result=command.run([sys.executable,str(self.core/'bootstrap.py'),'guard'],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(p.read_text(),'VALUE = 1\n');self.assertEqual(p.stat().st_mode & 0o222,0)
        self.assertTrue(list((self.core/'reviews/quarantine').rglob('ROLLBACK.txt')))

    def test_progress_cannot_hide_final_blocker(self):
        lines=[{"type":"item.completed","item":{"type":"agent_message","text":"Working on it."}},
               {"type":"item.completed","item":{"type":"agent_message","text":"BLOCKER: actual failure"}}]
        output="\n".join(map(json.dumps,lines))
        with patch.object(lanes,'run',return_value=NS(returncode=0,stdout=output,stderr='')),patch.object(lanes,'sandbox_command',side_effect=lambda cmd,cwd,**kwargs:cmd):
            self.assertEqual(lanes.cli('codex','task',self.root,True,100),'BLOCKER: actual failure')

    def test_incorrect_harvest_is_reopened_and_retry_does_not_move(self):
        folder=self.folder();(folder/'RESULT.txt').write_text('Progress.\nBLOCKER: unfinished\n')
        state.job_event('a','harvested',job_dir=str(folder),managed=True,verified=True,outcome='result')
        self.recover();first=state.jobs()['a'];self.assertEqual(first['state'],'blocked')
        self.recover();self.assertEqual(state.jobs()['a']['retry_at'],first['retry_at'])

    def test_external_coder_claim_blocks_new_webjam_work(self):
        notice=self.core/'reviews/WEBJAM-TEST-BUILD-SCHEDULER.md';notice.parent.mkdir()
        notice.write_text('Status: ACTIVE — test build.\n')
        self.assertTrue(jobs.external_webjam_lease({}))
        notice.write_text('Status: COMPLETE\n');self.assertFalse(jobs.external_webjam_lease({}))
        self.assertTrue(jobs.external_webjam_lease({'svc-webjam-test':'123.svc-webjam-test'}))

    def test_coding_boundary_allows_real_commit_and_normal_push(self):
        repo=self.root/'repo';repo.mkdir();remote=self.root/'remote.git'
        command.run(['git','init','--bare',str(remote)],capture_output=True,timeout=10,check=True)
        workspaces.git(repo,'init','-b','draft/fixture');workspaces.git(repo,'config','user.name','Fixture');workspaces.git(repo,'config','user.email','fixture@localhost')
        workspaces.git(repo,'remote','add','origin',str(remote))
        (repo/'proof.txt').write_text('verified commit/push boundary\n')
        for args in [['add','proof.txt'],['commit','-m','fixture'],['push','origin','HEAD']]:
            command.run(workspaces.sandbox_command(['git','-C',str(repo),*args],repo),capture_output=True,timeout=10,check=True)
        self.assertEqual(workspaces.git(repo,'rev-parse','HEAD'),workspaces.git(remote,'rev-parse','refs/heads/draft/fixture'))

    def test_rebase_replacement_uses_authorized_new_draft_branch(self):
        folder=self.folder();record={'job_id':'a','job_dir':str(folder),'pr':26,'remote':'owner/repo',
                                   'branch':'draft/replacement','repo':str(self.root),'publish_new_draft':True}
        state.job_event('a','running',**{k:v for k,v in record.items() if k!='job_id'})
        response=NS(stdout=json.dumps({'isDraft':True,'state':'OPEN','headRefName':'published-26','url':'fixture'}))
        with patch.object(jobs,'run',return_value=response),patch.object(jobs,'prepare',return_value=self.root),patch.object(jobs,'evidence',return_value=''):
            jobs.setup_record(record)
        self.assertEqual(state.jobs()['a']['publish_branch'],'draft/replacement')
        self.assertEqual(record['fetch_ref'],'published-26')

    def test_claude_is_never_selected_for_coding_or_general_jobs(self):
        health={n:{'state':'ready'} for n in lanes.LANES}
        self.assertFalse(jobs.can_assign({'kind':'coding','project':'WebJam'},'claude',[],health))
        self.assertFalse(jobs.can_assign({'kind':'non-coding','project':'WebJam'},'claude',[],health))
        self.assertTrue(jobs.can_assign({'kind':'non-coding','project':'WebJam','small_review':True},'claude',[],health))
        with self.assertRaises(RuntimeError):lanes.ask('claude','Implement feature',coding=True)

    def test_claude_short_prompt_and_durable_rate_limit_backoff(self):
        with patch.object(lanes,'analysis_workspace',return_value=self.root),patch.object(lanes,'cli',return_value='A short review with evidence') as cli:
            lanes.ask('claude','x'*20000,purpose='review',timeout=500)
        self.assertLess(len(cli.call_args.args[1]),7000);self.assertEqual(cli.call_args.args[4],120)
        result=NS(returncode=1,stdout='{"is_error":true,"result":"rate_limit_error"}',stderr='')
        with patch.object(lanes,'run',return_value=result),patch.object(lanes,'sandbox_command',side_effect=lambda cmd,cwd,**kwargs:cmd):
            with self.assertRaises(RuntimeError):lanes.cli('claude','review',self.root,False,120)
        with patch.object(lanes,'cli') as cli:
            with self.assertRaisesRegex(RuntimeError,'cooldown'):lanes.ask('claude','review',purpose='review')
        cli.assert_not_called()

    def test_live_dashboard_snapshot_fields(self):
        import live_dashboard
        jobs_map = {"job-a": {"job_id": "job-a", "state": "running", "launched_at": time.time() - 120,
                               "engine": "cursor", "job_dir": str(self.root / "job-a")}}
        ops = live_dashboard.build_live_ops(sessions={"job-a": "1.job-a"}, jobs_map=jobs_map,
                                            lanes={"cursor": {"state": "busy"}}, spend={"minimax": {"committed_usd": 1.5}},
                                            now=time.time())
        self.assertIn("running_jobs", ops)
        self.assertEqual(ops["minimax_spend"]["cap_usd"], 59.0)
        self.assertTrue(ops["running_jobs"][0]["plain_now"])
        self.assertIn("scores", ops)
        self.assertIn("roles", ops)
        self.assertIn("now_line", ops)
        self.assertIn("webchat_round", ops)
        job = ops["running_jobs"][0]
        self.assertIn("log_tail", job)
        self.assertIn("last_commit", job)
        self.assertIn("stall_state", job)
        self.assertIn("events", job)
        self.assertTrue(any(e.get("kind") == "status" for e in job["events"]))
        self.assertIn("dashboard_freshness_seconds", ops)

    def test_alignment_events_append_and_tail(self):
        ledger_dir = str(HERE.parent / "state")
        if ledger_dir not in sys.path:
            sys.path.insert(0, ledger_dir)
        import alignment_events

        seq = alignment_events.append_event(self.root, actor="test", kind="chat-turn", summary="hello alignment")
        self.assertGreaterEqual(seq, 1)
        rows = alignment_events.read_events(self.root, since_seq=seq - 1)
        self.assertTrue(any(r.get("summary") == "hello alignment" for r in rows))
        self.assertTrue((self.root / "conductor/state/events.jsonl").exists())

    def test_state_ledger_catchup_and_now(self):
        ledger_dir = str(HERE.parent / "state")
        if ledger_dir not in sys.path:
            sys.path.insert(0, ledger_dir)
        import ledger as state_ledger

        state_ledger.write_now(self.root, "Round 8 alignment pass", sha="deadbeef")
        state_ledger.append_inbox(self.root, "re-read INBOX between steps", source="test")
        state_ledger.write_catchup(self.root)
        catchup = (self.root / "conductor/state/BOB-CATCHUP.md").read_text()
        self.assertIn("INBOX", catchup)
        self.assertTrue((self.root / "conductor/state/NOW.md").exists())
        loaded = state_ledger.load_state(self.root)
        self.assertGreaterEqual(int(loaded.get("revision") or 0), 2)

    def test_state_ledger_mutate_under_lock(self):
        ledger_dir = str(HERE.parent / "state")
        if ledger_dir not in sys.path:
            sys.path.insert(0, ledger_dir)
        import ledger as state_ledger

        rev0 = int(state_ledger.load_state(self.root).get("revision") or 0)
        state_ledger.record_webchat_turn(self.root, ask="hello", provider="state")
        state_ledger.add_open_ask(self.root, "ship tab polish")
        rev1 = int(state_ledger.load_state(self.root).get("revision") or 0)
        self.assertGreater(rev1, rev0)

    def test_scores_table_uses_highest_round_not_mtime(self):
        import live_dashboard
        with patch.object(live_dashboard, "CONDUCTOR", self.core):
            reviews = self.core / "reviews"
            reviews.mkdir(parents=True, exist_ok=True)
            old = reviews / "WEBCHAT-READY-R5-RESULT.md"
            new = reviews / "WEBCHAT-READY-R11-RESULT.md"
            old.write_text("| Area | R4 | **R5** |\n| Reliability | 9 | **9.5** |\n")
            new.write_text("| Area | R10 | **R11** |\n| Reliability | 9.8 | **9.9** |\n")
            os.utime(old, (time.time() + 60, time.time() + 60))
            rows = live_dashboard._scores_table()
        self.assertTrue(rows)
        self.assertIn("9.9", rows[0]["score"])

    def test_alignment_events_paginated_read(self):
        ledger_dir = str(HERE.parent / "state")
        if ledger_dir not in sys.path:
            sys.path.insert(0, ledger_dir)
        import alignment_events

        for index in range(1, 95):
            alignment_events.append_event(self.root, actor="test", kind="tick", summary=f"tick {index}")
        page = alignment_events.read_events_since_paginated(self.root, since_seq=0, page_size=40, max_pages=3)
        self.assertEqual(len(page), 94)

    def test_alignment_collect_events_truncation(self):
        ledger_dir = str(HERE.parent / "state")
        if ledger_dir not in sys.path:
            sys.path.insert(0, ledger_dir)
        import alignment_events

        for index in range(1, 250):
            alignment_events.append_event(self.root, actor="test", kind="chat-turn", summary=f"msg {index}")
        batch = alignment_events.collect_events_since(self.root, since_seq=0, page_size=40, max_pages=6)
        self.assertEqual(len(batch["events"]), 240)
        self.assertTrue(batch["truncated"])
        rest = alignment_events.collect_events_since(self.root, since_seq=batch["high_seq"], page_size=40, max_pages=6)
        self.assertGreaterEqual(len(rest["events"]), 9)
        self.assertFalse(rest["truncated"])

    def test_public_live_ops_allowlists_log_tail(self):
        import live_dashboard
        payload = live_dashboard.build_live_ops(sessions={}, jobs_map={}, lanes={}, spend={}, now=time.time())
        payload["running_jobs"] = [{
            "engine": "cursor", "stall_state": "running", "elapsed_seconds": 10,
            "plain_now": "PASS tests 46", "log_tail": ["ghp_supersecrettoken12345678901234567890", "Round 6 handback drill OK"],
            "last_commit": {"sha": "abc1234", "message": "fix webchat panel"},
            "round": 6, "live_screen": True, "started_at": "2026-09-27T00:00:00+00:00",
        }]
        payload["dashboard_freshness_seconds"] = 42
        payload["roles"] = {"building": "cursor", "reviewing": "gemini"}
        public = live_dashboard.public_live_ops(payload)
        self.assertEqual(public.get("dashboard_freshness_seconds"), 42)
        self.assertEqual(public.get("service_screen_count"), 0)
        self.assertEqual(public.get("roles", {}).get("building"), "cursor")
        tail = public["running_jobs"][0]["log_tail"]
        self.assertEqual(len(tail), 1)
        self.assertIn("handback", tail[0].lower())
        events = public["running_jobs"][0]["events"]
        self.assertTrue(any(e.get("kind") == "log" for e in events))
        self.assertTrue(any(e.get("kind") == "commit" for e in events))


    def test_public_live_ops_screen_count_contract(self):
        import json

        import live_dashboard

        payload = {
            "service_screens": ["svc-a", "svc-b", "ghp_supersecrettoken12345678901234567890"],
            "service_screen_count": "3",
            "running_jobs": [],
        }
        public = live_dashboard.public_live_ops(payload)
        self.assertEqual(public.get("service_screen_count"), 3)
        self.assertNotIn("service_screens", public)
        blob = json.dumps(public)
        self.assertNotIn("ghp_", blob)
        bad = live_dashboard.public_live_ops({"service_screen_count": -5, "service_screens": ["x"]})
        self.assertEqual(bad.get("service_screen_count"), 0)
        typed = live_dashboard.public_live_ops({"service_screen_count": True, "service_screens": ["a", "b"]})
        self.assertEqual(typed.get("service_screen_count"), 2)

    def test_compact_handback_digest(self):
        webchat = HERE.parent / "webchat"
        sys.path.insert(0, str(webchat))
        from handback import append_turn, compact_digest, refresh_summary
        folder = self.core / "handback"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "BOB-STATE.md").write_text("# state\nRunning: nightly review\n")
        append_turn(self.root, ask="status?", provider="gemini", jobs=[], files=[], commits=["deadbeef"],
                    confirmations=[], refusals=[], open_items=[])
        refresh_summary(self.root)
        digest = compact_digest(self.root)
        self.assertIn("nightly", digest.lower())
        self.assertIn("status", digest.lower())

if __name__=='__main__':unittest.main(verbosity=2)

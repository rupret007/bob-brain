"""Private browser proof of prepared handoff and checked artifact import."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import uuid
from unittest.mock import patch

from app import Server
from instinct_fixture import InstinctFixture
from test_project_handoffs import setup_report, return_for
import project_handoffs
import task_queue


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(); os.umask(0o077); args.output_dir.mkdir(parents=True,exist_ok=True)
    with InstinctFixture() as fixture:
        job=setup_report(fixture)
        fixture.chat.reconcile_tasks()
        fixture.chat.submit(fixture.identifier,'Prepare a review handoff of report '+job+' for Dot',str(uuid.uuid4()))
        handoff=next(iter(fixture.chat.get(fixture.identifier)['_project_handoffs'].values()))
        artifact=return_for(handoff)
        artifact['report']+=' <img src=x onerror=alert(1)> Imported text is data.'
        artifact['report_sha256']=hashlib.sha256(artifact['report'].encode()).hexdigest()
        original=task_queue.tasks(fixture.root)
        server=Server(('127.0.0.1',0),fixture.chat)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with patch('live_status_snapshot._screen_sessions',return_value={}),patch('live_status_snapshot.process_table',return_value={}):
                result=subprocess.run(['node',str(Path(__file__).with_name('browser_project_handoffs.cjs'))],
                    input=json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}',password=fixture.chat.password,
                                          handoff_id=handoff['handoff_id'],artifact=artifact)),
                    text=True,capture_output=True,timeout=120)
            if result.returncode: raise RuntimeError(result.stderr)
            evidence=json.loads(result.stdout)
            assert evidence['all_pass'] and len(evidence['browsers'])==2
            assert not fixture.mock.sends and not fixture.mock.unexpected_writes
            assert not fixture.providers.calls and task_queue.tasks(fixture.root)==original
            evidence.update(scope='private fixture; authenticated Chromium/WebKit handoff UI, no native receiver',
                            model_calls=0,texts_sent=0,workers_executed=0,task_journal_unchanged=True)
            (args.output_dir/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
            print(json.dumps(evidence))
        finally:
            server.shutdown(); server.server_close(); thread.join(3)


if __name__=='__main__':main()

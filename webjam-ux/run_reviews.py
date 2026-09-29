#!/usr/bin/env python3
"""Run independent review calls concurrently; no code-writing agents are launched."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
HELPER = ROOT.parents[1] / 'bin/ask-minimax.sh'


def run(row):
    number = row['pass']
    name = f'pass-{number:03d}'
    if (ROOT / (name + '.md')).exists() or (ROOT / (name + '.error.txt')).exists():
        return {'pass': number, 'skipped_existing': True}
    cmd = [str(HELPER), '--ux-pass', str(number), str(ROOT / row['prompt'])]
    result = subprocess.run(cmd, capture_output=True, text=True)
    (ROOT / (name + '.runner.log')).write_text(result.stdout + result.stderr)
    return {'pass': number, 'file': row.get('file'), 'exit': result.returncode,
            'result': result.stdout.strip()[-1200:]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=999)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--manifest', default='manifest.json')
    args = parser.parse_args()
    rows = [r for r in json.loads((ROOT / args.manifest).read_text())
            if args.start <= r['pass'] <= args.end]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run, row) for row in rows]
        for future in as_completed(futures):
            print(json.dumps(future.result()), flush=True)


if __name__ == '__main__':
    main()

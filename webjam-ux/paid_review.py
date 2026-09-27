#!/usr/bin/env python3
"""One metered MiniMax review. No automatic retries; uncertain calls stay reserved."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
INPUT_RATE = 0.30 / 1_000_000
OUTPUT_RATE = 1.20 / 1_000_000
RESERVE_INPUT_RATE = 0.375 / 1_000_000
CAP = 48.0


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def account(event):
    with (ROOT / 'budget.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = ROOT / 'spend.log'
        events = [json.loads(s) for s in ledger.read_text().splitlines()] if ledger.exists() else []
        calls = {}
        for row in events:
            calls[row['pass']] = row
        committed = sum(r.get('cost_usd', r.get('reserved_usd', 0)) for r in calls.values())
        if event['event'] == 'reserve':
            if event['pass'] in calls:
                raise RuntimeError('Pass already attempted; choose a new pass number.')
            if committed + event['reserved_usd'] > CAP:
                raise RuntimeError('Budget guard: next worst-case reservation exceeds $48.')
        event['at'] = stamp()
        with ledger.open('a') as out:
            out.write(json.dumps(event, sort_keys=True) + '\n')
            out.flush()
            os.fsync(out.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('number', type=int)
    parser.add_argument('prompt', type=Path)
    parser.add_argument('--max-tokens', type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 32000:
        raise ValueError('max-tokens outside review guard')
    key = os.environ.get('MINIMAX_API_KEY')
    if not key:
        raise RuntimeError('MINIMAX_API_KEY missing; no request sent')
    prompt = args.prompt.read_text()
    name = f'pass-{args.number:03d}'
    # UTF-8 bytes conservatively bound prompt tokens. Cache writes cost more
    # than normal input, so reserve at that rate; no cache discount assumed.
    reserve = (len(prompt.encode()) + 1000) * RESERVE_INPUT_RATE + args.max_tokens * OUTPUT_RATE
    account({'pass': name, 'event': 'reserve', 'reserved_usd': reserve,
             'model': 'MiniMax-M2.7', 'max_tokens': args.max_tokens})
    body = {'model': 'MiniMax-M2.7', 'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': args.max_tokens, 'reasoning_split': True,
            'temperature': 0.5}
    request = urllib.request.Request(
        'https://api.minimax.io/v1/text/chatcompletion_v2',
        json.dumps(body).encode(),
        {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.load(response)
        (ROOT / 'raw').mkdir(exist_ok=True)
        (ROOT / 'raw' / (name + '.json')).write_text(json.dumps(result, indent=2))
        usage = result.get('usage', {})
        if all(k in usage for k in ('prompt_tokens', 'completion_tokens')):
            cost = usage['prompt_tokens'] * INPUT_RATE + usage['completion_tokens'] * OUTPUT_RATE
            account({'pass': name, 'event': 'response', 'cost_usd': cost,
                     'usage': usage, 'model': result.get('model'), 'response_id': result.get('id')})
        else:
            account({'pass': name, 'event': 'usage_missing', 'reserved_usd': reserve})
        if result.get('base_resp', {}).get('status_code', 0):
            raise RuntimeError('MiniMax API error: ' + str(result['base_resp']))
        choice = result.get('choices', [{}])[0]
        content = choice.get('message', {}).get('content', '')
        answer = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
        finish = choice.get('finish_reason')
        valid = bool(answer) and finish not in ('length', 'max_tokens') and '<think>' not in answer
        (ROOT / (name + '.md')).write_text(
            f'# {name} — MiniMax-M2.7\n\nStatus: {"complete" if valid else "INCOMPLETE; not accepted as review"}\n'
            f'Finish reason: {finish}\nUsage: `{json.dumps(usage)}`\n'
            f'Prompt: [source](prompts/{args.prompt.name})\n\n{answer or "No final answer returned."}\n')
        print(json.dumps({'pass': name, 'ok': valid, 'usage': usage, 'finish': finish}), flush=True)
        return 0 if valid else 2
    except Exception as exc:
        # Do not print request objects, URL credentials, or environment values.
        (ROOT / (name + '.error.txt')).write_text(type(exc).__name__ + ': ' + str(exc) + '\n')
        print(json.dumps({'pass': name, 'ok': False, 'error_type': type(exc).__name__}), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

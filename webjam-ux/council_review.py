#!/usr/bin/env python3
"""Read-only council calls; Claude has no tools and neither reviewer can edit."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('model', choices=('gemini', 'claude'))
    parser.add_argument('name')
    parser.add_argument('prompt', type=Path)
    args = parser.parse_args()
    folder = ROOT / 'council'
    folder.mkdir(exist_ok=True)
    target = folder / (args.model + '-' + args.name)
    prompt = args.prompt.read_text()
    if args.model == 'gemini':
        key = os.environ['GEMINI_API_KEY']
        model = os.environ.get('UX_GEMINI_MODEL', 'gemini-3.1-pro-preview')
        body = {'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'maxOutputTokens': 32000, 'temperature': 0.3,
                                     'thinkingConfig': ({'thinkingLevel': 'high'} if '3.' in model
                                                        else {'thinkingBudget': 8192})}}
        request = urllib.request.Request(
            'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
            json.dumps(body).encode(), {'Content-Type': 'application/json', 'x-goog-api-key': key})
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.load(response)
        target.with_suffix('.json').write_text(json.dumps(result, indent=2))
        candidate = result.get('candidates', [{}])[0]
        answer = '\n'.join(p.get('text', '') for p in candidate.get('content', {}).get('parts', [])
                           if not p.get('thought'))
        complete = candidate.get('finishReason') == 'STOP' and bool(answer.strip())
        usage = result.get('usageMetadata')
    else:
        env = dict(os.environ)
        env.pop('ANTHROPIC_API_KEY', None)
        cmd = ['claude', '-p', '--tools', '', '--no-session-persistence', '--setting-sources', '',
               '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--output-format', 'json']
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              env=env, cwd=ROOT, timeout=900)
        target.with_suffix('.stderr.txt').write_text(proc.stderr)
        target.with_suffix('.json').write_text(proc.stdout)
        result = json.loads(proc.stdout)
        answer = result.get('result', '')
        complete = proc.returncode == 0 and not result.get('is_error') and bool(answer.strip())
        usage = result.get('usage')
    target.with_suffix('.md').write_text(
        f'# {args.model} council — {args.name}\n\nStatus: {"complete" if complete else "INCOMPLETE"}\n'
        f'Usage: `{json.dumps(usage)}`\n\n{answer}\n')
    print(json.dumps({'model': args.model, 'name': args.name, 'ok': complete, 'usage': usage}), flush=True)
    return 0 if complete else 2


if __name__ == '__main__':
    raise SystemExit(main())

"""Private stdin/stdout worker for bounded file actions; no network or shell."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / name) for name in ('webchat', 'services', 'state')]

from local_tasks import LocalTasks, LocalTaskError, parse


def run(request):
    def no_search(_query):
        raise LocalTaskError('Web lookups are unavailable in the file worker.')

    actions = LocalTasks(request['folder'], root=request['root'], search=no_search,
                         clock=lambda: request['now'], _worker=True)
    actions.files.home = Path(request['home'])
    method, args = request['method'], request['args']
    if method not in ('handle', 'validate_routine'):
        raise LocalTaskError('Unsupported file worker operation.')
    spec = parse(args[0])
    if spec and spec['kind'] == 'search':
        raise LocalTaskError('Web lookups are unavailable in the file worker.')
    return getattr(actions, method)(*args, **request['kwargs'])


if __name__ == '__main__':
    try:
        result = {'result': run(json.load(sys.stdin))}
    except LocalTaskError as exc:
        result = {'error': str(exc)}
    print(json.dumps(result))

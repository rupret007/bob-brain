"""Find an installed browser runtime for isolated verification subprocesses."""
from __future__ import annotations

import os
from pathlib import Path


def playwright_environment(code: Path, environment=None):
    """Return a child environment without changing the caller's environment."""
    env = dict(os.environ if environment is None else environment)
    code = Path(code).resolve()
    override = env.get('BOB_PLAYWRIGHT_MODULE')
    if override is not None:
        if not override or not Path(override).is_dir():
            raise RuntimeError(
                'BOB_PLAYWRIGHT_MODULE must name an installed Playwright package directory: '
                + repr(override))
        module = Path(override)
    else:
        candidates = [code / 'node_modules/playwright',
                      *(parent / 'conductor/webchat/node_modules/playwright'
                        for parent in code.parents)]
        module = next((candidate for candidate in candidates if candidate.is_dir()), None)
        if module is None:
            raise RuntimeError(
                'Set BOB_PLAYWRIGHT_MODULE to the installed Playwright package; '
                f'no local or shared runtime was found from {code}')
    env['BOB_PLAYWRIGHT_MODULE'] = str(module.resolve())
    return env

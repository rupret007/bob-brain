"""N4 v3 fallback repros: PR #151 comments/reviews were empty on 2026-10-17.

These are replacement repros, not Karen's verbatim seven. Existing JS/TS files
are exercised through patch, staged and committed-range guard entry points.
"""
import difflib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

POL = Path(__file__).resolve().parents[1] / 'ops/lane-ops/nucbox/nuc-tools/gat-policy.py'
spec = importlib.util.spec_from_file_location('gat_n4_v3', POL)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
BASE = "it('works', () => {\n  expect(f()).toBe(1);\n});\n"
REPROS = (
    ('uncalled declaration', 'function never(){ expect(f()).toBe(1); }'),
    ('unused arrow', 'const never = () => { assert.equal(f(), 1); };'),
    ('local rebind', 'const expect = fake;'),
    ('global dot rebind', 'globalThis.expect = fake;'),
    ('global computed rebind', "globalThis['it'] = fake;"),
    ('exit expression', 'const result = process.exit(0);'),
    ('hook return', 'beforeAll(() => { return setup(); });'),
    ('jest mock', "jest.mock('./m', () => ({ f: () => 1 }));"),
    ('vi mock', "vi.mock('./m', () => ({ f: () => 1 }));"),
)


def patch(old, new, path='a.test.js'):
    return ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                       fromfile='a/' + path if old else '/dev/null',
                                       tofile='b/' + path, n=1000))


class N4V3(unittest.TestCase):
    def refused(self, old, new, reason, path='a.test.js'):
        diff = patch(old, new, path)
        for mode in ('patch', 'contents'):
            with self.subTest(mode=mode):
                findings = (policy.check(diff) if mode == 'patch' else
                            policy.check_files(policy.parse_files(diff), contents={path: (old, new)}))
                self.assertTrue(any(reason in r for r in findings), findings)

    def test_fallback_repros(self):
        for name, statement in REPROS:
            with self.subTest(repro=name):
                self.assertTrue(policy.check(patch(BASE, BASE + statement + '\n')))

    def test_uncalled_assertion_functions(self):
        for function in (
            'function never(){ expect(f()).toBe(1); }',
            'async function never(){ assert(f()); }',
            'const never = () => { expect(f()).toBe(1); };',
            'const never = () => assert.equal(f(), 1);',
            'const never = function named(){ expect(f()).toBe(1); };',
            'const never = function(){ assert.strictEqual(f(), 1); };',
            '(() => { expect(f()).toBe(1); });',
            'function never(){ expect(f()).toBe(1); never(); }',
            'function outer(){ inner(); }\nfunction inner(){ assert(f()); }',
            'const outer = () => { const inner = () => assert(f()); inner(); };',
        ):
            for path in ('a.test.js', 'a.spec.ts', '__tests__/a.tsx', 'a.test.mjs'):
                with self.subTest(function=function, path=path):
                    self.refused(BASE, BASE + function + '\n', 'uncalled', path)

    def test_added_wrapper_hides_unchanged_assertion(self):
        new = BASE.replace('  expect', '  function never(){\n  expect').replace('\n});', '\n  }\n});')
        self.refused(BASE, new, 'uncalled')
        old = 'function never(){\n  work();\n}\n' + BASE
        new = old.replace('  work();', '  work();\n  assert.equal(f(), 1);')
        self.refused(old, new, 'uncalled')

    def test_rebinding_forms(self):
        for name in ('expect', 'it', 'test', 'describe'):
            for statement in (
                f'const {name} = fake;', f'let {name};', f'var {name} = fake;',
                f'{name} = fake;', f'{name} ||= fake;', f'{name} += fake;',
                f'const safe = 1, {name} = fake;', f'let {name}: Runner = fake;',
                f'const {{ {name} }} = fake;', f'let {{ other: {name} }} = fake;',
                f'const {{ nested: {{ other: {name} }} }} = fake;',
                f'const [{name}] = fake;', f'({{ other: {name} }} = fake);',
                f'[{name}] = fake;', f'function {name}() {{}}',
                f'import {{ other as {name} }} from "fake";',
                f'import {name} from "fake";', f'import * as {name} from "fake";',
                f'globalThis.{name} = fake;', f'globalThis["{name}"] = fake;',
                f'globalThis[\'{name}\'] = fake;',
                f'globalThis[\'{name}\']\n = fake;',
            ):
                with self.subTest(statement=statement):
                    self.refused(BASE, statement + '\n' + BASE, 'rebind')

    def test_exit_anywhere_in_added_expression(self):
        for statement in ('const x = process.exit(0);', 'ready && process.exit(0);',
                          'if (process.exit(0)) {}', 'consume(process.exit(0));',
                          'const x = () => process.exit(0);', 'void process . exit (0);',
                          'process["exit"](0);'):
            with self.subTest(statement=statement):
                self.refused(BASE, BASE + statement + '\n', 'process.exit')

    def test_every_hook_refuses_even_terminal_returns(self):
        for hook in ('beforeAll', 'beforeEach', 'afterAll', 'afterEach'):
            for callback in ('() =>', 'function ()', 'async () =>', 'async function named()'):
                statement = f'{hook}({callback} {{ return setup(); }});'
                with self.subTest(statement=statement):
                    self.refused(BASE, BASE + statement + '\n', 'early exit')

    def test_mocks_are_flagged(self):
        for runner in ('jest', 'vi'):
            for call in (f'{runner}.mock', f'{runner} . mock', f'{runner}["mock"]'):
                with self.subTest(call=call):
                    self.refused(BASE, BASE + call + "('./m');\n", 'mock')

    def test_unchanged_hazards_do_not_block_unrelated_additions(self):
        for name, statement in REPROS:
            with self.subTest(repro=name):
                old = statement + '\n' + BASE
                new = old + 'checkResult();\n'
                self.assertEqual(policy.check(patch(old, new)), [])

    def test_live_assertions_and_called_helpers_still_pass(self):
        for statement in (
            "it('added', () => { expect(f()).toBe(1); });",
            "test('added', () => assert.equal(f(), 1));",
            'function check(){ expect(f()).toBe(1); }\ncheck();',
            'const check = () => assert(f());\ncheck();',
            'function check(){ assert(f()); }\nit("added", check);',
            '(() => { assert(f()); })();',
            'beforeEach(() => { expect(f()).toBe(1); });',
            'const text = "const expect = fake; jest.mock(x);";',
            '/* function never(){ assert(f()); } */ doWork();',
            'const alias = expect;\nconst other = globalThis.it;',
        ):
            with self.subTest(statement=statement):
                self.assertEqual(policy.check(patch(BASE, BASE + statement + '\n')), [])

    def test_staged_and_range_cli_refuse_fallback_repros(self):
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                return subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True, text=True)
            git('init', '-q')
            path = Path(repo) / 'a.spec.ts'
            path.write_text(BASE)
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=t@t', 'commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD').stdout.strip()
            for name, statement in REPROS:
                with self.subTest(repro=name):
                    path.write_text(BASE + statement + '\n')
                    git('add', '.')
                    result = subprocess.run([sys.executable, str(POL), '--staged', repo], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                    git('-c', 'user.name=Test', '-c', 'user.email=t@t', 'commit', '-qm', name)
                    result = subprocess.run([sys.executable, str(POL), '--range', repo, base, 'HEAD'], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 3, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

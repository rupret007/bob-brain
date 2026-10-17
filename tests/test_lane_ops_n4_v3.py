"""Karen's exact seven N4 v3 repros, plus the earlier supplemental cases.

Existing JS/TS files are exercised through patch, staged and committed-range
guard entry points. The exact probes use Karen's original BASE/body harness.
"""
import difflib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_lane_ops_n4_v2 import BASE as KAREN_BASE, E, before_expect

POL = Path(__file__).resolve().parents[1] / 'ops/lane-ops/nucbox/nuc-tools/gat-policy.py'
spec = importlib.util.spec_from_file_location('gat_n4_v3', POL)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
BASE = "it('works', () => {\n  expect(f()).toBe(1);\n});\n"
SUPPLEMENTAL_REPROS = (
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

EXACT_REPROS = (
    ('1 unused arrow', (before_expect('      const later = () => {').replace(
        E, E + '\n      };', 1),), 'uncalled'),
    ('2 uncalled declaration', (before_expect('      function never() {').replace(
        E, E + '\n      }', 1),), 'uncalled'),
    ('3 top-level expect', ('expect = () => ({ toBe() {} });\n' + KAREN_BASE,), 'rebind'),
    ('4 local expect', (before_expect('      const expect = () => ({ toBe() {} });'),), 'rebind'),
    ('5 global it', (before_expect('      globalThis.it = () => {};'),), 'rebind'),
    ('6 exit hook', (before_expect('      beforeAll(() => process.exit(0));'),), 'process.exit'),
    ('7 soft mocks', (before_expect("      jest.mock('./m');"),
                      before_expect("      vi.mock('./m');")), 'mock'),
)


def patch(old, new, path='a.test.js', context=1000):
    return ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                       fromfile='a/' + path if old else '/dev/null',
                                       tofile='b/' + path, n=context))


class N4V3(unittest.TestCase):
    def refused(self, old, new, reason, path='a.test.js'):
        diff = patch(old, new, path)
        for mode in ('patch', 'contents'):
            with self.subTest(mode=mode):
                findings = (policy.check(diff) if mode == 'patch' else
                            policy.check_files(policy.parse_files(diff), contents={path: (old, new)}))
                self.assertTrue(any(reason in r for r in findings), findings)

    def test_supplemental_repros(self):
        for name, statement in SUPPLEMENTAL_REPROS:
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
        for name, statement in SUPPLEMENTAL_REPROS:
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

    def test_declarations_without_initializers_and_multiline_calls(self):
        for statement, reason in (
            ('let safe, expect;', 'rebind'),
            ('var safe,\n it;', 'rebind'),
            ('process["exit"](0)', 'process.exit'),
            ('jest["mock"]("./m")', 'mock'),
            ('vi["mock"]("./m")', 'mock'),
        ):
            with self.subTest(statement=statement):
                self.refused(BASE, BASE + statement + '\n', reason)

    def test_unreachable_calls_do_not_authorize_assertion_helpers(self):
        for statement in (
            'function never(){ assert(f()); }\nif (false) never();',
            'function never(){ assert(f()); }\nif (false) { never(); }',
            'function never(){ assert(f()); }\nfalse && never();',
            'function* never(){ assert(f()); }\nnever();',
        ):
            with self.subTest(statement=statement):
                self.refused(BASE, BASE + statement + '\n', 'uncalled')

    def test_unchanged_computed_calls_without_semicolons(self):
        for call in ('process["exit"](0)', 'jest["mock"]("./m")', 'vi["mock"]("./m")'):
            old = BASE + call + '\n'
            with self.subTest(call=call):
                self.assertEqual(policy.check(patch(old, old + 'checkResult();\n')), [])

    def test_staged_and_range_cli_refuse_supplemental_repros(self):
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                return subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True, text=True)
            git('init', '-q')
            path = Path(repo) / 'a.spec.ts'
            path.write_text(BASE)
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=t@t', 'commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD').stdout.strip()
            for name, statement in SUPPLEMENTAL_REPROS:
                with self.subTest(repro=name):
                    path.write_text(BASE + statement + '\n')
                    git('add', '.')
                    result = subprocess.run([sys.executable, str(POL), '--staged', repo], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                    git('-c', 'user.name=Test', '-c', 'user.email=t@t', 'commit', '-qm', name)
                    result = subprocess.run([sys.executable, str(POL), '--range', repo, base, 'HEAD'], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 3, result.stdout + result.stderr)


class KarenExactN4V3(unittest.TestCase):
    def test_exact_seven_patch_and_contents(self):
        self.assertEqual(len(EXACT_REPROS), 7)
        for name, variants, reason in EXACT_REPROS:
            for new in variants:
                diff = patch(KAREN_BASE, new)
                for mode in ('patch', 'contents'):
                    with self.subTest(repro=name, new=new, mode=mode):
                        findings = (policy.check(diff) if mode == 'patch' else
                                    policy.check_files(policy.parse_files(diff),
                                                       contents={'a.test.js': (KAREN_BASE, new)}))
                        self.assertTrue(any(reason in r for r in findings), findings)

    def test_exact_seven_staged_and_range(self):
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                return subprocess.run(['git', '-C', repo, *args], check=True,
                                      capture_output=True, text=True)
            git('init', '-q')
            path = Path(repo) / 'a.test.js'
            path.write_text(KAREN_BASE)
            git('add', 'a.test.js')
            git('-c', 'user.name=Test', '-c', 'user.email=t@t', 'commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD').stdout.strip()
            for name, variants, reason in EXACT_REPROS:
                for new in variants:
                    path.write_text(new)
                    git('add', 'a.test.js')
                    staged = ['--staged', repo]
                    result = subprocess.run([sys.executable, str(POL), *staged],
                                            capture_output=True, text=True)
                    with self.subTest(repro=name, new=new, mode='staged'):
                        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                        self.assertIn(reason, result.stdout)
                    git('-c', 'user.name=Test', '-c', 'user.email=t@t', 'commit', '-qm', name)
                    result = subprocess.run([sys.executable, str(POL), '--range', repo, base, 'HEAD'],
                                            capture_output=True, text=True)
                    with self.subTest(repro=name, new=new, mode='range'):
                        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                        self.assertIn(reason, result.stdout)
                    if reason == 'mock':
                        for args in (staged, ['--range', repo, base, 'HEAD']):
                            with self.subTest(repro=name, new=new, push=args[0]):
                                result = subprocess.run([sys.executable, str(POL), '--push', *args],
                                                        capture_output=True, text=True)
                                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                                self.assertIn('GAT policy WARN:', result.stdout)
                                self.assertIn('.mock', result.stdout)

    def test_exact_soft_mocks_flagged_in_push_mode(self):
        for new in EXACT_REPROS[6][1]:
            for context in (0, 3, 1000):
                with self.subTest(new=new, context=context):
                    warnings = []
                    findings = policy.check(patch(KAREN_BASE, new, context=context),
                                            push=True, warnings=warnings)
                    self.assertEqual(findings, [])
                    self.assertTrue(any('.mock' in warning for warning in warnings), warnings)

    def test_push_mock_warning_only_for_new_calls(self):
        for statement in ("jest.mock('./m');", "vi.mock('./m');"):
            old = before_expect('      ' + statement)
            for new in (old + 'checkResult();\n',):
                warnings = []
                self.assertEqual(policy.check(patch(old, new), push=True, warnings=warnings), [])
                self.assertEqual(warnings, [])
            for quoted in ('// ' + statement, '/* ' + statement + ' */',
                           'const text = "' + statement + '";'):
                warnings = []
                self.assertEqual(policy.check(patch(KAREN_BASE, before_expect('      ' + quoted)),
                                              push=True, warnings=warnings), [])
                self.assertEqual(warnings, [])


if __name__ == '__main__':
    unittest.main()

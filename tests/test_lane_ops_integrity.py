"""Karen #151 test-integrity detector extensions (global rewrites, exit aliases, doMock, dead wrappers)."""
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_lane_ops_n4_v2 import BASE, E, before_expect

POL = Path(__file__).resolve().parents[1] / 'ops/lane-ops/nucbox/nuc-tools/gat-policy.py'
spec = importlib.util.spec_from_file_location('gat_integrity', POL)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

EXP = "        expect(f()).toBe(2);"


def top(stmt):
    return BASE.replace("\nfunction helper", "\n" + stmt + "\n\nfunction helper", 1)


def wrap(before, after):
    return BASE.replace(E, before + "\n" + E + "\n" + after, 1)


def staged(path, new, base=BASE):
    with tempfile.TemporaryDirectory() as repo:
        def sh(*args):
            return subprocess.run(args, cwd=repo, check=True, capture_output=True)

        sh('git', 'init', '-q')
        p = Path(repo) / path
        p.parent.mkdir(parents=True, exist_ok=True)
        if base is None:
            (Path(repo) / 'README').write_text('seed\n')
            sh('git', 'add', '-A')
            sh('git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'seed')
        p.write_text(base if base is not None else new)
        if base is None:
            sh('git', 'add', '-A')
            return subprocess.run([sys.executable, str(POL), '--staged', repo], capture_output=True, text=True)
        sh('git', 'add', '-A')
        sh('git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'base')
        p.write_text(new)
        sh('git', 'add', '-A')
        return subprocess.run([sys.executable, str(POL), '--staged', repo], capture_output=True, text=True)


class TestIntegrityDetector(unittest.TestCase):
    def assert_refused(self, name, new, reason, path='a.test.js', base=BASE):
        r = staged(path, new, base=base)
        with self.subTest(case=name):
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertIn(reason, r.stdout)

    def assert_allowed(self, name, new, path='a.test.js', base=BASE):
        r = staged(path, new, base=base)
        with self.subTest(case=name):
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_global_rewrites(self):
        cases = (
            ("defineProperty it", top("Object.defineProperty(globalThis, 'it', { value: () => {} });"), 'rebind'),
            ("Reflect.set expect", top("Reflect.set(globalThis, 'expect', () => ({ toBe() {} }));"), 'rebind'),
            ("Object.assign it", top("Object.assign(globalThis, { it: () => {} });"), 'rebind'),
            ("vi.stubGlobal expect", top("vi.stubGlobal('expect', () => ({ toBe() {} }));"), 'rebind'),
            ("expect.extend pass true", top("expect.extend({ toBe: () => ({ pass: true, message: () => '' }) });"), 'rebind'),
        )
        for name, stmt, reason in cases:
            self.assert_refused(name, stmt, reason)

    def test_exit_aliases(self):
        cases = (
            ("p.exit", top("const p = process;\np.exit(0);")),
            ("destructured exit", top("const { exit } = process;\nbeforeAll(() => exit(0));")),
            ("require process exit", top("beforeAll(() => require('process').exit(0));")),
            ("reallyExit", top("beforeAll(() => process.reallyExit(0));")),
        )
        for name, stmt in cases:
            self.assert_refused(name, stmt, 'process.exit')

    def test_domock_and_new_files(self):
        for name, stmt in (
            ('jest.doMock', top("jest.doMock('./m');")),
            ('vi.doMock', top("vi.doMock('./m');")),
            ('unstable_mockModule', top("jest.unstable_mockModule('./m', () => ({}));")),
        ):
            self.assert_refused(name, stmt, 'mock')
        new_body = "import { f } from './m';\njest.doMock('./m');\nit('n', () => { expect(f()).toBe(1); });\n"
        r = staged('b.test.js', new_body, base=None)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn('mock', r.stdout)
        r2 = staged('c.test.js', "globalThis.expect = () => ({ toBe() {} });\n", base=None)
        self.assertEqual(r2.returncode, 3, r2.stdout)
        self.assertIn('rebind', r2.stdout)

    def test_dead_code_wrappers(self):
        wrappers = (
            ("if Math.random>2", wrap("      if (Math.random() > 2) {", "      }")),
            ("for empty", wrap("      for (const _ of []) {", "      }")),
            ("while false var", wrap("      const no = false;\n      while (no) {", "      }")),
            ("switch no match", wrap("      switch (1) { case 2:", "      }")),
            ("catch expect", wrap("      try {\n        throw () => ({ toBe() {} });\n      } catch (expect) {", "      }"), 'rebind'),
            ("with expect", wrap("      with ({ expect: () => ({ toBe() {} }) }) {", "      }")),
            ("class method", wrap("      class K { m() {", "      } }")),
            ("object method", wrap("      const o = { m() {", "      } };")),
            ("getter", wrap("      const o = { get m() {", "      } };")),
        )
        for item in wrappers:
            name, body = item[0], item[1]
            reason = item[2] if len(item) > 2 else 'uncalled'
            with self.subTest(wrapper=name):
                self.assert_refused(name, body, reason)

    def test_post_return_helper_call_refused(self):
        bypass = before_expect(
            "      const later = () => {\n" + EXP + "\n      };\n      return;\n      later();"
        )
        self.assert_refused('post-return helper', bypass, 'uncalled')

    def test_legit_helper_after_control(self):
        legit = (
            BASE.replace(
                "      const r = await f();",
                "      const check = (v) => {\n        expect(v).toBe(1);\n      };\n      check(f());\n      const r = await f();",
                1,
            ),
            top("function check(v) {\n  expect(v).toBe(1);\n}").replace(E, "      check(f());\n" + E, 1),
            BASE.replace(
                "      const r = await f();",
                "      (() => {\n        expect(f()).toBe(1);\n      })();\n      const r = await f();",
                1,
            ),
        )
        for i, body in enumerate(legit):
            self.assert_allowed(f"legit-{i}", body)

    def test_mutant_m1_is_killed(self):
        orig = POL.read_text()
        needle = "                    if kind in ('return', 'label'):"
        self.assertIn(needle, orig)
        mutant = orig.replace(
            needle,
            "                    if False:\n                        return False  # M1",
        )
        POL.write_text(mutant)
        try:
            r = subprocess.run(
                [sys.executable, '-m', 'unittest', 'test_lane_ops_integrity.TestIntegrityDetector.test_post_return_helper_call_refused'],
                cwd=str(Path(__file__).resolve().parent),
                capture_output=True,
                text=True,
            )
        finally:
            POL.write_text(orig)
        self.assertNotEqual(r.returncode, 0, 'M1 mutant must be killed by post-return helper regression')
        self.assertTrue(re.search(r'^FAIL:', r.stderr, re.M), r.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()

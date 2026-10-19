"""N4 v2: Karen's exact probe fixtures, copied verbatim from SHA-256
f13df1e0d31a338b45698f8140f46f80f691d6a08c6b7a95eee98f9d84e0ccb2.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

POL = str(Path(__file__).resolve().parents[1] / "ops/lane-ops/nucbox/nuc-tools/gat-policy.py")

BASE = """import { f, g } from './m';

function helper(x) {
  const y = x + 1;
  return y;
}

describe('outer', () => {
  describe('inner', () => {
    it('works', async () => {
      const r = await f();
      if (r) {
        g();
      }
      expect(f()).toBe(1);
    });
  });
  it('arrow', () => expect(f()).toBe(1));
});
"""
E="      expect(f()).toBe(1);"
def before_expect(stmt): return BASE.replace(E, stmt+"\n"+E,1)
cases=[
 ("repro1 return await 0","a.test.js",before_expect("      return await 0;")),
 ("repro2 return expect resolves","a.test.js",before_expect("      return expect(f()).resolves;")),
 ("repro3 return new Promise","a.test.js",before_expect("      return new Promise(r=>r());")),
 ("return void 0","a.test.js",before_expect("      return void 0")),
 ("return;//","a.test.js",before_expect("      return;//")),
 ("return(0)","a.test.js",before_expect("      return(0)")),
 ("return newline 0","a.test.js",before_expect("      return\n      0")),
 ("if (1) return","a.test.js",before_expect("      if (1) return")),
 ("ts file","a.spec.ts",before_expect("      return;")),
 ("tsx file","a.test.tsx",before_expect("      return;")),
 ("mjs file","a.test.mjs",before_expect("      return;")),
 ("cjs file","a.test.cjs",before_expect("      return;")),
 ("__tests__ dir","__tests__/x.js",before_expect("      return;")),
 ("arrow body -> {}","a.test.js",BASE.replace("it('arrow', () => expect(f()).toBe(1));","it('arrow', () => {});")),
 ("test.skip added","a.test.js",BASE.replace("it('works'","it.skip('works'")),
 ("xit added","a.test.js",BASE.replace("it('works'","xit('works'")),
 ("xdescribe added","a.test.js",BASE.replace("describe('inner'","xdescribe('inner'")),
 ("it.only added","a.test.js",BASE.replace("it('works'","it.only('works'")),
 ("describe.only","a.test.js",BASE.replace("describe('inner'","describe.only('inner'")),
 ("test.skip new test","a.test.js",BASE.replace("  it('arrow'","  test.skip('n', () => {});\n  it('arrow'")),
 # legit
 ("LEGIT return closes block","a.test.js",BASE.replace(E+"\n    });",E+"\n      return;\n    });")),
 ("LEGIT helper return change","a.test.js",BASE.replace("  return y;","  const z = y;\n  return z;")),
 # bypass attempts
 ("BYPASS if(true){return;} new block","a.test.js",before_expect("      if (true) {\n        return;\n      }")),
 ("BYPASS if(globalThis){return}","a.test.js",before_expect("      if (globalThis) {\n        return;\n      }")),
 ("BYPASS return inside existing if","a.test.js",BASE.replace("        g();","        g();\n        return;")),
 ("BYPASS wrap expect in uninvoked fn","a.test.js",BASE.replace("      const r = await f();","      const r = await f();\n      }); (() => {",1)),
 ("BYPASS for..of loop return","a.test.js",before_expect("      for (const _ of [1]) {\n        return;\n      }")),
 ("BYPASS try{return}","a.test.js",before_expect("      try {\n        return;\n      } finally {}")),
 ("BYPASS label block","a.test.js",before_expect("      x: {\n        return;\n      }")),
 ("BYPASS throw-free reject promise","a.test.js",before_expect("      await new Promise(() => {});")),
 ("BYPASS expect.assertions(0) skip?","a.test.js",before_expect("      if (process.env.CI) {\n        return;\n      }")),
 ("BYPASS describe.skipIf","a.test.js",BASE.replace("describe('inner'","describe.skipIf(true)('inner'")),
 ("BYPASS it.todo","a.test.js",BASE.replace("it('works'","it.todo('works'")),
 ("BYPASS it['skip']","a.test.js",BASE.replace("it('works'","it['skip']('works'")),
 ("BYPASS const it2=it.skip alias","a.test.js",BASE.replace("describe('outer'","const T = it;\nconst S = T.skip;\ndescribe('outer'")),
 ("BYPASS comment out expect","a.test.js",BASE.replace(E,"      // expect(f()).toBe(1);")),
]


class KarenN4V2(unittest.TestCase):
    def check_staged(self, path, new, base=BASE):
        with tempfile.TemporaryDirectory() as repo:
            def sh(*args):
                return subprocess.run(args, cwd=repo, check=True, capture_output=True)
            sh("git", "init", "-q")
            p = Path(repo) / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(base)
            sh("git", "add", "-A")
            sh("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
            p.write_text(new)
            sh("git", "add", "-A")
            return subprocess.run([sys.executable, POL, "--staged", repo], cwd=repo,
                                  capture_output=True, text=True)

    def test_exact_karen_cases(self):
        self.assertEqual(len(cases), 36)
        for name, path, new in cases:
            with self.subTest(case=name, path=path):
                result = self.check_staged(path, new)
                expected = 0 if name.startswith("LEGIT ") else 3
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


    def test_return_must_belong_directly_to_the_test_callback(self):
        statements = (
            "if (ready) return;", "if (ready) { return; }", "for (;;) return;",
            "while (ready) return;", "do { return; } while (ready);",
            "label: return;", "label: { return; }", "{ return; }",
            "try { return; } finally {}", "const hidden = () => { return; };",
            "describe('suite', () => { return; });",
            "return; expect(f()).toBe(1);",
            "return void 0\n      expect(f()).toBe(1);",
            "return 0\n      !expect(f()).toBe(1);",
            "return 0\n      { expect(f()).toBe(1); }",
            "return\n      expect(f()).toBe(1);",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                new = BASE.replace(E + "\n    });", E + "\n      " + statement + "\n    });")
                result = self.check_staged("a.test.js", new)
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn("early exit", result.stdout)

    def test_terminal_callback_returns_and_balanced_new_blocks(self):
        for callback in ("async () =>", "async function ()", "async function named()"):
            base = BASE.replace("async () =>", callback)
            for statement in ("return;", "return await f();", "return expect(f()).resolves;",
                              "return new Promise(r=>r());", "return void 0", "return(0)"):
                with self.subTest(callback=callback, statement=statement):
                    new = base.replace(E + "\n    });", E + "\n      " + statement + "\n    });")
                    result = self.check_staged("a.spec.ts", new, base)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for statement in ("if (ready) { g(); }", "const braces = '}); return; {';",
                          "/* }); return; { */ g();", "const text = `return; }`;",
                          "if (ready) {\n        g();\n      }"):
            with self.subTest(statement=statement):
                result = self.check_staged("a.test.js", before_expect("      " + statement))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_added_closing_brace_is_independently_refused(self):
        new = BASE.replace("      const r = await f();", "      const r = await f();\n      }); (() => {", 1)
        result = self.check_staged("a.test.js", new)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("closes an existing block", result.stdout)
        new = BASE.replace("        g();", "        g();\n      } /* existing block */\n      if (false) {")
        result = self.check_staged("a.test.js", new)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("closes an existing block", result.stdout)

    def test_helper_exception_cannot_remove_or_weaken_test_code(self):
        changes = (
            BASE.replace("  return y;", "  return 0;"),
            BASE.replace("  return y;", "  return;\n  return y;"),
            BASE.replace("  return y;", "  const z = 0;\n  return z;"),
            BASE.replace("  return y;", "  const z = y;\n  return z;").replace(E, "      g();"),
            BASE.replace("        g();", "        return y;").replace("  return y;", "  return z;", 1),
        )
        for new in changes:
            with self.subTest(new=new):
                result = self.check_staged("a.test.js", new)
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_ambiguous_or_incomplete_syntax_fails_closed(self):
        for statement in ("const re = /return[}]/;", "const s = `${f()}`;",
                          "const el = <Widget />;", "if (ready) {", "label:"):
            with self.subTest(statement=statement):
                result = self.check_staged("a.test.tsx", before_expect("      " + statement))
                # A label followed by expect is valid, so exercise a missing body at EOF.
                if statement == "label:":
                    result = self.check_staged("a.test.js", BASE.replace(E + "\n    });", E + "\n      label:\n    });"))
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn("structure", result.stdout)


if __name__ == "__main__":
    unittest.main()

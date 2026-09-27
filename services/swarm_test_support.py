"""Real-Git fixture shared by offline swarm tests."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from planner import Planner


class SwarmRepository(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="swarm-unit-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo, self.conductor = self.root / "repo", self.root / "conductor"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Swarm test")
        self.git("config", "user.email", "swarm@test.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", "/dev/null")
        (self.repo / "code.py").write_text("before\n")
        (self.repo / "other.py").write_text("base\n")
        self.commit("contract")
        self.base = self.git("rev-parse", "HEAD")
        self.git("branch", "integration/webbob")
        self.planner = Planner(self.conductor, "webbob")
        self.planner.initialize(self.repo, "integration/webbob", self.base)

    def git(self, *args, repo=None):
        return subprocess.run(["git", "-C", str(repo or self.repo), *map(str, args)],
                              check=True, capture_output=True, text=True, timeout=15).stdout.strip()

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")

    def worker(self, name="one", path="code.py", content="feature\n", *, finish=True):
        branch = "draft/" + name
        self.git("checkout", "-b", branch, self.base)
        row = self.planner.assign(name, "Implement " + path, "feature", branch, [path], model_vendor="openai")
        (self.repo / path).write_text(content)
        sha = self.commit(name)
        self.git("checkout", "main")
        if finish:
            row = self.planner.finish(name, row["lease"]["token"], sha)
        return row

    def advance(self, path="other.py", content="train\n"):
        self.git("checkout", "integration/webbob")
        (self.repo / path).write_text(content)
        tip = self.commit("advance train")
        self.git("checkout", "main")
        return tip

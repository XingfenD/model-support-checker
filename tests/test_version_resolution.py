"""Regression tests for first-release version resolution.

The real bug: the local resolver iterated *all* tags by creation date,
including synthetic ``proto-*`` tags, and returned ``proto-v0.2.0`` for
DeepSeek-V4.1-Flash even though the implementation landed in v0.30.0.
"""

import os
import tempfile
import unittest

from src.framework_strategies.vllm import VllmStrategy

from tests.helpers import commit, git, init_repo, tag, write


MODEL_PATH = "vllm/models/deepseek_v41/__init__.py"
MODEL_BODY = "class DeepseekV41ForCausalLM:\n    pass\nEntryClass = [DeepseekV41ForCausalLM]\n"


class VersionResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = init_repo(self.tmp.name)
        self.strategy = VllmStrategy()
        self.ctx = self.strategy.make_context(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ignores_proto_tags_and_picks_first_stable_release(self):
        write(self.repo, "README.md", "start\n")
        commit(self.repo, "initial", date="2026-09-01T00:00:00+00:00")
        tag(self.repo, "v0.29.0", date="2026-09-01T00:00:00+00:00")

        write(self.repo, MODEL_PATH, MODEL_BODY)
        commit(self.repo, "add DeepSeek V4.1", date="2026-09-10T00:00:00+00:00")
        tag(self.repo, "proto-v0.2.0", date="2026-09-11T00:00:00+00:00")
        tag(self.repo, "v0.30.0", date="2026-09-12T00:00:00+00:00")

        write(self.repo, "README.md", "later\n")
        commit(self.repo, "later work", date="2026-09-20T00:00:00+00:00")
        tag(self.repo, "v0.31.0", date="2026-09-20T00:00:00+00:00")

        self.assertEqual(
            self.strategy.get_version(MODEL_PATH, self.ctx),
            "v0.30.0",
        )

    def test_follows_file_rename(self):
        write(self.repo, "README.md", "start\n")
        commit(self.repo, "initial", date="2026-09-01T00:00:00+00:00")
        write(self.repo, MODEL_PATH, MODEL_BODY)
        commit(self.repo, "add DeepSeek V4.1", date="2026-09-10T00:00:00+00:00")
        tag(self.repo, "v0.30.0", date="2026-09-12T00:00:00+00:00")

        git_rename = "vllm/models/deepseek_v41/model.py"
        os.makedirs(os.path.dirname(os.path.join(self.repo, git_rename)), exist_ok=True)

        git(self.repo, "mv", MODEL_PATH, git_rename)
        commit(self.repo, "rename model package", date="2026-09-14T00:00:00+00:00")

        self.assertEqual(
            self.strategy.get_version(git_rename, self.ctx),
            "v0.30.0",
        )

    def test_falls_back_to_rc_when_no_stable_tag_exists(self):
        write(self.repo, MODEL_PATH, MODEL_BODY)
        commit(self.repo, "add model", date="2026-09-10T00:00:00+00:00")
        tag(self.repo, "v0.29.0.rc1", date="2026-09-12T00:00:00+00:00")

        self.assertEqual(
            self.strategy.get_version(MODEL_PATH, self.ctx),
            "v0.29.0.rc1",
        )

    def test_returns_unreleased_when_no_tag_contains_the_commit(self):
        write(self.repo, "README.md", "start\n")
        commit(self.repo, "initial", date="2026-09-01T00:00:00+00:00")
        tag(self.repo, "v0.29.0", date="2026-09-01T00:00:00+00:00")
        write(self.repo, MODEL_PATH, MODEL_BODY)
        commit(self.repo, "add model", date="2026-09-10T00:00:00+00:00")

        self.assertEqual(
            self.strategy.get_version(MODEL_PATH, self.ctx),
            "unreleased (main)",
        )


if __name__ == "__main__":
    unittest.main()

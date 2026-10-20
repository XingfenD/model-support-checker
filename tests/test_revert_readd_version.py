"""Regression tests for version resolution across revert/re-add histories."""

import os
import subprocess
import tempfile
import unittest

from src.framework_strategies.vllm_ascend import VllmAscendStrategy

from tests.helpers import commit, git, init_repo, tag, write


OLD_PATH = "vllm_ascend/models/deepseek_v4/vl_model.py"
MODEL_PATH = "vllm_ascend/models/deepseek_v41/vl_model.py"
VISION_BODY = "class AscendDeepseekV4Vision:\n    pass\n"
MODEL_BODY = "class AscendDeepseekV41ForCausalLM:\n    pass\n"


class RevertReaddVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = init_repo(self.tmp.name)
        self.strategy = VllmAscendStrategy()
        self.ctx = self.strategy.make_context(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_revert_then_readd_uses_readd_tag(self):
        write(self.repo, MODEL_PATH, VISION_BODY)
        commit(
            self.repo,
            "V4 vision precursor",
            date="2026-09-04T00:00:00+00:00",
        )

        write(self.repo, MODEL_PATH, MODEL_BODY)
        commit(
            self.repo,
            "add DeepSeek V4.1 (#16544)",
            date="2026-09-18T00:00:00+00:00",
        )

        git(self.repo, "rm", "-q", MODEL_PATH)
        commit(
            self.repo,
            "revert DeepSeek V4.1 (#16905)",
            date="2026-09-18T12:00:00+00:00",
        )
        tag(self.repo, "v0.28.0.rc1", date="2026-09-28T00:00:00+00:00")

        os.makedirs(
            os.path.dirname(os.path.join(self.repo, MODEL_PATH)),
            exist_ok=True,
        )
        write(self.repo, MODEL_PATH, MODEL_BODY)
        commit(
            self.repo,
            "re-add DeepSeek V4.1 (#16925)",
            date="2026-09-21T00:00:00+00:00",
        )
        tag(self.repo, "v0.29.0.rc1", date="2026-09-29T00:00:00+00:00")

        self.assertEqual(
            self.strategy.get_version(MODEL_PATH, self.ctx),
            "v0.29.0.rc1",
        )

        # The early tag really does not contain the file.
        with self.assertRaises(subprocess.CalledProcessError):
            git(self.repo, "cat-file", "-e", f"v0.28.0.rc1:{MODEL_PATH}")
        git(self.repo, "cat-file", "-e", f"v0.29.0.rc1:{MODEL_PATH}")

    def test_pure_rename_anchors_at_original_add(self):
        os.makedirs(
            os.path.dirname(os.path.join(self.repo, OLD_PATH)),
            exist_ok=True,
        )
        write(self.repo, OLD_PATH, MODEL_BODY)
        commit(
            self.repo,
            "add original model file",
            date="2026-09-10T00:00:00+00:00",
        )
        tag(self.repo, "v0.30.0", date="2026-09-12T00:00:00+00:00")

        os.makedirs(
            os.path.dirname(os.path.join(self.repo, MODEL_PATH)),
            exist_ok=True,
        )
        git(self.repo, "mv", OLD_PATH, MODEL_PATH)
        commit(
            self.repo,
            "rename model file",
            date="2026-09-14T00:00:00+00:00",
        )
        tag(self.repo, "v0.31.0", date="2026-09-15T00:00:00+00:00")

        self.assertEqual(
            self.strategy.get_version(MODEL_PATH, self.ctx),
            "v0.30.0",
        )

    def test_copy_readd_anchors_at_copy_commit(self):
        # The real vLLM-Ascend re-add is detected as a copy (C062) because
        # the V4 source file exists; a plain --diff-filter=A misses it.
        write(self.repo, OLD_PATH, MODEL_BODY)
        commit(
            self.repo,
            "V4 vision source",
            date="2026-09-04T00:00:00+00:00",
        )

        write(self.repo, MODEL_PATH, MODEL_BODY)
        commit(
            self.repo,
            "add DeepSeek V4.1 (#16544)",
            date="2026-09-18T00:00:00+00:00",
        )

        git(self.repo, "rm", "-q", MODEL_PATH)
        commit(
            self.repo,
            "revert DeepSeek V4.1 (#16905)",
            date="2026-09-18T12:00:00+00:00",
        )
        tag(self.repo, "v0.28.0.rc1", date="2026-09-28T00:00:00+00:00")

        os.makedirs(
            os.path.dirname(os.path.join(self.repo, MODEL_PATH)),
            exist_ok=True,
        )
        write(self.repo, MODEL_PATH, MODEL_BODY)
        readd = commit(
            self.repo,
            "re-add DeepSeek V4.1 (#16925)",
            date="2026-09-21T00:00:00+00:00",
        )
        tag(self.repo, "v0.29.0.rc1", date="2026-09-29T00:00:00+00:00")

        copy_commits = git(
            self.repo,
            "log",
            "--follow",
            "--diff-filter=C",
            "--format=%H",
            "--",
            MODEL_PATH,
        ).stdout.split()
        self.assertIn(readd, copy_commits)
        self.assertEqual(
            self.strategy.get_version(MODEL_PATH, self.ctx),
            "v0.29.0.rc1",
        )


if __name__ == "__main__":
    unittest.main()

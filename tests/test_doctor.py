"""Regression tests for checkout validation in doctor / clone."""

import contextlib
import io
import os
import tempfile
import unittest

from src.state.clone import validate_checkout
from src.state.doctor import doctor


def _make_repo(root):
    os.makedirs(os.path.join(root, ".git"), exist_ok=True)


def _write_model(root, rel_dir, name="llama.py"):
    models = os.path.join(root, rel_dir)
    os.makedirs(models, exist_ok=True)
    with open(os.path.join(models, name), "w", encoding="utf-8") as f:
        f.write("class LlamaForCausalLM:\n    pass\n")


def _state(fw_name, path):
    return {"mode": "local", f"{fw_name.replace('-', '_')}_path": path}


class DoctorCheckoutTests(unittest.TestCase):
    def test_sglang_models_dir_without_init_is_healthy(self):
        with tempfile.TemporaryDirectory() as repo:
            _make_repo(repo)
            _write_model(repo, "python/sglang/srt/models")

            issues = doctor(_state("sglang", repo), None, framework="sglang")

            self.assertEqual([i.message for i in issues], [])

    def test_vllm_models_dir_with_init_is_healthy(self):
        with tempfile.TemporaryDirectory() as repo:
            _make_repo(repo)
            _write_model(
                repo, "vllm/model_executor/models", name="__init__.py"
            )

            issues = doctor(_state("vllm", repo), None, framework="vllm")

            self.assertEqual([i.message for i in issues], [])

    def test_missing_models_dir_is_reported(self):
        with tempfile.TemporaryDirectory() as repo:
            _make_repo(repo)

            issues = doctor(_state("sglang", repo), None, framework="sglang")

            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].severity, "warning")
            self.assertIn("not found", issues[0].message)


class ValidateCheckoutTests(unittest.TestCase):
    def test_sglang_namespace_models_dir_does_not_warn(self):
        with tempfile.TemporaryDirectory() as repo:
            _write_model(repo, "python/sglang/srt/models")
            out = io.StringIO()

            with contextlib.redirect_stdout(out):
                validate_checkout(repo, "sglang")

            self.assertEqual(out.getvalue(), "")

    def test_empty_models_dir_warns(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, "python/sglang/srt/models"))
            out = io.StringIO()

            with contextlib.redirect_stdout(out):
                validate_checkout(repo, "sglang")

            self.assertIn("contains no Python files", out.getvalue())

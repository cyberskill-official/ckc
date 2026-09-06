"""Unit tests for optional OpenAI-compatible / LM Studio synthesis."""

from __future__ import annotations
import json
import unittest
from unittest.mock import MagicMock, patch

from code_chain.core import llm


class TestLlmHelpers(unittest.TestCase):
    def test_not_configured_without_base_url(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(llm.resolve_llm_config())
            self.assertFalse(llm.llm_is_configured())
            self.assertEqual(
                llm.maybe_append_llm_section("# hello", task="query", enabled=True),
                "# hello",
            )

    def test_resolve_ckc_env(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "qwen",
            "CKC_LLM_API_KEY": "lm-studio",
        }
        with patch.dict("os.environ", env, clear=True):
            cfg = llm.resolve_llm_config()
            self.assertEqual(cfg, ("http://127.0.0.1:1234/v1", "qwen", "lm-studio"))

    def test_resolve_openai_aliases(self):
        env = {
            "OPENAI_BASE_URL": "http://localhost:1234/v1/",
            "OPENAI_MODEL": "local",
            "OPENAI_API_KEY": "x",
        }
        with patch.dict("os.environ", env, clear=True):
            cfg = llm.resolve_llm_config()
            self.assertEqual(cfg[0], "http://localhost:1234/v1")
            self.assertEqual(cfg[1], "local")

    def test_chat_completions_mocked(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "local-model",
        }
        payload = {
            "choices": [{"message": {"content": "Short grounded summary."}}]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch.dict("os.environ", env, clear=True):
            with patch("urllib.request.urlopen", return_value=mock_resp) as mocked:
                text = llm.chat_completions(
                    [{"role": "user", "content": "hi"}], timeout=5
                )
                self.assertEqual(text, "Short grounded summary.")
                mocked.assert_called_once()

    def test_append_section_on_success(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "local-model",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch(
                "code_chain.core.llm.synthesize_stacked_context",
                return_value="Auth flows through login.",
            ):
                out = llm.maybe_append_llm_section(
                    "# Stacked\n\nbody", task="query", enabled=True
                )
        self.assertIn("## Local model synthesis", out)
        self.assertIn("Auth flows through login.", out)

    def test_soft_fail_appends_notice(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "local-model",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch(
                "code_chain.core.llm.synthesize_stacked_context", return_value=None
            ):
                out = llm.maybe_append_llm_section("# Keep me", enabled=True)
        self.assertIn("# Keep me", out)
        self.assertIn("Local model synthesis unavailable", out)

    def test_finalize_trim_llm_retrim(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "local-model",
        }
        long_body = "word " * 2000
        with patch.dict("os.environ", env, clear=True):
            with patch(
                "code_chain.core.llm.synthesize_stacked_context",
                return_value="SYNTH " + ("x" * 5000),
            ):
                out = llm.finalize_stacked_markdown(
                    long_body, task="query", enabled=True, max_tokens_budget=80
                )
        self.assertIn("truncated to max_tokens_budget", out)
        self.assertLessEqual(llm._approx_tokens(out), 80 + 20)

    def test_use_llm_false_skips_even_when_configured(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "local-model",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch(
                "code_chain.core.llm.synthesize_stacked_context"
            ) as synth:
                out = llm.finalize_stacked_markdown(
                    "# body", task="query", enabled=False, max_tokens_budget=4000
                )
        synth.assert_not_called()
        self.assertEqual(out.strip(), "# body")
        self.assertNotIn("Local model synthesis", out)


if __name__ == "__main__":
    unittest.main()

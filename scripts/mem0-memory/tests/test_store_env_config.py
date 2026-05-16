"""Store.config() honors MEM0_* env vars to enable proxy / OpenAI / fastembed modes
without code changes."""
from __future__ import annotations

import pytest

from mem0_memory.store import Store


def test_no_env_means_no_llm_or_embedder_blocks(hermes_home, monkeypatch, fake_memory_factory):
    """v3.2.0 backward compat: with no env, mem0 keeps its built-in OpenAI defaults."""
    for k in ("MEM0_LLM_BASE_URL", "MEM0_LLM_API_KEY", "MEM0_LLM_MODEL",
              "MEM0_EMBEDDER_PROVIDER", "MEM0_EMBEDDER_MODEL"):
        monkeypatch.delenv(k, raising=False)
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert "llm" not in cfg
    assert "embedder" not in cfg


def test_llm_base_url_env_injects_proxy_block(hermes_home, monkeypatch, fake_memory_factory):
    monkeypatch.setenv("MEM0_LLM_BASE_URL", "http://localhost:8765/v1")
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["config"]["openai_base_url"] == "http://localhost:8765/v1"
    # api_key + model fall back to safe defaults
    assert cfg["llm"]["config"]["api_key"] == "sk-mem0-local-dummy"
    assert cfg["llm"]["config"]["model"] == "gpt-5.5"


def test_llm_api_key_and_model_env_override(hermes_home, monkeypatch, fake_memory_factory):
    monkeypatch.setenv("MEM0_LLM_BASE_URL", "http://localhost:8765/v1")
    monkeypatch.setenv("MEM0_LLM_API_KEY", "sk-real")
    monkeypatch.setenv("MEM0_LLM_MODEL", "gpt-5.4-mini")
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert cfg["llm"]["config"]["api_key"] == "sk-real"
    assert cfg["llm"]["config"]["model"] == "gpt-5.4-mini"

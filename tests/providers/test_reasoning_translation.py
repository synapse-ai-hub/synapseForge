"""Unit tests for gateway x model reasoning translation.

Exercises the real ``translate_reasoning``, ``get_reasoning_options``
and ``get_reasoning_streaming_config`` from
``backend.agent.utils.model_catalog`` against an isolated SQLite
catalog seeded with representative models.dev rows (no network, no
mocks of the code under test).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.agent.ddl_setup import setup_database
from backend.agent.utils import model_catalog

_SEED_ROWS = [
    # (provider, model_id, reasoning, reasoning_options, npm)
    # Rows use representative reasoning_options shapes from models.dev.
    ("groq", "openai/gpt-oss-120b", 1,
     [{"type": "effort", "values": ["low", "medium", "high"]}],
     "@ai-sdk/groq"),
    ("groq", "qwen/qwen3.8-27b", 1,
     [{"type": "effort", "values": ["none", "default", "low", "medium", "high"]}],
     "@ai-sdk/groq"),
    ("groq", "llama-3.3-70b-versatile", 0, [], "@ai-sdk/groq"),
    ("openrouter", "openai/gpt-oss-120b", 1,
     [{"type": "effort", "values": ["low", "medium", "high"]}],
     "@openrouter/ai-sdk-provider"),
    ("openrouter", "qwen/qwen3.7-flash", 1,
     [{"type": "toggle"}, {"type": "budget_tokens"}],
     "@openrouter/ai-sdk-provider"),
    ("openrouter", "google/gemini-2.5-pro", 1,
     [{"type": "budget_tokens", "min": 128, "max": 32768}],
     "@openrouter/ai-sdk-provider"),
    ("openrouter", "google/gemini-3.1-pro-preview", 1,
     [{"type": "effort", "values": ["low", "medium", "high"]}],
     "@openrouter/ai-sdk-provider"),
    ("openrouter", "qwen/qwen3-235b-a22b", 1,
     [{"type": "toggle"}],
     "@openrouter/ai-sdk-provider"),
    ("openrouter", "deepseek/deepseek-r1", 1,
     [],
     "@openrouter/ai-sdk-provider"),
    ("google", "gemini-2.5-flash", 1,
     [{"type": "toggle"}, {"type": "budget_tokens", "min": 0, "max": 24576}],
     "@ai-sdk/google"),
    ("google", "gemini-3.1-pro-preview", 1,
     [{"type": "effort", "values": ["low", "medium", "high"]}],
     "@ai-sdk/google"),
    ("deepseek", "deepseek-flash", 1,
     [{"type": "toggle"}, {"type": "effort", "values": ["low", "high", "max"]}],
     "@ai-sdk/deepseek"),
    ("openai", "gpt-6-astra", 1,
     [{"type": "effort", "values": ["low", "medium", "high", "xhigh", "max"]}],
     "@ai-sdk/openai"),
    ("alibaba", "qwen3.8-max", 1,
     [{"type": "toggle"},
      {"type": "effort", "values": ["low", "medium", "xhigh"]},
      {"type": "budget_tokens", "min": 0, "max": 262144}],
     "@ai-sdk/openai-compatible"),
]


@pytest.fixture()
def catalog_db(tmp_path, monkeypatch):
    """Create an isolated catalog DB and patch the module connection."""
    db_path = str(tmp_path / "test_catalog.db")
    conn = sqlite3.connect(db_path)
    try:
        setup_database(conn)
        conn.executemany(
            """INSERT INTO model_catalog
               (provider, model_id, reasoning, reasoning_options, npm, updated_at)
               VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00')""",
            [
                (p, m, r, json.dumps(o), n)
                for p, m, r, o, n in _SEED_ROWS
            ],
        )
        conn.commit()
    finally:
        conn.close()

    def _fake_connect():
        fake = sqlite3.connect(db_path)
        fake.row_factory = sqlite3.Row
        return fake

    monkeypatch.setattr(model_catalog, "_connect", _fake_connect)
    return db_path


def tr(provider, value, model="", budget=None):
    """Call the real translator with explicit kwargs."""
    return model_catalog.translate_reasoning(
        provider=provider,
        reasoning_value=value,
        model_id=model,
        budget_tokens=budget,
    )


# --- Groq (plain OpenAI-compatible gateway) ---

def test_groq_effort_uses_string_shape(catalog_db):
    assert tr("groq", "high", "openai/gpt-oss-120b") == {"reasoning_effort": "high"}


def test_groq_off_variants(catalog_db):
    # gpt-oss only accepts low/medium/high: "off" sends nothing.
    for value in ("off", "none", False, "false"):
        assert tr("groq", value, "openai/gpt-oss-120b") == {}
    # qwen on groq accepts "none": "off" maps to it.
    for value in ("off", "none", False, "false"):
        assert tr("groq", value, "qwen/qwen3.8-27b") == {
            "reasoning_effort": "none"
        }


def test_groq_default_variants_send_nothing(catalog_db):
    for value in (None, "default", "", True, "on", "true"):
        assert tr("groq", value, "openai/gpt-oss-120b") == {}


def test_groq_unlisted_value_sends_nothing(catalog_db):
    assert tr("groq", "auto", "openai/gpt-oss-120b") == {}
    assert tr("groq", "xhigh", "openai/gpt-oss-120b") == {}
    assert tr("groq", 1, "openai/gpt-oss-120b") == {}


def test_groq_non_reasoning_model_sends_nothing(catalog_db):
    assert tr("groq", "high", "llama-3.3-70b-versatile") == {}


def test_groq_unknown_model_uses_gateway_fallback(catalog_db):
    assert tr("groq", "low", "some-future-model") == {"reasoning_effort": "low"}
    assert tr("groq", "off", "some-future-model") == {"reasoning_effort": "none"}


def test_translate_malformed_options_row_uses_gateway_default(catalog_db):
    conn = sqlite3.connect(catalog_db)
    try:
        conn.execute(
            "INSERT INTO model_catalog (provider, model_id, reasoning,"
            " reasoning_options, updated_at)"
            " VALUES ('groq', 'bad-model', 1, '{broken', '2026-01-01T00:00:00')"
        )
        conn.commit()
    finally:
        conn.close()
    assert tr("groq", "high", "bad-model") == {"reasoning_effort": "high"}


def test_translate_null_options_row_uses_gateway_default(catalog_db):
    conn = sqlite3.connect(catalog_db)
    try:
        conn.execute(
            "INSERT INTO model_catalog (provider, model_id, reasoning,"
            " reasoning_options, updated_at)"
            " VALUES ('groq', 'null-model', 1, NULL, '2026-01-01T00:00:00')"
        )
        conn.commit()
    finally:
        conn.close()
    assert tr("groq", "high", "null-model") == {"reasoning_effort": "high"}


# --- OpenRouter gateway (reasoning object) ---

def test_openrouter_effort_uses_object_shape(catalog_db):
    assert tr("openrouter", "medium", "openai/gpt-oss-120b") == {
        "reasoning": {"effort": "medium"}
    }


def test_openrouter_off_excludes_reasoning(catalog_db):
    assert tr("openrouter", "off", "openai/gpt-oss-120b") == {
        "reasoning": {"exclude": True}
    }


def test_openrouter_budget_model(catalog_db):
    # Realistic call: default reasoning (True) + explicit budget.
    assert tr("openrouter", True, "qwen/qwen3.7-flash", budget=5000) == {
        "reasoning": {"max_tokens": 5000}
    }
    assert tr("openrouter", "default", "qwen/qwen3.7-flash", budget=5000) == {
        "reasoning": {"max_tokens": 5000}
    }


def test_openrouter_off_wins_over_budget(catalog_db):
    assert tr("openrouter", "off", "qwen/qwen3.7-flash", budget=5000) == {
        "reasoning": {"exclude": True}
    }


def test_openrouter_budget_range_reaches_options(catalog_db):
    opts = model_catalog.get_reasoning_options("openrouter", "google/gemini-2.5-pro")
    assert opts["reasoning_type"] == "budget_tokens"
    assert opts["budget_min"] == 128
    assert opts["budget_max"] == 32768
    assert tr("openrouter", True, "google/gemini-2.5-pro", budget=2000) == {
        "reasoning": {"max_tokens": 2000}
    }


def test_openrouter_google_model_does_not_use_thinking_config(catalog_db):
    result = tr(
        "openrouter", "high", "google/gemini-3.1-pro-preview"
    )
    assert result == {"reasoning": {"effort": "high"}}
    assert "thinking_config" not in result


def test_openrouter_toggle_only_model(catalog_db):
    assert tr("openrouter", "default", "qwen/qwen3-235b-a22b") == {}
    assert tr("openrouter", "off", "qwen/qwen3-235b-a22b") == {
        "reasoning": {"exclude": True}
    }


def test_openrouter_no_control_model_sends_nothing(catalog_db):
    # deepseek-r1 via OpenRouter declares no caller control ([]).
    assert tr("openrouter", "high", "deepseek/deepseek-r1") == {}
    assert tr("openrouter", True, "deepseek/deepseek-r1", budget=5000) == {}
    assert tr("openrouter", "off", "deepseek/deepseek-r1") == {
        "reasoning": {"exclude": True}
    }


def test_openrouter_unknown_model_uses_gateway_shape(catalog_db):
    assert tr("openrouter", "high", "some-future-model") == {
        "reasoning": {"effort": "high"}
    }


def test_openrouter_effort_on_budget_only_model(catalog_db):
    # OpenRouter converts effort automatically for budget-based models.
    assert tr("openrouter", "high", "google/gemini-2.5-pro") == {
        "reasoning": {"effort": "high"}
    }


def test_openrouter_budget_on_effort_only_model(catalog_db):
    # max_tokens is ignored when the model does not support it.
    assert tr("openrouter", True, "openai/gpt-oss-120b", budget=5000) == {
        "reasoning": {"max_tokens": 5000}
    }


def test_openrouter_budget_on_toggle_only_model(catalog_db):
    assert tr("openrouter", True, "qwen/qwen3-235b-a22b", budget=5000) == {}


# --- Google direct gateway ---

def test_google_effort_uses_thinking_level(catalog_db):
    assert tr("google", "high", "gemini-3.1-pro-preview") == {
        "thinking_config": {"thinking_level": "high"}
    }


def test_google_effort_outside_values_sends_nothing(catalog_db):
    assert tr("google", "xhigh", "gemini-3.1-pro-preview") == {}


def test_google_budget_uses_thinking_budget(catalog_db):
    assert tr("google", True, "gemini-2.5-flash", budget=1000) == {
        "thinking_config": {"thinking_budget": 1000}
    }


def test_google_budget_on_level_model_uses_thinking_budget(catalog_db):
    assert tr("google", True, "gemini-3.1-pro-preview", budget=1000) == {
        "thinking_config": {"thinking_budget": 1000}
    }


def test_google_effort_on_budget_model_sends_nothing(catalog_db):
    # Gemini 2.5 has no thinking_level control.
    assert tr("google", "high", "gemini-2.5-flash") == {}


def test_google_off_disables_thinking(catalog_db):
    assert tr("google", "off", "gemini-2.5-flash") == {
        "thinking_config": {"thinking_budget": 0}
    }


def test_google_off_on_level_model_sends_nothing(catalog_db):
    assert tr("google", "off", "gemini-3.1-pro-preview") == {}


def test_google_default_sends_nothing(catalog_db):
    assert tr("google", "default", "gemini-3.1-pro-preview") == {}
    assert tr("google", None, "gemini-3.1-pro-preview") == {}


def test_google_unknown_model_uses_gateway_shape(catalog_db):
    assert tr("google", "high", "some-future-model") == {
        "thinking_config": {"thinking_level": "high"}
    }
    assert tr("google", True, "some-future-model", budget=1000) == {
        "thinking_config": {"thinking_budget": 1000}
    }
    assert tr("google", "off", "some-future-model") == {
        "thinking_config": {"thinking_budget": 0}
    }


def test_google_invalid_budget_falls_back_to_effort(catalog_db):
    assert tr("google", "high", "gemini-2.5-flash", budget=0) == {}
    assert tr("google", "high", "gemini-2.5-flash", budget="junk") == {}
    assert tr("google", "high", "gemini-3.1-pro-preview", budget=-5) == {
        "thinking_config": {"thinking_level": "high"}
    }


# --- Other plain OpenAI-compatible gateways ---

def test_deepseek_effort_uses_string_shape(catalog_db):
    assert tr("deepseek", "high", "deepseek-flash") == {"reasoning_effort": "high"}


def test_deepseek_off_sends_nothing(catalog_db):
    # deepseek-flash declares no "none" value.
    assert tr("deepseek", "off", "deepseek-flash") == {}


def test_alibaba_effort_in_values_uses_string_shape(catalog_db):
    assert tr("alibaba", "medium", "qwen3.8-max") == {"reasoning_effort": "medium"}


def test_alibaba_effort_outside_values_sends_nothing(catalog_db):
    assert tr("alibaba", "high", "qwen3.8-max") == {}
    assert tr("alibaba", "off", "qwen3.8-max") == {}


def test_openai_extended_levels_pass_through(catalog_db):
    assert tr("openai", "xhigh", "gpt-6-astra") == {"reasoning_effort": "xhigh"}


def test_plain_gateway_budget_has_no_generic_param(catalog_db):
    assert tr("alibaba", "default", "qwen3.8-max", budget=4000) == {}


def test_plain_gateway_effort_wins_over_budget(catalog_db):
    # Plain gateways have no budget param: an explicit effort level is
    # preserved instead of being dropped.
    assert tr("groq", "high", "openai/gpt-oss-120b", budget=5000) == {
        "reasoning_effort": "high"
    }


def test_provider_without_synced_models_uses_registry_fallback(catalog_db):
    assert tr("together", "medium", "some-model") == {"reasoning_effort": "medium"}


def test_unknown_provider_sends_nothing(catalog_db):
    assert tr("no-such-provider", "high", "any-model") == {}


def test_empty_provider_sends_nothing(catalog_db):
    assert tr("", "high", "any-model") == {}


def test_invalid_budget_falls_back_to_effort(catalog_db):
    assert tr("openrouter", "medium", "openai/gpt-oss-120b", budget=0) == {
        "reasoning": {"effort": "medium"}
    }
    assert tr("openrouter", "medium", "openai/gpt-oss-120b", budget=-5) == {
        "reasoning": {"effort": "medium"}
    }
    assert tr("groq", "low", "openai/gpt-oss-120b", budget="junk") == {
        "reasoning_effort": "low"
    }


# --- Provider normalization, model_id=None, LOCAL, int values ---

def test_provider_name_normalization(catalog_db):
    assert tr("GROQ", "high", "openai/gpt-oss-120b") == {"reasoning_effort": "high"}
    assert tr("  openrouter  ", "medium", "openai/gpt-oss-120b") == {
        "reasoning": {"effort": "medium"}
    }
    assert tr("Google", "high", "gemini-3.1-pro-preview") == {
        "thinking_config": {"thinking_level": "high"}
    }


def test_model_id_none_skips_lookup(catalog_db):
    assert tr("groq", "high", None) == {"reasoning_effort": "high"}


def test_string_budget_coerced(catalog_db):
    assert tr("openrouter", True, "qwen/qwen3.7-flash", budget="5000") == {
        "reasoning": {"max_tokens": 5000}
    }


def test_local_provider_sends_nothing(catalog_db):
    # Local reasoning is handled by model_resolver, never via API kwargs.
    assert tr("LOCAL", "high", "llama3") == {}
    assert tr("ollama", "high", "llama3") == {}


# --- get_reasoning_options coverage ---

def test_options_non_reasoning_model(catalog_db):
    opts = model_catalog.get_reasoning_options("groq", "llama-3.3-70b-versatile")
    assert opts["reasoning_supported"] is False
    assert opts["reasoning_type"] is None


def test_options_effort_model(catalog_db):
    opts = model_catalog.get_reasoning_options("groq", "openai/gpt-oss-120b")
    assert opts["reasoning_supported"] is True
    assert opts["reasoning_type"] == "effort_levels"
    assert [o["value"] for o in opts["reasoning_options"]] == [
        "default", "low", "medium", "high",
    ]


def test_options_toggle_model(catalog_db):
    opts = model_catalog.get_reasoning_options("openrouter", "qwen/qwen3-235b-a22b")
    assert opts["reasoning_supported"] is True
    assert opts["reasoning_type"] == "boolean"


def test_options_combined_model_reports_budget_range(catalog_db):
    opts = model_catalog.get_reasoning_options("alibaba", "qwen3.8-max")
    assert opts["reasoning_supported"] is True
    assert opts["reasoning_type"] == "budget_tokens"
    assert opts["budget_min"] == 0
    assert opts["budget_max"] == 262144
    assert [o["value"] for o in opts["reasoning_options"]] == ["default"]


def test_options_google_budget_range(catalog_db):
    opts = model_catalog.get_reasoning_options("google", "gemini-2.5-flash")
    assert opts["reasoning_supported"] is True
    assert opts["reasoning_type"] == "budget_tokens"
    assert opts["budget_min"] == 0
    assert opts["budget_max"] == 24576


def test_options_unknown_model(catalog_db):
    opts = model_catalog.get_reasoning_options("groq", "no-such-model")
    assert opts["reasoning_supported"] is None
    assert opts["reasoning_type"] is None
    assert opts["reasoning_options"] == []


def test_options_malformed_json_row(catalog_db, tmp_path, monkeypatch):
    bad_path = str(tmp_path / "bad.db")
    conn = sqlite3.connect(bad_path)
    try:
        setup_database(conn)
        conn.execute(
            """INSERT INTO model_catalog
               (provider, model_id, reasoning, reasoning_options, npm, updated_at)
               VALUES ('groq', 'bad-model', 1, '{broken', '@ai-sdk/groq',
                       '2026-01-01T00:00:00')"""
        )
        conn.commit()
    finally:
        conn.close()

    def _bad_connect():
        fake = sqlite3.connect(bad_path)
        fake.row_factory = sqlite3.Row
        return fake

    monkeypatch.setattr(model_catalog, "_connect", _bad_connect)
    opts = model_catalog.get_reasoning_options("groq", "bad-model")
    assert opts["reasoning_supported"] is True
    assert opts["reasoning_type"] is None
    assert [o["value"] for o in opts["reasoning_options"]] == ["default"]


# --- Streaming config ---

def test_streaming_config_is_empty(catalog_db):
    for provider in ("groq", "openrouter", "google", "deepseek", "unknown"):
        assert model_catalog.get_reasoning_streaming_config(provider) == {}


def test_streaming_config_ignores_argument(catalog_db):
    assert model_catalog.get_reasoning_streaming_config(None) == {}
    assert model_catalog.get_reasoning_streaming_config("") == {}

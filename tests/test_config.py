from pathlib import Path

import pytest

from src.config import (
    _ENV_FIELDS,
    PROJECT_ROOT,
    ConfigError,
    Settings,
    describe_settings,
    load_settings,
)


def test_defaults_are_valid():
    settings = load_settings({})
    assert settings == Settings()
    assert settings.llm_provider == "mock"
    assert settings.reranker_enabled is False
    assert settings.min_retrieval_score is None
    assert settings.raw_dir == PROJECT_ROOT / "data" / "raw"


def test_env_values_are_parsed():
    settings = load_settings(
        {
            "BM25_TOP_K": " 42 ",
            "RERANKER_ENABLED": "yes",
            "MIN_RERANK_SCORE": "0.25",
            "LLM_PROVIDER": "Anthropic",
            "LLM_MODEL": "some-model",
            "UNDATED_SOURCE_POLICY": "EXCLUDE",
        }
    )
    assert settings.bm25_top_k == 42
    assert settings.reranker_enabled is True
    assert settings.min_rerank_score == 0.25
    assert settings.llm_provider == "anthropic"
    assert settings.undated_source_policy == "exclude"


def test_relative_paths_resolve_against_project_root(tmp_path):
    settings = load_settings({"DATA_DIR": "my_data", "INDEX_DIR": str(tmp_path)})
    assert settings.data_dir == PROJECT_ROOT / "my_data"
    assert settings.index_dir == Path(tmp_path)


def test_empty_threshold_disables_it():
    assert load_settings({"MIN_RETRIEVAL_SCORE": ""}).min_retrieval_score is None


@pytest.mark.parametrize(
    ("env", "expected_fragment"),
    [
        ({"BM25_TOP_K": "abc"}, "BM25_TOP_K has an invalid value"),
        ({"RERANKER_ENABLED": "maybe"}, "RERANKER_ENABLED has an invalid value"),
        ({"CHUNK_SIZE": "0"}, "CHUNK_SIZE must be a positive integer"),
        ({"CHUNK_SIZE": "100", "CHUNK_OVERLAP": "100"}, "must be smaller than CHUNK_SIZE"),
        ({"CHUNK_OVERLAP": "-1"}, "CHUNK_OVERLAP must be >= 0"),
        ({"MAX_GENERATION_RETRIES": "2"}, "MAX_GENERATION_RETRIES must be between 0 and 1"),
        ({"LLM_PROVIDER": "unknown"}, "LLM_PROVIDER must be one of"),
        ({"LLM_PROVIDER": "openai"}, "LLM_MODEL must be set"),
        ({"RERANKER_ENABLED": "true", "RERANKER_MODEL": " "}, "RERANKER_MODEL must be set"),
        ({"UNDATED_SOURCE_POLICY": "ignore"}, "UNDATED_SOURCE_POLICY must be one of"),
    ],
)
def test_invalid_values_raise_clear_errors(env, expected_fragment):
    with pytest.raises(ConfigError, match=expected_fragment):
        load_settings(env)


def test_all_validation_errors_are_reported_together():
    with pytest.raises(ConfigError) as exc_info:
        load_settings({"RRF_K": "0", "DENSE_TOP_K": "-5"})
    message = str(exc_info.value)
    assert "RRF_K" in message
    assert "DENSE_TOP_K" in message


def test_api_key_required_only_for_real_providers():
    assert load_settings({}).require_llm_api_key() == ""

    settings = load_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m"})
    with pytest.raises(ConfigError, match="LLM_API_KEY is required"):
        settings.require_llm_api_key()

    settings = load_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m", "LLM_API_KEY": "k"})
    assert settings.require_llm_api_key() == "k"


def test_api_key_is_never_displayed():
    settings = load_settings({"LLM_API_KEY": "secret-value"})
    assert "secret-value" not in repr(settings)
    assert "secret-value" not in describe_settings(settings)


def test_env_example_is_valid_and_complete():
    env = {}
    for line in (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name, _, value = line.partition("=")
            env[name.strip()] = value

    settings = load_settings(env)
    assert settings == Settings()
    assert set(env) == set(_ENV_FIELDS)

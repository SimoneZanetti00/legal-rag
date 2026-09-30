"""Centralized, validated configuration.

All tunable settings live in `Settings` and are read from environment
variables (optionally via a local `.env` file). See `.env.example` for the
full list of variables and their defaults.

Run `python -m src.config` to check that the current configuration is valid.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# "mock" never contacts an external service. It is the default so that no
# legal material is sent to a third-party provider without an explicit choice.
# Real providers are wired up in the generation phase.
SUPPORTED_LLM_PROVIDERS = ("mock", "anthropic", "openai")

# What to do with sources lacking effective dates when a question has an
# "as of" date: keep them but warn, or exclude them.
UNDATED_SOURCE_POLICIES = ("warn", "exclude")

# Spec §11: at most one controlled retry for malformed LLM output.
MAX_ALLOWED_GENERATION_RETRIES = 1


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    # Paths (relative values are resolved against the project root).
    data_dir: Path = PROJECT_ROOT / "data"
    index_dir: Path = PROJECT_ROOT / "data" / "indexes"

    # Models.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    llm_provider: str = "mock"
    llm_model: str = ""
    llm_api_key: str | None = field(default=None, repr=False)

    # Retrieval and evidence selection.
    bm25_top_k: int = 20
    dense_top_k: int = 20
    rerank_top_k: int = 20
    final_evidence_count: int = 5
    rrf_k: int = 60
    context_token_budget: int = 3000

    # Chunking (measured in characters).
    chunk_size: int = 1200
    chunk_overlap: int = 150

    # Thresholds. None disables the threshold.
    min_retrieval_score: float | None = None
    min_rerank_score: float | None = None

    # Temporal filtering and generation.
    undated_source_policy: str = "warn"
    max_generation_retries: int = 1

    def __post_init__(self) -> None:
        errors = _validate(self)
        if errors:
            raise ConfigError(_format_errors(errors))

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def evaluation_dir(self) -> Path:
        return self.data_dir / "evaluation"

    def require_llm_api_key(self) -> str:
        """Return the API key, or fail clearly if a real provider needs one."""
        if self.llm_provider == "mock":
            return ""
        if not self.llm_api_key:
            raise ConfigError(
                f"LLM_API_KEY is required for LLM_PROVIDER={self.llm_provider!r}. "
                "Set it in your environment or in a local .env file (never commit it)."
            )
        return self.llm_api_key


def _validate(settings: Settings) -> list[str]:
    errors: list[str] = []

    positive_ints = {
        "BM25_TOP_K": settings.bm25_top_k,
        "DENSE_TOP_K": settings.dense_top_k,
        "RERANK_TOP_K": settings.rerank_top_k,
        "FINAL_EVIDENCE_COUNT": settings.final_evidence_count,
        "RRF_K": settings.rrf_k,
        "CONTEXT_TOKEN_BUDGET": settings.context_token_budget,
        "CHUNK_SIZE": settings.chunk_size,
    }
    for name, value in positive_ints.items():
        if value <= 0:
            errors.append(f"{name} must be a positive integer (got {value}).")

    if settings.chunk_overlap < 0:
        errors.append(f"CHUNK_OVERLAP must be >= 0 (got {settings.chunk_overlap}).")
    elif settings.chunk_overlap >= settings.chunk_size > 0:
        errors.append(
            f"CHUNK_OVERLAP ({settings.chunk_overlap}) must be smaller than "
            f"CHUNK_SIZE ({settings.chunk_size})."
        )

    if not 0 <= settings.max_generation_retries <= MAX_ALLOWED_GENERATION_RETRIES:
        errors.append(
            f"MAX_GENERATION_RETRIES must be between 0 and {MAX_ALLOWED_GENERATION_RETRIES} "
            f"(got {settings.max_generation_retries})."
        )

    if not settings.embedding_model.strip():
        errors.append("EMBEDDING_MODEL must not be empty.")
    if settings.reranker_enabled and not settings.reranker_model.strip():
        errors.append("RERANKER_MODEL must be set when RERANKER_ENABLED is true.")

    if settings.llm_provider not in SUPPORTED_LLM_PROVIDERS:
        errors.append(
            f"LLM_PROVIDER must be one of {', '.join(SUPPORTED_LLM_PROVIDERS)} "
            f"(got {settings.llm_provider!r})."
        )
    elif settings.llm_provider != "mock" and not settings.llm_model.strip():
        errors.append(f"LLM_MODEL must be set when LLM_PROVIDER is {settings.llm_provider!r}.")

    if settings.undated_source_policy not in UNDATED_SOURCE_POLICIES:
        errors.append(
            f"UNDATED_SOURCE_POLICY must be one of {', '.join(UNDATED_SOURCE_POLICIES)} "
            f"(got {settings.undated_source_policy!r})."
        )

    return errors


def _format_errors(errors: list[str]) -> str:
    return "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)


# --- Loading from environment variables -------------------------------------

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError("expected true/false")


def _parse_optional_float(raw: str) -> float | None:
    return None if raw.strip() == "" else float(raw)


def _parse_path(raw: str) -> Path:
    path = Path(raw.strip())
    return path if path.is_absolute() else PROJECT_ROOT / path


# Environment variable name -> (Settings field, parser).
_ENV_FIELDS = {
    "DATA_DIR": ("data_dir", _parse_path),
    "INDEX_DIR": ("index_dir", _parse_path),
    "EMBEDDING_MODEL": ("embedding_model", str.strip),
    "RERANKER_ENABLED": ("reranker_enabled", _parse_bool),
    "RERANKER_MODEL": ("reranker_model", str.strip),
    "LLM_PROVIDER": ("llm_provider", lambda raw: raw.strip().lower()),
    "LLM_MODEL": ("llm_model", str.strip),
    "LLM_API_KEY": ("llm_api_key", lambda raw: raw.strip() or None),
    "BM25_TOP_K": ("bm25_top_k", int),
    "DENSE_TOP_K": ("dense_top_k", int),
    "RERANK_TOP_K": ("rerank_top_k", int),
    "FINAL_EVIDENCE_COUNT": ("final_evidence_count", int),
    "RRF_K": ("rrf_k", int),
    "CONTEXT_TOKEN_BUDGET": ("context_token_budget", int),
    "CHUNK_SIZE": ("chunk_size", int),
    "CHUNK_OVERLAP": ("chunk_overlap", int),
    "MIN_RETRIEVAL_SCORE": ("min_retrieval_score", _parse_optional_float),
    "MIN_RERANK_SCORE": ("min_rerank_score", _parse_optional_float),
    "UNDATED_SOURCE_POLICY": ("undated_source_policy", lambda raw: raw.strip().lower()),
    "MAX_GENERATION_RETRIES": ("max_generation_retries", int),
}


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build validated settings from environment variables.

    When `env` is None, a `.env` file in the project root is loaded first
    (without overriding variables already set in the process environment).
    Pass an explicit mapping to load settings in isolation, e.g. in tests.
    Unset variables fall back to the defaults defined on `Settings`.
    """
    if env is None:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env", override=False)
        env = os.environ

    values: dict[str, object] = {}
    errors: list[str] = []
    for env_name, (field_name, parse) in _ENV_FIELDS.items():
        raw = env.get(env_name)
        if raw is None:
            continue
        try:
            values[field_name] = parse(raw)
        except ValueError:
            errors.append(f"{env_name} has an invalid value {raw!r}.")

    if errors:
        raise ConfigError(_format_errors(errors))
    return Settings(**values)


def describe_settings(settings: Settings) -> str:
    """Human-readable summary of settings, with secrets masked."""
    lines = []
    for f in fields(settings):
        value = getattr(settings, f.name)
        if f.name == "llm_api_key":
            value = "<set>" if value else "<not set>"
        lines.append(f"{f.name} = {value}")
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        loaded = load_settings()
    except ConfigError as exc:
        raise SystemExit(str(exc)) from None
    print("Configuration is valid.\n")
    print(describe_settings(loaded))

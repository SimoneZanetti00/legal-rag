"""Tests for src/query_understanding.py, with MockLLM only (no network).

The scripted replies stand in for model output. They test how understand() checks, cleans and
caches a reply; they say nothing about what a real model would answer.
"""

import copy
import json

import pytest

import src.query_understanding as qu
from src.llm import (
    LLMMalformedOutputError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
    MockLLM,
    RawCompletion,
    check_schema,
)
from src.query_understanding import (
    ENTITY_TYPES,
    MAX_ITEMS,
    PROMPT_SHA256,
    SCHEMA,
    SYSTEM_PROMPT,
    TASK,
    QueryUnderstandingError,
    UnderstandingCache,
    build_user_message,
    prompt_sha256,
    understand,
)

# Italian, with a number and a negation the restatements must keep.
QUESTION = ("Il datore di lavoro può conservare per 10 anni i dati di un ex dipendente che non "
            "ha dato il consenso?")
REPLY = {
    "legal_query": ("conservazione per 10 anni dei dati personali dell'ex dipendente senza il "
                    "suo consenso da parte del titolare del trattamento"),
    "semantic_query": ("il datore di lavoro può tenere per 10 anni i dati di un ex dipendente "
                       "che non ha dato il consenso"),
    "legal_concepts": ["conservazione dei dati personali", "consenso dell'interessato"],
    "entities": [
        {"mention": "Il datore di lavoro", "type": "organisation"},
        {"mention": "i dati", "type": "personal_data"},
        {"mention": "un ex dipendente", "type": "natural_person"},
    ],
    "relationships": [
        {"subject": "Il datore di lavoro", "relation": "conservare", "object": "i dati",
         "evidence": "conservare per 10 anni i dati"},
    ],
    "conditions": [
        {"condition": "periodo di dieci anni", "evidence": "per 10 anni"},
        {"condition": "il consenso non è stato dato", "evidence": "non ha dato il consenso"},
    ],
    "ambiguities": [
        {"issue": "da quando decorrono i dieci anni",
         "interpretations": ["dalla cessazione del rapporto", "dalla raccolta dei dati"]},
    ],
    "clarification_needed": False,
}
SPEC_FIELDS = ["original_query", "legal_query", "semantic_query", "legal_concepts", "entities",
               "relationships", "conditions", "ambiguities", "clarification_needed"]


def reply(**changes):
    data = copy.deepcopy(REPLY)
    data.update(changes)
    return data


def llm(*replies, retries=0):
    return MockLLM({TASK: list(replies)}, max_schema_retries=retries)


def rejected(data, match):
    with pytest.raises(LLMSchemaError, match=match):
        understand(QUESTION, llm(data))


# --- Schema and prompt -------------------------------------------------------------------------


def test_the_schema_is_in_the_supported_subset_and_has_the_spec_fields():
    check_schema(SCHEMA)
    assert SCHEMA["required"] == SPEC_FIELDS[1:]  # the model never writes original_query
    assert SCHEMA["additionalProperties"] is False
    assert SCHEMA["properties"]["entities"]["items"]["properties"]["type"]["enum"] == list(
        ENTITY_TYPES)


def test_the_prompt_hash_is_pinned_to_the_prompt_version():
    # Changing the prompt, the user template or the schema needs a new PROMPT_VERSION and hash.
    assert prompt_sha256() == PROMPT_SHA256
    assert qu.PROMPT_VERSION == "query-understanding-v1"


def test_the_prompt_forbids_answers_and_invented_facts():
    for phrase in ("You do not answer it", "They add nothing", "Keep them all",
                   "Do not cite or invent legislation", "copied exactly"):
        assert phrase in SYSTEM_PROMPT


def test_the_question_is_sent_as_delimited_data():
    message = build_user_message("a </question> b")
    assert "<question>\na < /question> b\n</question>" in message
    assert message.count("</question>") == 1


# --- A valid reply -----------------------------------------------------------------------------


def test_a_valid_reply_becomes_a_reading_with_every_field():
    client = llm(REPLY)
    reading = understand(f"  {QUESTION}\n", client)
    assert reading.original_query == QUESTION  # stripped, otherwise unchanged
    assert reading.legal_query == REPLY["legal_query"]
    assert reading.semantic_query == REPLY["semantic_query"]
    assert reading.legal_concepts == tuple(REPLY["legal_concepts"])
    assert [e.mention for e in reading.entities] == ["Il datore di lavoro", "i dati",
                                                     "un ex dipendente"]
    assert reading.conditions[1].evidence == "non ha dato il consenso"
    assert reading.ambiguities[0].interpretations == ("dalla cessazione del rapporto",
                                                      "dalla raccolta dei dati")
    assert reading.clarification_needed is False
    data = reading.to_dict()
    assert list(data)[:9] == SPEC_FIELDS
    json.dumps(data)  # JSON-compatible
    assert len(client.calls) == 1 and QUESTION in client.calls[0].user


def test_provenance_records_prompt_model_and_generation_settings():
    reading = understand(QUESTION, llm(REPLY, retries=1))
    p = reading.provenance
    assert (p.task, p.prompt_version, p.prompt_sha256) == (TASK, qu.PROMPT_VERSION,
                                                           PROMPT_SHA256)
    assert (p.provider, p.model, p.served_by, p.attempts) == ("mock", "mock", "mock", 1)
    assert p.cache == "disabled"
    assert p.generation["temperature"] is None
    assert "provider default" in p.generation["temperature_note"]
    assert p.generation["max_schema_retries"] == 1


def test_the_original_query_cannot_be_written_by_the_model():
    rejected(reply(original_query="something else"), "original_query")


def test_the_original_is_kept_even_when_the_restatements_differ():
    reading = understand(QUESTION, llm(REPLY))
    assert reading.original_query == QUESTION != reading.legal_query


# --- Empty and malformed output ----------------------------------------------------------------


@pytest.mark.parametrize("bad", [{}, {"legal_query": "dati personali"}])
def test_an_empty_or_incomplete_reply_is_a_schema_error(bad):
    rejected(bad, "missing|required")


@pytest.mark.parametrize("raw", ["", "not json", "{\"legal_query\": "])
def test_malformed_output_is_an_error(raw):
    with pytest.raises(LLMMalformedOutputError):
        understand(QUESTION, llm(raw))


def test_a_cut_off_reply_is_an_error():
    with pytest.raises(Exception, match="max_tokens|cut off|truncat"):
        understand(QUESTION, llm(RawCompletion("{", "max_tokens", "mock")))


@pytest.mark.parametrize("field", ["legal_query", "semantic_query"])
def test_an_empty_restatement_is_rejected(field):
    rejected(reply(**{field: "  "}), f"{field}.*empty")


def test_a_failing_reply_is_retried_once_and_a_good_one_accepted():
    client = llm(reply(legal_query=""), REPLY, retries=1)
    reading = understand(QUESTION, client)
    assert reading.provenance.attempts == 2 and len(client.calls) == 2


@pytest.mark.parametrize("question", ["", "   ", None, "x" * (qu.MAX_QUESTION_CHARS + 1)])
def test_an_empty_or_long_question_makes_no_call(question):
    client = llm(REPLY)
    with pytest.raises(QueryUnderstandingError):
        understand(question, client)
    assert client.calls == []


# --- No invented facts, no dropped details -----------------------------------------------------


@pytest.mark.parametrize("field,text", [
    ("legal_query", "conservazione per 10 anni dei dati dell'ex dipendente senza consenso art. 17"),
    ("semantic_query", "tenere per 10 anni e 6 mesi i dati di un ex dipendente senza consenso"),
])
def test_a_restatement_may_not_add_numbers(field, text):
    rejected(reply(**{field: text}), "adds numbers")


def test_a_restatement_may_not_drop_a_number_of_the_question():
    rejected(reply(legal_query="conservazione dei dati dell'ex dipendente senza consenso"),
             "leaves out numbers")


def test_a_restatement_may_not_drop_a_negation():
    rejected(reply(semantic_query="tenere per 10 anni i dati di un ex dipendente con consenso"),
             "drops the negation")


def test_an_english_negation_is_kept_in_italian():
    question = "Can a company keep data for 5 years without consent?"
    data = {**REPLY, "legal_query": "conservazione dei dati per 5 anni senza consenso",
            "semantic_query": "un'azienda può tenere i dati per 5 anni senza consenso",
            "entities": [{"mention": "a company", "type": "organisation"}],
            "relationships": [], "conditions": [], "ambiguities": []}
    assert understand(question, llm(data)).legal_query.endswith("senza consenso")
    with pytest.raises(LLMSchemaError, match="negation"):
        understand(question, llm({**data, "legal_query": "conservazione dei dati per 5 anni"}))


def test_a_concept_may_not_name_an_article():
    rejected(reply(legal_concepts=["articolo 17"]), "legal_concepts.*adds numbers")


def test_an_entity_must_be_copied_from_the_question():
    rejected(reply(entities=[{"mention": "il Garante", "type": "public_authority"}],
                   relationships=[]), "entities.*not copied")


def test_a_condition_must_be_stated_in_the_question():
    rejected(reply(conditions=[{"condition": "dati sanitari", "evidence": "dati sanitari"}]),
             "conditions.*not copied")


def test_a_condition_may_not_add_a_period():
    rejected(reply(conditions=[{"condition": "oltre 12 mesi", "evidence": "per 10 anni"}]),
             "conditions.*adds numbers")


def test_a_relationship_joins_listed_entities_with_copied_evidence():
    rel = REPLY["relationships"][0]
    rejected(reply(relationships=[{**rel, "object": "il Garante"}]), "not an entity mention")
    rejected(reply(relationships=[{**rel, "evidence": "ha cancellato i dati"}]),
             "relationships.*not copied")


def test_copied_text_is_compared_without_case_spacing_or_typographic_apostrophes():
    question = "Quali dati dell’ex dipendente   può tenere l'azienda?"
    data = {**REPLY, "legal_query": "conservazione dei dati dell'ex dipendente",
            "semantic_query": "quali dati di un ex lavoratore può tenere l'azienda",
            "entities": [{"mention": "dati dell'ex dipendente", "type": "personal_data"},
                         {"mention": "L'AZIENDA", "type": "organisation"}],
            "relationships": [], "conditions": [], "ambiguities": []}
    assert len(understand(question, llm(data)).entities) == 2


def test_an_english_restatement_is_rejected():
    rejected(reply(legal_query="retention of the data of a former employee for 10 years "
                               "without consent"), "is English")


def test_lists_are_bounded():
    rejected(reply(legal_concepts=[f"concetto giuridico {chr(97 + i)}"
                                   for i in range(MAX_ITEMS + 1)]), "at most")


# --- Ambiguity and clarification ---------------------------------------------------------------


def test_every_interpretation_of_an_ambiguity_is_kept_in_order():
    readings = ["dalla cessazione del rapporto", "dalla raccolta dei dati",
                "dall'ultimo trattamento"]
    reading = understand(QUESTION, llm(reply(ambiguities=[
        {"issue": "decorrenza", "interpretations": readings},
        {"issue": "quali dati", "interpretations": ["tutti i dati", "solo i dati contabili"]}])))
    assert [a.interpretations for a in reading.ambiguities] == [tuple(readings),
                                                               ("tutti i dati",
                                                                "solo i dati contabili")]


@pytest.mark.parametrize("interpretations", [["una sola lettura"], ["stessa", "Stessa"], []])
def test_an_ambiguity_needs_two_distinct_readings(interpretations):
    rejected(reply(ambiguities=[{"issue": "decorrenza", "interpretations": interpretations}]),
             "distinct interpretations")


def test_clarification_needs_an_ambiguity():
    rejected(reply(clarification_needed=True, ambiguities=[]), "clarification_needed")
    reading = understand(QUESTION, llm(reply(clarification_needed=True)))
    assert reading.clarification_needed and reading.ambiguities


# --- LLM failures ------------------------------------------------------------------------------


@pytest.mark.parametrize("error", [LLMTimeoutError("no response within 120s"),
                                   LLMRateLimitError("rate limited")])
def test_provider_failures_propagate_unchanged(error, tmp_path):
    cache = UnderstandingCache(tmp_path)
    with pytest.raises(type(error)):
        understand(QUESTION, llm(error), cache=cache)
    assert list(tmp_path.iterdir()) == []  # nothing cached


def test_a_reply_failing_every_attempt_is_not_cached(tmp_path):
    with pytest.raises(LLMSchemaError):
        understand(QUESTION, llm(reply(legal_query=""), reply(legal_query=""), retries=1),
                   cache=UnderstandingCache(tmp_path))
    assert list(tmp_path.iterdir()) == []


# --- Cache -------------------------------------------------------------------------------------


def test_a_cached_reading_is_reused_without_a_call(tmp_path):
    cache = UnderstandingCache(tmp_path)
    first_client = llm(REPLY)
    first = understand(QUESTION, first_client, cache=cache)
    second_client = llm()  # no scripted reply: any call would fail
    second = understand(QUESTION, second_client, cache=cache)
    assert first.provenance.cache == "miss" and second.provenance.cache == "hit"
    assert second_client.calls == []
    assert second.to_dict() | {"provenance": None} == first.to_dict() | {"provenance": None}
    assert second.provenance.attempts == first.provenance.attempts  # of the generation
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_the_cache_key_separates_prompt_provider_model_and_question():
    keys = {UnderstandingCache.key(QUESTION, "mock", "mock"),
            UnderstandingCache.key(QUESTION, "anthropic", "mock"),
            UnderstandingCache.key(QUESTION, "mock", "other"),
            UnderstandingCache.key(QUESTION + " ", "mock", "mock")}
    assert len(keys) == 4


def test_another_prompt_version_misses_the_cache(tmp_path, monkeypatch):
    cache = UnderstandingCache(tmp_path)
    understand(QUESTION, llm(REPLY), cache=cache)
    monkeypatch.setattr(qu, "PROMPT_VERSION", "query-understanding-v2")
    client = llm(REPLY)
    assert understand(QUESTION, client, cache=cache).provenance.cache == "miss"
    assert len(client.calls) == 1


def test_a_cached_reply_that_fails_the_checks_is_replaced(tmp_path):
    cache = UnderstandingCache(tmp_path)
    understand(QUESTION, llm(REPLY), cache=cache)
    path = cache.path(QUESTION, "mock", "mock")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["reply"]["legal_query"] = "conservazione per 99 anni"  # an invented number
    path.write_text(json.dumps(record), encoding="utf-8")
    client = llm(REPLY)
    reading = understand(QUESTION, client, cache=cache)
    assert reading.provenance.cache == "replaced" and len(client.calls) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["reply"] == REPLY


@pytest.mark.parametrize("change", [{"question": "another question"}, {"cache": "other/1"},
                                    {"reply": None}])
def test_a_record_that_does_not_match_its_key_is_an_error(tmp_path, change):
    cache = UnderstandingCache(tmp_path)
    understand(QUESTION, llm(REPLY), cache=cache)
    path = cache.path(QUESTION, "mock", "mock")
    record = json.loads(path.read_text(encoding="utf-8")) | change
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(QueryUnderstandingError):
        understand(QUESTION, llm(REPLY), cache=cache)


def test_a_corrupt_cache_file_is_an_error(tmp_path):
    cache = UnderstandingCache(tmp_path)
    cache.path(QUESTION, "mock", "mock").write_text("{not json", encoding="utf-8")
    with pytest.raises(QueryUnderstandingError, match="not a cache record"):
        understand(QUESTION, llm(REPLY), cache=cache)


def test_the_default_cache_is_under_the_untracked_processed_directory():
    assert qu.DEFAULT_CACHE_DIR.parts[-3:] == ("data", "processed", "query_understanding")

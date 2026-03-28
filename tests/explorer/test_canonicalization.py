"""Tests for canonical_lexicon and canonicalization modules."""

from __future__ import annotations

import pytest

from pipeline.component2.canonical_lexicon import CONCEPT_ALIASES, lookup_canonical
from pipeline.component2.canonicalization import (
    EVENT_TYPE_TO_RULE_TYPE,
    canonicalize_concept,
    canonicalize_short_statement,
    canonicalize_subconcept,
    classify_rule_type,
    make_canonical_id,
    normalize_label,
)


# ----- normalize_label -----


class TestNormalizeLabel:
    def test_lowercase_and_strip(self):
        assert normalize_label("  Level  ") == "level"

    def test_collapse_whitespace(self):
        assert normalize_label("false   breakout") == "false breakout"

    def test_strip_punctuation_noise(self):
        assert normalize_label("stop-loss!") == "stop-loss"

    def test_unicode_normalization(self):
        assert normalize_label("\u200bуровень\u200b") == "уровень"


# ----- lookup_canonical -----


class TestLookupCanonical:
    def test_known_russian_term(self):
        assert lookup_canonical("уровень") == "level"

    def test_known_english_term(self):
        assert lookup_canonical("false breakout") == "false_breakout"

    def test_case_insensitive(self):
        assert lookup_canonical("LEVEL") == "level"
        assert lookup_canonical("Уровень") == "level"

    def test_unknown_returns_none(self):
        assert lookup_canonical("completely_unknown_term_xyz") is None

    def test_whitespace_trimmed(self):
        assert lookup_canonical("  level  ") == "level"


# ----- make_canonical_id -----


class TestMakeCanonicalId:
    def test_known_concept(self):
        assert make_canonical_id("concept", "Level") == "concept:level"

    def test_known_russian(self):
        assert make_canonical_id("concept", "Уровень") == "concept:level"

    def test_fallback_slugification_english(self):
        result = make_canonical_id("concept", "Some Unknown Concept")
        assert result == "concept:some_unknown_concept"

    def test_fallback_transliterates_cyrillic(self):
        result = make_canonical_id("concept", "Новый Термин")
        assert result.startswith("concept:")
        assert "а" not in result and "о" not in result

    def test_subconcept_prefix(self):
        assert make_canonical_id("subconcept", "Stop Loss").startswith("subconcept:")


# ----- canonicalize_concept / canonicalize_subconcept -----


class TestCanonicalizeHelpers:
    def test_concept_none_returns_none(self):
        assert canonicalize_concept(None) is None

    def test_concept_empty_returns_none(self):
        assert canonicalize_concept("") is None
        assert canonicalize_concept("   ") is None

    def test_concept_known_term(self):
        assert canonicalize_concept("Level") == "concept:level"

    def test_subconcept_none_returns_none(self):
        assert canonicalize_subconcept(None) is None

    def test_subconcept_known_term(self):
        assert canonicalize_subconcept("False Breakout") == "subconcept:false_breakout"

    def test_subconcept_fallback(self):
        result = canonicalize_subconcept("Entry Criteria")
        assert result is not None
        assert result.startswith("subconcept:")


# ----- canonicalize_short_statement -----


class TestCanonicalizeShortStatement:
    def test_condition_statement(self):
        result = canonicalize_short_statement("condition", "Price above level")
        assert result.startswith("condition:")

    def test_known_term_in_statement(self):
        result = canonicalize_short_statement("invalidation", "Пробой")
        assert result == "invalidation:breakout"


# ----- classify_rule_type -----


class TestClassifyRuleType:
    def test_rule_statement(self):
        assert classify_rule_type("rule_statement") == "rule"

    def test_definition(self):
        assert classify_rule_type("definition") == "definition"

    def test_condition(self):
        assert classify_rule_type("condition") == "condition"

    def test_unknown_returns_none(self):
        assert classify_rule_type("nonexistent_type") is None

    @pytest.mark.parametrize("event_type", list(EVENT_TYPE_TO_RULE_TYPE.keys()))
    def test_all_known_types_mapped(self, event_type):
        result = classify_rule_type(event_type)
        assert result is not None


# ----- Lexicon coverage -----


class TestLexiconCoverage:
    def test_aliases_are_all_lowercase_keys(self):
        for key in CONCEPT_ALIASES:
            assert key == key.lower(), f"Key should be lowercase: {key!r}"

    def test_aliases_values_are_slugs(self):
        import re
        for key, slug in CONCEPT_ALIASES.items():
            assert re.fullmatch(r"[a-z0-9_]+", slug), f"Value not a valid slug: {key!r} -> {slug!r}"

    def test_no_empty_values(self):
        for key, slug in CONCEPT_ALIASES.items():
            assert slug, f"Empty slug for key: {key!r}"


# ----- Canonical ID without English labels -----


class TestNoEnglishLabels:
    """Verify that canonical IDs don't contain bilingual fields -- just machine slugs."""

    def test_canonical_id_has_no_spaces(self):
        cid = make_canonical_id("concept", "Risk Management")
        assert " " not in cid

    def test_canonical_id_is_ascii(self):
        cid = make_canonical_id("concept", "Уровень")
        assert cid.isascii(), f"Canonical ID should be ASCII: {cid!r}"

    def test_russian_concept_produces_ascii_id(self):
        cid = make_canonical_id("subconcept", "Ложный пробой")
        assert cid.isascii()
        assert cid == "subconcept:false_breakout"

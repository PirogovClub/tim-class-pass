from __future__ import annotations

from pipeline.rag.contracts import GraphExpansionResult


def test_alias_resolves_to_canonical_concept(concept_expander):
    result = concept_expander.expand_query("стоп лосс")
    assert "node:stop_loss" in result.canonical_concept_ids


def test_one_hop_expansion_works(concept_expander):
    result = concept_expander.expand_query("накопление")
    assert "node:breakout" in result.expanded_concept_ids


def test_expansion_trace_is_recorded(concept_expander):
    result = concept_expander.expand_query("ложный пробой")
    assert result.expansion_trace


def test_result_is_typed(concept_expander):
    result = concept_expander.expand_query("breakout")
    assert isinstance(result, GraphExpansionResult)

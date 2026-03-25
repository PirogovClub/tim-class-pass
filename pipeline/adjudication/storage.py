"""SQLite schema DDL for adjudication (Stage 5.1)."""

from __future__ import annotations

ADJUDICATION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reviewers (
    reviewer_id TEXT PRIMARY KEY,
    reviewer_kind TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_decisions (
    decision_id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    note TEXT,
    reason_code TEXT,
    related_target_id TEXT,
    artifact_version TEXT,
    proposal_id TEXT,
    prior_state_json TEXT,
    new_state_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_decisions_target_time
    ON review_decisions (target_type, target_id, created_at);
CREATE INDEX IF NOT EXISTS idx_review_decisions_reviewer_time
    ON review_decisions (reviewer_id, created_at);

CREATE TABLE IF NOT EXISTS canonical_rule_families (
    family_id TEXT PRIMARY KEY,
    canonical_title TEXT NOT NULL,
    normalized_summary TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    primary_concept TEXT,
    primary_subconcept TEXT,
    review_completeness TEXT
);

CREATE TABLE IF NOT EXISTS canonical_rule_memberships (
    membership_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    membership_role TEXT NOT NULL,
    added_by_decision_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (family_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_canonical_memberships_family
    ON canonical_rule_memberships (family_id);
CREATE INDEX IF NOT EXISTS idx_canonical_memberships_rule
    ON canonical_rule_memberships (rule_id);

CREATE TABLE IF NOT EXISTS rule_card_reviewed_state (
    target_id TEXT PRIMARY KEY,
    current_status TEXT,
    latest_decision_type TEXT,
    canonical_family_id TEXT,
    is_duplicate INTEGER NOT NULL DEFAULT 0,
    duplicate_of_rule_id TEXT,
    is_ambiguous INTEGER NOT NULL DEFAULT 0,
    is_deferred INTEGER NOT NULL DEFAULT 0,
    is_unsupported INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT,
    last_reviewer_id TEXT,
    last_decision_id TEXT,
    notes_summary TEXT
);

CREATE TABLE IF NOT EXISTS evidence_link_reviewed_state (
    target_id TEXT PRIMARY KEY,
    support_status TEXT,
    last_reviewed_at TEXT,
    last_reviewer_id TEXT,
    last_decision_id TEXT
);

CREATE TABLE IF NOT EXISTS concept_link_reviewed_state (
    target_id TEXT PRIMARY KEY,
    link_status TEXT,
    last_reviewed_at TEXT,
    last_reviewer_id TEXT,
    last_decision_id TEXT
);

CREATE TABLE IF NOT EXISTS related_rule_relation_reviewed_state (
    target_id TEXT PRIMARY KEY,
    relation_status TEXT,
    last_reviewed_at TEXT,
    last_reviewer_id TEXT,
    last_decision_id TEXT
);
"""

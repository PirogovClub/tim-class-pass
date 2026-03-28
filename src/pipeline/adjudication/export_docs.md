# Stage 5.6 — Reviewed corpus export

## Purpose

Read-only export of adjudicated corpus slices into **JSONL** artifacts plus an **`export_manifest.json`**, for evaluation, analytics, and future ML datasets. Export **never mutates** adjudication tables.

## Artifacts

| File | Contents |
|------|-----------|
| `gold_rules.jsonl` | `rule_card` rows with materialized **gold** tier (policy-filtered). |
| `gold_evidence_links.jsonl` | `evidence_link` gold tier rows. |
| `gold_concept_links.jsonl` | `concept_link` gold tier rows. |
| `gold_relations.jsonl` | `related_rule_relation` gold tier rows. |
| `gold_canonical_families.jsonl` | **Active** canonical families with ≥1 **gold** member rule. |
| `silver_*.jsonl` | Same layout as gold, **silver** tier only (never mixed with gold). |
| `eval_retrieval_rules.jsonl` | `{target_id, lesson_id?}` from gold rules. |
| `eval_duplicate_pairs.jsonl` | Gold rules marked duplicate with `duplicate_of_rule_id`. |
| `eval_evidence_support.jsonl` | Gold evidence links + support status. |
| `eval_canonical_assignments.jsonl` | Gold rules with `canonical_family_id` set. |
| `export_manifest.json` | Metadata, counts, inclusion/exclusion documentation. |

## Row schema (common)

Each JSONL object includes at minimum:

- `schema_version` — e.g. `export.v1`
- `exporter_version` — implementation stamp
- `tier` — `gold` or `silver`
- `target_type` / `target_id` (link/rule rows) or family fields for canonical export
- `tier_policy_version` — from materialized tier row (`tier_policy.v1`)
- `materialized_resolved_at` — ISO timestamp from `materialized_tier_state`
- `lesson_id` / `evidence_ref_ids` — when explorer is wired (optional in CLI default)

See Pydantic models in `export_models.py`.

## Policy

Documented in `export_policy.py`:

- **Gold / silver** require matching materialized tier and `is_eligible_for_downstream_use`.
- **Rule cards** additionally require reviewed state and `is_unsupported == false`.
- **Corpus filter** (optional): only targets present in a `CorpusTargetIndex` JSON.

## CLI

After `pip install -e .`, the entry point is **`adjudication-export`** (same subcommands as below).

```bash
python -m pipeline.adjudication.export_cli export \
  --db path/to/adjudication.sqlite \
  --output-dir path/to/export_out \
  --tiers both \
  --corpus-json path/to/corpus_index.json
```

`corpus_index.json` shape:

```json
{
  "rule_card_ids": ["rule:a", "rule:b"],
  "evidence_link_ids": ["ev:1"],
  "concept_link_ids": [],
  "related_rule_relation_ids": []
}
```

Skip inventory filtering:

```bash
python -m pipeline.adjudication.export_cli export --db ... --output-dir ... --tiers gold --no-corpus-filter
```

Validate an export directory:

```bash
python -m pipeline.adjudication.export_cli validate --export-dir path/to/export_out
```

**Stronger checks (recommended for audit handoff):**

- `--db path/to/adjudication.sqlite` — confirms each exported `rule_card` / `evidence_link` row exists in adjudication state, `duplicate_of_rule_id` resolves, and `canonical_family_id` exists in `canonical_rule_families`.
- `--strict-provenance` — fails if any exported `rule_card` row has empty/missing `lesson_id` (use when explorer populated the export).

Default validation (no flags) still enforces: manifest + line counts, JSON shape, tier labels, **no gold/silver overlap**, **unique `(target_type, target_id)` per tier file**, **canonical_family_id** present in `gold_canonical_families.jsonl`, **family members ⊆ gold_rules**, **duplicate_of_rule_id** present in `gold_rules.jsonl` when `--db` is not passed (closed-world), and **eval subset** rows pointing only at exported gold ids.

## Downstream usage

- Treat **gold** and **silver** as distinct trust levels; do not merge without relabeling.
- Join exports to lesson or explorer content using `target_id` / `lesson_id` as keys.
- Pin `schema_version` and `tier_policy_version` when versioning training/eval snapshots.

## Limitations

- **Bronze** / **unresolved** tiers are not exported in 5.6 bundles.
- Without **explorer**, `lesson_id` and `evidence_ref_ids` may be null (provenance note set).
- `canonical_rule_family` targets are not materialized in `materialized_tier_state`; family export is membership-derived from gold rules.

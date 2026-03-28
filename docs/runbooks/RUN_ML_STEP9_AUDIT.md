# Run ML Step 9 audit (model-family decision)

## Dependencies

Same lightweight stack as Step 8 audits: **PyYAML** (already in project dependencies).

```bash
pip install -r requirements-ml-step7-audit.txt
```

(or full project `uv sync`).

## Layout

- Decision config: `ml/step9_decision_config.yaml`
- Code: `ml/step9/`
- Default Step 8 inputs: `evidence.step8_root` in the YAML (default `ml_output/step8_audit_sample`)

## Commands (from repository root)

Validate config:

```bash
python -m ml.step9.cli validate-config --config ml/step9_decision_config.yaml
```

Evidence summary only:

```bash
python -m ml.step9.cli evidence-summary --config ml/step9_decision_config.yaml
```

Failure-mode report:

```bash
python -m ml.step9.cli failure-modes --config ml/step9_decision_config.yaml
```

Decision JSON:

```bash
python -m ml.step9.cli decide --config ml/step9_decision_config.yaml
```

Step 10 brief:

```bash
python -m ml.step9.cli step10-brief --config ml/step9_decision_config.yaml
```

**Full pipeline** (all artifacts + manifest):

```bash
python -m ml.step9.cli full-audit-run --config ml/step9_decision_config.yaml
```

Override repository root if needed:

```bash
python -m ml.step9.cli full-audit-run --config ml/step9_decision_config.yaml --repo-root .
```

## Tests

```bash
python -m pytest tests/test_step9_decision_config.py tests/test_step9_evidence_loader.py tests/test_failure_mode_analysis.py tests/test_model_family_decider.py tests/test_step10_brief_builder.py tests/test_step9_report_builder.py -q
```

## Inspect outputs

Default directory: `ml_output/step9/`

- `model_family_decision.json` — outcome + scores + rationale
- `step10_architecture_brief.json` — next engineering contract
- `step9_manifest.json` — artifact index
- `regime_breakdown_report.json`, `class_stability_report.json` — optional encouraged breakdowns (always written by `full-audit-run`)

## Audit zip (timestamped)

```bash
python scripts/generate_ml_step9_audit_bundle.py
```

Produces `audit/ml_step9_audit_bundle_<UTC-timestamp>.zip` and a copy under `audit/archives/`.

## Extracted bundle

- **Tests:** `cd <bundle>/source`, `pip install -r requirements-ml-step7-audit.txt`, then  
  `python -m pytest tests/test_step9_decision_config.py tests/test_step9_evidence_loader.py tests/test_failure_mode_analysis.py tests/test_model_family_decider.py tests/test_step10_brief_builder.py tests/test_step9_report_builder.py -q`
- **Full run from bundle root** (parent of `source/` and `examples/`):  
  `python -m ml.step9.cli full-audit-run --config examples/step9_decision_config_audit.yaml --repo-root .`  
  (requires `PYTHONPATH` including `source`, e.g. `set PYTHONPATH=source` on Windows before the command, or run from an environment where `ml` is importable from `source`.)

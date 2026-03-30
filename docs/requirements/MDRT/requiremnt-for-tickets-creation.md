You are a senior technical program manager, staff architect, and implementation planner.

Your task is to create an execution plan and ticket breakdown for the MDRT system using the documentation pack attached in this chat.

CRITICAL RULE:
You must use the attached MDRT documentation as the primary source of truth.
Do not produce a generic software plan.
Do not invent architecture that is not present in the docs.
Do not rely on background assumptions if the docs specify something else.

==================================================
DOCUMENT-USAGE INSTRUCTIONS
==================================================

1. First, read the attached MDRT documentation pack completely.

2. Build a source map before planning:
   - list all docs you found
   - identify which docs are normative
   - identify which docs are historical/background/reference only

3. Use the documentation hierarchy defined by the pack itself.

4. If the pack contains files such as:
   - index.md
   - numbered requirement docs such as 01-..., 02-..., etc.
   - root.md
   - req-review-*.md
   then treat:
   - index.md plus numbered requirement docs as normative
   - root.md and req-review-*.md as non-normative unless the pack explicitly says otherwise

5. If you find contradictions between docs, do not silently resolve them.
   Instead:
   - list the contradiction explicitly
   - identify which doc should win based on the pack’s stated hierarchy
   - use only the winning interpretation in the implementation plan

6. Every epic, ticket, and recommendation must be traceable to the MDRT docs.
   If a requirement is not found in the docs, do not present it as a requirement.
   You may include it only under a separate heading:
   - "Recommendation beyond current docs"

==================================================
PROJECT CONTEXT TO RESPECT
==================================================

Use the attached docs to confirm exact details, but expect the current approved system direction to include:

- IBKR-first design
- historical market data retrieval/archive tool
- U.S. equities Phase 1 scope
- use_rth=True
- what_to_show=TRADES
- supported bar sizes:
  - 1m
  - 5m
  - 15m
  - 1h
  - 4h
  - 1D
  - 1M

Likely architecture concepts include:
- ProviderSession
- ContractResolver
- HistoricalDataCollector
- raw landing
- normalization
- validation
- archive writer
- catalog
- window builder
- CLI
- tests

If the docs say something more specific, use the docs.

==================================================
REQUIRED PLANNING DISCIPLINE
==================================================

The coding agent will work ticket by ticket, not on the entire system at once.

The plan must:
- keep Phase 1 narrow
- prefer small tickets over large tickets
- support auditing after each ticket
- reduce ambiguity for a junior or mid-level coding agent
- avoid tickets that mix too many responsibilities

Do not create vague tickets such as:
- "implement IB integration"
- "build archive"
- "add validation"

Instead create narrow tickets such as:
- add ProviderSession interface and IB session readiness implementation
- add ContractResolver and persist resolved instrument identity
- add RequestSpec model and request hash generation
- add raw landing writer for provider-native transcripts
- add normalized bar schema writer for approved timeframes

==================================================
REQUIRED FOLDER STRUCTURE RULES
==================================================

You must propose the implementation plan using an explicit repo/folder structure.

If the MDRT docs already define a folder structure, use that as authoritative.
If the docs do not define it fully, propose one under:
"Recommendation beyond current docs"

When discussing tickets, always specify where code, tests, docs, examples, fixtures, and audit artifacts should live.

Assume the project should keep these areas clearly separated:

1. Source code
   Example logical area:
   - src/
   or package root if already defined by the docs

2. Tests
   Example logical area:
   - tests/
   with subfolders that mirror the code structure where practical

3. Documentation
   Example logical area:
   - docs/
   or a requirements/ folder if already defined

4. Examples / sample outputs / fixtures
   Example logical areas:
   - examples/
   - tests/fixtures/

5. Audit bundles / implementation evidence
   Example logical area:
   - audit/
   - audit-results/
   - audit-bundles/
   depending on what the docs or current workflow already imply

6. Generated data / outputs
   If discussed, keep clearly distinct from source code.
   Example logical areas:
   - output/
   - data/
   - tmp/
   only if consistent with the docs

For every ticket, identify exactly which folder(s) are expected to be touched.

==================================================
FILE NAMING RULES
==================================================

You must define file naming rules for:
- implementation tickets
- planning docs
- audit bundles
- examples
- fixtures
- generated manifests
- test files
- markdown requirement or execution docs

Use the naming rules already present in the docs if they exist.
If not, propose consistent naming rules.

Preferred rules:
1. Markdown docs:
   - use lowercase kebab-case
   - numbered docs use zero-padded numeric prefixes if part of an ordered series
   - examples:
     - 01-architecture.md
     - 02-data-models.md
     - implementation-plan.md
     - ticket-mdrt-001-provider-session.md

2. Python files:
   - use lowercase snake_case
   - examples:
     - provider_session.py
     - contract_resolver.py
     - request_spec.py

3. Test files:
   - use test_*.py naming
   - examples:
     - test_provider_session.py
     - test_contract_resolver.py
     - test_overlap_policy.py

4. Fixtures:
   - use descriptive lowercase snake_case or kebab-case consistently
   - examples:
     - good_friday_session.json
     - ib_historical_bars_1d_fixture.json

5. Audit bundles:
   - use stable ticket-based names
   - examples:
     - mdrt-001-audit-bundle/
     - mdrt-002-audit-bundle/
   Contents may include:
     - summary.md
     - changed-files.txt
     - test-results.txt
     - artifacts-manifest.json

6. Ticket IDs:
   - use a stable format such as:
     - MDRT-001
     - MDRT-002
   and keep it consistent across:
     - plan
     - ticket docs
     - audit bundle folders
     - implementation logs

7. Generated manifests:
   - use clear, descriptive names
   - examples:
     - request_manifest.json
     - archive_write_manifest.json
     - window_export_manifest.json

When producing the implementation plan, explicitly state the naming convention you chose.

==================================================
OUTPUT REQUIREMENTS
==================================================

Your output must have these sections:

1. Source map
Create a document source map that includes:
- file name
- role of the file
- normative or non-normative
- short summary of what that file governs

2. Normative rules extracted from the docs
Extract the key implementation rules directly from the MDRT pack.
Group them under headings such as:
- scope
- architecture
- schema/data model
- provider behavior
- calendar/session behavior
- CLI
- testing
- overlap policy
- non-goals

For each rule, include:
- the rule
- the source doc(s)

3. Open contradictions or ambiguities
If any contradictions remain in the pack:
- list them explicitly
- say which doc wins
- say how the implementation plan should interpret them

4. Proposed repo/folder structure
Provide the folder structure that the implementation plan and ticket set will assume.
Separate:
- source code
- tests
- docs
- fixtures
- examples
- audit artifacts
- generated outputs

For each area, explain its purpose.

5. Naming conventions
Provide the naming conventions for:
- tickets
- markdown docs
- python modules
- tests
- fixtures
- audit bundles
- manifests
- examples

6. Executive implementation strategy
Explain:
- the recommended build order
- the critical path
- what must be done sequentially
- what can be parallelized later

This strategy must be based on the MDRT docs, not generic engineering advice.

7. Epic breakdown
Create implementation epics derived from the MDRT docs.

For each epic include:
- Epic ID
- Title
- Goal
- Why it matters
- Source docs
- Dependencies
- Risks
- Exit criteria

8. Ticket breakdown
Break each epic into small tickets that can be executed one by one by a coding agent.

Each ticket must be small enough for one focused coding run.

For each ticket include:
- Ticket ID
- Title
- Purpose
- Source docs
- Exact requirements pulled from the docs
- In scope
- Out of scope
- Expected files/modules to create or modify
- Expected folder locations
- Required tests
- Required documentation updates
- Deliverables
- Definition of done
- Audit evidence required
- Audit bundle folder/file naming
- Dependencies
- Risk level: low / medium / high

9. Recommended ticket order
Produce the exact execution order.
Call out:
- blocker tickets
- tickets that require prior audit approval before the next one starts
- tickets that can be parallelized later

10. Handoff template for coding agent tickets
Create a reusable strict work-order template for a single implementation ticket.
It must include:
- mission
- exact scope
- non-goals
- source docs
- repo/folder locations
- files to touch
- files not to touch
- required tests
- required documentation changes
- output bundle
- audit bundle location and required files
- definition of done
- audit checklist

11. Anti-drift rules
Write strict rules the coding agent must follow so implementation stays aligned with the MDRT docs.

Examples:
- do not widen Phase 1 scope
- do not treat reference docs as normative
- do not add new providers
- do not add unsupported timeframes
- do not change schema semantics without explicit ticket scope
- do not skip tests
- do not leave output examples inconsistent with the schema
- do not place files outside the agreed folder structure
- do not invent naming conventions per ticket

12. First 10 tickets ready for execution
Write the first 10 tickets in exact execution order, fully specified and ready to hand to a coding agent.
Each ticket must include:
- source-doc traceability
- folder targets
- file naming expectations
- audit bundle naming expectations

==================================================
STRICTNESS RULES
==================================================

- Be concrete and strict.
- Do not produce vague agile fluff.
- Prefer smaller tickets over larger tickets.
- Assume every ticket will be audited before moving to the next one.
- If a ticket is too big, split it.
- Every ticket must be traceable to the MDRT docs.
- If a requirement is not in the docs, do not invent it unless you clearly label it as an implementation recommendation.
- If you make an implementation recommendation beyond the docs, separate it under:
  "Recommendation beyond current docs"
- Keep the architecture unchanged unless the docs explicitly require something else.

IMPORTANT:
Before writing the plan, explicitly state:
- which files are normative
- which files are background only
- which file wins in case of conflict
- which folder structure is already defined by the docs
- which naming rules are already defined by the docs vs proposed by you
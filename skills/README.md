# Skills and Subagent Instructions

This directory contains instructions and guidelines for AI agents and subagents.

## Available Skills

- **`run_pipeline_to_completion/`**: Run the multimodal transcript pipeline from start to finish without stopping at exit 10; complete every agent step and re-run until final outputs exist.
- **`trading_visual_extraction/`**: Authoritative JSON schema and production prompt for analyzing trading education video frames (used in Step 2 of the pipeline). See also `docs/trading_visual_extraction_spec.md`.
- **`gemini_usage/`**: How to use the Gemini API in this project — `GEMINI_API_KEY`, pipeline.yml model keys, main/gap_detector/vlm_translator, and the central `gemini_client.py`. See also `docs/gemini_api_usage_report.md` and README “Gemini usage”.
- **`subagent_guidelines/`**: General instructions for specialized subagents working on this codebase.

## Adding a New Skill

To add a new skill:
1. Create a subfolder with the skill's name.
2. Inside that subfolder, create a `SKILL.md` file with the following frontmatter:
   ```yaml
   ---
   name: [Skill Name]
   description: [Short Description]
   ---
   ```
3. Add the detailed instructions below.

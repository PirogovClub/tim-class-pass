---
name: Subagent Guidelines
description: Instructions for subagents performing specialized tasks in the tim-class-pass repository.
---

# Subagent Guidelines

This skill provides guidelines for specialized subagents (e.g., browser-based testing, data analysis, or refactoring) to follow standard project conventions.

## Code Conventions
- Follow PEP 8 for Python code.
- Use `src` layout for all application code.
- All new functionality must have corresponding tests in the `tests/` directory.

## Tool Usage
- Use `uv` for all package management including installing libraries and running scripts.
- Use `pytest` for all project testing.
- When creating web components (if applicable), use Vanilla CSS as per project preference.

## Communication
- Clearly report summarizing findings before finishing a task.
- Be proactive but follow the user's intent as defined in previous context.

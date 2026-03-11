---
name: python-click-cli
description: Create and update Python command-line interfaces using click instead of argparse. Use when building CLI apps, adding flags or subcommands, wiring script entrypoints, or when the user mentions click, argparse, command-line parsing, or CLI help output.
---

# Python Click CLI

## Default rule

For Python CLI applications in this repository, use `click` for argument parsing.

- Prefer `@click.command()` or `@click.group()`
- Prefer `@click.option()` and `@click.argument()`
- Do not introduce new `argparse`-based parsers
- If touching an `argparse` CLI, prefer migrating it to `click` instead of expanding it

Use `pipeline/main.py` and `pipeline/component2/main.py` as the local style references.

## Implementation pattern

Structure CLI code like this:

1. Keep the real business logic in a plain function such as `run_*()`
2. Expose a thin `click` entrypoint for parsing and validation
3. Keep help text concise and task-focused
4. Validate cross-option constraints with `click.UsageError`

Example:

```python
import click


def run_job(input_path: str, verbose: bool) -> None:
    ...


@click.command()
@click.option("--input-path", required=True, help="Path to the input file.")
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
def main(input_path: str, verbose: bool) -> None:
    run_job(input_path=input_path, verbose=verbose)


if __name__ == "__main__":
    main()
```

## Option rules

- Prefer kebab-case flag names for new CLIs, but preserve existing repository flag names when a CLI already exposes underscore-style options such as `--video_id`
- Use `click.Choice(...)` for enumerated values
- Use `is_flag=True` for booleans
- Use `type=int` / `type=float` for scalar numeric options
- Use `click.Path(...)` for filesystem arguments when validation helps
- Use explicit `required=True` when the option must be provided

## Validation rules

When the rule depends on multiple options, parse first with `click`, then validate in the command body.

Example:

```python
if (url and video_id) or (not url and not video_id):
    raise click.UsageError("Exactly one of --url or --video_id is required.")
```

## Async rule

If the CLI needs async work, keep `click` as the parser and call `asyncio.run(...)` inside the command body or inside a plain helper function. Do not switch to `argparse` just because the implementation is async.

## Migration rule

When replacing `argparse`:

1. Remove `build_arg_parser()`
2. Convert each `add_argument()` to `@click.option()` or `@click.argument()`
3. Replace `parse_args()` with a decorated `main(...)`
4. Replace manual usage text with `click` help and `click.UsageError`
5. Preserve flag names unless the user asked to rename them

## Testing rule

For CLI tests, use `click.testing.CliRunner`.

Example:

```python
from click.testing import CliRunner


def test_main_help() -> None:
    from your_module import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
```

## When to apply this skill

Apply this skill when:

- creating a new Python CLI tool
- editing a script entrypoint
- adding or changing CLI flags
- converting a parser from `argparse`
- writing CLI help or CLI tests

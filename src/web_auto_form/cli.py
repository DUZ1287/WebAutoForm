"""Command-line interface for web_auto_form."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import run


@click.group()
def cli() -> None:
    """web_auto_form — Browser automation for form filling and submission."""


@cli.command(name="run")
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--data", "-d", multiple=True, help="Override data values as key=value pairs.")
@click.option("--headless/--no-headless", default=None, help="Override headless mode.")
@click.option("--debug/--no-debug", default=None, help="Override debug mode.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write output JSON to file.")
def run_cmd(
    config_file: str,
    data: tuple[str, ...],
    headless: bool | None,
    debug: bool | None,
    output: str | None,
) -> None:
    """Execute a web_auto_form JSON configuration."""
    text = Path(config_file).read_text(encoding="utf-8")
    config = json.loads(text)

    # Apply --data overrides
    if data:
        data_obj = config.get("data", {})
        for pair in data:
            if "=" not in pair:
                click.echo(f"Invalid data format: {pair!r} (expected key=value)", err=True)
                sys.exit(1)
            key, value = pair.split("=", 1)
            _set_nested(data_obj, key, value)
        config["data"] = data_obj

    # Apply --headless override
    if headless is not None:
        config.setdefault("options", {})["headless"] = headless

    # Apply --debug override
    if debug is not None:
        config.setdefault("options", {})["debug"] = debug

    result = run(config)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(output_json, encoding="utf-8")
        click.echo(f"Output written to {output}")
    else:
        click.echo(output_json)

    sys.exit(0 if result["status"] == "success" else 1)


def _set_nested(obj: dict, key: str, value: str) -> None:
    """Set a nested dict value using dot notation (e.g. 'user.name')."""
    parts = key.split(".")
    for part in parts[:-1]:
        obj = obj.setdefault(part, {})
    obj[parts[-1]] = value

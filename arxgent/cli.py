from __future__ import annotations

import click


@click.group()
def cli() -> None:
    """Arxgent — an arxiv research agent that learns your interests."""


@cli.command()
def setup() -> None:
    """Run the profile setup wizard."""
    click.echo("Setup wizard not yet implemented.")


@cli.command()
@click.option("--date", type=click.Choice(["today", "last-week", "custom"]), default="last-week")
def run(date: str) -> None:
    """Search, summarize, and save papers from arxiv."""
    click.echo(f"Run command not yet implemented (date={date}).")


@cli.command()
def review() -> None:
    """Review previously delivered papers and give feedback."""
    click.echo("Review command not yet implemented.")


@cli.command()
def status() -> None:
    """Show your profile and delivery stats."""
    click.echo("Status command not yet implemented.")


if __name__ == "__main__":
    cli()

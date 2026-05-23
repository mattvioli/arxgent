from __future__ import annotations

import click
from rich.console import Console

from arxgent.config import load_config, save_config, config_exists
from arxgent.profile import Profile, load_profile, profile_exists, run_setup_wizard

console = Console()


@click.group()
def cli() -> None:
    """Arxgent — an arxiv research agent that learns your interests."""


@cli.command()
@click.option("--model", default=None, help="LLM model (e.g. gpt-4o-mini, claude-sonnet-4-20250514)")
def setup(model: str | None) -> None:
    """Run the profile setup wizard."""
    existing = load_profile() if profile_exists() else None

    if existing is not None and existing.topics:
        console.print("[yellow]Profile already exists. Running wizard again will update it.[/yellow]")

    profile = run_setup_wizard(existing=existing)

    if model:
        cfg = load_config()
        cfg.llm.model = model
        save_config(cfg)
        console.print(f"[green]LLM model set to:[/green] {model}")

    if not profile.topics:
        console.print("[red]No topics selected. Run [bold]arxgent setup[/bold] to configure.[/red]")
        return

    console.print("[green]Setup complete! Run [bold]arxgent run[/bold] to get your first paper.[/green]")


@cli.command()
@click.option("--date", type=click.Choice(["today", "last-week", "custom"]), default="last-week")
def run(date: str) -> None:
    """Search, summarize, and save papers from arxiv."""
    if not profile_exists():
        console.print("[yellow]No profile found. Running setup first...[/yellow]")
        run_setup_wizard()

    profile = load_profile()
    if not profile.topics:
        console.print("[red]No topics configured. Run [bold]arxgent setup[/bold] first.[/red]")
        return

    console.print(f"[green]Running search for date={date}, topics={list(profile.topics.keys())}[/green]")
    console.print("[dim]Paper search and summarization coming in a future step.[/dim]")


@cli.command()
def review() -> None:
    """Review previously delivered papers and give feedback."""
    if not profile_exists():
        console.print("[yellow]No profile found. Run [bold]arxgent setup[/bold] first.[/yellow]")
        return

    profile = load_profile()
    if not profile.history:
        console.print("[yellow]No papers have been delivered yet. Run [bold]arxgent run[/bold] first.[/yellow]")
        return

    console.print("[dim]Review mode coming in a future step.[/dim]")


@cli.command()
def status() -> None:
    """Show your profile and delivery stats."""
    if not profile_exists():
        console.print("[yellow]No profile found. Run [bold]arxgent setup[/bold] to get started.[/yellow]")
        return

    profile = load_profile()
    cfg = load_config()

    console.print("\n[bold]Arxgent Status[/bold]")
    console.print("=" * 40)
    console.print(f"[bold]Model:[/bold] {cfg.llm.model}")
    console.print(f"[bold]Output directory:[/bold] {cfg.output_dir}")
    console.print(f"[bold]Topics:[/bold] {len(profile.topics)} area(s)")
    for group, subs in profile.topics.items():
        console.print(f"  [cyan]{group}:[/cyan] {', '.join(subs)}")
    if profile.interest:
        console.print(f"[bold]Interest:[/bold] {profile.interest[:100]}")
    if profile.history:
        total = len(profile.history)
        read_count = sum(1 for p in profile.history if p.read)
        console.print(f"[bold]Papers delivered:[/bold] {total}")
        console.print(f"[bold]Papers read:[/bold] {read_count}")
    else:
        console.print("[yellow]No papers delivered yet.[/yellow]")
    console.print("")


if __name__ == "__main__":
    cli()

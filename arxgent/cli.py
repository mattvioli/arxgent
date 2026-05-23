from __future__ import annotations

from datetime import date, timedelta

import click
import questionary
from rich.console import Console

from arxgent.agents import refine_interest, research_papers, summarize_paper
from arxgent.config import load_config, save_config
from arxgent.profile import PaperEntry, Profile, load_profile, profile_exists, run_setup_wizard, save_profile
from arxgent.storage import save_paper_md

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
@click.option("--date", "date_opt", type=click.Choice(["today", "last-week", "custom"]), default="last-week")
@click.option("--start", default=None, help="Start date (YYYY-MM-DD) for --date=custom")
@click.option("--end", default=None, help="End date (YYYY-MM-DD) for --date=custom")
@click.option("--skip-review", is_flag=True, default=False, help="Skip the review prompt")
def run(date_opt: str, start: str | None, end: str | None, skip_review: bool) -> None:
    """Search, summarize, and save papers from arxiv."""
    if not profile_exists():
        console.print("[yellow]No profile found. Running setup first...[/yellow]")
        run_setup_wizard()

    profile = load_profile()
    if not profile.topics:
        console.print("[red]No topics configured. Run [bold]arxgent setup[/bold] first.[/red]")
        return

    cfg = load_config()
    today = date.today()

    if date_opt == "today":
        start_date = end_date = today.isoformat()
    elif date_opt == "last-week":
        end_date = today.isoformat()
        start_date = (today - timedelta(days=7)).isoformat()
    else:
        if not start or not end:
            console.print("[red]--start and --end are required with --date=custom[/red]")
            return
        start_date = start
        end_date = end

    with console.status("[bold green]Searching arxiv...") as status:
        papers = research_papers(
            profile=profile,
            start_date=start_date,
            end_date=end_date,
            num_papers=cfg.num_papers,
        )

    if not papers:
        console.print("[yellow]No papers found in the given date range. Try widening the window.[/yellow]")
        return

    console.print(f"\n[bold]Found {len(papers)} paper(s). Summarizing...[/bold]")

    for i, paper in enumerate(papers, 1):
        with console.status(f"[bold green]Summarizing paper {i}/{len(papers)}..."):
            summary = summarize_paper(
                paper=paper,
                profile=profile,
                model=cfg.llm.model,
            )

        filepath = save_paper_md(paper, summary, cfg.output_dir)
        console.print(f"  [green]{i}.[/green] {paper.title}")
        console.print(f"       Saved: {filepath}")

    profile.history.extend(
        PaperEntry(
            arxiv_id=p.arxiv_id,
            title=p.title,
            authors=p.authors,
            date_delivered=today.isoformat(),
        )
        for p in papers
    )
    save_profile(profile)

    console.print(f"\n[green]Done! Papers saved to {cfg.output_dir}[/green]")

    should_review = not (skip_review or cfg.skip_review)
    if should_review and profile.history:
        _prompt_review()


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

    _prompt_review()


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


def _prompt_review() -> None:
    profile = load_profile()
    unread = [p for p in profile.history if not p.read]
    if not unread:
        console.print("[green]All papers reviewed![/green]")
        return

    for entry in unread:
        console.print(f"\n[bold]Paper:[/bold] {entry.title} ({entry.arxiv_id})")
        console.print(f"[dim]Delivered: {entry.date_delivered}[/dim]")

        did_read = questionary.confirm("Did you read this paper?", default=False).ask()
        if did_read is None:
            return

        entry.read = did_read

        if did_read:
            liked = questionary.select(
                "What did you think of it?",
                choices=["Liked it", "Disliked it", "Neutral"],
            ).ask()
            if liked is None:
                return

            if liked == "Liked it":
                entry.liked = True
            elif liked == "Disliked it":
                entry.liked = False
            else:
                entry.liked = None

            feedback = questionary.text(
                "Any specific feedback? (optional)",
                default="",
                instruction="(press Enter to skip)",
            ).ask() or ""
            entry.feedback = feedback
        else:
            entry.liked = None
            entry.feedback = ""

        save_profile(profile)
        console.print("[green]Feedback saved![/green]")

    _offer_interest_refinement(profile)

    remaining = sum(1 for p in profile.history if not p.read)
    if remaining:
        console.print(f"[yellow]{remaining} paper(s) remaining to review.[/yellow]")
    else:
        console.print("[green]All caught up![/green]")


def _offer_interest_refinement(profile: Profile) -> None:
    cfg = load_config()
    liked_recent = [(e.title, e.feedback) for e in profile.history if e.liked and e.feedback]
    if not liked_recent:
        return

    try:
        with console.status("[bold green]Refining your interest paragraph..."):
            new_interest = refine_interest(profile, model=cfg.llm.model)
    except Exception:
        return

    if not new_interest or new_interest == profile.interest:
        return

    console.print("\n[bold]Interest update available:[/bold]")
    console.print(f"  [dim]Current:[/dim]  {profile.interest[:200]}")
    console.print(f"  [green]Proposed:[/green] {new_interest[:200]}")

    apply = questionary.confirm("Update your interest paragraph?", default=True).ask()
    if apply:
        profile.interest = new_interest
        save_profile(profile)
        console.print("[green]Interest paragraph updated![/green]")


if __name__ == "__main__":
    cli()

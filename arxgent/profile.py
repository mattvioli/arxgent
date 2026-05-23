from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import questionary
from pydantic import BaseModel, Field, ValidationError

from arxgent.categories import GROUPS
from arxgent.config import CONFIG_DIR, PROFILE_FILE


class PaperEntry(BaseModel):
    arxiv_id: str
    title: str
    date_delivered: str
    read: bool = False
    liked: Optional[bool] = None
    feedback: str = ""


class Profile(BaseModel):
    topics: Dict[str, List[str]] = Field(default_factory=dict)
    interest: str = ""
    history: List[PaperEntry] = Field(default_factory=list)


def load_profile() -> Profile:
    path = PROFILE_FILE
    if not path.exists():
        return Profile()
    try:
        raw = json.loads(path.read_text())
        return Profile.model_validate(raw)
    except (json.JSONDecodeError, ValidationError):
        return Profile()


def save_profile(profile: Profile) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = profile.model_dump(mode="json")
    PROFILE_FILE.write_text(json.dumps(data, indent=2))


def profile_exists() -> bool:
    return PROFILE_FILE.exists()


def _get_group_choices() -> list[dict]:
    return [{"name": name, "value": name} for name in GROUPS]


def _get_subcategory_choices(group_name: str) -> list[dict]:
    subs = GROUPS[group_name]
    return [{"name": f"{cid} — {display}", "value": cid} for cid, display in subs]


def run_setup_wizard(existing: Optional[Profile] = None) -> Profile:
    current = existing or Profile()

    print("\n" + "=" * 60)
    print("  Welcome to Arxgent setup!")
    print("  First, let's figure out what you're interested in.")
    print("=" * 60 + "\n")

    group_choices = _get_group_choices()
    preselected_groups = [name for name in GROUPS if name in current.topics]

    selected_groups = questionary.checkbox(
        "Which areas interest you? (space to toggle, enter to confirm)",
        choices=[
            questionary.Choice(
                title=(
                    f"\u2713 {name}"
                    if name in preselected_groups
                    else f"  {name}"
                ),
                value=name,
                checked=name in preselected_groups,
            )
            for name in GROUPS
        ],
    ).ask()

    if selected_groups is None:
        selected_groups = []

    topics: Dict[str, List[str]] = {}
    for group in selected_groups:
        sub_choices = _get_subcategory_choices(group)
        current_subs = current.topics.get(group, [])
        selected_subs = questionary.checkbox(
            f"Subcategories for {group}:",
            choices=[
                questionary.Choice(
                    title=(
                        f"\u2713 {choice['name']}"
                        if choice["value"] in current_subs
                        else f"  {choice['name']}"
                    ),
                    value=choice["value"],
                    checked=choice["value"] in current_subs,
                )
                for choice in sub_choices
            ],
        ).ask()

        if selected_subs:
            topics[group] = selected_subs

    interest = questionary.text(
        "Describe your research interests in a few sentences:",
        default=current.interest or "",
        multiline=True,
        instruction="(press Alt+Enter or Esc+Enter when done)",
    ).ask() or ""

    print("\n" + "-" * 60)
    print("  Summary")
    print("-" * 60)
    print(f"  Topics: {len(topics)} area(s)")
    for group, subs in topics.items():
        print(f"    {group}: {', '.join(subs)}")
    print(f"  Interest: {interest[:80]}{'...' if len(interest) > 80 else ''}")
    print("-" * 60)

    if not topics:
        print("No topics selected. Setup cancelled.")
        return current or Profile()

    confirmed = questionary.confirm("Save this profile?", default=True).ask()
    if not confirmed:
        print("Setup cancelled.")
        return current or Profile()

    profile = Profile(topics=topics, interest=interest, history=current.history)
    save_profile(profile)
    print("\nProfile saved! You're all set up.\n")
    return profile

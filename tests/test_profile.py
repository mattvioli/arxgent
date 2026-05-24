from __future__ import annotations

import json
from pathlib import Path

import questionary
import pytest

from arxgent import profile as arxgent_profile
from arxgent.profile import (
    PaperEntry,
    Profile,
    load_profile,
    profile_exists,
    run_setup_wizard,
    save_profile,
)


class TestProfileModel:
    def test_empty_profile_defaults(self) -> None:
        p = Profile()
        assert p.topics == {}
        assert p.interest == ""
        assert p.history == []

    def test_profile_with_topics(self) -> None:
        p = Profile(topics={"Computer Science": ["cs.LG", "cs.AI"]})
        assert p.topics["Computer Science"] == ["cs.LG", "cs.AI"]

    def test_profile_with_interest(self) -> None:
        p = Profile(interest="Deep learning and transformers")
        assert p.interest == "Deep learning and transformers"


class TestPaperEntry:
    def test_minimal_entry(self) -> None:
        entry = PaperEntry(arxiv_id="1706.03762", title="Attention Is All You Need", date_delivered="2026-05-23")
        assert entry.arxiv_id == "1706.03762"
        assert entry.read is False
        assert entry.liked is None
        assert entry.feedback == ""

    def test_full_entry(self) -> None:
        entry = PaperEntry(
            arxiv_id="1706.03762",
            title="Attention Is All You Need",
            date_delivered="2026-05-23",
            read=True,
            liked=True,
            feedback="Great paper on transformers",
        )
        assert entry.read is True
        assert entry.liked is True
        assert entry.feedback == "Great paper on transformers"

    def test_entry_with_dislike(self) -> None:
        entry = PaperEntry(
            arxiv_id="1234.56789",
            title="Some Paper",
            date_delivered="2026-05-22",
            read=True,
            liked=False,
            feedback="Too theoretical",
        )
        assert entry.liked is False


class TestProfileRoundtrip:
    def test_save_and_load(self, tmp_config_dir: Path) -> None:
        profile = Profile(
            topics={"Computer Science": ["cs.LG"], "Physics": ["quant-ph"]},
            interest="quantum machine learning",
            history=[
                PaperEntry(arxiv_id="1706.03762", title="Attention", date_delivered="2026-05-23"),
            ],
        )
        save_profile(profile)
        loaded = load_profile()
        assert loaded.topics == profile.topics
        assert loaded.interest == "quantum machine learning"
        assert len(loaded.history) == 1
        assert loaded.history[0].arxiv_id == "1706.03762"

    def test_save_updates_existing(self, tmp_config_dir: Path) -> None:
        p1 = Profile(topics={"CS": ["cs.LG"]}, interest="ML")
        save_profile(p1)
        p2 = Profile(topics={"CS": ["cs.LG", "cs.AI"]}, interest="ML + AI")
        save_profile(p2)
        loaded = load_profile()
        assert loaded.topics["CS"] == ["cs.LG", "cs.AI"]
        assert loaded.interest == "ML + AI"


class TestProfileFileOps:
    def test_load_nonexistent_returns_empty(self, tmp_config_dir: Path) -> None:
        profile = load_profile()
        assert isinstance(profile, Profile)
        assert profile.topics == {}

    def test_corrupted_json_returns_empty(self, tmp_config_dir: Path) -> None:
        arxgent_profile.PROFILE_FILE.write_text("not valid json")
        profile = load_profile()
        assert isinstance(profile, Profile)
        assert profile.topics == {}

    def test_wrong_types_returns_empty(self, tmp_config_dir: Path) -> None:
        arxgent_profile.PROFILE_FILE.write_text(json.dumps({"topics": "not_a_dict"}))
        profile = load_profile()
        assert isinstance(profile, Profile)


class TestProfileExists:
    def test_exists(self, tmp_config_dir: Path) -> None:
        save_profile(Profile())
        assert profile_exists() is True

    def test_not_exists(self, tmp_config_dir: Path) -> None:
        assert profile_exists() is False


class TestHistoryManagement:
    def test_add_to_history(self) -> None:
        profile = Profile()
        entry = PaperEntry(arxiv_id="1706.03762", title="Attention", date_delivered="2026-05-23")
        profile.history.append(entry)
        assert len(profile.history) == 1

    def test_multiple_entries(self) -> None:
        profile = Profile(history=[
            PaperEntry(arxiv_id="A", title="Paper A", date_delivered="2026-05-22"),
            PaperEntry(arxiv_id="B", title="Paper B", date_delivered="2026-05-23"),
        ])
        assert len(profile.history) == 2

    def test_update_feedback(self) -> None:
        entry = PaperEntry(arxiv_id="1706.03762", title="Attention", date_delivered="2026-05-23")
        entry.read = True
        entry.liked = True
        entry.feedback = "Excellent paper"
        assert entry.read is True
        assert entry.liked is True
        assert entry.feedback == "Excellent paper"

    def test_history_roundtrip(self, tmp_config_dir: Path) -> None:
        profile = Profile(history=[
            PaperEntry(arxiv_id="A", title="Paper A", date_delivered="2026-05-22", read=True, liked=False, feedback="Not great"),
        ])
        save_profile(profile)
        loaded = load_profile()
        assert len(loaded.history) == 1
        assert loaded.history[0].read is True
        assert loaded.history[0].liked is False
        assert loaded.history[0].feedback == "Not great"


class FakeQuestionary:
    Choice = questionary.Choice

    def __init__(self, return_values):
        self._return_values = return_values
        self._call_count = 0

    def checkbox(self, prompt, **kw):
        result = self._next("checkbox", prompt)
        return FakeAskable(result)

    def text(self, prompt, **kw):
        result = self._next("text", prompt)
        return FakeAskable(result)

    def confirm(self, prompt, **kw):
        result = self._next("confirm", prompt)
        return FakeAskable(result)

    def _next(self, kind, prompt):
        if self._call_count >= len(self._return_values):
            return None
        val = self._return_values[self._call_count]
        self._call_count += 1
        return val


class FakeAskable:
    def __init__(self, val):
        self._val = val

    def ask(self):
        return self._val


class TestWizardHelpers:
    def test_wizard_runs_and_creates_profile(self, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQuestionary([
            ["Computer Science", "Mathematics"],
            ["cs.LG", "cs.AI"],
            ["math.ST"],
            "I study machine learning",
            True,
        ])
        monkeypatch.setattr("arxgent.profile.questionary", fake)

        profile = run_setup_wizard()
        assert "Computer Science" in profile.topics
        assert "Mathematics" in profile.topics
        assert profile.topics["Computer Science"] == ["cs.LG", "cs.AI"]
        assert profile.topics["Mathematics"] == ["math.ST"]
        assert profile.interest == "I study machine learning"

    def test_wizard_cancelled_returns_existing(self, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQuestionary([
            ["Physics"],
            ["quant-ph"],
            "",
            False,
        ])
        monkeypatch.setattr("arxgent.profile.questionary", fake)

        existing = Profile(topics={"Physics": ["quant-ph"]}, interest="quantum")
        result = run_setup_wizard(existing=existing)
        assert result.topics["Physics"] == ["quant-ph"]

    def test_wizard_empty_topics_does_not_save(self, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQuestionary([
            [],
            "",
            True,
        ])
        monkeypatch.setattr("arxgent.profile.questionary", fake)

        result = run_setup_wizard()
        assert result.topics == {}
        assert not profile_exists()

    def test_wizard_no_groups_returns_empty(self, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQuestionary([
            [],
            "",
            True,
        ])
        monkeypatch.setattr("arxgent.profile.questionary", fake)

        result = run_setup_wizard()
        assert result.topics == {}

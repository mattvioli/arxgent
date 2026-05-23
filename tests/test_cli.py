from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from arxgent.cli import cli
from arxgent.profile import PaperEntry, Profile, save_profile


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def profile_with_unread(tmp_config_dir: Path) -> Profile:
    profile = Profile(
        topics={"CS": ["cs.LG"]},
        interest="ML",
        history=[
            PaperEntry(arxiv_id="1706.03762", title="Attention", date_delivered="2026-05-20"),
            PaperEntry(arxiv_id="1603.05027", title="Adam", date_delivered="2026-05-21"),
        ],
    )
    save_profile(profile)
    return profile


class FakeReviewQuestionary:
    def __init__(self, answers: list):
        self._answers = answers
        self._call_count = 0

    def confirm(self, prompt: str, **kw):
        val = self._next()
        return FakeAskable(val)

    def select(self, prompt: str, **kw):
        val = self._next()
        return FakeAskable(val)

    def text(self, prompt: str, **kw):
        val = self._next()
        return FakeAskable(val)

    def _next(self):
        if self._call_count >= len(self._answers):
            return None
        val = self._answers[self._call_count]
        self._call_count += 1
        return val


class FakeAskable:
    def __init__(self, val):
        self._val = val

    def ask(self):
        return self._val


class TestReviewCommand:
    def test_no_profile(self, runner: CliRunner, tmp_config_dir: Path) -> None:
        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "No profile found" in result.output

    def test_no_history(self, runner: CliRunner, tmp_config_dir: Path) -> None:
        save_profile(Profile(topics={"CS": ["cs.LG"]}, interest="ML"))
        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "No papers have been delivered" in result.output

    def test_all_reviewed(self, runner: CliRunner, tmp_config_dir: Path) -> None:
        save_profile(Profile(
            topics={"CS": ["cs.LG"]},
            interest="ML",
            history=[PaperEntry(arxiv_id="1", title="A", date_delivered="2026-05-20", read=True, liked=True)],
        ))
        result = runner.invoke(cli, ["review"])
        assert "All papers reviewed" in result.output

    def test_mark_as_read_liked(self, runner: CliRunner, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_profile(Profile(
            topics={"CS": ["cs.LG"]},
            interest="ML",
            history=[PaperEntry(arxiv_id="1706.03762", title="Attention", date_delivered="2026-05-20")],
        ))

        fake = FakeReviewQuestionary([True, "Liked it", "Great paper about transformers"])
        monkeypatch.setattr("arxgent.cli.questionary", fake)

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "Feedback saved" in result.output

        from arxgent.profile import load_profile
        profile = load_profile()
        assert profile.history[0].read is True
        assert profile.history[0].liked is True
        assert profile.history[0].feedback == "Great paper about transformers"

    def test_mark_as_read_disliked(self, runner: CliRunner, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_profile(Profile(
            topics={"CS": ["cs.LG"]},
            interest="ML",
            history=[PaperEntry(arxiv_id="1706.03762", title="Attention", date_delivered="2026-05-20")],
        ))

        fake = FakeReviewQuestionary([True, "Disliked it", "Too theoretical"])
        monkeypatch.setattr("arxgent.cli.questionary", fake)

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0

        from arxgent.profile import load_profile
        profile = load_profile()
        assert profile.history[0].read is True
        assert profile.history[0].liked is False
        assert profile.history[0].feedback == "Too theoretical"

    def test_mark_as_not_read(self, runner: CliRunner, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_profile(Profile(
            topics={"CS": ["cs.LG"]},
            interest="ML",
            history=[PaperEntry(arxiv_id="1706.03762", title="Attention", date_delivered="2026-05-20")],
        ))

        fake = FakeReviewQuestionary([False])
        monkeypatch.setattr("arxgent.cli.questionary", fake)

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0

        from arxgent.profile import load_profile
        profile = load_profile()
        assert profile.history[0].read is False
        assert profile.history[0].liked is None
        assert profile.history[0].feedback == ""

    def test_review_multiple_papers(self, runner: CliRunner, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_profile(Profile(
            topics={"CS": ["cs.LG"]},
            interest="ML",
            history=[
                PaperEntry(arxiv_id="1", title="Paper One", date_delivered="2026-05-20"),
                PaperEntry(arxiv_id="2", title="Paper Two", date_delivered="2026-05-21"),
            ],
        ))

        fake = FakeReviewQuestionary([True, "Liked it", "Good", True, "Disliked it", "Bad"])
        monkeypatch.setattr("arxgent.cli.questionary", fake)

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "All caught up" in result.output

        from arxgent.profile import load_profile
        profile = load_profile()
        assert profile.history[0].read is True
        assert profile.history[0].liked is True
        assert profile.history[1].read is True
        assert profile.history[1].liked is False


class TestReviewIntegration:
    def test_run_with_skip_review_flag(self, runner: CliRunner, tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from arxgent.profile import save_profile
        save_profile(Profile(topics={"CS": ["cs.LG"]}, interest="ML"))

        monkeypatch.setattr("arxgent.cli.research_papers", lambda **kw: [])
        result = runner.invoke(cli, ["run", "--skip-review"])
        assert result.exit_code == 0
        assert "No papers found" in result.output

    def test_review_command_no_profile(self, runner: CliRunner, tmp_config_dir: Path) -> None:
        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "No profile found" in result.output

    def test_status_shows_review_counts(self, runner: CliRunner, tmp_config_dir: Path) -> None:
        save_profile(Profile(
            topics={"CS": ["cs.LG"]},
            interest="ML",
            history=[
                PaperEntry(arxiv_id="1", title="A", date_delivered="2026-05-20", read=True),
                PaperEntry(arxiv_id="2", title="B", date_delivered="2026-05-21", read=False),
            ],
        ))
        result = runner.invoke(cli, ["status"])
        assert "Papers delivered: 2" in result.output
        assert "Papers read: 1" in result.output

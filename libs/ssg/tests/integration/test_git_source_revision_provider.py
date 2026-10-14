import os
import subprocess
from datetime import date
from pathlib import Path

import pytest
from ssg.infrastructure.git_source_revision_provider import (
    GitSourceRevisionProvider,
)


def _git(
    directory: Path, *args: str, extra_env: dict[str, str] | None = None
) -> None:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["git", *args],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _commit_all(directory: Path, committer_date: str) -> None:
    pinned = {
        "GIT_AUTHOR_DATE": committer_date,
        "GIT_COMMITTER_DATE": committer_date,
    }
    _git(directory, "add", "--all", extra_env=pinned)
    _git(
        directory,
        "-c",
        "user.name=SSG Tests",
        "-c",
        "user.email=tests@example.com",
        "commit",
        "-m",
        "test commit",
        extra_env=pinned,
    )


@pytest.mark.integration
class TestGitSourceRevisionProvider:
    def test_newest_commit_date_returns_committer_date(
        self, tmp_path: Path
    ) -> None:
        _git(tmp_path, "init")
        source = tmp_path / "docs" / "page.md"
        source.parent.mkdir()
        source.write_text("# Page\n", encoding="utf-8")
        _commit_all(tmp_path, "2024-03-05T10:00:00+00:00")

        provider = GitSourceRevisionProvider()

        assert provider.newest_commit_date(source) == date(2024, 3, 5)
        assert provider.repository_path(source) == "docs/page.md"

    def test_newest_commit_date_uses_latest_commit(
        self, tmp_path: Path
    ) -> None:
        _git(tmp_path, "init")
        source = tmp_path / "page.md"
        source.write_text("v1\n", encoding="utf-8")
        _commit_all(tmp_path, "2024-03-05T10:00:00+00:00")
        source.write_text("v2\n", encoding="utf-8")
        _commit_all(tmp_path, "2025-06-07T08:00:00+00:00")

        provider = GitSourceRevisionProvider()

        assert provider.newest_commit_date(source) == date(2025, 6, 7)

    def test_untracked_file_has_path_but_no_date(self, tmp_path: Path) -> None:
        _git(tmp_path, "init")
        source = tmp_path / "drafts" / "new-page.md"
        source.parent.mkdir()
        source.write_text("# Draft\n", encoding="utf-8")

        provider = GitSourceRevisionProvider()

        assert provider.newest_commit_date(source) is None
        assert provider.repository_path(source) == "drafts/new-page.md"

    def test_returns_none_outside_a_repository(self, tmp_path: Path) -> None:
        source = tmp_path / "page.md"
        source.write_text("# Page\n", encoding="utf-8")

        provider = GitSourceRevisionProvider()

        assert provider.newest_commit_date(source) is None
        assert provider.repository_path(source) is None

    def test_repository_path_is_none_for_file_outside_repo(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init")
        outside = tmp_path / "elsewhere" / "page.md"
        outside.parent.mkdir()
        outside.write_text("# Page\n", encoding="utf-8")

        provider = GitSourceRevisionProvider()

        assert provider.repository_path(outside) is None
        assert provider.repository_path(repo / "inside.md") == "inside.md"

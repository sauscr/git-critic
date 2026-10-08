from datetime import date, timedelta
from pathlib import Path

import pytest
from conftest import commit_file, git
from gcritic_core import CriticError
from gcritic_git import GitCli, logic

svc = GitCli()


# ─── Чистый разбор ────────────────────────────────────────────────────────────


def test_parse_status_with_rename_and_spaces():
    output = "M  a.py\0R  new name.py\0old name.py\0?? dir/x.txt\0"
    changes = logic.parse_status(output)
    assert [(c.index, c.worktree, c.path, c.orig_path) for c in changes] == [
        ("M", " ", "a.py", None),
        ("R", " ", "new name.py", "old name.py"),
        ("?", "?", "dir/x.txt", None),
    ]
    assert changes[0].staged and not changes[0].unstaged
    assert not changes[2].staged


def test_parse_log_and_dates_skip_garbage():
    sep, rec = logic.FIELD_SEP, logic.RECORD_SEP
    output = f"abc{sep}Me{sep}2026-10-08 10:00{sep}fix: a{sep}b{rec}\nbad{rec}"
    assert logic.parse_log(output) == []  # 5 полей — не наш формат
    output = f"abc{sep}Me{sep}2026-10-08 10:00{sep}fix: a | b{rec}\n"
    assert logic.parse_log(output)[0].subject == "fix: a | b"
    assert logic.parse_dates("2026-10-08\nnope\n") == [date(2026, 10, 8)]


# ─── Живой git ────────────────────────────────────────────────────────────────


def test_ensure_repository(repo: Path, tmp_path: Path):
    sub = repo / "sub"
    sub.mkdir()
    assert svc.ensure_repository(sub) == repo.resolve()
    with pytest.raises(CriticError, match="не Git"):
        svc.ensure_repository(tmp_path)
    with pytest.raises(CriticError, match="не найдена"):
        svc.ensure_repository(tmp_path / "nope")


def test_empty_repo(empty_repo: Path):
    assert not svc.has_commits(empty_repo)
    assert svc.current_branch(empty_repo) == "main"
    assert svc.log(empty_repo, 5) == []
    assert svc.log_patches(empty_repo, 5) == ""
    assert svc.branches(empty_repo) == []
    assert svc.commit_dates(empty_repo, date.today()) == []
    (empty_repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(empty_repo, "add", "a.txt")
    assert "+a" in svc.diff_head(empty_repo)


def test_status_and_diffs(repo: Path):
    (repo / "app.py").write_text("print('bye')\n", encoding="utf-8")
    (repo / "lib.py").write_text("x = 2\n", encoding="utf-8")
    git(repo, "add", "lib.py")
    (repo / "новый файл.txt").write_text("n\n", encoding="utf-8")

    by_path = {c.path: c for c in svc.status(repo)}
    assert set(by_path) == {"app.py", "lib.py", "новый файл.txt"}
    assert by_path["app.py"].worktree == "M" and not by_path["app.py"].staged
    assert by_path["lib.py"].staged
    assert by_path["новый файл.txt"].index == "?"

    assert "bye" in svc.diff(repo) and "x = 2" not in svc.diff(repo)
    assert "x = 2" in svc.diff(repo, staged=True)
    assert "bye" not in svc.diff(repo, path="lib.py")
    head = svc.diff_head(repo)
    assert "bye" in head and "x = 2" in head


def test_log_branches_dates(repo: Path):
    commits = svc.log(repo, 10)
    assert [c.subject for c in commits] == ["feat: библиотека", "feat: первый коммит"]
    assert len(svc.log(repo, 1)) == 1
    assert "lib.py" in svc.log_patches(repo, 1)

    git(repo, "branch", "feature")
    branches = svc.branches(repo)
    assert [(b.name, b.current) for b in branches] == [("feature", False), ("main", True)]

    dates = svc.commit_dates(repo, date.today() - timedelta(days=6))
    assert dates == [date.today(), date.today()]


def test_detached_head(repo: Path):
    git(repo, "checkout", "-q", "--detach", "HEAD~1")
    assert svc.current_branch(repo).startswith("(detached ")


def test_git_error_is_critic_error(tmp_path: Path):
    with pytest.raises(CriticError, match="упал"):
        svc.status(tmp_path)


def test_commit_file_helper_still_works(repo: Path):
    commit_file(repo, "c.py", "c\n", "third")
    assert svc.log(repo, 1)[0].subject == "third"

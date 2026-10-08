"""Разбор вывода git: чистые функции без побочных эффектов."""

from __future__ import annotations

from datetime import date

from gcritic_core.types import Branch, Commit, FileChange

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"

LOG_FORMAT = f"--pretty=format:%h{FIELD_SEP}%an{FIELD_SEP}%ad{FIELD_SEP}%s{RECORD_SEP}"
LOG_DATE = "--date=format-local:%Y-%m-%d %H:%M"
BRANCH_FORMAT = (
    f"--format=%(HEAD){FIELD_SEP}%(refname:short){FIELD_SEP}"
    f"%(upstream:short){FIELD_SEP}%(upstream:track)"
)


def parse_status(output: str) -> list[FileChange]:
    """`git status --porcelain=v1 -z`: «XY path\\0», у переименований следом «orig\\0»."""
    entries = output.split("\0")
    changes: list[FileChange] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        x, y, path = entry[0], entry[1], entry[3:]
        orig = None
        if x in "RC" and index < len(entries):
            orig = entries[index]
            index += 1
        changes.append(FileChange(path=path, index=x, worktree=y, orig_path=orig))
    return changes


def parse_log(output: str) -> list[Commit]:
    commits: list[Commit] = []
    for record in output.split(RECORD_SEP):
        parts = record.strip("\n").split(FIELD_SEP)
        if len(parts) == 4:
            commits.append(Commit(*parts))
    return commits


def parse_branches(output: str) -> list[Branch]:
    branches: list[Branch] = []
    for line in output.splitlines():
        parts = line.split(FIELD_SEP)
        if len(parts) == 4:
            head, name, upstream, track = parts
            branches.append(Branch(name=name, current=head == "*", upstream=upstream, track=track))
    return branches


def parse_dates(output: str) -> list[date]:
    dates: list[date] = []
    for line in output.splitlines():
        try:
            dates.append(date.fromisoformat(line.strip()))
        except ValueError:
            continue
    return dates

"""gcritic — сборка сервисов и запуск оболочки."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from gcritic_core import CriticError, load_settings
from gcritic_critic import Critic
from gcritic_git import GitCli
from gcritic_stats import Stats
from gcritic_tui import Context, Session, run_shell
from gcritic_tui.render import error
from gcritic_tui.theme import BASE
from rich.console import Console

PACKAGE = "gcritic"
UPDATE_COMMAND = ("uv", "tool", "upgrade", PACKAGE, "--reinstall")


def app_version() -> str:
    try:
        return version(PACKAGE)
    except PackageNotFoundError:
        return "0.0.0-dev"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=PACKAGE,
        description="Консольный git-клиент с ИИ-обзором кода в стиле StopGame.",
    )
    parser.add_argument("repo", nargs="?", default=".", help="путь к репозиторию (по умолчанию .)")
    parser.add_argument("--version", action="version", version=f"{PACKAGE} {app_version()}")
    parser.add_argument("--update", action="store_true", help="обновить gcritic из исходников")
    return parser.parse_args(argv)


def update_script(pids: list[int]) -> str:
    """PowerShell: дождаться выхода gcritic (Windows держит его exe), затем обновить."""
    wait = ",".join(str(pid) for pid in pids)
    return (
        f"Wait-Process -Id {wait} -ErrorAction SilentlyContinue; "
        f"{' '.join(UPDATE_COMMAND)}; "
        "if ($LASTEXITCODE -eq 0) { Write-Host 'gcritic обновлён.' -ForegroundColor Green } "
        "else { Write-Host 'Обновление не удалось.' -ForegroundColor Red }; "
        "Read-Host 'Enter — закрыть'"
    )


def run_update() -> int:
    if shutil.which("uv") is None:
        print("uv не найден в PATH. Запусти install.ps1 заново.", file=sys.stderr)
        return 1
    if sys.platform != "win32":
        return subprocess.call(UPDATE_COMMAND)
    script = update_script([os.getpid(), os.getppid()])
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print("Обновление запущено в отдельном окне.")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    if args.update:
        return run_update()

    console = Console(style=BASE, highlight=False)
    try:
        settings = load_settings()
    except CriticError as exc:
        console.print(error(f"Настройки: {exc}"))
        return 1

    git = GitCli()
    try:
        repo: Path | None = git.ensure_repository(Path(args.repo).resolve())
    except CriticError as exc:
        console.print(error(str(exc)))
        repo = None

    ctx = Context(
        settings=settings,
        git=git,
        critic=Critic(settings),
        stats=Stats(settings.stats_days),
        console=console,
        session=Session(repo=repo),
        version=app_version(),
    )
    return run_shell(ctx)


if __name__ == "__main__":
    sys.exit(main())

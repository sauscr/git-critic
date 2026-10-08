# git_critic — план реализации

Консольный git-клиент уровня GitHub Desktop + ИИ-ревью кода в стиле StopGame.
Pure Black интерфейс, `/команды` с подсказками, горячие клавиши.

## Решения

| Вопрос | Решение |
|---|---|
| Python | 3.15 через uv (`requires-python = ">=3.15,<3.16"`), как в job-radar |
| Сборка | uv workspace, один `uv.lock` |
| Архитектура | модульные пакеты-сервисы с контрактами (`Protocol`) в одном процессе; любой сервис выносится в отдельный процесс (JSON-RPC по stdio) без изменения TUI |
| Стиль кода | функциональный: конфиг и константы наверху, ниже чистые функции; побочные эффекты (git, сеть, экран) — только на краях |
| Настройки | `core/settings.py` — все переменные в одном месте с комментариями (что / где / по умолчанию); любую можно переопределить в `.env` |
| Секреты | `%USERPROFILE%\.gcritic\.env` (`OPENAI_API_KEY` — необязателен, и переопределения); переменные окружения важнее `.env`; шаблон `.env.example` |
| Запуск | одна команда `gcritic` из любой папки (`uv tool install`) |
| Установка | `install.ps1` (Windows) / `install.sh` (Linux, macOS): uv → Python 3.15 → `uv tool install` → `.env` (ключ необязателен) → PATH. Релиз: Chocolatey, PyPI, AUR/brew |
| TUI | `prompt_toolkit` (ввод, меню `/`, хоткеи, нижняя строка подсказок) + `rich` (отрисовка) + `pyfiglet` (логотип: larry3d и ещё 5 шрифтов, `/logo`) |
| Загрузка | Демо-заставка в стиле кряктро 90-х/00-х (звёзды, copper-бары, радужный логотип, синус-скроллер, прогресс реальной загрузки); любая клавиша — пропустить; `/intro`, `GCRITIC_INTRO=0` |
| ИИ | Бэкенды критика (`GCRITIC_BACKEND`, `/backend`): `openai` — API-ключ, `gpt-4o-mini`, Structured Outputs; `codex` — `codex exec --output-schema` под входом ChatGPT; `claude` — `claude -p --json-schema` под входом Claude. `auto`: ключ → codex → claude |

## Структура

```
git_critic/
  pyproject.toml            workspace root, Python 3.15
  .env.example              шаблон секретов и переопределений
  install.ps1               установщик (одна команда)
  uninstall.ps1             удаление (оставляет ~/.gcritic, если не -Purge)
  packages/
    core/                   settings.py (все переменные), загрузка .env, контракты, типы, ошибки
    git_svc/                обёртка git: чтение (alpha) → запись (beta)
    critic_svc/             OpenAI: ревью, сообщение коммита
    stats_svc/              активность по дням, метрики
    tui/                    REPL, реестр команд, хоткеи, рендер-функции
  apps/cli/                 точка входа: сборка сервисов → команда `gcritic`
  tests/                    по папке на пакет
```

Правило зависимостей: `tui` → `core` ← сервисы. Сервисы не знают друг о друге и о TUI.
Каждый пакет: `config` (константы) → `types` → `logic` (чистые функции) → `io` (git/сеть).

## Альфа 0.1 — каркас и чтение

1. uv workspace, Python 3.15, пакеты `core / git_svc / critic_svc / stats_svc / tui / apps/cli`.
2. `core`: `settings.py` (все переменные с комментариями) + загрузка `~/.gcritic/.env` → frozen-dataclass; контракты `GitService`, `CriticService`, `StatsService`; `CriticError`.
3. Перенос логики из `git_critic.py` (v0) по пакетам без изменения поведения.
4. `git_svc` (чтение): `status`, `diff` (рабочая копия / staged / файл), `log`, `branches`, `current_branch`, `ensure_repository`.
5. `tui`: REPL на prompt_toolkit.
   - Реестр команд: имя, аргументы, описание, хоткей, обработчик — одна таблица, из неё строятся `/help`, автодополнение и строка подсказок.
   - Меню автодополнения при вводе `/` с описаниями команд.
   - Нижняя строка: репозиторий · ветка · кол-во изменений · `? help · ^R review · ^L clear · ^D exit`.
   - История ввода (↑/↓), Ctrl+R/Ctrl+L/Ctrl+D, Esc — сброс ввода.
6. Команды: `/help`, `/review`, `/stats`, `/status`, `/diff [файл]`, `/log [n]`, `/branches`, `/repo <путь>`, `/clear`, `/exit`.
7. `install.ps1` / `uninstall.ps1` / `.env.example`; `gcritic --version`, `gcritic --update`.
8. Тесты: `git_svc` на временных репозиториях, `critic_svc.parse_review`, рендер на `Console(record=True)`.
9. Готово когда: после `.\install.ps1` команда `gcritic` в новом терминале открывает оболочку, все команды работают, тесты зелёные.

## Бета 0.5 — функции GitHub Desktop

1. `git_svc` (запись): stage/unstage (файл, все), discard, commit, branch create/delete, checkout, fetch/pull/push, stash push/pop/list.
2. Команды: `/stage`, `/unstage`, `/discard`, `/commit [-m]`, `/branch`, `/checkout`, `/fetch`, `/pull`, `/push`, `/stash`.
3. Выбор файлов стрелками + пробел (чекбоксы) для stage/unstage/discard.
4. Подтверждение необратимого: discard, branch delete, push с расхождением.
5. `critic_svc`: `/commit` без `-m` → ИИ предлагает сообщение (Conventional Commits), правка перед коммитом.
6. `/review <файл>`, `/review --staged`; кэш ревью по хэшу диффа.
7. Хоткеи: Ctrl+S stage, Ctrl+K commit, Ctrl+P push.
8. Готово когда: полный цикл «правка → stage → ИИ-commit → push» без выхода из оболочки.

## Релиз 1.0

1. `/pr` — создание PR через `gh`, ИИ-описание по диффу ветки.
2. `/clone <url>`, `/init`.
3. Конфликты merge: список, просмотр, выбор ours/theirs, `/merge`, `/rebase --abort`.
4. ИИ-ревью перед коммитом (переменная в `settings.py` / `.env`).
5. Дистрибуция для своих (кентов):
   - публичный GitHub-репозиторий + релизы по тегу (GitHub Actions: тесты → сборка → публикация);
   - PyPI: один пакет `gcritic` (сборка всех `src/` в один wheel или публикация 6 пакетов workspace)
     → `uv tool install gcritic` / `pipx install gcritic` на любой ОС;
   - Windows: пакет Chocolatey `gcritic` (`choco install gcritic`): nuspec + `chocolateyinstall.ps1`
     ставит uv и вызывает `uv tool install gcritic`; модерация community-репозитория ~дни;
     одной строкой без choco: `irm https://raw.githubusercontent.com/sauscr/git-critic/main/install.ps1 | iex`;
   - Linux/macOS: `install.sh` (готов, ставит из клона), одной строкой:
     `curl -LsSf https://raw.githubusercontent.com/sauscr/git-critic/main/install.sh | sh`;
     дальше — AUR (`gcritic`), Homebrew tap, .deb через GitHub Releases;
   - Python 3.15 сейчас rc: до финала 3.15 uv скачивает rc сам, у кентов ничего ставить не нужно.
   Опционально: `.exe`-установщик (PyInstaller + Inno Setup).
6. Лог ошибок в файл, `--debug`.
7. README: установка, команды, хоткеи, конфиг.
8. Готово когда: `gcritic` заменяет GitHub Desktop в ежедневной работе.

## Перенос в процессы (по необходимости, после 1.0)

Контракты из `core` → JSON-RPC по stdio; `apps/cli` запускает сервисы как подпроцессы.
TUI не меняется.

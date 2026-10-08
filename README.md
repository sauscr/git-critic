# gcritic

Консольный git-клиент с ИИ-обзором кода в стиле StopGame. Pure Black, `/команды`, хоткеи,
демо-заставка в духе кряктро 90-х.

> Альфа 0.1: чтение репозитория и обзоры. Запись (stage, commit, push) — в бете, см. [PLAN.md](PLAN.md).

## Установка

Windows (PowerShell):

```powershell
git clone https://github.com/sauscr/git_critic; cd git_critic; .\install.ps1
```

Linux / macOS:

```sh
git clone https://github.com/sauscr/git_critic && cd git_critic && ./install.sh
```

Установщик сам поставит [uv](https://docs.astral.sh/uv/) и Python 3.15. Дальше в любой папке: `gcritic`.
Обновление: `gcritic --update`. Удаление: `.\uninstall.ps1` / `./install.sh --uninstall`.

## Кто пишет обзор

| Бэкенд | Что нужно |
|---|---|
| `openai` | API-ключ `OPENAI_API_KEY` в `~/.gcritic/.env` |
| `codex` | вход ChatGPT: [Codex CLI](https://github.com/openai/codex) + `codex login` |
| `claude` | вход Claude: [Claude Code](https://claude.com/claude-code) |

По умолчанию `auto`: ключ → codex → claude. Переключить: `/backend <имя>` или `GCRITIC_BACKEND`.

## Команды

| Команда | Хоткей | Что делает |
|---|---|---|
| `/review` | `Ctrl+R` | ИИ-обзор незакоммиченных изменений (или последних коммитов) |
| `/status` | | изменённые файлы |
| `/diff [--staged] [файл]` | | дифф |
| `/log [n]` | | последние коммиты |
| `/branches` | | ветки и upstream |
| `/stats` | | активность по дням |
| `/backend [имя]` | | кто пишет обзор |
| `/logo [шрифт]` | | шрифт логотипа: larry3d, 3d-ascii, bloody, delta_corps_priest_1, sub-zero, poison |
| `/intro` | | демо-заставка |
| `/repo <путь>` | | сменить репозиторий |
| `/help` | `?` | справка |
| `/clear` · `/exit` | `Ctrl+L` · `Ctrl+D` | |

## Настройки

Все переменные с описанием — в [`.env.example`](.env.example) и
[`settings.py`](packages/core/src/gcritic_core/settings.py). Рабочий файл: `~/.gcritic/.env`.

## Разработка

```sh
uv sync && uv run pytest && uv run ruff check .
```

Лицензия: MIT.

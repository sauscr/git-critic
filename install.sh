#!/usr/bin/env sh
# Установка gcritic (Linux / macOS): uv -> Python 3.15 -> uv tool install -> ~/.gcritic/.env -> PATH.
#   ./install.sh                 спросит ключ OpenAI (Enter — пропустить: хватит входа в codex/claude)
#   ./install.sh --api-key sk-…  без вопросов
#   ./install.sh --uninstall     удалить (~/.gcritic остаётся; --purge — удалить и её)
set -eu

PYTHON_VERSION="3.15"
SOURCE="$(cd "$(dirname "$0")" && pwd)/apps/cli"
TEMPLATE="$(cd "$(dirname "$0")" && pwd)/.env.example"
HOME_DIR="$HOME/.gcritic"
ENV_FILE="$HOME_DIR/.env"
UV_INSTALLER="https://astral.sh/uv/install.sh"

step() { printf '\033[1;36m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$1"; }

API_KEY=""
UNINSTALL=0
PURGE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --api-key) API_KEY="$2"; shift 2 ;;
        --uninstall) UNINSTALL=1; shift ;;
        --purge) UNINSTALL=1; PURGE=1; shift ;;
        *) echo "Неизвестный аргумент: $1" >&2; exit 2 ;;
    esac
done

if [ "$UNINSTALL" -eq 1 ]; then
    command -v uv >/dev/null 2>&1 && uv tool uninstall gcritic || warn "gcritic не был установлен через uv."
    if [ "$PURGE" -eq 1 ]; then rm -rf "$HOME_DIR" && echo "Удалено: $HOME_DIR"; fi
    exit 0
fi

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
    step "Ставлю uv"
    curl -LsSf "$UV_INSTALLER" | sh
    PATH="$HOME/.local/bin:$PATH"
fi

# 2. Python
step "Python $PYTHON_VERSION"
uv python install "$PYTHON_VERSION"

# 3. gcritic
step "gcritic из $SOURCE"
uv tool install --python "$PYTHON_VERSION" --force --reinstall "$SOURCE"

# 4. Настройки и ключ
mkdir -p "$HOME_DIR"
if [ ! -f "$ENV_FILE" ]; then
    cp "$TEMPLATE" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    step "Создан $ENV_FILE"
fi
if ! grep -Eq '^[[:space:]]*OPENAI_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]' "$ENV_FILE"; then
    if [ -z "$API_KEY" ] && [ -t 0 ]; then
        printf 'Ключ OpenAI (Enter - пропустить, если есть вход в codex/claude): '
        stty -echo; read -r API_KEY || true; stty echo; echo
    fi
    if [ -n "$API_KEY" ]; then
        grep -Ev '^[[:space:]]*OPENAI_API_KEY[[:space:]]*=' "$ENV_FILE" > "$ENV_FILE.tmp" || true
        { echo "OPENAI_API_KEY=$API_KEY"; cat "$ENV_FILE.tmp"; } > "$ENV_FILE"
        rm -f "$ENV_FILE.tmp"
        step "Ключ записан в $ENV_FILE"
    else
        warn "Ключа нет - критик пойдёт через codex/claude (нужен вход: codex login или claude)."
    fi
fi

# 5. PATH
step "PATH"
uv tool update-shell || true
PATH="$(uv tool dir --bin):$PATH"
gcritic --version
printf '\033[1;32mГотово. Открой новый терминал и запусти: gcritic\033[0m\n'

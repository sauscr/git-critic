<#
.SYNOPSIS
    Установка gcritic одной командой: uv -> Python 3.15 -> uv tool install -> .env -> PATH.
.PARAMETER ApiKey
    Ключ OpenAI. Не задан — спросит, если в .env ключа ещё нет (Enter — пропустить).
    Ключ необязателен: без него критик работает через вход в codex (ChatGPT) или claude.
.EXAMPLE
    .\install.ps1
    .\install.ps1 -ApiKey sk-...
#>
[CmdletBinding()]
param([string]$ApiKey = "")

$ErrorActionPreference = "Stop"

$PythonVersion = "3.15"
$Source = Join-Path $PSScriptRoot "apps\cli"
$Template = Join-Path $PSScriptRoot ".env.example"
$HomeDir = Join-Path $env:USERPROFILE ".gcritic"
$EnvFile = Join-Path $HomeDir ".env"
$UvInstaller = "https://astral.sh/uv/install.ps1"
$Utf8 = New-Object System.Text.UTF8Encoding $false

function Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }

function Invoke-Native([string]$What, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What : код выхода $LASTEXITCODE" }
}

function Read-ApiKey {
    if (-not [Environment]::UserInteractive) { return "" }
    $secure = Read-Host "Ключ OpenAI (Enter - пропустить, если есть вход в codex/claude)" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

# 1. uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Step "Ставлю uv"
    Invoke-RestMethod $UvInstaller | Invoke-Expression
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}

# 2. Python
Step "Python $PythonVersion"
Invoke-Native "uv python install" { uv python install $PythonVersion }

# 3. gcritic
Step "gcritic из $Source"
Invoke-Native "uv tool install" { uv tool install --python $PythonVersion --force --reinstall $Source }

# 4. Настройки и ключ
New-Item -ItemType Directory -Force $HomeDir | Out-Null
if (-not (Test-Path $EnvFile)) {
    Copy-Item $Template $EnvFile
    Step "Создан $EnvFile"
}
$lines = [IO.File]::ReadAllLines($EnvFile, $Utf8)
$hasKey = [bool]($lines | Where-Object { $_ -match '^\s*OPENAI_API_KEY\s*=\s*\S' })
if (-not $ApiKey -and -not $hasKey) { $ApiKey = Read-ApiKey }
if ($ApiKey) {
    $lines = @($lines | Where-Object { $_ -notmatch '^\s*OPENAI_API_KEY\s*=' })
    $lines = @("OPENAI_API_KEY=$ApiKey") + $lines
    [IO.File]::WriteAllLines($EnvFile, $lines, $Utf8)
    Step "Ключ записан в $EnvFile"
} elseif (-not $hasKey) {
    Write-Host "Ключа нет - критик пойдёт через codex/claude (нужен вход: codex login или claude)." -ForegroundColor Yellow
    Write-Host "Ключ можно добавить позже: OPENAI_API_KEY в $EnvFile" -ForegroundColor Yellow
}

# 5. PATH
Step "PATH"
Invoke-Native "uv tool update-shell" { uv tool update-shell }
$binDir = (& uv tool dir --bin).Trim()
if (($env:PATH -split ";") -notcontains $binDir) { $env:PATH = "$binDir;$env:PATH" }

Invoke-Native "gcritic --version" { gcritic --version }
Write-Host "Готово. Открой новый терминал и запусти: gcritic" -ForegroundColor Green

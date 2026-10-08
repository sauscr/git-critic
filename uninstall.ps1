<#
.SYNOPSIS
    Удаление gcritic. Папка %USERPROFILE%\.gcritic (ключ, история) остаётся, если не указан -Purge.
.EXAMPLE
    .\uninstall.ps1
    .\uninstall.ps1 -Purge
#>
[CmdletBinding()]
param([switch]$Purge)

$ErrorActionPreference = "Stop"
$HomeDir = Join-Path $env:USERPROFILE ".gcritic"

if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv tool uninstall gcritic
    if ($LASTEXITCODE -ne 0) { Write-Host "gcritic не был установлен через uv." -ForegroundColor Yellow }
} else {
    Write-Host "uv не найден - удалять нечего." -ForegroundColor Yellow
}

if ($Purge -and (Test-Path $HomeDir)) {
    Remove-Item -Recurse -Force $HomeDir
    Write-Host "Удалено: $HomeDir"
} elseif (Test-Path $HomeDir) {
    Write-Host "Оставлено: $HomeDir (ключ и история). Удалить всё: .\uninstall.ps1 -Purge"
}
Write-Host "gcritic удалён." -ForegroundColor Green

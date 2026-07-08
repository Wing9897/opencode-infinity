# Build OpenCode Infinity desktop exe locally (same output as CI).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pip
pip install -r requirements-desktop.txt

$sha = (git rev-parse --short HEAD 2>$null)
if (-not $sha) { $sha = "local" }

$meta = @{
    version = "dev-local"
    sha     = $sha
} | ConvertTo-Json -Compress
Set-Content -Path "desktop/build-meta.json" -Value $meta -Encoding utf8

pyinstaller desktop/opencode_infinity.spec --noconfirm --clean

Get-ChildItem dist/*.exe | Format-Table Name, Length

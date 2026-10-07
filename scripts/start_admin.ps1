param([ValidateRange(0, 65535)][int]$AdminPort = 8765)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$serverScript = Join-Path $PSScriptRoot "admin_server.py"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "未找到 Python。请安装 Python 3.10 或更高版本后重试。"
}

python -B -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
  throw "需要 Python 3.10 或更高版本。"
}

Set-Location -LiteralPath $projectRoot
python -B $serverScript --port $AdminPort

# Claude token-usage tracker installer (Windows PowerShell).
$ErrorActionPreference = 'Stop'

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

$py = $null
foreach ($name in @('python', 'python3')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source; break }
}

if (-not $py) {
    Write-Host "ERROR: Python 3 is required but was not found on PATH." -ForegroundColor Red
    Write-Host "Install Python 3 from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
    exit 1
}

& $py (Join-Path $dir 'install.py') @args
exit $LASTEXITCODE

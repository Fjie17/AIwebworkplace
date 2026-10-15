# Start ChatGPT monitor in background and open the dashboard.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Creating venv..."
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -U pip
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

$existing = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
  Write-Host "Starting monitor on http://127.0.0.1:8765 ..."
  Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "main.py" -WorkingDirectory $Root -WindowStyle Minimized
  Start-Sleep -Seconds 2
} else {
  Write-Host "Monitor already listening on 8765."
}

Start-Process "http://127.0.0.1:8765/"

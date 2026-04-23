$pythonCandidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)

$pythonExe = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $pythonExe) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike "*WindowsApps*") {
        $pythonExe = $pythonCommand.Source
    }
}

if (-not $pythonExe) {
    Write-Error "Could not find a working Python interpreter. Install Python 3.11+ or update start_web.ps1."
    exit 1
}

Write-Host "Starting Overlay Typer Bot Web with $pythonExe"
& $pythonExe "$PSScriptRoot\web_app.py"

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Python {
    if (Test-Path ".\.venv\Scripts\python.exe") {
        return ".\.venv\Scripts\python.exe"
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -3 -c "import sys" 2>$null | Out-Null
            return "py -3"
        } catch {}
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "[ERROR] Python が見つかりません。.venv を用意するか run.ps1 を先に実行してください。" -ForegroundColor Red
    exit 1
}

& $py import_gifs.py @args
exit $LASTEXITCODE

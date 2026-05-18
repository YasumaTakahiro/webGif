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
    $candidates = @(
        "$env:USERPROFILE\.local\bin\python3.12.exe",
        "$env:USERPROFILE\.local\bin\python3.exe",
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:LocalAppData\Programs\Python\Python311\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host ""
    Write-Host "[ERROR] 使える Python が見つかりません。" -ForegroundColor Red
    Write-Host "https://www.python.org/downloads/ から Python 3.10+ をインストールし、"
    Write-Host "このフォルダで run.bat または run.ps1 を再実行してください。"
    Write-Host ""
    exit 1
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Python: $py"
    Write-Host "仮想環境を作成しています..."
    if ($py -eq "py -3") {
        & py -3 -m venv .venv
    } else {
        & $py -m venv .venv
    }
    $py = ".\.venv\Scripts\python.exe"
}

Write-Host "依存パッケージを確認しています..."
& $py -m pip install -q -r requirements.txt

Write-Host ""
Write-Host "既存の webGif サーバーを停止しています..."
& "$PSScriptRoot\stop.ps1"

$port = if ($env:WEBGIF_PORT) { $env:WEBGIF_PORT } else { "5055" }
$url = "http://127.0.0.1:$port/"

Write-Host "起動中: $url"
Write-Host "終了: Ctrl+C  または別のターミナルで .\stop.ps1"
Write-Host "ログファイル: $PSScriptRoot\webgif.log"
Write-Host ""
Write-Host "重要: ブラウザは必ず $url を開いてください（ポート 5000 ではありません）"
Write-Host "接続テスト: ${url}health で webGif OK と表示されれば接続成功"
Write-Host ""
$env:MAX_UPLOAD_MB = "0"
$env:WEBGIF_PORT = $port
$env:PYTHONUNBUFFERED = "1"
& $py -u app.py

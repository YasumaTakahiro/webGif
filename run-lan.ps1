# 同一 LAN 内の PC・スマホからアクセスできるよう 0.0.0.0 で起動
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:WEBGIF_HOST = "0.0.0.0"
$port = if ($env:WEBGIF_PORT) { $env:WEBGIF_PORT } else { "5055" }

Write-Host ""
Write-Host "=== LAN 公開モード ===" -ForegroundColor Cyan
Write-Host "この PC と同じ Wi-Fi / 有線 LAN 内の端末から、次の URL で開けます:"
Write-Host ""

$shown = $false
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*"
    } |
    ForEach-Object {
        Write-Host "  http://$($_.IPAddress):$port/" -ForegroundColor Green
        $shown = $true
    }

if (-not $shown) {
    Write-Host "  (IP を取得できませんでした。ipconfig で IPv4 を確認してください)"
    Write-Host "  例: http://192.168.0.10:$port/"
}

Write-Host ""
Write-Host "この PC 自身: http://127.0.0.1:$port/"
Write-Host "注意: 認証なし。信頼できる家庭内 LAN のみで使ってください。"
Write-Host "Windows ファイアウォールでブロックされたら、Python の通信を許可してください。"
Write-Host ""

& "$PSScriptRoot\run.ps1"

# Stop webGif server (when Ctrl+C does not work)
$ErrorActionPreference = "SilentlyContinue"
Set-Location $PSScriptRoot

$ports = @(5055, 5000)
if ($env:WEBGIF_PORT) {
    $ports = @([int]$env:WEBGIF_PORT) + $ports | Select-Object -Unique
}

Write-Host "Stopping webGif servers..."
$stopped = 0

foreach ($port in $ports) {
    $lines = netstat -ano | Select-String "127.0.0.1:$port\s" | Select-String "LISTENING"
    if (-not $lines) {
        $lines = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
    }
    foreach ($line in $lines) {
        $parts = ($line.ToString().Trim() -split '\s+')
        $procId = $parts[-1]
        if ($procId -match '^\d+$' -and $procId -ne '0') {
            Write-Host "  port $port -> kill PID $procId"
            Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            if (-not $?) {
                taskkill /F /PID $procId 2>$null | Out-Null
            }
            $stopped++
        }
    }
}

Start-Sleep -Milliseconds 500

foreach ($port in $ports) {
    $still = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
    if ($still) {
        Write-Host "[WARN] port $port is still in use" -ForegroundColor Yellow
    }
}

if ($stopped -eq 0) {
    Write-Host "No server found (may already be stopped)."
} else {
    Write-Host "Done: stopped $stopped process(es)."
}
Write-Host ""

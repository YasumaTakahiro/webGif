@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY="

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
  goto :ready
)

where py >nul 2>&1 && (
  py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
)
if defined PY goto :create_venv

if exist "%USERPROFILE%\.local\bin\python3.12.exe" (
  set "PY=%USERPROFILE%\.local\bin\python3.12.exe"
  goto :create_venv
)
if exist "%USERPROFILE%\.local\bin\python3.exe" (
  set "PY=%USERPROFILE%\.local\bin\python3.exe"
  goto :create_venv
)

for %%P in (
  "%LocalAppData%\Programs\Python\Python312\python.exe"
  "%LocalAppData%\Programs\Python\Python311\python.exe"
  "%LocalAppData%\Programs\Python\Python310\python.exe"
) do (
  if exist %%P (
    set "PY=%%~fP"
    goto :create_venv
  )
)

echo.
echo [ERROR] 使える Python が見つかりません。
echo.
echo 次のいずれかを行ってください:
echo   1. https://www.python.org/downloads/ から Python 3.10+ をインストール
echo      （「Add python.exe to PATH」にチェック）
echo   2. インストール後、このフォルダで再度 run.bat を実行
echo.
echo 注意: ストア版の「python」だけでは動きません。run.bat を使ってください。
echo.
pause
exit /b 1

:create_venv
echo Python: %PY%
echo 仮想環境を作成しています...
%PY% -m venv .venv
if errorlevel 1 (
  echo [ERROR] venv の作成に失敗しました。
  pause
  exit /b 1
)
set "PY=.venv\Scripts\python.exe"

:ready
echo 依存パッケージを確認しています...
"%PY%" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install に失敗しました。
  pause
  exit /b 1
)

echo.
if not defined WEBGIF_PORT set WEBGIF_PORT=5055
echo 既存サーバーを停止しています...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
echo.
echo 起動中: http://127.0.0.1:%WEBGIF_PORT%/
echo ログファイル: %~dp0webgif.log
echo 終了するには Ctrl+C を押してください。
echo 重要: ブラウザはポート %WEBGIF_PORT% を開いてください（5000 ではありません）
echo.
set MAX_UPLOAD_MB=0
set PYTHONUNBUFFERED=1
"%PY%" -u app.py
pause

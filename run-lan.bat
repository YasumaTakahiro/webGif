@echo off
setlocal
cd /d "%~dp0"
set WEBGIF_HOST=0.0.0.0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-lan.ps1"
exit /b %ERRORLEVEL%

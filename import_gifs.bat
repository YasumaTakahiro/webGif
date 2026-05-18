@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" import_gifs.py %*
) else (
  py -3 import_gifs.py %*
)
exit /b %ERRORLEVEL%

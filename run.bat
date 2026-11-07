@echo off
REM Time to Power - double-click to start the dashboard at http://localhost:8001
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/ and tick "Add to PATH".
  pause
  exit /b 1
)
REM Optional: put ANTHROPIC_API_KEY=... in a .env file next to this script for the Claude-drafted disclosure note and live sites to buy or lease
if exist .env (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
)
echo Checking packages...
python -m pip install -q fastapi "uvicorn[standard]" pandas numpy python-multipart anthropic
start "" http://localhost:8001
python -m uvicorn app.main:app --port 8001
pause

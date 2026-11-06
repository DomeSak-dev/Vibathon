@echo off
REM Time to Power - double-click to start the dashboard at http://localhost:8001
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/ and tick "Add to PATH".
  pause
  exit /b 1
)
echo Checking packages...
python -m pip install -q fastapi "uvicorn[standard]" pandas numpy
start "" http://localhost:8001
python -m uvicorn app.main:app --port 8001
pause

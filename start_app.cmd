@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run

where python >nul 2>&1
if errorlevel 1 goto nopython

echo Preparing the local environment. This is only needed once...
python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

:run
echo Starting the local bill analyzer...
echo Your browser should open http://127.0.0.1:8501
echo Press Ctrl+C in this window to stop the app.
powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8501'"
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --browser.gatherUsageStats false
if errorlevel 1 goto failed
exit /b 0

:nopython
echo Python was not found. Install Python 3.11 or newer and enable Add Python to PATH.
pause
exit /b 1

:failed
echo The app could not start. Copy the error above and send it to Codex.
pause
exit /b 1

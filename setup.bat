@echo off
cd /d "%~dp0"
py -m venv .venv_portal
if errorlevel 1 goto failed
.venv_portal\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Ready. Run start.bat to play.
pause
exit /b 0
:failed
echo Installation failed. Check Python and your internet connection.
pause
exit /b 1

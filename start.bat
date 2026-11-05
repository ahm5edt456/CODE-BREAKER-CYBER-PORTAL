@echo off
cd /d "%~dp0"
if not exist .venv_portal\Scripts\python.exe (
 echo First run setup.bat to install the interface libraries.
 pause
 exit /b 1
)
.venv_portal\Scripts\python.exe main.py
if errorlevel 1 pause

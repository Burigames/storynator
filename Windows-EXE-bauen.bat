@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe scripts\build_windows.py
if errorlevel 1 goto fail
echo Fertig: dist\Storynator.exe
echo Diese einzelne Datei kann direkt gestartet und weitergegeben werden.
pause
exit /b 0
:fail
echo Build fehlgeschlagen.
pause
exit /b 1

@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name Storynator app.py
if errorlevel 1 goto fail
echo Fertig: dist\Storynator\Storynator.exe
echo Den gesamten Ordner dist\Storynator weitergeben. Die fertige App benoetigt weder Python noch Internet.
pause
exit /b 0
:fail
echo Build fehlgeschlagen.
pause
exit /b 1

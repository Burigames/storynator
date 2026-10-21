@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Installation abgeschlossen. Start mit Start-Storynator.bat.
pause
exit /b 0
:fail
echo Installation fehlgeschlagen. Python 3.11 oder neuer und Netzwerkzugang zur Paketinstallation erforderlich.
pause
exit /b 1

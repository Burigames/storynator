"""Developer build: produces a conventional Windows application directory."""
import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QLibraryInfo

ROOT=Path(__file__).resolve().parents[1]
def build():
    if sys.platform!='win32':raise SystemExit('Der Windows-Build muss unter Windows laufen.')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--noupx','--windowed','--name','Storynator','--icon',str(ROOT/'assets'/'Storynator.ico'),'--add-data',str(ROOT/'Beispiel.storynator')+os.pathsep+'.','--add-data',str(ROOT/'LICENSE')+os.pathsep+'.','--add-data',str(Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath))/'qtbase_de.qm')+os.pathsep+'translations','--version-file',str(ROOT/'assets'/'windows-version.txt'),'--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtWebEngineWidgets','--exclude-module','PySide6.QtQml','--exclude-module','PySide6.QtQuick',str(ROOT/'app.py')],cwd=ROOT,check=True)
    exe=ROOT/'dist'/'Storynator'/'Storynator.exe'
    if not exe.exists():raise RuntimeError('EXE wurde nicht erzeugt.')
    print('Fertige Anwendung:',exe)
if __name__=='__main__':build()

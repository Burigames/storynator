"""Developer build: produces a conventional Windows application directory."""
import os,json
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QLibraryInfo

ROOT=Path(__file__).resolve().parents[1]
def build():
    if sys.platform!='win32':raise SystemExit('Der Windows-Build muss unter Windows laufen.')
    version='0.8.'+os.environ['GITHUB_RUN_NUMBER'] if os.environ.get('GITHUB_RUN_NUMBER') else '0.8.1'
    build_data=ROOT/'build';build_data.mkdir(exist_ok=True);info=build_data/'release-info.json';info.write_text(json.dumps({'version':version}),encoding='utf-8');windows_info=build_data/'windows-version.txt';base=(ROOT/'assets'/'windows-version.txt').read_text(encoding='utf-8');numbers=tuple(map(int,version.split('.')))+(0,);windows_info.write_text(base.replace('(0,8,1,0)',str(numbers)).replace('0.8.1',version),encoding='utf-8')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--noupx','--windowed','--name','Storynator','--icon',str(ROOT/'assets'/'Storynator.ico'),'--add-data',str(ROOT/'Beispiel.storynator')+os.pathsep+'.','--add-data',str(ROOT/'assets'/'dictionaries')+os.pathsep+'assets/dictionaries','--add-data',str(info)+os.pathsep+'assets','--add-data',str(ROOT/'LICENSE')+os.pathsep+'.','--add-data',str(Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath))/'qtbase_de.qm')+os.pathsep+'translations','--version-file',str(windows_info),'--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtWebEngineWidgets','--exclude-module','PySide6.QtQml','--exclude-module','PySide6.QtQuick',str(ROOT/'app.py')],cwd=ROOT,check=True)
    exe=ROOT/'dist'/'Storynator'/'Storynator.exe'
    if not exe.exists():raise RuntimeError('EXE wurde nicht erzeugt.')
    print('Fertige Anwendung:',exe)
if __name__=='__main__':build()

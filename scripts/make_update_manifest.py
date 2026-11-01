"""Release metadata is created only after Windows build/installer checks."""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from versioning import version_tuple

def make(path,version):
    version_tuple(version);path=Path(path)
    return dict(format='storynator.update',version=1,release=version,url='https://github.com/Burigames/storynator/releases/download/v'+version+'/Storynator-Setup.exe',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),size=path.stat().st_size)
if __name__=='__main__':
    version='0.8.'+os.environ['GITHUB_RUN_NUMBER'];(ROOT/'dist'/'update.json').write_text(json.dumps(make(ROOT/'dist'/'Storynator-Setup.exe',version),indent=2),encoding='utf-8')

import copy,hashlib,json
from pathlib import Path
import pytest
from test_storynator import qt,isolated_preferences
from test_safety import studio
from PySide6.QtCore import QObject,Signal,QTimer,QUrl,QByteArray
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QNetworkRequest,QNetworkReply
from versioning import version_tuple,current_version
from updates import manifest,allowed_url,verify_installer,install_update,installer_arguments,Download,MANIFEST_URL

def info(raw=b'MZ'+b'0'*126):
    return dict(format='storynator.update',version=1,release='9.1.2',url='https://github.com/Burigames/storynator/releases/download/v9.1.2/Storynator-Setup.exe',sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
def test_versions_are_numeric_and_manifest_is_pinned():
    assert version_tuple('0.8.20')>version_tuple('v0.8.9');data=info();assert manifest(json.dumps(data).encode())==data
    for key,value in [('url','https://evil.example/setup.exe'),('sha256','bad'),('release','9.1.2-beta'),('size',True),('version',True)]:
        bad={**data,key:value}
        with pytest.raises(ValueError):manifest(json.dumps(bad).encode())
    for value in ['https://github.com/Other/repo/releases/latest','http://github.com/Burigames/storynator/releases/latest','https://github.com@evil.example/Burigames/storynator/releases/latest','file:///tmp/x','https://github.com:444/Burigames/storynator/releases/latest']:assert not allowed_url(value)
    assert allowed_url(MANIFEST_URL) and allowed_url('https://release-assets.githubusercontent.com/signed.exe?token=example')

def test_installer_integrity_and_arguments(tmp_path):
    raw=b'MZ'+b'0'*126;path=tmp_path/'update.exe';path.write_bytes(raw);verify_installer(path,info(raw));appdir=tmp_path/'Program with spaces';appdir.mkdir();(appdir/'unins000.exe').write_bytes(b'original');args=installer_arguments(appdir/'Storynator.exe',tmp_path/'My Book.storynator');assert '/DIR='+str(appdir) in args and '/STORYNATORUPDATE=1' in args and any(x.startswith('/STORYNATORPROJECT=') for x in args);assert not any(x.startswith('/DIR=') for x in installer_arguments(tmp_path/'portable'/'Storynator.exe'))
    path.write_bytes(raw+b'x')
    with pytest.raises(ValueError):verify_installer(path,info(raw))
    path.write_bytes(b'MZ'+b'1'*126)
    with pytest.raises(ValueError):verify_installer(path,info(raw))

def test_handoff_saves_guard_once_and_preserves_work_on_failure(qt,tmp_path):
    raw=b'MZ'+b'0'*126;path=tmp_path/'setup.exe';path.write_bytes(raw);w=studio(tmp_path);w.p['documents'][0]['html']='<p>Unsaved words</p>';w.dirty=True;calls=[];w.guard=lambda:(calls.append('guard') or False);launched=[]
    assert not install_update(w,path,info(raw),lambda *a:launched.append(a));assert calls==['guard'] and not launched and not w._closing
    w.guard=lambda:(calls.append('guard') or True)
    with pytest.raises(OSError):install_update(w,path,info(raw),lambda *a:(False,0))
    assert not w._closing and w.dirty and not getattr(w,'_update_approved',False)
    old=len(calls);assert install_update(w,path,info(raw),lambda *a:(launched.append(a) or (True,123)));assert len(calls)==old+1 and w._closing and w._update_approved;assert w.backups.list(w.p['project_id']);assert 'Unsaved words' in w.backups.read(w.backups.list(w.p['project_id'])[0])['documents'][0]['html'];QApplication.processEvents()

class Reply(QObject):
    readyRead=Signal();finished=Signal()
    def __init__(self,url,data=b'',status=200,redirect=None):super().__init__();self.address=QUrl(url);self.data=data;self.status=status;self.redirect=redirect;self.aborted=False
    def setReadBufferSize(self,value):pass
    def bytesAvailable(self):return len(self.data)
    def read(self,n):out=self.data[:n];self.data=self.data[n:];return QByteArray(out)
    def readAll(self):return self.read(len(self.data))
    def attribute(self,key):
        if key==QNetworkRequest.HttpStatusCodeAttribute:return self.status
        if key==QNetworkRequest.RedirectionTargetAttribute:return QUrl(self.redirect) if self.redirect else None
    def url(self):return self.address
    def error(self):return QNetworkReply.OperationCanceledError if self.aborted else QNetworkReply.NoError
    def abort(self):
        if not self.aborted:self.aborted=True;self.finished.emit()
    def deliver(self):
        self.readyRead.emit()
        if not self.aborted:self.finished.emit()
class Manager:
    def __init__(self,responses):self.responses=list(responses);self.urls=[]
    def get(self,req):
        self.urls.append(req.url().toString());r=Reply(req.url().toString(),**self.responses.pop(0));QTimer.singleShot(0,r.deliver);return r

def run_download(qt,tmp_path,responses,raw,checksum=None,size=None,limit=1000):
    d=Download();d.manager=Manager(responses);path=tmp_path/'setup.exe';path.write_bytes(b'old file');results=[];errors=[];d.complete.connect(results.append);d.failed.connect(errors.append);d.start(MANIFEST_URL,limit,path,checksum,size)
    for _ in range(20):QApplication.processEvents()
    return d,path,results,errors

def test_download_streams_redirects_and_commits_only_verified_bytes(qt,tmp_path):
    raw=b'MZ'+b'1'*126;d,path,results,errors=run_download(qt,tmp_path,[dict(status=302,redirect='https://release-assets.githubusercontent.com/a'),dict(data=raw)],raw,hashlib.sha256(raw).hexdigest(),len(raw));assert not errors and results==[path] and path.read_bytes()==raw and len(d.manager.urls)==2

def test_download_rejects_hash_truncation_oversize_and_redirects(qt,tmp_path):
    raw=b'MZ'+b'1'*126
    for responses,checksum,size,limit in [([dict(data=raw)],'0'*64,len(raw),1000),([dict(data=raw)],None,len(raw)+1,1000),([dict(data=raw)],None,None,10),([dict(status=302,redirect='https://evil.example/a')],None,None,1000),([dict(status=500)],None,None,1000)]:
        d,path,results,errors=run_download(qt,tmp_path,responses,raw,checksum,size,limit);assert errors and not results and path.read_bytes()==b'old file';assert not d.timer.isActive() and not d.total_timer.isActive()

def test_cancel_keeps_existing_file_and_metadata_size_is_bounded(qt,tmp_path):
    d=Download();d.manager=Manager([dict(data=b'MZ'+b'x'*100)]);path=tmp_path/'old.exe';path.write_bytes(b'old');errors=[];d.failed.connect(errors.append);d.start(MANIFEST_URL,1000,path);d.cancel();QApplication.processEvents();assert path.read_bytes()==b'old' and errors
    with pytest.raises(ValueError):manifest(b'x'*65537)

def test_update_dialog_is_explicit_and_no_downgrade(qt,tmp_path,monkeypatch):
    from update_ui import UpdateDialog
    w=studio(tmp_path);d=UpdateDialog(w,auto_check=False);assert d.download.reply is None;d.phase='manifest';data=info();d.received(json.dumps(data).encode());assert '9.1.2' in d.status.text() and w.update_button.toolTip().endswith('9.1.2');same={**data,'release':current_version(),'url':'https://github.com/Burigames/storynator/releases/download/v'+current_version()+'/Storynator-Setup.exe'};d.received(json.dumps(same).encode());assert 'neuesten Stand' in d.status.text() and not d.install.isEnabled();d.reject();w.dirty=False;w.close()

def test_release_metadata_matches_installer(tmp_path):
    from scripts.make_update_manifest import make
    path=tmp_path/'Storynator-Setup.exe';raw=b'MZ'+b'3'*126;path.write_bytes(raw);data=make(path,'0.8.99');assert manifest(json.dumps(data).encode())==data and data['sha256']==hashlib.sha256(raw).hexdigest()

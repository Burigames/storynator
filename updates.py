"""User-initiated GitHub updates, streamed downloads and verified installer handoff."""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import QObject,Signal,QTimer,QUrl,QSaveFile,QIODevice,QProcess
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from versioning import current_version,version_tuple
MANIFEST_URL='https://github.com/Burigames/storynator/releases/latest/download/update.json'
MAX_INSTALLER=200*1024*1024

def allowed_url(value):
    try:
        u=urlparse(value)
        return u.scheme=='https' and not u.username and not u.password and u.port in [None,443] and not u.fragment and (u.hostname=='release-assets.githubusercontent.com' or u.hostname=='github.com' and u.path.startswith('/Burigames/storynator/releases/'))
    except (ValueError,TypeError):return False

def manifest(raw):
    if len(raw)>65536:raise ValueError('Updatebeschreibung ist zu groß.')
    data=json.loads(raw)
    if not isinstance(data,dict) or set(data)!={'format','version','release','url','sha256','size'} or data['format']!='storynator.update' or (type(data['version']) is not int or data['version']!=1):raise ValueError('Unbekanntes Updateformat.')
    version_tuple(data['release'])
    if data['release'].startswith('v'):raise ValueError('Ungültige Versionsnummer.')
    expected='https://github.com/Burigames/storynator/releases/download/v'+data['release']+'/Storynator-Setup.exe'
    if data['url']!=expected or not isinstance(data['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',data['sha256']) or type(data['size']) is not int or not 64<=data['size']<=MAX_INSTALLER:raise ValueError('Ungültige Updatequelle, Dateigröße oder Prüfsumme.')
    return data

def verify_installer(path,info):
    path=Path(path)
    if path.stat().st_size!=info['size']:raise ValueError('Der Update-Download ist unvollständig.')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        header=stream.read(64)
        if not header.startswith(b'MZ'):raise ValueError('Die Update-Datei ist kein Windows-Installer.')
        digest.update(header)
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    if digest.hexdigest()!=info['sha256']:raise ValueError('Die Update-Prüfsumme stimmt nicht. Die Datei wird nicht gestartet.')

def installer_arguments(executable,project_path=None):
    directory=Path(executable).resolve().parent
    args=['/SILENT','/NORESTART','/STORYNATORUPDATE=1']
    # Installed builds update in place. Portable copies install/update the registered application.
    if (directory/'unins000.exe').is_file():args.append('/DIR='+str(directory))
    if project_path:args.append('/STORYNATORPROJECT='+str(Path(project_path).resolve()))
    return args

def install_update(host,path,info,launcher=None,executable=None):
    if version_tuple(info['release'])<=version_tuple(current_version()):raise ValueError('Diese Version ist nicht neuer als die laufende Version.')
    verify_installer(path,info)
    host.flush_editors();host.record_writing_session();host.backup_pool.waitForDone();host.backups.create(host.p,host.path,'Vor Programmaktualisierung')
    if not host.guard():return False
    verify_installer(path,info)
    args=installer_arguments(executable or sys.executable,host.path)
    launch=launcher or QProcess.startDetached;result=launch(str(path),args,str(Path(path).parent));started=result[0] if isinstance(result,tuple) else bool(result)
    if not started:raise OSError('Der Update-Installer konnte nicht gestartet werden. Storynator bleibt geöffnet.')
    host._update_approved=True;host.close();return True

class Download(QObject):
    complete=Signal(object);failed=Signal(str);progress=Signal(int,int)
    def __init__(self,parent=None):
        super().__init__(parent);self.manager=QNetworkAccessManager(self);self.reply=None;self.file=None;self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout);self.total_timer=QTimer(self);self.total_timer.setSingleShot(True);self.total_timer.timeout.connect(self.timeout);self.cancelled=False;self.reason=''
    def start(self,url,limit=65536,path=None,checksum=None,expected_size=None):
        if self.reply:raise ValueError('Ein Download läuft bereits.')
        if not allowed_url(url):raise ValueError('Nicht erlaubte Updatequelle.')
        self.limit=limit;self.path=Path(path) if path else None;self.checksum=checksum;self.expected_size=expected_size;self.data=bytearray();self.hash=hashlib.sha256();self.received=0;self.redirects=0;self.cancelled=False;self.reason=''
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True);self.file=QSaveFile(str(self.path))
            if not self.file.open(QIODevice.WriteOnly):self.file=None;raise OSError('Update-Datei konnte nicht angelegt werden.')
        self.total_timer.start(600000 if path else 60000);self.request(url)
    def request(self,url):
        req=QNetworkRequest(QUrl(url));req.setAttribute(QNetworkRequest.RedirectPolicyAttribute,QNetworkRequest.ManualRedirectPolicy);req.setAttribute(QNetworkRequest.CacheLoadControlAttribute,QNetworkRequest.AlwaysNetwork);req.setRawHeader(b'User-Agent',('Storynator/'+current_version()).encode());req.setRawHeader(b'Cache-Control',b'no-cache');self.reply=self.manager.get(req);self.reply.setReadBufferSize(1024*1024);self.reply.readyRead.connect(self.read);self.reply.finished.connect(self.finish);self.timer.start(30000)
    def timeout(self):self.reason='Zeitüberschreitung beim Update-Download.';self.cancel()
    def cancel(self):
        self.cancelled=True
        if self.reply:self.reply.abort()
        else:self.cleanup()
    def cleanup(self):
        self.timer.stop();self.total_timer.stop()
        if self.file:self.file.cancelWriting();self.file=None
    def read(self):
        if not self.reply:return
        status=self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status!=200:self.reply.readAll();return
        while self.reply.bytesAvailable():
            chunk=bytes(self.reply.read(min(1024*1024,self.reply.bytesAvailable())))
            if not chunk:break
            self.received+=len(chunk)
            if self.received>self.limit or self.expected_size is not None and self.received>self.expected_size:self.reason='Update-Download ist größer als angekündigt.';self.reply.abort();return
            self.hash.update(chunk)
            if self.file:
                if self.file.write(chunk)!=len(chunk):self.reason='Update-Datei konnte nicht geschrieben werden.';self.reply.abort();return
            else:self.data.extend(chunk)
        self.timer.start(30000);self.progress.emit(self.received,self.expected_size or 0)
    def finish(self):
        reply=self.reply
        if reply is None:return
        reply.finished.disconnect(self.finish)
        if not self.reason and not self.cancelled:self.read()
        self.timer.stop();self.reply=None;status=reply.attribute(QNetworkRequest.HttpStatusCodeAttribute);redirect=reply.attribute(QNetworkRequest.RedirectionTargetAttribute);error=reply.error();reply.deleteLater()
        if self.cancelled or self.reason:self.cleanup();self.failed.emit(self.reason or 'Download abgebrochen.');return
        if status in [301,302,303,307,308] and redirect is not None:
            url=reply.url().resolved(redirect).toString();self.redirects+=1
            if self.redirects>5 or not allowed_url(url):self.cleanup();self.failed.emit('Die Updatequelle hat auf eine nicht erlaubte Adresse umgeleitet.');return
            self.request(url);return
        if error!=QNetworkReply.NoError or status!=200:self.cleanup();self.failed.emit('GitHub konnte nicht erreicht werden. Internetverbindung prüfen und erneut versuchen.');return
        if self.expected_size is not None and self.received!=self.expected_size:self.cleanup();self.failed.emit('Der Update-Download ist unvollständig.');return
        if self.checksum and self.hash.hexdigest()!=self.checksum:self.cleanup();self.failed.emit('Die Update-Prüfsumme stimmt nicht. Die Datei wird nicht gestartet.');return
        self.total_timer.stop()
        if self.file:
            if not self.file.commit():self.file=None;self.failed.emit('Update-Datei konnte nicht gespeichert werden.');return
            self.file=None;self.complete.emit(self.path)
        else:self.complete.emit(bytes(self.data))

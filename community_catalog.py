"""Opt-in GitHub catalog, async Qt requests, bounded responses and pinned digests."""
import hashlib,json,re
from urllib.parse import urlparse
from PySide6.QtCore import QObject,QUrl,QTimer,Signal
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
CATALOG='https://raw.githubusercontent.com/Burigames/storynator/main/community/catalog.json'
def catalog(raw):
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('format')!='storynator.catalog' or data.get('version')!=1 or not isinstance(data.get('packages'),list) or len(data['packages'])>1000:raise ValueError('Unbekannter Community-Katalog.')
    for item in data['packages']:
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in ['title','url','sha256','release','id','language','kind','license']):raise ValueError('Ungültiger Katalogeintrag.')
        url=urlparse(item['url'])
        if url.scheme!='https' or url.hostname!='raw.githubusercontent.com' or not url.path.startswith('/Burigames/storynator/') or url.username or url.password or url.port not in [None,443] or not re.fullmatch('[a-f0-9]{64}',item['sha256']):raise ValueError('Ungültige Paketquelle oder Prüfsumme.')
    return data['packages']
class Fetcher(QObject):
    complete=Signal(bytes);failed=Signal(str)
    def __init__(self,parent):super().__init__(parent);self.manager=QNetworkAccessManager(self);self.reply=None;self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout)
    def fetch(self,url,limit=2*1024*1024,checksum=None):
        if self.reply:raise ValueError('Ein Download läuft bereits.')
        req=QNetworkRequest(QUrl(url));req.setAttribute(QNetworkRequest.RedirectPolicyAttribute,QNetworkRequest.ManualRedirectPolicy);self.limit=limit;self.checksum=checksum;self.data=bytearray();self.reply=self.manager.get(req);self.reply.readyRead.connect(self.receive);self.reply.finished.connect(self.finished);self.timer.start(30000)
    def timeout(self):
        if self.reply:self.reply.abort()
    def receive(self):
        if not self.reply:return
        self.data.extend(bytes(self.reply.readAll()))
        if len(self.data)>self.limit:self.reply.abort()
    def finished(self):
        self.timer.stop();reply=self.reply
        if not reply:return
        self.receive();self.reply=None;status=reply.attribute(QNetworkRequest.HttpStatusCodeAttribute);error=reply.error();message=reply.errorString();reply.deleteLater();raw=bytes(self.data)
        if error!=QNetworkReply.NoError or status!=200:self.failed.emit('Download fehlgeschlagen: '+message);return
        if len(raw)>self.limit:self.failed.emit('Download zu groß.');return
        if self.checksum and hashlib.sha256(raw).hexdigest()!=self.checksum:self.failed.emit('Die Paket-Prüfsumme stimmt nicht.');return
        self.complete.emit(raw)
    def cancel(self):
        if self.reply:self.reply.abort()

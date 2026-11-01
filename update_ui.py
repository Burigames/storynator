import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QProgressBar
from design import label,primary,icon,CURRENT
from i18n import tr
from updates import Download,MANIFEST_URL,manifest,install_update,MAX_INSTALLER
from versioning import current_version,version_tuple
class UpdateDialog(QDialog):
    def __init__(self,host,auto_check=True):
        super().__init__(host);self.host=host;self.info=None;self.path=None;self.setWindowTitle(tr('Storynator aktualisieren'));self.resize(620,350);layout=QVBoxLayout(self);layout.addWidget(label(tr('Storynator aktuell halten'),'title'));layout.addWidget(label(tr('Installierte Version: ')+current_version()));notice=label(tr('Die Prüfung kontaktiert ausschließlich GitHub. Projektinhalte werden nicht übertragen.'));notice.setWordWrap(True);layout.addWidget(notice);self.status=label('');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status,1);self.progress=QProgressBar();self.progress.hide();layout.addWidget(self.progress);row=QHBoxLayout();self.check=QPushButton(tr('Erneut prüfen'));self.check.clicked.connect(self.check_now);row.addWidget(self.check);self.install=primary(tr('Update installieren'),self.install_now,'update');self.install.setEnabled(False);row.addWidget(self.install);self.close_button=QPushButton(tr('Schließen'));self.close_button.clicked.connect(self.reject);row.addWidget(self.close_button);layout.addLayout(row);self.download=Download(self);self.download.complete.connect(self.received);self.download.failed.connect(self.failed);self.download.progress.connect(self.on_progress);self.phase='';self._stopped=False
        if auto_check:self.check_now()
    def check_now(self):
        self.info=None;self.path=None;self.install.setEnabled(False);self.check.setEnabled(False);self.phase='manifest';self.status.setText(tr('Neueste GitHub-Version wird geprüft …'))
        try:self.download.start(MANIFEST_URL)
        except Exception as e:self.failed(str(e))
    def received(self,value):
        if self.phase=='manifest':
            try:
                self.info=manifest(value);self.check.setEnabled(True)
                if version_tuple(self.info['release'])<=version_tuple(current_version()):self.install.setEnabled(False);self.host.update_button.setIcon(icon('update'));self.status.setText(tr('Storynator ist auf dem neuesten Stand.'));self.host.update_button.setToolTip(tr('Keine neue Version verfügbar.'));return
                self.status.setText(tr('Neue Version verfügbar: ')+self.info['release']+'\n'+tr('Der Installer aktualisiert die vorhandene Installation. Vorher wird das Projekt gesichert.'));self.host.update_button.setIcon(icon('update',CURRENT['link']));self.host.update_button.setToolTip(tr('Neue Version verfügbar: ')+self.info['release']);self.install.setEnabled(sys.platform=='win32' and bool(getattr(sys,'frozen',False)))
                if self.install.isEnabled() and not (Path(sys.executable).resolve().parent/'unins000.exe').is_file():self.status.setText(self.status.text()+'\n'+tr('Die portable Ausgabe wechselt beim Update zur installierten Windows-Version.'))
                if not self.install.isEnabled():self.status.setText(self.status.text()+'\n'+tr('Die direkte Installation steht in der Windows-EXE zur Verfügung.'))
            except Exception as e:self.failed(str(e))
        else:
            self.path=Path(value);self.progress.hide();self.status.setText(tr('Download geprüft. Installation wird vorbereitet …'))
            try:
                if install_update(self.host,self.path,self.info):self.accept()
                else:self.status.setText(tr('Installation abgebrochen. Das Update kann erneut gestartet werden.'));self.install.setEnabled(True);self.check.setEnabled(True)
            except Exception as e:self.failed(str(e))
    def install_now(self):
        if not self.info:return
        try:
            if self.path:
                if install_update(self.host,self.path,self.info):self.accept()
                return
            self.phase='installer';self.install.setEnabled(False);self.check.setEnabled(False);self.progress.setRange(0,100);self.progress.setValue(0);self.progress.show();self.status.setText(tr('Update wird heruntergeladen …'));path=self.host.data_root/'updates'/('Storynator-'+self.info['release']+'-'+self.info['sha256'][:12]+'.exe');self.download.start(self.info['url'],MAX_INSTALLER,path,self.info['sha256'],self.info['size'])
        except Exception as e:self.failed(str(e))
    def on_progress(self,received,total):
        if total:self.progress.setValue(int(received*100/total))
    def failed(self,error):self.status.setText(tr(error));self.check.setEnabled(True);self.install.setEnabled(False);self.progress.hide()
    def done(self,result):
        if not self._stopped:
            self._stopped=True;self.download.complete.disconnect();self.download.failed.disconnect();self.download.cancel()
        super().done(result)
def show_updates(host):
    dialog=UpdateDialog(host);dialog.exec();dialog.deleteLater()

"""Project covers, backup history, integrity review and local safety preferences."""
import base64,copy,json,shutil
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt,QSignalBlocker
from PySide6.QtGui import QPixmap,QImage
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox,QFormLayout,QSpinBox,QTextBrowser,QCheckBox,QDialogButtonBox
from ui import RoomyList
from PySide6.QtWidgets import QListWidgetItem
from design import label,primary
from core import load_project,uid,objects
from safety import project_report,used_assets
from media import import_image,image_from_asset
from i18n import tr

class CoversDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.setWindowTitle(tr('Projekt & Buchcover'));self.resize(760,580);layout=QVBoxLayout(self);layout.addWidget(label(tr('Cover werden nur im PDF ausgegeben, niemals beim Drucken.')));cards=QHBoxLayout();layout.addLayout(cards);draft=copy.deepcopy(host.p.get('covers',{'project':'','book':''}));assets={};self.draft=draft
        for kind,title in [('project','Projektcover'),('book','Buchcover')]:
            box=QVBoxLayout();box.addWidget(label(tr(title),'title'));preview=QLabel();preview.setAlignment(Qt.AlignCenter);preview.setMinimumSize(240,290);box.addWidget(preview,1)
            def refresh(k=kind,view=preview):
                image=image_from_asset(host.p,draft.get(k,''),330);view.setPixmap(QPixmap.fromImage(image));view.setText(tr('Kein Cover') if image.isNull() else '')
            def choose(checked=False,k=kind,refresh=refresh):
                path,_=QFileDialog.getOpenFileName(self,tr('Cover auswählen'),'','Bilder (*.png *.jpg *.jpeg *.webp *.bmp)')
                if path:
                    try:
                        key=import_image(host.p,path);draft[k]=key;refresh()
                    except (OSError,ValueError) as e:host.error(e)
            box.addWidget(primary(tr('Bild auswählen'),choose,'image'));remove=QPushButton(tr('Entfernen'));remove.clicked.connect(lambda checked=False,k=kind,refresh=refresh:(draft.update({k:''}),refresh()));box.addWidget(remove);cards.addLayout(box);refresh()
        notice=label(tr('Im PDF-Dialog lassen sich Projekt- und Buchcover getrennt ein- oder ausschalten. Sind beide gewählt, erscheint zuerst das Projektcover.'));notice.setWordWrap(True);layout.addWidget(notice)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(lambda:(host.p.update(covers=draft),host.changed(),self.accept()));buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        # Imports are staged in the project assets; rejected, unreferenced additions are removed.
        original=set(host.p['assets'])
        self.rejected.connect(lambda:[host.p['assets'].pop(key,None) for key in list(host.p['assets']) if key not in original and key not in used_assets(host.p)])

class BackupDialog(QDialog):
    def __init__(self,host,startup=False):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Sicherungen & Wiederherstellung'));self.resize(850,650);layout=QVBoxLayout(self);notice=label(tr('Wiederherstellen öffnet eine Kopie. Die ursprüngliche Projektdatei wird nicht überschrieben.'));notice.setWordWrap(True);layout.addWidget(notice);self.all=QCheckBox(tr('Alle Projekte anzeigen'));self.all.setChecked(startup);layout.addWidget(self.all);self.list=RoomyList();layout.addWidget(self.list,1);self.preview=QTextBrowser();self.preview.setMinimumHeight(165);layout.addWidget(self.preview);self.cover=QLabel();self.cover.setMaximumHeight(110);layout.addWidget(self.cover);row=QHBoxLayout();row.addWidget(primary(tr('Als Kopie wiederherstellen'),self.restore));manual=QPushButton(tr('Jetzt sichern'));manual.clicked.connect(self.snapshot);row.addWidget(manual);export=QPushButton(tr('Sicherung exportieren'));export.clicked.connect(self.export);row.addWidget(export);close=QPushButton(tr('Schließen'));close.clicked.connect(self.accept);row.addWidget(close);layout.addLayout(row);self.list.currentRowChanged.connect(self.selection);self.all.toggled.connect(self.refresh);self.refresh()
    def refresh(self):
        self.items=self.host.backups.list(None if self.all.isChecked() else self.host.p['project_id']);self.list.clear()
        for meta in self.items:
            time=datetime.fromisoformat(meta['time']).astimezone().strftime('%d.%m.%Y %H:%M:%S');item=QListWidgetItem(time+' · '+meta['name']+' · '+tr(meta['reason']));self.list.addItem(item)
        if self.items:self.list.setCurrentRow(0)
    def snapshot(self):
        try:self.host.flush_editors();self.host.backups.create(self.host.p,self.host.path,'Manuell');self.refresh()
        except Exception as error:self.host.error(error)
    def selected(self):return self.items[self.list.currentRow()] if 0<=self.list.currentRow()<len(self.items) else None
    def selection(self,*args):
        meta=self.selected();self.preview.clear();self.cover.clear()
        if not meta:return
        try:
            p=self.host.backups.preview(meta);import html,re
            snippets=''.join('<p><b>'+html.escape(o['name'])+'</b><br>'+html.escape(re.sub('<[^>]*>',' ',o.get('html',''))[:200])+'</p>' for o in p['documents'][:3]);self.preview.setHtml('<b>'+html.escape(p['name'])+'</b><p>'+str(len(p['documents']))+' '+tr('Kapitel')+' · '+str(len(p['entries']))+' '+tr('Einträge')+' · '+str(len(p['events']))+' '+tr('Ereignisse')+'</p>'+snippets);self.cover.setPixmap(QPixmap.fromImage(image_from_asset(p,p['covers'].get('book') or p['covers'].get('project'),100)))
        except Exception as error:self.preview.setPlainText(tr(str(error)))
    def restore(self):
        meta=self.selected()
        if not meta:return
        try:
            p=self.host.backups.read(meta)
            if not self.host.guard():return
            if self.host.dirty:self.host.backups.create(self.host.p,self.host.path,'Vor Wiederherstellung')
            p['project_id']=uid();self.host.adopt_project(p,None);self.host.changed();self.accept()
        except Exception as error:self.host.error(error)
    def export(self):
        meta=self.selected()
        if not meta:return
        try:
            self.host.backups.read(meta);path,_=QFileDialog.getSaveFileName(self,tr('Sicherung exportieren'),meta['name']+'.storynator','Storynator (*.storynator)')
            if path:
                if not path.lower().endswith('.storynator'):path+='.storynator'
                if Path(path).exists():raise ValueError('Zum Schutz vorhandener Projekte bitte einen neuen Dateinamen wählen.')
                shutil.copyfile(meta['path'],path)
        except Exception as error:self.host.error(error)

class IntegrityDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Projekt prüfen & bereinigen'));self.resize(820,610);layout=QVBoxLayout(self);notice=label(tr('Verweise und Ressourcen werden geprüft. Inhalte werden nur nach Auswahl und Bestätigung entfernt. Vor dem Bereinigen wird eine Sicherung erstellt.'));notice.setWordWrap(True);layout.addWidget(notice);self.list=RoomyList();layout.addWidget(self.list,1);row=QHBoxLayout();check=QPushButton(tr('Erneut prüfen'));check.clicked.connect(self.refresh);row.addWidget(check);clean=QPushButton(tr('Ausgewählte unbenutzte Ressourcen löschen'));clean.clicked.connect(self.clean);row.addWidget(clean);open=QPushButton(tr('Eintrag öffnen'));open.clicked.connect(self.open);row.addWidget(open);layout.addLayout(row);self.refresh()
    def refresh(self):
        self.issues=project_report(self.host.p,lambda data:not QImage.fromData(data).isNull());self.list.clear()
        for issue in self.issues:
            item=QListWidgetItem(tr(issue['kind'])+' · '+issue['name']+' · '+issue['detail']);self.list.addItem(item)
            if issue['kind']=='Unbenutzte Ressource':item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);item.setIcon(__import__('PySide6.QtGui',fromlist=['QIcon']).QIcon(QPixmap.fromImage(image_from_asset(self.host.p,issue['detail'],60))))
        if not self.issues:self.list.addItem(tr('Keine Probleme gefunden.'))
    def open(self):
        row=self.list.currentRow()
        if 0<=row<len(self.issues) and self.issues[row].get('id'):
            self.host.open_object(self.issues[row]['id']);self.accept()
    def clean(self):
        keys=[issue['detail'] for i,issue in enumerate(self.issues) if issue['kind']=='Unbenutzte Ressource' and self.list.item(i).checkState()==Qt.Checked]
        if not keys:return
        if QMessageBox.question(self,tr('Ressourcen bereinigen'),str(len(keys))+' '+tr('ausgewählte Ressourcen löschen?'))!=QMessageBox.Yes:return
        try:
            self.host.backups.create(self.host.p,self.host.path,'Vor Bereinigung');used=used_assets(self.host.p)
            for key in keys:
                if key not in used:self.host.p['assets'].pop(key,None)
            self.host.changed();self.refresh()
        except Exception as error:self.host.error(error)

def backup_preferences(host):
    d=QDialog(host);d.setWindowTitle(tr('Sicherungseinstellungen'));form=QFormLayout(d);interval=QSpinBox();interval.setRange(15,3600);interval.setValue(int(host.settings.value('backup/interval',60)));keep=QSpinBox();keep.setRange(3,200);keep.setValue(int(host.settings.value('backup/keep',20)));form.addRow(tr('Intervall in Sekunden'),interval);form.addRow(tr('Sicherungsstände pro Projekt'),keep);notice=label(tr('Sicherungen liegen lokal im Anwendungsdatenordner. Aufbewahrung wird beim nächsten Sicherungslauf angewendet.'));notice.setWordWrap(True);form.addRow(notice)
    def apply():host.settings.setValue('backup/interval',interval.value());host.settings.setValue('backup/keep',keep.value());host.timer.setInterval(interval.value()*1000);host.backups.keep=keep.value();d.accept()
    form.addRow(primary(tr('Übernehmen'),apply));d.resize(520,260);d.exec()

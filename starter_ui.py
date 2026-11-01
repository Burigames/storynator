from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QPushButton,QTextEdit,QFileDialog,QListWidgetItem
from ui import RoomyList
from design import label,primary
from i18n import tr
import community,starters
class StarterDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.project=None;self.library=community.Library(host.data_root/'community');self.setWindowTitle(tr('Neues Projekt'));self.resize(840,650);layout=QVBoxLayout(self);layout.addWidget(label(tr('Deine nächste Geschichte'),'title'));self.name=QLineEdit(tr('Meine Geschichte'));self.name.setAccessibleName(tr('Projektname'));layout.addWidget(self.name);self.list=RoomyList();layout.addWidget(self.list,1);self.preview=QTextEdit();self.preview.setReadOnly(True);layout.addWidget(self.preview,1);row=QHBoxLayout();row.addWidget(primary(tr('Projekt erstellen'),self.create,'plus'));b=QPushButton(tr('Projektstarter importieren'));b.clicked.connect(self.import_file);row.addWidget(b);cancel=QPushButton(tr('Abbrechen'));cancel.clicked.connect(self.reject);row.addWidget(cancel);layout.addLayout(row);self.list.currentRowChanged.connect(self.selection);self.refresh()
    def refresh(self,selected=None):
        self.specs=[None]+starters.builtin_starters()+[s for _,s in self.library.items() if s['kind'] in ['starter','challenge']];self.list.clear()
        for spec in self.specs:self.list.addItem(tr('Leeres Projekt') if spec is None else spec['metadata']['title']+' · '+spec['metadata']['release'])
        row=next((i for i,s in enumerate(self.specs) if s is not None and selected and community.digest(s)==community.digest(selected)),0);self.list.setCurrentRow(row)
    def selection(self,*_):
        index=self.list.currentRow();spec=self.specs[index] if index>=0 else None;self.preview.setPlainText(community.summary(spec) if spec else tr('Ein leeres Projekt mit einem ersten Kapitel.'))
    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,tr('Projektstarter importieren'),'','Storynator (*.storynator-pack)')
        if not path:return
        try:
            spec=community.load(path)
            if spec['kind'] not in ['starter','challenge']:raise ValueError('Diese Datei ist kein Projekt-Starter.')
            from community_ui import PreviewDialog
            if PreviewDialog(self,spec).exec()==QDialog.Accepted:self.library.install(spec);self.refresh(spec)
        except Exception as e:self.host.error(e)
    def create(self):
        try:
            index=self.list.currentRow()
            if index<0:return
            spec=self.specs[index]
            if spec:self.project=starters.instantiate(spec,self.name.text())
            else:
                if not self.name.text().strip():raise ValueError('Projektname fehlt.')
                from app import project_for_language
                self.project=project_for_language(self.name.text().strip())
            self.accept()
        except Exception as e:self.host.error(e)

from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QCheckBox,QFileDialog,QTextEdit
from ui import RoomyList
from design import label
from i18n import tr
from docx_import import read_docx

def import_docx(host):
    path,_=QFileDialog.getOpenFileName(host,tr('DOCX importieren'),'','Word (*.docx)')
    if not path:return
    d=QDialog(host);d.setWindowTitle(tr('DOCX importieren'));d.resize(800,650);box=QVBoxLayout(d);box.addWidget(label(Path(path).name));split=QCheckBox(tr('An Überschrift 1 in Kapitel aufteilen'));split.setChecked(True);box.addWidget(split);items=RoomyList();box.addWidget(items,1);notice=QTextEdit();notice.setReadOnly(True);box.addWidget(notice,1);result={};row=QHBoxLayout();button=QPushButton(tr('Kapitel importieren'));row.addWidget(button);cancel=QPushButton(tr('Abbrechen'));cancel.clicked.connect(d.reject);row.addWidget(cancel);box.addLayout(row)
    def preview():
        nonlocal result
        try:
            result=read_docx(path,split.isChecked());items.clear();items.addItems([o['name'] for o in result['documents']]);notice.setPlainText('\n'.join([str(len(result['assets']))+' '+tr('eingebettete Bilder'),tr('Das Layout kann vom Original abweichen.'),*map(tr,result['warnings'])]));button.setEnabled(True)
        except Exception as e:result={};button.setEnabled(False);host.error(e)
    def apply():
        try:
            if not result:return
            host.flush_editors();host.backups.create(host.p,host.path,'Vor DOCX-Import');host.p['documents'].extend(result['documents']);host.p['assets'].update(result['assets']);host.changed();host.refresh();host.open_object(result['documents'][0]['id']);d.accept()
        except Exception as e:host.error(e)
    split.toggled.connect(preview);button.clicked.connect(apply);d.finished.connect(lambda *_:result.clear());preview();d.exec();d.deleteLater()

from pathlib import Path
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox,QInputDialog,QListWidgetItem
from ui import RoomyList
from design import label,primary
from i18n import tr
import addons

class AddonManager(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Addons'));self.resize(760,540);layout=QVBoxLayout(self);layout.setContentsMargins(26,24,26,24);layout.setSpacing(16);layout.addWidget(label(tr('Vorlagen für deine Welt'),'title'));notice=label(tr('Addons enthalten ausschließlich Kategorien und Feldvorlagen. Sie erstellen niemals Einträge.'));notice.setWordWrap(True);layout.addWidget(notice);self.list=RoomyList();layout.addWidget(self.list,1);self.description=QLabel();self.description.setWordWrap(True);layout.addWidget(self.description);row=QHBoxLayout();row.addWidget(primary(tr('Hinzufügen'),self.import_file,'plus'));self.toggle=QPushButton(tr('Aktivieren'));self.toggle.clicked.connect(self.toggle_current);row.addWidget(self.toggle);remove=QPushButton(tr('Löschen'));remove.clicked.connect(self.remove_current);row.addWidget(remove);layout.addLayout(row);row=QHBoxLayout();export=QPushButton(tr('Eigene Kategorien exportieren'));export.clicked.connect(lambda:export_preset(host));row.addWidget(export);reset=QPushButton(tr('Integriertes Preset wiederherstellen'));reset.clicked.connect(self.restore_builtin);row.addWidget(reset);layout.addLayout(row);self.list.currentRowChanged.connect(self.selection);self.refresh()
    def refresh(self):
        old=self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None;self.specs=addons.library(self.host.settings,self.host.p);self.list.clear()
        for spec in self.specs:
            state=addons.state_for(self.host.p,spec['id']);enabled=state and state['enabled'];text=spec['name']+'  ·  '+tr('Aktiv' if enabled else 'Inaktiv')+'  ·  '+str(len(spec['categories']))+' '+tr('Kategorien');item=QListWidgetItem(text);item.setData(Qt.UserRole,spec['id']);self.list.addItem(item)
            if spec['id']==old:self.list.setCurrentItem(item)
        if self.list.currentRow()<0 and self.list.count():self.list.setCurrentRow(0)
        self.selection()
    def current_spec(self):
        item=self.list.currentItem();return next((s for s in self.specs if item and s['id']==item.data(Qt.UserRole)),None)
    def selection(self,*args):
        spec=self.current_spec()
        if not spec:self.description.setText('');self.toggle.setEnabled(False);return
        state=addons.state_for(self.host.p,spec['id']);self.toggle.setEnabled(True);self.toggle.setText(tr('Deaktivieren' if state and state['enabled'] else 'Aktivieren'));self.description.setText(spec.get('description','')+'\n'+', '.join(c['name'] for c in spec['categories']))
    def toggle_current(self):
        spec=self.current_spec()
        if not spec:return
        state=addons.state_for(self.host.p,spec['id'])
        if state and state['enabled']:addons.disable(self.host.p,spec['id'])
        else:addons.enable(self.host.p,spec)
        self.host.changed();self.host.refresh()
        if getattr(self.host.tabs.currentWidget(),'world_page',False):self.host.show_world()
        self.refresh()
    def import_file(self,path=None):
        if not isinstance(path,str):path=QFileDialog.getOpenFileName(self,tr('Preset hinzufügen'),'','Storynator Preset (*.storynator-preset *.json)')[0]
        if not path:return
        try:addons.import_preset(self.host.settings,addons.load(path));self.refresh()
        except (ValueError,OSError) as error:self.host.error(error)
    def remove_current(self):
        spec=self.current_spec()
        if not spec:return
        message=tr('Addon löschen? Bereits erstellte Welt-Einträge und benötigte Kategorien bleiben erhalten.')
        if QMessageBox.question(self,tr('Addon löschen'),message)!=QMessageBox.Yes:return
        addons.remove(self.host.p,self.host.settings,spec['id']);self.host.changed();self.host.refresh()
        if getattr(self.host.tabs.currentWidget(),'world_page',False):self.host.show_world()
        self.refresh()
    def restore_builtin(self):
        hidden=self.host.settings.value('addons/hidden',[],type=list);self.host.settings.setValue('addons/hidden',[id for id in hidden if id!=addons.BUILTIN['id']]);self.refresh()

def export_preset(host):
    d=QDialog(host);d.setWindowTitle(tr('Kategorien als Preset exportieren'));d.resize(600,500);layout=QVBoxLayout(d);text=label(tr('Nur Kategorievorlagen werden exportiert. Verknüpfte Quellkategorien werden mit aufgenommen, Einträge und Bilder niemals.'));text.setWordWrap(True);layout.addWidget(text);ls=RoomyList();layout.addWidget(ls)
    for cat in host.p['categories']:
        item=QListWidgetItem(cat['name']);item.setData(Qt.UserRole,cat['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked if cat.get('source_addon') else Qt.Checked);ls.addItem(item)
    def save():
        ids=[ls.item(i).data(Qt.UserRole) for i in range(ls.count()) if ls.item(i).checkState()==Qt.Checked];name,ok=QInputDialog.getText(d,tr('Preset-Name'),tr('Name:'),text=host.p['name']+' · '+tr('Kategorien'))
        if not ok:return
        try:
            spec=addons.export(host.p,ids,name);path,_=QFileDialog.getSaveFileName(d,tr('Preset speichern'),name+'.storynator-preset','Storynator Preset (*.storynator-preset)')
            if path:
                if not path.endswith('.storynator-preset'):path+='.storynator-preset'
                Path(path).write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8');d.accept()
        except (ValueError,OSError) as error:host.error(error)
    layout.addWidget(primary(tr('Exportieren'),save,'save'));d.exec()

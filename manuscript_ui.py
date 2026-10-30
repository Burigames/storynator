"""Manuscript organization, revision tools, notes and writing goals."""
import copy,json,time
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QTextDocument,QTextCursor,QColor
from PySide6.QtWidgets import *
from ui import RoomyTree,RoomyList,RoomyTable,ArrowCombo as QComboBox,ArrowSpin as QSpinBox
from core import uid,resolve
from authoring import *
from design import label,primary
from i18n import tr

class ManuscriptTree(RoomyTree):
    def __init__(self,host):super().__init__();self.host=host;self.setDragDropMode(QAbstractItemView.InternalMove);self.setDefaultDropAction(Qt.MoveAction)
    def dropEvent(self,event):
        selected=self.currentItem();target=self.itemAt(event.position().toPoint());ids={o['id'] for o in self.host.p['documents']}
        if not selected or selected.data(0,Qt.UserRole) not in ids:event.ignore();return
        ancestor=target
        while ancestor and ancestor.parent():ancestor=ancestor.parent()
        if ancestor is not self.topLevelItem(0):event.ignore();return
        super().dropEvent(event)
        try:
            rows=[]
            def scan(parent,parent_id=None):
                for i in range(parent.childCount()):
                    item=parent.child(i);id=item.data(0,Qt.UserRole);rows.append((id,parent_id));scan(item,id)
            scan(self.topLevelItem(0));set_structure(self.host.p,rows);self.host.changed()
        except ValueError as e:self.host.error(e)
        self.host.refresh()

def current_doc(host):
    obj=host.current()
    return obj if obj and any(o['id']==obj['id'] for o in host.p['documents']) else next(iter(ordered_documents(host.p)),None)

def reload_documents(host,ids):
    active=host.current();active_id=active['id'] if active else None;positions={}
    for i in reversed(range(host.tabs.count())):
        page=host.tabs.widget(i)
        if getattr(page,'obj',{}).get('id') in ids:
            editor=page.findChild(__import__('app').Rich)
            if editor:positions[page.obj['id']]=editor.textCursor().position()
            host.tabs.removeTab(i)
    host.refresh()
    for id,position in positions.items():
        host.open_object(id);editor=host.editor()
        if editor:
            cursor=editor.textCursor();cursor.setPosition(min(position,editor.document().characterCount()-1));editor.setTextCursor(cursor)
    if active_id and resolve(host.p,active_id):host.open_object(active_id)

class StructureDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Manuskriptstruktur & Status'));self.resize(820,600);layout=QVBoxLayout(self);notice=label(tr('Teile, Kapitel und Szenen ziehen, umbenennen und verschachteln. Änderungen werden mit Übernehmen gespeichert.'));notice.setWordWrap(True);layout.addWidget(notice);self.tree=RoomyTree();self.tree.setColumnCount(4);self.tree.setHeaderLabels([tr('Name'),tr('Art'),tr('Status'),tr('Wörter')]);self.tree.setDragDropMode(QAbstractItemView.InternalMove);self.tree.setDefaultDropAction(Qt.MoveAction);layout.addWidget(self.tree,1);self.items={}
        for doc in ordered_documents(host.p):
            item=QTreeWidgetItem([doc['name'],'','',str(words(doc['html']))]);item.setData(0,Qt.UserRole,doc['id']);item.setFlags(item.flags()|Qt.ItemIsEditable);parent=self.items.get(doc.get('parent'));parent.addChild(item) if parent else self.tree.addTopLevelItem(item);self.items[doc['id']]=item
            for col,options,value in [(1,KINDS,doc.get('kind','chapter')),(2,STATUSES,doc.get('status','draft'))]:
                combo=QComboBox()
                for key,text in options.items():combo.addItem(tr(text),key)
                combo.setCurrentIndex(max(0,combo.findData(value)));item.setData(col,Qt.UserRole+1,value);combo.currentIndexChanged.connect(lambda _,item=item,col=col,combo=combo:item.setData(col,Qt.UserRole+1,combo.currentData()));self.tree.setItemWidget(item,col,combo)
        self.tree.expandAll();self.tree.header().setSectionResizeMode(0,QHeaderView.Stretch);self.tree.setColumnWidth(1,145);self.tree.setColumnWidth(2,170);self.tree.setColumnWidth(3,85);self.tree.model().rowsInserted.connect(lambda *args:QTimer.singleShot(0,self.restore_controls));buttons=QDialogButtonBox(QDialogButtonBox.Apply|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def restore_controls(self):
        def visit(parent):
            for i in range(parent.childCount()):
                item=parent.child(i)
                for col,options in [(1,KINDS),(2,STATUSES)]:
                    if self.tree.itemWidget(item,col):continue
                    combo=QComboBox()
                    for key,text in options.items():combo.addItem(tr(text),key)
                    combo.setCurrentIndex(max(0,combo.findData(item.data(col,Qt.UserRole+1))));combo.currentIndexChanged.connect(lambda _,item=item,col=col,combo=combo:item.setData(col,Qt.UserRole+1,combo.currentData()));self.tree.setItemWidget(item,col,combo)
                visit(item)
        visit(self.tree.invisibleRootItem())
    def apply(self):
        host=self.host;lookup={d['id']:d for d in host.p['documents']};draft={id:dict(doc) for id,doc in lookup.items()};rows=[]
        def visit(parent,parent_id=None):
            for i in range(parent.childCount()):
                item=parent.child(i);id=item.data(0,Qt.UserRole);name=item.text(0).strip()
                if not name:raise ValueError('Name fehlt.')
                draft[id].update(name=name,kind=self.tree.itemWidget(item,1).currentData() if self.tree.itemWidget(item,1) else item.data(1,Qt.UserRole+1),status=self.tree.itemWidget(item,2).currentData() if self.tree.itemWidget(item,2) else item.data(2,Qt.UserRole+1));rows.append((id,parent_id));visit(item,id)
        try:
            visit(self.tree.invisibleRootItem());trial={'documents':list(draft.values())};set_structure(trial,rows)
            for doc in trial['documents']:lookup[doc['id']].update({key:doc[key] for key in ['name','kind','status','parent']})
            host.p['documents']=[lookup[id] for id,parent in rows];host.changed();host.refresh();host.refresh_open_views();self.accept()
        except ValueError as e:host.error(e)

class ReplaceDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Suchen & Ersetzen'));self.resize(720,550);layout=QVBoxLayout(self);form=QFormLayout();self.query=QLineEdit();self.replacement=QLineEdit();self.scope=QComboBox();self.scope.addItem(tr('Aktuelles Kapitel'),'current');self.scope.addItem(tr('Gesamtes Manuskript'),'all');self.case=QCheckBox(tr('Groß-/Kleinschreibung'));self.whole=QCheckBox(tr('Ganze Wörter'));form.addRow(tr('Suchen'),self.query);form.addRow(tr('Ersetzen durch'),self.replacement);form.addRow(tr('Bereich'),self.scope);form.addRow(self.case);form.addRow(self.whole);layout.addLayout(form);self.list=RoomyList();layout.addWidget(self.list,1);layout.addWidget(label(tr('Verknüpfte Namen werden übersprungen. Ziele im Welt-Bereich umbenennen.')));row=QHBoxLayout();preview=QPushButton(tr('Treffer prüfen'));preview.clicked.connect(self.preview);row.addWidget(preview);row.addWidget(primary(tr('Alle ersetzen'),self.replace));layout.addLayout(row)
    def docs(self):
        self.host.flush_editors();doc=current_doc(self.host);return ordered_documents(self.host.p) if self.scope.currentData()=='all' else [doc] if doc else []
    def preview(self):
        self.list.clear()
        for id,count in replacement_preview(self.docs(),self.query.text(),self.case.isChecked(),self.whole.isChecked()):self.list.addItem((resolve(self.host.p,id) or {})['name']+' · '+str(count)+' '+tr('Treffer'))
    def replace(self):
        try:
            docs=self.docs();preview=replacement_preview(docs,self.query.text(),self.case.isChecked(),self.whole.isChecked());count=sum(n for id,n in preview)
            if not count:return
            if QMessageBox.question(self,tr('Ersetzen bestätigen'),str(count)+' '+tr('Treffer ersetzen? Vorher werden Kapitelstände angelegt.'))!=QMessageBox.Yes:return
            ids=[id for id,n in preview];replace_all(docs,self.query.text(),self.replacement.text(),self.case.isChecked(),self.whole.isChecked());self.host.changed();reload_documents(self.host,ids);self.preview()
        except ValueError as e:self.host.error(e)

class NotesDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.doc=current_doc(host);self.setWindowTitle(tr('Kommentare & Lesezeichen'));self.resize(730,540);layout=QVBoxLayout(self);self.list=RoomyList();layout.addWidget(self.list,1);row=QHBoxLayout()
        for text,fn in [('Kommentar hinzufügen',lambda:self.add('comment')),('Lesezeichen hinzufügen',lambda:self.add('bookmark')),('Zur Stelle',self.jump),('Bearbeiten',self.edit),('Erledigt / offen',self.resolve),('Löschen',self.remove)]:b=QPushButton(tr(text));b.clicked.connect(fn);row.addWidget(b)
        layout.addLayout(row);self.list.itemActivated.connect(self.jump);self.refresh()
    def editor(self):
        if not self.doc:return None
        self.host.open_object(self.doc['id']);return self.host.editor()
    def refresh(self):
        self.list.clear()
        if not self.doc:return
        self.host.flush_editors()
        for note in self.doc.get('annotations',[]):
            text=('✓ ' if note.get('resolved') else '')+tr('Kommentar' if note['kind']=='comment' else 'Lesezeichen')+' · '+note['text']+(' · '+tr('Textstelle entfernt') if note.get('detached') else '');item=QListWidgetItem(text);item.setData(Qt.UserRole,note['id']);item.setToolTip(note.get('quote',''));self.list.addItem(item)
    def selected(self):return next((n for n in (self.doc or {}).get('annotations',[]) if self.list.currentItem() and n['id']==self.list.currentItem().data(Qt.UserRole)),None)
    def add(self,kind):
        editor=self.editor()
        if not editor:return
        text,ok=QInputDialog.getMultiLineText(self,tr('Kommentar' if kind=='comment' else 'Lesezeichen'),tr('Text'))
        if not ok or not text.strip():return
        cursor=editor.textCursor();self.doc.setdefault('annotations',[]).append(dict(id=uid(),kind=kind,text=text.strip(),start=cursor.selectionStart(),end=cursor.selectionEnd(),quote=cursor.selectedText(),resolved=False));editor.reload_annotations();self.host.changed();self.refresh()
    def jump(self,*args):
        note=self.selected();editor=self.editor()
        if not note or not editor:return
        cursor=QTextCursor(editor.document());last=editor.document().characterCount()-1;cursor.setPosition(min(last,note['start']));cursor.setPosition(min(last,note['end']),QTextCursor.KeepAnchor);editor.setTextCursor(cursor);editor.ensureCursorVisible();self.accept();editor.setFocus()
    def edit(self):
        note=self.selected()
        if not note:return
        text,ok=QInputDialog.getMultiLineText(self,tr('Bearbeiten'),tr('Text'),note['text'])
        if ok:note['text']=text;self.host.changed();self.refresh()
    def resolve(self):
        note=self.selected()
        if note:note['resolved']=not note.get('resolved');self.host.changed();self.refresh()
    def remove(self):
        note=self.selected()
        if note and QMessageBox.question(self,tr('Löschen'),tr('Notiz löschen?'))==QMessageBox.Yes:self.doc['annotations'].remove(note);self.editor().reload_annotations();self.host.changed();self.refresh()

class RevisionsDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.doc=current_doc(host);self.setWindowTitle(tr('Kapitelstände'));self.resize(760,600);layout=QVBoxLayout(self);self.list=RoomyList();layout.addWidget(self.list,1);self.preview=QTextBrowser();layout.addWidget(self.preview,1);row=QHBoxLayout()
        for text,callback in [('Stand anlegen',self.create),('Wiederherstellen',self.restore),('Stand löschen',self.remove)]:button=QPushButton(tr(text));button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.list.currentRowChanged.connect(self.selection);self.refresh()
    def refresh(self):
        self.list.clear()
        for item in reversed((self.doc or {}).get('history',[])):
            row=QListWidgetItem((tr(item['name']) if item.get('automatic') else item['name'])+' · '+datetime.fromisoformat(item['time']).astimezone().strftime('%d.%m.%Y %H:%M:%S'));row.setData(Qt.UserRole,item['id']);self.list.addItem(row)
        if self.list.count():self.list.setCurrentRow(0)
    def selected(self):return next((x for x in (self.doc or {}).get('history',[]) if self.list.currentItem() and x['id']==self.list.currentItem().data(Qt.UserRole)),None)
    def selection(self,*args):
        item=self.selected();self.preview.setPlainText(plain(item['content']['html']) if item else '')
    def create(self):
        if not self.doc:return
        self.host.flush_editors();name,ok=QInputDialog.getText(self,tr('Stand anlegen'),tr('Name:'))
        if ok and name.strip():snapshot(self.doc,name);self.host.changed();self.refresh()
    def remove(self):
        item=self.selected()
        if item and QMessageBox.question(self,tr('Stand löschen'),tr('Diesen Kapitelstand dauerhaft entfernen?'))==QMessageBox.Yes:self.doc['history'].remove(item);self.host.changed();self.refresh()
    def restore(self):
        item=self.selected()
        if not item:return
        if QMessageBox.question(self,tr('Wiederherstellen'),tr('Kapitelstand wiederherstellen? Der aktuelle Stand wird vorher gesichert.'))!=QMessageBox.Yes:return
        self.host.flush_editors();restore_snapshot(self.doc,item['id']);self.host.changed();reload_documents(self.host,[self.doc['id']]);self.refresh()

class GoalsDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);host.flush_editors();host.record_writing_session();self.setWindowTitle(tr('Schreibziele & Statistik'));self.resize(650,550);layout=QVBoxLayout(self);form=QFormLayout();goal=host.p.get('writing_goals',{});total=QSpinBox();total.setRange(0,10000000);total.setValue(goal.get('total',0));daily=QSpinBox();daily.setRange(0,1000000);daily.setValue(goal.get('daily',0));track=QCheckBox(tr('Schreibsitzungen lokal im Projekt erfassen'));track.setChecked(goal.get('track',False));form.addRow(tr('Projektziel in Wörtern · 0 = aus'),total);form.addRow(tr('Tagesziel in Wörtern · 0 = aus'),daily);form.addRow(track);layout.addLayout(form);count=sum(words(d['html']) for d in host.p['documents']);layout.addWidget(label(str(count)+' '+tr('Wörter im Projekt'),'title'));progress=QProgressBar();progress.setRange(0,max(1,total.value()));progress.setValue(min(count,progress.maximum()));progress.setVisible(total.value()>0);total.valueChanged.connect(lambda value:(progress.setVisible(value>0),progress.setMaximum(max(1,value)),progress.setValue(min(count,max(1,value)))));layout.addWidget(progress);table=RoomyTable(0,2);table.setHorizontalHeaderLabels([tr('Dokument'),tr('Wörter')]);table.horizontalHeader().setStretchLastSection(True)
        for i,doc in enumerate(ordered_documents(host.p)):table.insertRow(i);table.setItem(i,0,QTableWidgetItem(doc['name']));table.setItem(i,1,QTableWidgetItem(str(words(doc['html']))))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers);layout.addWidget(table);sessions=host.p.get('writing_sessions',[]);today=datetime.now().astimezone().date();added=sum(max(0,x.get('words_added',0)) for x in sessions if datetime.fromisoformat(x['started']).astimezone().date()==today);layout.addWidget(label(tr('Heute erfasst: ')+str(added)+' / '+str(daily.value())+' · '+str(len(sessions))+' '+tr('Sitzungen')))
        show_sessions=QPushButton(tr('Sitzungen anzeigen'));layout.addWidget(show_sessions)
        def inspect_sessions():
            dialog=QDialog(self);dialog.setWindowTitle(tr('Schreibsitzungen'));outer=QVBoxLayout(dialog);table=RoomyTable(0,3);table.setHorizontalHeaderLabels([tr('Beginn'),tr('Aktive Minuten'),tr('Netto neue Wörter')]);table.horizontalHeader().setStretchLastSection(True);table.setEditTriggers(QAbstractItemView.NoEditTriggers);outer.addWidget(table)
            for row,session in enumerate(reversed(host.p.get('writing_sessions',[]))):
                table.insertRow(row)
                for col,text in enumerate([datetime.fromisoformat(session['started']).astimezone().strftime('%d.%m.%Y %H:%M'),str(round(session.get('seconds',0)/60,1)),str(session.get('words_added',0))]):table.setItem(row,col,QTableWidgetItem(text))
            dialog.resize(650,450);dialog.exec()
        show_sessions.clicked.connect(inspect_sessions)
        def save():host.p['writing_goals']=dict(total=total.value(),daily=daily.value(),track=track.isChecked());host.changed();self.accept()
        layout.addWidget(primary(tr('Übernehmen'),save))

def print_selection_tree(p,selected=None):
    tree=RoomyTree();tree.setHeaderHidden(True);parents={d.get('parent') for d in p['documents']};items={};leaves=[]
    for doc in ordered_documents(p):
        item=QTreeWidgetItem([tr(KINDS.get(doc.get('kind','chapter'),'Kapitel'))+' · '+doc['name']]);item.setData(0,Qt.UserRole,doc['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);parent=items.get(doc.get('parent'));parent.addChild(item) if parent else tree.addTopLevelItem(item);items[doc['id']]=item
        if doc['id'] in parents:
            item.setData(0,Qt.UserRole+1,True);item.setFlags(item.flags()|Qt.ItemIsAutoTristate);body=QTreeWidgetItem([tr('Überschrift & Kapiteltext')]);body.setData(0,Qt.UserRole,doc['id']);body.setFlags(body.flags()|Qt.ItemIsUserCheckable);item.addChild(body);leaves.append(body)
        else:leaves.append(item)
    for item in leaves:item.setCheckState(0,Qt.Checked if selected is None or item.data(0,Qt.UserRole) in selected else Qt.Unchecked)
    tree.expandAll();return tree

def selected_document_ids(tree):
    ids=[]
    def visit(parent):
        for i in range(parent.childCount()):
            item=parent.child(i)
            if not item.data(0,Qt.UserRole+1) and item.checkState(0)==Qt.Checked:ids.append(item.data(0,Qt.UserRole))
            visit(item)
    visit(tree.invisibleRootItem());return ids

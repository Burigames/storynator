import sys, json, base64, os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QSettings, QMarginsF
from PySide6.QtGui import QAction, QFont, QTextCharFormat, QTextCursor, QTextDocument, QImage, QTextImageFormat, QTextFormat, QTextListFormat, QColor, QPageSize
from PySide6.QtWidgets import *
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog, QPageSetupDialog
from core import *

TYPES=['Text','Richtext','Zahl','Checkbox','Dropdown','Mehrfachauswahl','Slider','Bild','Galerie','Datum','Zeitspanne','Verknüpfung']
FIELD_RENDERERS={}
def register_field_type(name,renderer):
    FIELD_RENDERERS[name]=renderer
    if name not in TYPES:TYPES.append(name)


def button(text,fn):
    b=QPushButton(text); b.clicked.connect(fn); return b

def ask(parent,title,value=''):
    s,ok=QInputDialog.getText(parent,title,'Name:',text=value); return s.strip() if ok and s.strip() else None

class Picker(QDialog):
    def __init__(self,w):
        super().__init__(w); self.setWindowTitle('Eintrag verknüpfen'); self.resize(510,400); self.id=None
        lay=QVBoxLayout(self); self.search=QLineEdit(); self.search.setPlaceholderText('Name suchen …'); lay.addWidget(self.search); self.list=QListWidget(); lay.addWidget(self.list)
        def refresh():
            self.list.clear()
            for position,x in enumerate(objects(w.p),1):
                if self.search.text().casefold() in x['name'].casefold():
                    cat=next((c['name'] for c in w.p['categories'] if c['id']==x.get('category')),'Timeline' if x in w.p['events'] else 'Dokument')
                    detail=re.sub('<[^>]+>',' ',x.get('html','')).strip()[:70]; i=QListWidgetItem(x['name']+'  ·  '+cat+('  ·  '+detail if detail else '  ·  Eintrag '+str(position))); i.setData(Qt.UserRole,x['id']); self.list.addItem(i)
        def choose():
            if self.list.currentItem(): self.id=self.list.currentItem().data(Qt.UserRole); self.accept()
        self.search.textChanged.connect(refresh); self.list.itemDoubleClicked.connect(choose); lay.addWidget(button('Verknüpfen',choose)); refresh()

class Rich(QTextEdit):
    def __init__(self,w,obj,key='html'):
        super().__init__(); self.w=w; self.obj=obj; self.key=key; self.setAcceptRichText(True); self.setFont(QFont('Georgia',12)); self.document().setDocumentMargin(35)
        self.load_assets(); self.setHtml(render(w.p,obj.get(key,''))); self.textChanged.connect(self.store)
    def load_assets(self):
        for k,v in self.w.p['assets'].items(): self.document().addResource(QTextDocument.ImageResource,QUrl('asset:'+k),QImage.fromData(base64.b64decode(v)))
    def store(self): self.obj[self.key]=self.toHtml(); self.w.changed()
    def link(self):
        cur=self.textCursor(); p=Picker(self.w)
        if p.exec():
            fmt=QTextCharFormat(); fmt.setAnchor(True); fmt.setAnchorHref('story:'+p.id); fmt.setForeground(QColor('#7461bb')); fmt.setFontUnderline(False)
            cur.insertText(resolve(self.w.p,p.id)['name'],fmt); cur.insertText(' ',QTextCharFormat()); self.setTextCursor(cur)
    def keyPressEvent(self,e):
        if e.text()=='@': self.link(); return
        super().keyPressEvent(e)
    def mouseReleaseEvent(self,e):
        href=self.anchorAt(e.position().toPoint())
        if href.startswith('story:'): self.w.open_object(href[6:]); return
        super().mouseReleaseEvent(e)
    def insertFromMimeData(self,m):
        # Only images copied into project storage are accepted; no external image paths.
        if m.hasImage():
            image=QImage(m.imageData()); from PySide6.QtCore import QBuffer,QByteArray,QIODevice
            a=QByteArray(); b=QBuffer(a); b.open(QIODevice.WriteOnly); image.save(b,'PNG'); key=uid()+'.png'; self.w.p['assets'][key]=base64.b64encode(bytes(a)).decode(); self.add_image(key)
        else: self.insertPlainText(m.text())
    def add_image(self,key):
        self.load_assets(); f=QTextImageFormat(); f.setName('asset:'+key); img=QImage.fromData(base64.b64decode(self.w.p['assets'][key])); f.setWidth(min(550,img.width())); f.setHeight(min(550,img.width())*img.height()/max(1,img.width())); self.textCursor().insertImage(f)

class TimelineView(QGraphicsView):
    def wheelEvent(self,e):
        if e.modifiers()&Qt.ControlModifier: self.scale(1.2 if e.angleDelta().y()>0 else 1/1.2,1); e.accept()
        else: super().wheelEvent(e)

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.p=new_project(); self.path=None; self.dirty=False; self.settings=QSettings('Storynator','Storynator'); self.resize(1280,820)
        self.recovery=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))/'recovery.storynator'
        self.tabs=QTabWidget(); self.tabs.setTabsClosable(True); self.tabs.tabCloseRequested.connect(self.tabs.removeTab); self.tabs.currentChanged.connect(lambda _:self.update_status())
        self.nav=QTreeWidget(); self.nav.setHeaderLabel('PROJEKT'); self.nav.itemDoubleClicked.connect(lambda i,c:self.open_object(i.data(0,Qt.UserRole)))
        sidebar=QWidget(); sl=QVBoxLayout(sidebar); title=QLabel('✦  STORYNATOR'); title.setStyleSheet('font-size:22px;font-weight:bold;color:#7461bb;padding:15px'); sl.addWidget(title)
        for label,fn in [('＋ Kapitel',self.add_doc),('＋ Kategorie',self.add_category),('＋ Welt-Eintrag',self.add_entry),('＋ Ereignis / Zeitalter',self.add_event),('◷ Timeline',self.show_timeline),('⚙ Projektkalender',self.calendar)]: sl.addWidget(button(label,fn))
        sl.addWidget(self.nav); split=QSplitter(); split.addWidget(sidebar); split.addWidget(self.tabs); split.setSizes([270,1010]); self.setCentralWidget(split)
        self.active_editor=None;QApplication.instance().focusChanged.connect(self.track_editor)
        self.toolbar(); self.menus(); self.refresh(); self.home()
        self.timer=QTimer(self); self.timer.timeout.connect(self.autosave); self.timer.start(30000)
        if self.recovery.exists() and QMessageBox.question(self,'Wiederherstellung','Wiederherstellungssicherung öffnen?')==QMessageBox.Yes:
            try:self.p=load_project(self.recovery); self.tabs.clear(); self.refresh(); self.changed()
            except Exception as e:self.error(e)
    def error(self,e): QMessageBox.warning(self,'Storynator',str(e))
    def changed(self): self.dirty=True; self.update_status()
    def update_status(self):
        self.setWindowTitle(('● ' if self.dirty else '')+self.p['name']+' — Storynator'); self.statusBar().showMessage(('Ungespeichert' if self.dirty else 'Gespeichert')+'  ·  Lokal & offline  ·  @ verknüpft Einträge')
    def refresh(self):
        self.nav.clear()
        for title,seq in [('Editor',self.p['documents']),('Welt',self.p['categories']),('Timeline',self.p['events'])]:
            root=QTreeWidgetItem([title]); self.nav.addTopLevelItem(root)
            for o in seq:
                item=QTreeWidgetItem([o['name']]); item.setData(0,Qt.UserRole,o['id']); root.addChild(item)
                if title=='Welt':
                    for en in self.p['entries']:
                        if en['category']==o['id']:
                            sub=QTreeWidgetItem([en['name']]);sub.setData(0,Qt.UserRole,en['id']); item.addChild(sub)
        self.nav.expandAll(); self.update_status()
    def menus(self):
        m=self.menuBar().addMenu('Projekt')
        for name,fn,key in [('Neu',self.new,'Ctrl+N'),('Öffnen',self.open_file,'Ctrl+O'),('Speichern',self.save,'Ctrl+S'),('Speichern unter',lambda:self.save(True),'Ctrl+Shift+S'),('Startseite',self.home,''),('Druckvorschau / PDF',self.printing,'Ctrl+P')]:
            a=m.addAction(name); a.triggered.connect(fn); a.setShortcut(key)
        m=self.menuBar().addMenu('Eintrag')
        for name,fn in [('Umbenennen',self.rename),('Löschen',self.delete),('Nach oben',lambda:self.move(-1)),('Nach unten',lambda:self.move(1))]:m.addAction(name).triggered.connect(fn)
        search=QLineEdit(); search.setPlaceholderText('Projekt durchsuchen …'); self.menuBar().setCornerWidget(search); search.returnPressed.connect(lambda:self.search(search.text()))
    def current(self):
        w=self.tabs.currentWidget(); return getattr(w,'obj',None)
    def track_editor(self,old,new):
        if isinstance(new,Rich):self.active_editor=new
    def editor(self):
        focus=QApplication.focusWidget()
        if isinstance(focus,Rich):return focus
        page=self.tabs.currentWidget()
        if page and self.active_editor and page.isAncestorOf(self.active_editor):return self.active_editor
        return page.findChild(Rich) if page else None
    def fmt(self,method,value):
        e=self.editor()
        if e:
            f=QTextCharFormat();getattr(f,method)(value);e.mergeCurrentCharFormat(f);e.setFocus()
    def toolbar(self):
        tb=self.addToolBar('Text'); tb.setMovable(False)
        font=QFontComboBox(); font.currentFontChanged.connect(lambda f:self.fmt('setFontFamily',f.family()));tb.addWidget(font)
        size=QSpinBox();size.setRange(6,96);size.setValue(12);size.valueChanged.connect(lambda v:self.fmt('setFontPointSize',v));tb.addWidget(size)
        for text,fn in [('Fett',lambda:self.fmt('setFontWeight',QFont.Bold if self.editor() and self.editor().fontWeight()!=QFont.Bold else QFont.Normal)),('Kursiv',lambda:self.fmt('setFontItalic',not self.editor().fontItalic() if self.editor() else False)),('Unterstrichen',lambda:self.fmt('setFontUnderline',not self.editor().fontUnderline() if self.editor() else False)),('Farbe',self.color),('↶',lambda:self.editor() and self.editor().undo()),('↷',lambda:self.editor() and self.editor().redo()),('Bild',self.image),('@',lambda:self.editor() and self.editor().link()),('Seitenumbruch',self.pagebreak)]:tb.addAction(text).triggered.connect(fn)
        tb.addSeparator(); style=QComboBox();style.addItems(['Absatz','Überschrift 1','Überschrift 2','Aufzählung','Nummeriert']);style.activated.connect(self.paragraph);tb.addWidget(style)
        for text,align in [('Links',Qt.AlignLeft),('Mitte',Qt.AlignHCenter),('Rechts',Qt.AlignRight),('Blocksatz',Qt.AlignJustify)]:tb.addAction(text).triggered.connect(lambda checked=False,a=align:self.editor() and self.editor().setAlignment(a))
    def color(self):
        c=QColorDialog.getColor(parent=self)
        if c.isValid():self.fmt('setForeground',c)
    def paragraph(self,i):
        e=self.editor()
        if not e:return
        cur=e.textCursor()
        if i>=3:
            f=QTextListFormat();f.setStyle(QTextListFormat.ListDisc if i==3 else QTextListFormat.ListDecimal);cur.createList(f)
        else:
            if cur.currentList():cur.currentList().remove(cur.block())
            f=cur.blockFormat(); f.setHeadingLevel(i);cur.setBlockFormat(f);self.fmt('setFontPointSize',[12,24,18][i]);self.fmt('setFontWeight',QFont.Bold if i else QFont.Normal)
    def image(self):
        e=self.editor()
        if e:
            path,_=QFileDialog.getOpenFileName(self,'Bild einbetten','','Bilder (*.png *.jpg *.jpeg *.webp *.bmp)')
            if path:e.add_image(embed(self.p,path))
    def pagebreak(self):
        e=self.editor()
        if e:
            cur=e.textCursor();cur.insertBlock();f=cur.blockFormat();f.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore);cur.setBlockFormat(f)
    def home(self):
        page=QWidget();l=QVBoxLayout(page);l.addWidget(QLabel('<h1>Deine nächste Welt beginnt hier.</h1><p>Schreiben. Zusammenhänge entdecken. Geschichten bewahren.</p>'));l.addWidget(button('Neues Projekt',self.new));l.addWidget(button('Projekt öffnen',self.open_file))
        for path in self.settings.value('recent',[],type=list):l.addWidget(button(str(path),lambda checked=False,p=path:self.open_file(p)))
        l.addStretch(); self.tabs.addTab(page,'Start');self.tabs.setCurrentWidget(page)
    def guard(self):
        if not self.dirty:return True
        r=QMessageBox.question(self,'Ungespeicherte Änderungen','Änderungen speichern?',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        return self.save() if r==QMessageBox.Save else r==QMessageBox.Discard
    def new(self):
        if not self.guard():return
        name=ask(self,'Neues Projekt')
        if name:self.p=new_project(name);self.path=None;self.tabs.clear();self.refresh();self.changed();self.open_object(self.p['documents'][0]['id'])
    def open_file(self,path=None):
        if not self.guard():return
        if not isinstance(path,str):path=QFileDialog.getOpenFileName(self,'Projekt öffnen','','Storynator (*.storynator)')[0]
        if not path:return
        try:
            p=load_project(path);self.p=p;self.path=path;self.dirty=False;self.tabs.clear();self.refresh();self.remember(path);self.open_object(p['documents'][0]['id']) if p['documents'] else self.home()
        except Exception as e:self.error(e)
    def remember(self,path):
        recent=self.settings.value('recent',[],type=list);self.settings.setValue('recent',([str(path)]+[p for p in recent if p!=str(path)])[:10])
    def save(self,as_new=False):
        path=self.path
        if as_new or not path:path=QFileDialog.getSaveFileName(self,'Projekt speichern',path or self.p['name']+'.storynator','Storynator (*.storynator)')[0]
        if not path:return False
        if not path.endswith('.storynator'):path+='.storynator'
        try:save_project(self.p,path);self.path=path;self.dirty=False;self.remember(path);self.update_status();self.recovery.unlink(missing_ok=True);return True
        except Exception as e:self.error(e);return False
    def autosave(self):
        if self.dirty:
            try:save_project(self.p,self.recovery)
            except Exception as e:self.statusBar().showMessage('Wiederherstellung fehlgeschlagen: '+str(e))
    def closeEvent(self,e):
        if self.guard():self.recovery.unlink(missing_ok=True);e.accept()
        else:e.ignore()
    def add_doc(self):
        name=ask(self,'Kapitel erstellen')
        if name:o=dict(id=uid(),name=name,html='');self.p['documents'].append(o);self.changed();self.refresh();self.open_object(o['id'])
    def add_category(self):
        name=ask(self,'Kategorie erstellen')
        if name:c=dict(id=uid(),name=name,fields=[]);self.p['categories'].append(c);self.changed();self.refresh();self.template(c)
    def add_entry(self):
        if not self.p['categories']:self.add_category()
        if not self.p['categories']:return
        names=[c['name'] for c in self.p['categories']];name,ok=QInputDialog.getItem(self,'Kategorie','Kategorie:',names,0,False)
        if ok:
            c=self.p['categories'][names.index(name)];name=ask(self,'Eintrag erstellen')
            if name:o=dict(id=uid(),name=name,category=c['id'],values={},links=[],html='');self.p['entries'].append(o);self.changed();self.refresh();self.open_object(o['id'])
    def selected(self):
        i=self.nav.currentItem();return i.data(0,Qt.UserRole) if i else (self.current() or {}).get('id')
    def rename(self):
        id=self.selected();o=resolve(self.p,id) or next((c for c in self.p['categories'] if c['id']==id),None)
        if not o:return
        name=ask(self,'Umbenennen',o['name'])
        if name:
            o['name']=name
            for en in objects(self.p):
                if 'html' in en:en['html']=render(self.p,en['html'])
                for f,v in en.get('values',{}).items():
                    if isinstance(v,str) and 'story:' in v:en['values'][f]=render(self.p,v)
            for i in range(self.tabs.count()):
                page=self.tabs.widget(i)
                for e in page.findChildren(Rich):
                    cur=e.textCursor();pos=cur.position();e.blockSignals(True);e.setHtml(render(self.p,e.toHtml()));cur=e.textCursor();cur.setPosition(min(pos,e.document().characterCount()-1));e.setTextCursor(cur);e.blockSignals(False)
                for ls in page.findChildren(QListWidget):
                    for j in range(ls.count()):
                        target=resolve(self.p,ls.item(j).data(Qt.UserRole))
                        if target:ls.item(j).setText(target['name'])
                if getattr(page,'obj',None):
                    self.tabs.setTabText(i,page.obj['name'])
                    heading=page.findChild(QLabel,'entryHeading')
                    if heading:heading.setText(page.obj['name'])
            self.changed();self.refresh()
    def delete(self):
        id=self.selected();o=resolve(self.p,id)
        if not o:
            cat=next((c for c in self.p['categories'] if c['id']==id),None)
            if cat:
                if any(en['category']==id for en in self.p['entries']):self.error('Kategorie enthält Einträge. Einträge zuerst einzeln löschen; Inhalte werden nicht automatisch entfernt.');return
                if QMessageBox.question(self,'Kategorie löschen','Leere Kategorie und Vorlage löschen?')==QMessageBox.Yes:self.p['categories'].remove(cat);self.changed();self.refresh()
            return
        refs=references(self.p,id);message='„'+o['name']+'“ löschen?'
        if refs:message+='\nVorhandene Verweise in: '+', '.join(refs)+'\nSie bleiben als gelöschte Verweise erkennbar.'
        if QMessageBox.question(self,'Löschen',message)!=QMessageBox.Yes:return
        for seq in [self.p['entries'],self.p['events'],self.p['documents']]:
            if o in seq:seq.remove(o)
        for i in reversed(range(self.tabs.count())):
            if getattr(self.tabs.widget(i),'obj',{}).get('id')==id:self.tabs.removeTab(i)
        self.changed();self.refresh()
    def move(self,delta):
        id=self.selected()
        for seq in [self.p['documents'],self.p['entries'],self.p['categories']]:
            for i,o in enumerate(seq):
                if o['id']==id and 0<=i+delta<len(seq):seq[i],seq[i+delta]=seq[i+delta],seq[i];self.changed();self.refresh();return
    def search(self,text):
        d=QDialog(self);d.setWindowTitle('Suchergebnisse');l=QVBoxLayout(d);ls=QListWidget();l.addWidget(ls)
        for o in objects(self.p):
            if text.casefold() in json.dumps(o,ensure_ascii=False).casefold():i=QListWidgetItem(o['name']);i.setData(Qt.UserRole,o['id']);ls.addItem(i)
        ls.itemDoubleClicked.connect(lambda i:(self.open_object(i.data(Qt.UserRole)),d.accept()));d.resize(500,400);d.exec()
    def open_object(self,id):
        cat=next((c for c in self.p['categories'] if c['id']==id),None)
        if cat:self.template(cat);return
        o=resolve(self.p,id)
        if not o:self.error('Dieser Eintrag wurde gelöscht.');return
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i),'obj',{}).get('id')==id:self.tabs.setCurrentIndex(i);return
        page=QWidget();page.obj=o;l=QVBoxLayout(page);heading=QLabel(o['name']);heading.setObjectName('entryHeading');heading.setStyleSheet('font-size:24px;padding:12px');l.addWidget(heading)
        if o in self.p['documents']:l.addWidget(Rich(self,o))
        else:
            scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();form=QFormLayout(inner);scroll.setWidget(inner);l.addWidget(scroll)
            desc=Rich(self,o);desc.setMinimumHeight(200);form.addRow('Beschreibung',desc)
            if o in self.p['events']:
                form.addRow('Zeitliche Zuordnung',QLabel(o['start']+(' bis '+o['end'] if o['end'] else '')+' · '+o['kind']));form.addRow(button('Zeit ändern',lambda:self.edit_time(o,page)))
            else:
                cat=next(c for c in self.p['categories'] if c['id']==o['category']); form.addRow(button('Kategorievorlage bearbeiten',lambda:self.template(cat)))
                for f in cat['fields']:form.addRow(f['name'],self.field(o,f))
            form.addRow('Verknüpfungen',self.link_field(o,'links'))
        self.tabs.addTab(page,o['name']);self.tabs.setCurrentWidget(page)
    def edit_time(self,o,page):
        if self.time_dialog(o):self.tabs.removeTab(self.tabs.indexOf(page));self.open_object(o['id']);self.changed();self.refresh()
    def link_field(self,o,key,values=None):
        data=o if values is None else values; data.setdefault(key,[]);box=QWidget();l=QVBoxLayout(box);ls=QListWidget();ls.setMaximumHeight(130);l.addWidget(ls)
        def refresh():
            ls.clear()
            for id in data[key]:
                target=resolve(self.p,id);i=QListWidgetItem(target['name'] if target else '[Gelöschter Eintrag]');i.setData(Qt.UserRole,id);ls.addItem(i)
        def add():
            p=Picker(self)
            if p.exec() and p.id not in data[key]:data[key].append(p.id);refresh();self.changed()
        def remove():
            if ls.currentItem():data[key].remove(ls.currentItem().data(Qt.UserRole));refresh();self.changed()
        row=QHBoxLayout();row.addWidget(button('@ Verknüpfen',add));row.addWidget(button('Verweis entfernen',remove));l.addLayout(row);ls.itemDoubleClicked.connect(lambda i:self.open_object(i.data(Qt.UserRole)));refresh();return box
    def field(self,o,f):
        values=o['values'];key=f['id'];v=values.get(key);t=f['type'];opts=f.get('options',[])
        if t in FIELD_RENDERERS:return FIELD_RENDERERS[t](self,o,f)
        if t not in TYPES:return QLabel('Unbekannter Feldtyp · Wert bleibt gespeichert: '+str(v))
        def put(val):values[key]=val;self.changed()
        if t=='Richtext':
            values.setdefault(key,'');return Rich(self,values,key)
        if t=='Verknüpfung':return self.link_field(o,key,values)
        if t in ['Bild','Galerie']:
            box=QWidget();l=QVBoxLayout(box);preview=QLabel();preview.setWordWrap(True);l.addWidget(preview)
            def refresh():
                ids=values.get(key,[]);ids=ids if isinstance(ids,list) else [ids];preview.setText('')
                if ids:
                    from PySide6.QtGui import QPixmap
                    img=QImage.fromData(base64.b64decode(self.p['assets'].get(ids[0],'')));preview.setPixmap(QPixmap.fromImage(img).scaled(280,170,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                preview.setToolTip(str(len(ids))+' eingebettete Bilder')
            def add():
                paths,_=QFileDialog.getOpenFileNames(self,'Bilder einbetten','','Bilder (*.png *.jpg *.jpeg *.webp *.bmp)')
                if paths:
                    ids=[embed(self.p,p) for p in paths];put((values.get(key,[])+ids) if t=='Galerie' else ids[:1]);refresh()
            l.addWidget(button('Bilder auswählen',add))
            if t=='Galerie':
                def gallery():
                    d=QDialog(self);d.setWindowTitle(f['name']);lay=QVBoxLayout(d);sc=QScrollArea();sc.setWidgetResizable(True);inside=QWidget();il=QVBoxLayout(inside)
                    from PySide6.QtGui import QPixmap
                    for id in values.get(key,[]):
                        lab=QLabel();lab.setPixmap(QPixmap.fromImage(QImage.fromData(base64.b64decode(self.p['assets'][id]))).scaledToWidth(500,Qt.SmoothTransformation));il.addWidget(lab)
                    sc.setWidget(inside);lay.addWidget(sc);d.resize(560,600);d.exec()
                l.addWidget(button('Galerie öffnen',gallery))
            l.addWidget(button('Bilder entfernen',lambda:(put([]),refresh())));refresh();return box
        if t=='Checkbox':w=QCheckBox();w.setChecked(bool(v));w.toggled.connect(put);return w
        if t=='Zahl':w=QDoubleSpinBox();w.setRange(-1e12,1e12);w.setDecimals(5);w.setValue(v or 0);w.valueChanged.connect(put);return w
        if t=='Dropdown':
            w=QComboBox();w.addItem('');w.addItems(list(dict.fromkeys(opts+([v] if v and v not in opts else []))));w.setCurrentText(v or '');w.currentTextChanged.connect(put);return w
        if t=='Mehrfachauswahl':
            w=QListWidget()
            for opt in list(dict.fromkeys(opts+(v or []))):
                i=QListWidgetItem(opt);i.setFlags(i.flags()|Qt.ItemIsUserCheckable);i.setCheckState(Qt.Checked if opt in (v or []) else Qt.Unchecked);w.addItem(i)
            w.itemChanged.connect(lambda _:put([w.item(i).text() for i in range(w.count()) if w.item(i).checkState()==Qt.Checked]));w.setMaximumHeight(140);return w
        if t=='Slider':
            box=QWidget();l=QHBoxLayout(box);w=QSlider(Qt.Horizontal);lo=f.get('min',0);hi=f.get('max',100);step=f.get('step',1);w.setRange(0,round((hi-lo)/step));w.setValue(round(((v if v is not None else lo)-lo)/step));lab=QLabel(str(v if v is not None else lo));l.addWidget(w);l.addWidget(lab);w.valueChanged.connect(lambda n:(lab.setText(str(lo+n*step)),put(lo+n*step)));return box
        w=QLineEdit(str(v or ''))
        if t in ['Datum','Zeitspanne']:
            w.setPlaceholderText('Jahr/Monat/Tag'+(' .. Jahr/Monat/Tag' if t=='Zeitspanne' else '')+' · Jahreskalender: Jahr')
            def valid():
                try:
                    parts=w.text().split('..')
                    if w.text():Calendar(self.p['calendar']).span(parts[0].strip(),parts[1].strip() if len(parts)>1 else '')
                    put(w.text());w.setStyleSheet('')
                except Exception as e:w.setStyleSheet('border:1px solid #cf5964');self.error(e)
            w.editingFinished.connect(valid)
        else:w.textChanged.connect(put)
        return w
    def template(self,cat):
        d=QDialog(self);d.setWindowTitle('Vorlage · '+cat['name']);d.resize(850,500);l=QVBoxLayout(d);l.addWidget(QLabel('Felder haben stabile IDs. Entfernte Felder bleiben als archivierte Werte im Projekt erhalten.'))
        table=QTableWidget(0,3);table.setHorizontalHeaderLabels(['Feldname','Typ','Einstellungen · Doppelklick']);table.horizontalHeader().setStretchLastSection(True);l.addWidget(table)
        fields=json.loads(json.dumps(cat['fields']))
        def add_row(f=None):
            f=f or dict(id=uid(),name='Neues Feld',type='Text');r=table.rowCount();table.insertRow(r);i=QTableWidgetItem(f['name']);i.setData(Qt.UserRole,f['id']);table.setItem(r,0,i);cb=QComboBox();cb.addItems(TYPES+([f['type']] if f['type'] not in TYPES else []));cb.setCurrentText(f['type']);table.setCellWidget(r,1,cb);settings={k:v for k,v in f.items() if k not in ['id','name','type']};item=QTableWidgetItem('Einstellungen öffnen');item.setData(Qt.UserRole,settings);item.setFlags(item.flags() & ~Qt.ItemIsEditable);table.setItem(r,2,item)
        for f in fields:add_row(f)
        def settings_dialog(r,col):
            if col!=2:return
            t=table.cellWidget(r,1).currentText();item=table.item(r,2);settings=item.data(Qt.UserRole) or {};dialog=QDialog(d);dialog.setWindowTitle('Feldeinstellungen');form=QFormLayout(dialog)
            options=QPlainTextEdit('\n'.join(settings.get('options',[])));lo=QDoubleSpinBox();hi=QDoubleSpinBox();step=QDoubleSpinBox()
            for widget in [lo,hi,step]:widget.setRange(-1e9,1e9);widget.setDecimals(4)
            lo.setValue(settings.get('min',0));hi.setValue(settings.get('max',100));step.setValue(settings.get('step',1))
            if t in ['Dropdown','Mehrfachauswahl']:form.addRow('Eine Option pro Zeile',options)
            elif t=='Slider':form.addRow('Minimum',lo);form.addRow('Maximum',hi);form.addRow('Schrittweite',step)
            else:form.addRow(QLabel('Dieser Feldtyp benötigt keine zusätzlichen Einstellungen.'))
            def apply():
                if t in ['Dropdown','Mehrfachauswahl']:item.setData(Qt.UserRole,{'options':list(dict.fromkeys(s.strip() for s in options.toPlainText().splitlines() if s.strip()))})
                elif t=='Slider':
                    if hi.value()<lo.value() or step.value()<=0:self.error('Maximum muss mindestens Minimum sein; Schrittweite muss positiv sein.');return
                    item.setData(Qt.UserRole,{'min':lo.value(),'max':hi.value(),'step':step.value()})
                dialog.accept()
            form.addRow(button('Übernehmen',apply));dialog.exec()
        table.cellDoubleClicked.connect(settings_dialog)
        row=QHBoxLayout();row.addWidget(button('＋ Feld',lambda:add_row()));row.addWidget(button('Archivieren',lambda:table.removeRow(table.currentRow()) if table.currentRow()>=0 else None))
        def move(delta):
            r=table.currentRow();n=r+delta
            if 0<=r<table.rowCount() and 0<=n<table.rowCount():
                for col in [0,2]:a=table.takeItem(r,col);b=table.takeItem(n,col);table.setItem(r,col,b);table.setItem(n,col,a)
                a=table.cellWidget(r,1).currentText();b=table.cellWidget(n,1).currentText();table.cellWidget(r,1).setCurrentText(b);table.cellWidget(n,1).setCurrentText(a);table.setCurrentCell(n,0)
        def restore():
            archived=cat.get('archived',[])
            if not archived:return
            names=[f['name'] for f in archived];name,ok=QInputDialog.getItem(d,'Archiviertes Feld wiederherstellen','Feld:',names,0,False)
            if ok:
                f=archived[names.index(name)]
                if not any(table.item(r,0).data(Qt.UserRole)==f['id'] for r in range(table.rowCount())):add_row(f)
        row.addWidget(button('Aus Archiv',restore))
        row.addWidget(button('↑',lambda:move(-1)));row.addWidget(button('↓',lambda:move(1)));l.addLayout(row)
        l.addWidget(QLabel('Doppelklick auf Einstellungen: Auswahloptionen oder Sliderbereich bearbeiten.'))
        def commit():
            try:
                result=[]
                for r in range(table.rowCount()):
                    old=next((f for f in fields+cat.get('archived',[]) if f['id']==table.item(r,0).data(Qt.UserRole)),None);t=table.cellWidget(r,1).currentText()
                    if old and t!=old['type'] and any(old['id'] in en['values'] for en in self.p['entries'] if en['category']==cat['id']):raise ValueError('Feldtyp mit vorhandenen Werten nicht ändern. Neues Feld anlegen; altes Feld archivieren.')
                    settings=table.item(r,2).data(Qt.UserRole) or {};f={**settings,'id':table.item(r,0).data(Qt.UserRole),'name':table.item(r,0).text(),'type':t}
                    if not f['name'].strip():raise ValueError('Feldname fehlt.')
                    if t=='Slider' and (f.get('step',1)<=0 or f.get('max',100)<f.get('min',0)):raise ValueError('Ungültiger Sliderbereich.')
                    if t in ['Dropdown','Mehrfachauswahl'] and not isinstance(f.get('options',[]),list):raise ValueError('options muss eine Liste sein.')
                    result.append(f)
                active={f['id'] for f in result};cat['archived']=[f for f in cat.get('archived',[])+fields if f['id'] not in active];cat['archived']=list({f['id']:f for f in cat['archived']}.values());cat['fields']=result;self.changed()
                reopen=[]
                for i in reversed(range(self.tabs.count())):
                    o=getattr(self.tabs.widget(i),'obj',{})
                    if o.get('category')==cat['id']:reopen.append(o['id']);self.tabs.removeTab(i)
                for id in reopen:self.open_object(id)
                d.accept()
            except Exception as e:self.error(e)
        l.addWidget(button('Vorlage übernehmen',commit));d.exec()
    def calendar(self):
        c=json.loads(json.dumps(self.p['calendar']));d=QDialog(self);d.setWindowTitle('Projektkalender');d.resize(760,730);l=QVBoxLayout(d);form=QFormLayout();l.addLayout(form)
        name=QLineEdit(c['name']);epoch=QSpinBox();epoch.setRange(-1000000,1000000);epoch.setValue(c['epoch']);zero=QCheckBox('Jahr null verwenden');zero.setChecked(c['year_zero']);yearonly=QCheckBox('Nur Jahreszahlen verwenden');yearonly.setChecked(not c['months']);week=QLineEdit(', '.join(c.get('week',[])));fmt=QLineEdit(c['format']);units=[]
        form.addRow('Name der Zeitrechnung',name);form.addRow('Ausgangsjahr',epoch);form.addRow(zero);form.addRow(yearonly)
        for key,label in [('year','Jahreseinheit'),('month','Monatseinheit'),('day','Tageseinheit')]:
            w=QLineEdit(c.get('units',{}).get(key,label));units.append((key,w));form.addRow(label,w)
        form.addRow('Wochentage (Komma-getrennt, optional)',week);form.addRow('Datumsdarstellung',fmt);form.addRow(QLabel('Platzhalter: {year}, {month}, {day}, {weekday}'))
        months=QTableWidget(0,2);months.setHorizontalHeaderLabels(['Monatsname','Tage']);months.horizontalHeader().setStretchLastSection(True)
        def add_month(n='Neuer Mond',days=30):
            r=months.rowCount();months.insertRow(r);months.setItem(r,0,QTableWidgetItem(n));months.setItem(r,1,QTableWidgetItem(str(days)))
        for m in c['months']:add_month(m['name'],m['days'])
        l.addWidget(QLabel('Monate in ihrer Reihenfolge'));l.addWidget(months);row=QHBoxLayout();row.addWidget(button('Monat hinzufügen',lambda:add_month()));row.addWidget(button('Monat entfernen',lambda:months.removeRow(months.currentRow()) if months.currentRow()>=0 else None));l.addLayout(row)
        leaps=QTableWidget(0,4);leaps.setHorizontalHeaderLabels(['Alle … Jahre','Versatz','Monatsnummer','Zusätzliche Tage'])
        def add_leap(rule=None):
            rule=rule or dict(every=4,offset=0,month=1,days=1);r=leaps.rowCount();leaps.insertRow(r)
            for i,k in enumerate(['every','offset','month','days']):leaps.setItem(r,i,QTableWidgetItem(str(rule.get(k,0))))
        for rule in c.get('leaps',[]):add_leap(rule)
        l.addWidget(QLabel('Schaltregeln (optional, mehrere Regeln werden addiert)'));l.addWidget(leaps);row=QHBoxLayout();row.addWidget(button('Schaltregel hinzufügen',lambda:add_leap()));row.addWidget(button('Schaltregel entfernen',lambda:leaps.removeRow(leaps.currentRow()) if leaps.currentRow()>=0 else None));l.addLayout(row)
        def commit():
            try:
                if not name.text().strip():raise ValueError('Kalendername fehlt.')
                c.update(name=name.text().strip(),epoch=epoch.value(),year_zero=zero.isChecked(),months=[] if yearonly.isChecked() else [dict(name=months.item(r,0).text(),days=int(months.item(r,1).text())) for r in range(months.rowCount())],week=[s.strip() for s in week.text().split(',') if s.strip()],format=fmt.text(),units={key:w.text() for key,w in units},leaps=[] if yearonly.isChecked() else [{k:int(leaps.item(r,i).text()) for i,k in enumerate(['every','offset','month','days'])} for r in range(leaps.rowCount())]);cal=Calendar(c);cal.validate()
                if not yearonly.isChecked() and not c['months']:raise ValueError('Mindestens einen Monat anlegen oder nur Jahreszahlen wählen.')
                for en in self.p['events']:cal.span(en['start'],en['end'])
                for en in self.p['entries']:
                    cat=next(x for x in self.p['categories'] if x['id']==en['category'])
                    for f in cat['fields']:
                        if f['type'] in ['Datum','Zeitspanne'] and en['values'].get(f['id']):
                            parts=en['values'][f['id']].split('..');cal.span(parts[0].strip(),parts[1].strip() if len(parts)>1 else '')
                if self.p['events'] and QMessageBox.question(d,'Kalenderänderung','Bestehende Datumswerte werden im neuen Kalender interpretiert. Übernehmen?')!=QMessageBox.Yes:return
                self.p['calendar']=c;self.changed();d.accept()
            except Exception as e:self.error(e)
        l.addWidget(button('Kalender prüfen und übernehmen',commit));d.exec()
    def time_dialog(self,o):
        d=QDialog(self);d.setWindowTitle('Zeitliche Zuordnung');l=QFormLayout(d);name=QLineEdit(o.get('name',''));start=QLineEdit(o.get('start','1/1/1' if self.p['calendar']['months'] else '1'));end=QLineEdit(o.get('end',''));kind=QComboBox();kind.addItems(['Ereignis','Zeitalter','Notiz','Geschichte']);kind.setCurrentText(o.get('kind','Ereignis'));era=QComboBox();era.addItem('Keinem Zeitalter zugeordnet',None)
        for en in self.p['events']:
            if en['kind']=='Zeitalter' and en['id']!=o.get('id'):era.addItem(en['name'],en['id'])
        era.setCurrentIndex(max(0,era.findData(o.get('era'))));l.addRow('Name',name);l.addRow('Art',kind);units=self.p['calendar'].get('units',{});hint='/'.join(units.get(k,k) for k in ['year','month','day']) if self.p['calendar']['months'] else units.get('year','Jahr');l.addRow('Anfang ('+hint+')',start);l.addRow('Ende (optional)',end);l.addRow('Zeitalter (optional)',era)
        def commit():
            try:
                if not name.text().strip():raise ValueError('Name fehlt.')
                cal=Calendar(self.p['calendar']);a,b=cal.span(start.text(),end.text());parent=resolve(self.p,era.currentData())
                if parent:
                    x,y=cal.span(parent['start'],parent['end'])
                    if not x<=a<=b<=y:raise ValueError('Eintrag muss innerhalb des zugeordneten Zeitalters liegen.')
                if kind.currentText()=='Zeitalter' and not end.text():raise ValueError('Zeitalter benötigt ein Ende.')
                ancestor=parent;seen={o.get('id')}
                while ancestor:
                    if ancestor['id'] in seen:raise ValueError('Zyklische Zeitalter-Zuordnung ist nicht möglich.')
                    seen.add(ancestor['id']);ancestor=resolve(self.p,ancestor.get('era'))
                for child in self.p['events']:
                    if child.get('era')==o.get('id'):
                        x,y=cal.span(child['start'],child['end'])
                        if kind.currentText()!='Zeitalter' or not a<=x<=y<=b:raise ValueError('Zugeordnete Einträge liegen außerhalb des neuen Zeitalters.')
                o.update(name=name.text().strip(),start=start.text(),end=end.text(),kind=kind.currentText(),era=era.currentData());d.accept()
            except Exception as e:self.error(e)
        l.addRow(button('Übernehmen',commit));return d.exec()==QDialog.Accepted
    def add_event(self):
        o=dict(id=uid(),html='',links=[])
        if self.time_dialog(o):self.p['events'].append(o);self.changed();self.refresh();self.open_object(o['id'])
    def show_timeline(self):
        cal=Calendar(self.p['calendar']);page=QWidget();l=QVBoxLayout(page);l.addWidget(QLabel('<h2>Timeline</h2>Überlappungen bleiben in eigenen Spuren · Strg + Mausrad zoomt'))
        scene=QGraphicsScene();view=TimelineView(scene);view.setDragMode(QGraphicsView.ScrollHandDrag);l.addWidget(view,2);table=QTableWidget(0,4);table.setHorizontalHeaderLabels(['Name','Art','Anfang','Ende']);table.horizontalHeader().setStretchLastSection(True);l.addWidget(table,1)
        def draw():
            try:
                scene.clear();table.setRowCount(0);events=sorted(self.p['events'],key=lambda e:cal.ordinal(e['start']));spans=[cal.span(e['start'],e['end']) for e in events]
                lo=min((a for a,b in spans),default=0);hi=max((b for a,b in spans),default=1);factor=900/max(1,hi-lo)
                unit='Jahre' if not self.p['calendar']['months'] else 'Tage'
                scene.addText('Zeitachse · '+unit+' relativ zum Kalenderursprung').setPos(160,-50)
                scene.addLine(160,0,1060,0,QColor('#7461bb'))
                for tick in range(6):
                    x=160+tick*180;scene.addLine(x,-5,x,5,QColor('#7461bb'));scene.addText(str(round(lo+(hi-lo)*tick/5))).setPos(x,-30)
                for row,(en,(a,b)) in enumerate(zip(events,spans)):
                    y=30+row*48; x=160+(a-lo)*factor;width=max(10,(b-a)*factor)
                    scene.addLine(160,y+35,1100,y+35,QColor('#dddddd'));label=scene.addText(en['name']);label.setPos(0,y)
                    rect=scene.addRect(x,y,width,24,QColor('#7461bb'),QColor('#bcb0df') if en['kind']=='Zeitalter' else QColor('#7461bb'));rect.setFlag(QGraphicsItem.ItemIsSelectable);rect.setData(0,en['id']);rect.setToolTip(en['name']+' · '+cal.display(en['start'])+(' – '+cal.display(en['end']) if en['end'] else ''))
                    table.insertRow(row)
                    for col,text in enumerate([en['name'],en['kind'],cal.display(en['start']),cal.display(en['end']) if en['end'] else '']):i=QTableWidgetItem(text);i.setData(Qt.UserRole,en['id']);table.setItem(row,col,i)
                scene.setSceneRect(scene.itemsBoundingRect().adjusted(-10,-10,40,40))
            except Exception as e:self.error(e)
        scene.selectionChanged.connect(lambda:[self.open_object(i.data(0)) for i in scene.selectedItems() if i.data(0)]);table.itemDoubleClicked.connect(lambda i:self.open_object(i.data(Qt.UserRole)));l.addWidget(button('Aktualisieren',draw));draw();self.tabs.addTab(page,'Timeline');self.tabs.setCurrentWidget(page)
    def export_document(self,docs):
        doc=QTextDocument();doc.setDefaultFont(QFont('Georgia',12))
        for k,v in self.p['assets'].items():doc.addResource(QTextDocument.ImageResource,QUrl('asset:'+k),QImage.fromData(base64.b64decode(v)))
        cur=QTextCursor(doc)
        for index,o in enumerate(docs):
            if index:
                cur.insertBlock();bf=cur.blockFormat();bf.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore);cur.setBlockFormat(bf)
            cur.insertHtml(render(self.p,o['html']))
        # Remove only link marking; retain italic/bold/font and all non-link formatting.
        block=doc.begin()
        while block.isValid():
            it=block.begin()
            while not it.atEnd():
                f=it.fragment()
                if f.isValid() and f.charFormat().isAnchor():
                    cur=QTextCursor(doc);cur.setPosition(f.position());cur.setPosition(f.position()+f.length(),QTextCursor.KeepAnchor);fmt=f.charFormat();fmt.setAnchor(False);fmt.setAnchorHref('');fmt.setForeground(QColor('black'));fmt.setFontUnderline(False);cur.setCharFormat(fmt)
                it+=1
            block=block.next()
        return doc
    def printing(self):
        d=QDialog(self);d.setWindowTitle('Drucken & PDF');l=QVBoxLayout(d);l.addWidget(QLabel('Kapitel in Projekt-Reihenfolge auswählen:'));ls=QListWidget();l.addWidget(ls)
        for o in self.p['documents']:i=QListWidgetItem(o['name']);i.setFlags(i.flags()|Qt.ItemIsUserCheckable);i.setCheckState(Qt.Checked);i.setData(Qt.UserRole,o['id']);ls.addItem(i)
        printer=QPrinter(QPrinter.HighResolution);printer.setPageSize(QPageSize(QPageSize.A4));printer.setPageMargins(QMarginsF(20,20,20,20))
        def doc():
            ids=[ls.item(i).data(Qt.UserRole) for i in range(ls.count()) if ls.item(i).checkState()==Qt.Checked];return self.export_document([o for o in self.p['documents'] if o['id'] in ids])
        def preview():
            document=doc();p=QPrintPreviewDialog(printer,d);p.paintRequested.connect(document.print_);p.exec()
        def pdf():
            path,_=QFileDialog.getSaveFileName(d,'PDF speichern',self.p['name']+'.pdf','PDF (*.pdf)')
            if path:
                printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(path if path.endswith('.pdf') else path+'.pdf');doc().print_(printer);self.statusBar().showMessage('PDF exportiert: '+path)
        def print_now():
            printer.setOutputFormat(QPrinter.NativeFormat)
            if QPrintDialog(printer,d).exec():doc().print_(printer)
        for label,fn in [('Papier & Seitenränder',lambda:QPageSetupDialog(printer,d).exec()),('Druckvorschau',preview),('PDF exportieren',pdf),('Drucken',print_now)]:l.addWidget(button(label,fn))
        d.resize(500,480);d.exec()

from PySide6.QtCore import QStandardPaths

def main():
    app=QApplication(sys.argv);app.setApplicationName('Storynator');app.setStyle('Fusion')
    app.setStyleSheet('QMainWindow,QDialog{background:#f5f3f9;color:#292638} QTreeWidget,QListWidget,QTextEdit,QPlainTextEdit,QTableWidget{background:white;border:1px solid #e1ddeb;border-radius:5px;} QPushButton{padding:8px 12px;border:1px solid #ddd6e9;border-radius:5px;background:#fff;color:#423951} QPushButton:hover{background:#e7e0f4;} QTabBar::tab{padding:10px 20px;} QTabBar::tab:selected{background:white;color:#7461bb;} QToolBar{padding:5px;spacing:5px;background:#fff;} QLineEdit,QComboBox,QSpinBox{padding:5px;}')
    w=Main();w.show();sys.exit(app.exec())
if __name__=='__main__':main()

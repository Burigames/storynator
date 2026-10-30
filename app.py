import sys, json, base64, os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QSettings, QMarginsF, QSize, QEvent, QSignalBlocker
from PySide6.QtGui import QFontMetrics,QAction, QFont, QTextCharFormat, QTextCursor, QTextDocument, QImage, QTextImageFormat, QTextFormat, QTextListFormat, QColor, QPageSize, QTextBlockFormat, QFontInfo
from PySide6.QtWidgets import *
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog, QPageSetupDialog
from core import *
from i18n import tr,set_language,install_qt_translations
import printing
import addons
from addon_ui import AddonManager,export_preset
from worldview import WorldReader
import authoring,worldmodel
from manuscript_ui import print_selection_tree,selected_document_ids,ManuscriptTree,StructureDialog,ReplaceDialog,NotesDialog,RevisionsDialog,GoalsDialog
from spelling import SpellDialog,license_dialog
from world_ui import WorldBrowser,RelationshipDialog,GraphDialog
from worldlayout import fields_layout
import time
from safety import BackupStore,SearchIndex,migration_copy,project_report
from project_ui import CoversDialog,BackupDialog,IntegrityDialog,backup_preferences
from media import import_image,store_image,image_from_asset
from PySide6.QtCore import QLockFile,QSizeF,QThreadPool,QObject
from tasks import BackupTask
import copy
import logging,traceback
from timeline import TimelinePanel,TimelineCanvas
from ui import RoomyList as QListWidget, RoomyTable as QTableWidget, RoomyTree as QTreeWidget, ArrowCombo as QComboBox, ArrowFontCombo as QFontComboBox, ArrowSpin as QSpinBox, ArrowDoubleSpin as QDoubleSpinBox, FontSizeSpin
from design import icon, label, tool, primary, shadow, apply_theme, CURRENT, ACCENTS, theme_colors

TYPES=['Text','Richtext','Zahl','Checkbox','Dropdown','Mehrfachauswahl','Slider','Bild','Galerie','Datum','Zeitspanne','Verknüpfung']
FIELD_RENDERERS={}
def register_field_type(name,renderer):
    FIELD_RENDERERS[name]=renderer
    if name not in TYPES:TYPES.append(name)


def button(text,fn):
    b=QPushButton(tr(text)); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn); return b

def ask(parent,title,value=''):
    s,ok=QInputDialog.getText(parent,title,tr('Name:'),text=value); return s.strip() if ok and s.strip() else None

class Picker(QDialog):
    def __init__(self,w):
        super().__init__(w); self.setWindowTitle(tr('Eintrag verknüpfen')); self.resize(510,400); self.id=None
        lay=QVBoxLayout(self); self.search=QLineEdit(); self.search.setPlaceholderText(tr('Name suchen …')); lay.addWidget(self.search); self.list=QListWidget(); lay.addWidget(self.list)
        def refresh():
            self.list.clear()
            for position,x in enumerate(objects(w.p),1):
                if self.search.text().casefold() in x['name'].casefold():
                    cat=next((c['name'] for c in w.p['categories'] if c['id']==x.get('category')),'Timeline' if x in w.p['events'] else 'Dokument')
                    detail=re.sub('<[^>]+>',' ',x.get('html','')).strip()[:70]; i=QListWidgetItem(x['name']+'  ·  '+cat+('  ·  '+detail if detail else '  ·  Eintrag '+str(position))); i.setData(Qt.UserRole,x['id']); i.setToolTip(w.preview_html(x['id']));self.list.addItem(i)
            if self.list.count():self.list.setCurrentRow(0)
        def choose():
            if self.list.currentItem(): self.id=self.list.currentItem().data(Qt.UserRole); self.accept()
        self.list.viewport().installEventFilter(w);self.search.textChanged.connect(refresh); self.list.itemDoubleClicked.connect(choose);self.list.itemActivated.connect(choose);self.search.returnPressed.connect(choose);lay.addWidget(button('Verknüpfen',choose));refresh()

class Rich(QTextEdit):
    def __init__(self,w,obj,key='html'):
        super().__init__(); self.w=w; self.obj=obj; self.key=key; self.setAcceptRichText(True); self.setFont(QFont('Georgia',14)); self.document().setDocumentMargin(35)
        self.setAccessibleName(obj.get('name',tr('Formatierter Text')));self.setTabChangesFocus(True);self.setMinimumHeight(190);self.document().setDefaultFont(QFont('Georgia',14));self.load_assets();self.setHtml(render(w.p,obj.get(key,'')));self.setMouseTracking(True)
        self.cursorPositionChanged.connect(lambda:w.sync_format(self));self.currentCharFormatChanged.connect(lambda _:w.sync_format(self))
        self.store_timer=QTimer(self);self.store_timer.setSingleShot(True);self.store_timer.timeout.connect(self.flush);self.reload_annotations();self.textChanged.connect(self.store);self.mark_timer=QTimer(self);self.mark_timer.setSingleShot(True);self.mark_timer.timeout.connect(self.update_marks);self.textChanged.connect(lambda:self.mark_timer.start(60));self.update_marks()
    def reload_annotations(self):self.note_cursors=authoring.annotation_cursors(self.obj,self.document());self.update_marks()
    def sync_notes(self):authoring.sync_annotations(self.obj,getattr(self,'note_cursors',{}))
    def sync_links(self,lookup):
        ranges=[];block=self.document().begin()
        while block.isValid():
            it=block.begin()
            while not it.atEnd():
                fragment=it.fragment()
                if fragment.isValid() and fragment.charFormat().anchorHref().startswith('story:'):
                    href=fragment.charFormat().anchorHref();start=fragment.position();end=start+fragment.length()
                    if ranges and ranges[-1][2]==href and ranges[-1][1]==start:ranges[-1][1]=end
                    else:ranges.append([start,end,href,fragment.charFormat()])
                it+=1
            block=block.next()
        cursor=self.textCursor();changed=False
        with QSignalBlocker(self):
            for start,end,href,fmt in reversed(ranges):
                name=(lookup.get(href[6:]) or {}).get('name',tr('[Gelöschter Eintrag]'));edit=QTextCursor(self.document());edit.setPosition(start);edit.setPosition(end,QTextCursor.KeepAnchor)
                if edit.selectedText()!=name:authoring.replace_cursor(self.note_cursors,edit,name,fmt);changed=True
            self.setTextCursor(cursor)
        if changed:self.flush();self.update_marks()
    def load_assets(self):
        keys=set(re.findall(r'asset:([^\s\"<>]+)',self.obj.get(self.key,'')))
        for k in keys:
            if k in self.w.p['assets']:self.document().addResource(QTextDocument.ImageResource,QUrl('asset:'+k),image_from_asset(self.w.p,k,1600))
    def store(self):
        if self.document().characterCount()>100000:self.store_timer.start(250)
        else:self.obj[self.key]=self.toHtml()
        self.sync_notes();self.w.note_writing(self.obj);self.w.changed()
    def flush(self):
        if self.store_timer.isActive():self.store_timer.stop()
        self.obj[self.key]=self.toHtml()
    def link(self):
        cur=self.textCursor();base=QTextCharFormat(cur.charFormat());base.setAnchor(False);base.setAnchorHref('');base.setFontUnderline(cur.charFormat().fontUnderline());picker=Picker(self.w)
        if picker.exec():
            fmt=QTextCharFormat(base);fmt.setAnchor(True);fmt.setAnchorHref('story:'+picker.id)
            cur.beginEditBlock();cur.insertText(resolve(self.w.p,picker.id)['name'],fmt);cur.insertText(' ',base);cur.endEditBlock();self.setTextCursor(cur);self.setCurrentCharFormat(base);self.update_marks();self.w.sync_format(self)
    def update_marks(self):
        selections=[];block=self.document().begin();dark=CURRENT['mode']=='dark'
        while block.isValid():
            it=block.begin()
            while not it.atEnd():
                frag=it.fragment()
                if frag.isValid():
                    fmt=frag.charFormat();anchor=fmt.isAnchor() and fmt.anchorHref().startswith('story:');black=dark and fmt.hasProperty(QTextFormat.ForegroundBrush) and fmt.foreground().color().lightness()<45
                    if anchor or black:
                        sel=QTextEdit.ExtraSelection();sel.cursor=QTextCursor(self.document());sel.cursor.setPosition(frag.position());sel.cursor.setPosition(frag.position()+frag.length(),QTextCursor.KeepAnchor);sel.format.setForeground(QColor(CURRENT['link'] if anchor else '#e0e7ed'));selections.append(sel)
                it+=1
            block=block.next()
        for note in self.obj.get('annotations',[]):
            if note.get('resolved'):continue
            cursor=getattr(self,'note_cursors',{}).get(note['id'])
            if cursor and cursor.hasSelection():
                selection=QTextEdit.ExtraSelection();selection.cursor=QTextCursor(cursor);selection.format.setBackground(QColor(210,165,55,45));selections.append(selection)
        self.setExtraSelections(selections)
    def viewportEvent(self,event):
        if event.type()==QEvent.ToolTip:
            href=self.anchorAt(event.pos())
            if href.startswith('story:'):QToolTip.showText(event.globalPos(),self.w.preview_html(href[6:]),self);return True
        return super().viewportEvent(event)
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
            self.add_image(store_image(self.w.p,image))
        else: self.insertPlainText(m.text())
    def add_image(self,key):
        self.document().addResource(QTextDocument.ImageResource,QUrl('asset:'+key),image_from_asset(self.w.p,key,1600)); f=QTextImageFormat(); f.setName('asset:'+key); img=QImage.fromData(base64.b64decode(self.w.p['assets'][key])); f.setWidth(min(550,img.width())); f.setHeight(min(550,img.width())*img.height()/max(1,img.width())); self.textCursor().insertImage(f)

class TimelineView(QGraphicsView):
    def wheelEvent(self,e):
        if e.modifiers()&Qt.ControlModifier: self.scale(1.2 if e.angleDelta().y()>0 else 1/1.2,1); e.accept()
        else: super().wheelEvent(e)

class StudioTabs(QTabWidget):
    def __init__(self,owner):super().__init__(owner);self.owner=owner
    def addTab(self,*args):
        index=super().addTab(*args);self.owner.decorate_tabs();return index
    def removeTab(self,index):
        page=self.widget(index)
        if page:
            for editor in page.findChildren(Rich):
                if editor.store_timer.isActive():editor.flush()
                editor.store_timer.stop();editor.mark_timer.stop()
            if self.owner.active_editor and page.isAncestorOf(self.owner.active_editor):self.owner.active_editor=None
        super().removeTab(index)
        if page:page.deleteLater()
    def clear(self):
        with QSignalBlocker(self):
            while self.count():self.removeTab(0)

def project_for_language(name=None):
    p=new_project(name or tr('Meine Geschichte'));p['documents'][0]['name']=tr('Kapitel 1');c=p['calendar'];c['name']=tr('Weltzeit')
    for month in c['months']:month['name']=tr(month['name'])
    c['week']=[tr(day) for day in c['week']];c['units']={k:tr(v) for k,v in c['units'].items()};return p

class Main(QMainWindow):
    def __init__(self, recover=True):
        super().__init__()
        self.p=project_for_language();self.path=None;self.dirty=False;self.section='editor';self._project_lock=None;self.revision=0;self._search_revision=-1;self._syncing=False;self._writing_id=uid();self._writing_start=authoring.now();self._writing_base=0;self._writing_seconds=0;self._last_typing=None
        self.backup_pool=QThreadPool(self);self.backup_pool.setMaxThreadCount(1);self._backup_busy=False;self._closing=False
        self.status_timer=QTimer(self);self.status_timer.setSingleShot(True);self.status_timer.timeout.connect(self.update_status);self.views_timer=QTimer(self);self.views_timer.setSingleShot(True);self.views_timer.timeout.connect(self.refresh_open_views)
        self.settings=QSettings('Storynator','Storynator');self.resize(1500,960);self.setMinimumSize(800,600)
        self.setWindowIcon(icon('feather',CURRENT['link'],64))
        self.data_root=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation));self.backups=BackupStore(self.data_root/'backups',self.settings.value('backup/keep',20));self.recovery=self.data_root/'sessions'/(uid()+'.storynator');self.recovery.parent.mkdir(parents=True,exist_ok=True);self._session_lock=QLockFile(str(self.recovery)+'.lock');self._session_lock.setStaleLockTime(0);self._session_lock.tryLock(0)
        self.tabs=StudioTabs(self);self.tabs.setTabsClosable(True);self.tabs.setDocumentMode(True);self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab);self.tabs.currentChanged.connect(self.tab_changed)
        self.nav=ManuscriptTree(self);self.nav.setObjectName('projectTree');self.nav.setHeaderHidden(True);self.nav.setIndentation(14);self.nav.setAnimated(True)
        self.nav.setRootIsDecorated(False);self.nav.itemClicked.connect(lambda i,c:self.open_object(i.data(0,Qt.UserRole)) if i.data(0,Qt.UserRole) else None);self.nav.itemActivated.connect(lambda i,c:self.open_object(i.data(0,Qt.UserRole)) if i.data(0,Qt.UserRole) else None)
        self.nav.viewport().installEventFilter(self);self.nav.setContextMenuPolicy(Qt.CustomContextMenu);self.nav.customContextMenuRequested.connect(self.navigation_menu)
        sidebar=QWidget();sidebar.setObjectName('sidebar');sl=QVBoxLayout(sidebar);sl.setContentsMargins(18,18,18,14);sl.setSpacing(5)
        brand=QHBoxLayout();mark=QLabel();mark.setObjectName('brandMark');mark.setPixmap(icon('feather',CURRENT['link'],40).pixmap(36,36));brand.addWidget(mark);brand.addWidget(label('Storynator','title'));brand.itemAt(1).widget().setObjectName('brand');brand.addStretch();sl.addLayout(brand);sl.addSpacing(23)
        project=QFrame();project.setObjectName('projectCard');pl=QVBoxLayout(project);pl.setContentsMargins(15,14,15,14);pl.setSpacing(5);pl.addWidget(label('AKTUELLES PROJEKT','eyebrow'));self.project_label=label(self.p['name'],translate=False);self.project_label.setWordWrap(True);pl.addWidget(self.project_label);self.project_cover=QLabel();self.project_cover.setAlignment(Qt.AlignCenter);self.project_cover.hide();pl.addWidget(self.project_cover);sl.addWidget(project);sl.addSpacing(12)
        sl.addWidget(label('ARBEITSBEREICH','eyebrow'));sl.addSpacing(3);self.nav_buttons={}
        for section,text,name in [('editor','Editor','book'),('timeline','Timeline','timeline'),('world','Welt','world')]:
            btn=QPushButton('  '+tr(text));btn.setObjectName('navButton');btn.setCheckable(True);btn.setIcon(icon(name,'#b8c3ce'));btn.setIconSize(QSize(21,21));btn.setCursor(Qt.PointingHandCursor);btn.clicked.connect(lambda checked=False,key=section:self.navigate(key));self.nav_buttons[section]=btn;sl.addWidget(btn)
        sl.addSpacing(12);self.collection_label=label('MANUSKRIPT','eyebrow');sl.addWidget(self.collection_label);sl.addSpacing(4);sl.addWidget(self.nav,1)
        self.add_primary=button('+  Neues Kapitel',self.create_in_section);self.add_primary.setProperty('role','subtle');sl.addWidget(self.add_primary)
        self.add_secondary=button('+  Neue Kategorie',self.add_category);self.add_secondary.setProperty('role','subtle');self.add_secondary.hide();sl.addWidget(self.add_secondary);sl.addSpacing(15)
        sl.addWidget(tool('settings','Projektkalender',self.calendar,'Projektkalender'));sl.addWidget(tool('settings','Einstellungen',self.preferences,'Einstellungen'));sl.addWidget(tool('home','Startseite',self.home,'Startseite'))
        workspace=QWidget();wl=QVBoxLayout(workspace);wl.setContentsMargins(0,0,0,0);wl.setSpacing(0)
        header=QFrame();header.setObjectName('header');hl=QHBoxLayout(header);hl.setContentsMargins(28,14,26,14);hl.setSpacing(14)
        self.breadcrumb=label('DEIN SCHREIBATELIER','eyebrow');self.breadcrumb.setMinimumWidth(0);self.breadcrumb.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);hl.addWidget(self.breadcrumb);hl.addStretch()
        self.global_search=QLineEdit();self.global_search.setObjectName('globalSearch');self.global_search.setPlaceholderText(tr('Projekt durchsuchen …'));self.global_search.addAction(icon('search'),QLineEdit.LeadingPosition);self.global_search.setMinimumWidth(140);self.global_search.setMaximumWidth(280);self.global_search.returnPressed.connect(lambda:self.search(self.global_search.text()));hl.addWidget(self.global_search)
        hl.addWidget(tool('print','Drucken und als PDF exportieren · Strg+P',self.printing));self.save_button=primary('Speichern',lambda:self.save(),'save');hl.addWidget(self.save_button);wl.addWidget(header)
        self.formatbar=QFrame();self.formatbar.setObjectName('formatbar');self.format_area=QScrollArea();self.format_area.setFrameShape(QFrame.NoFrame);self.format_area.setWidgetResizable(True);self.format_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.format_area.setMinimumWidth(0);self.format_area.setFixedHeight(76);self.format_area.setWidget(self.formatbar);wl.addWidget(self.format_area);wl.addWidget(self.tabs,1)
        split=QSplitter();split.setChildrenCollapsible(False);side_scroll=QScrollArea();side_scroll.setObjectName('sidebarScroll');side_scroll.setWidgetResizable(True);side_scroll.setWidget(sidebar);side_scroll.setMinimumWidth(235);side_scroll.setMaximumWidth(330);split.addWidget(side_scroll);split.addWidget(workspace);split.setSizes([258,1242]);self.setCentralWidget(split)
        self.active_editor=None;QApplication.instance().focusChanged.connect(self.track_editor)
        self.toolbar();self.menus();self.refresh();self.home()
        self.timer=QTimer(self);self.timer.timeout.connect(self.autosave_background);self.timer.start(int(self.settings.value('backup/interval',60))*1000)
        self.install_shortcuts()
        if recover:QTimer.singleShot(100,self.check_recovery)
    def note_writing(self,obj):
        if not obj.get('id') or not any(d['id']==obj['id'] for d in self.p['documents']):return
        tick=time.monotonic()
        if self._last_typing is not None:self._writing_seconds+=min(30,tick-self._last_typing)
        self._last_typing=tick
    def record_writing_session(self):
        if not self.p.get('writing_goals',{}).get('track') or self._last_typing is None:return
        item=next((s for s in self.p.get('writing_sessions',[]) if s['id']==self._writing_id),None)
        if item is None:
            item=dict(id=self._writing_id,started=self._writing_start);self.p.setdefault('writing_sessions',[]).append(item)
        item.update(seconds=round(self._writing_seconds),words_added=sum(authoring.words(d['html']) for d in self.p['documents'])-self._writing_base)
    def recent_ids(self):
        try:return json.loads(self.settings.value('browsing/'+self.p['project_id'],'[]'))
        except (ValueError,TypeError):return []
    def remember_object(self,id):
        recent=[id]+[old for old in self.recent_ids() if old!=id];self.settings.setValue('browsing/'+self.p['project_id'],json.dumps(recent[:100]))
    def install_shortcuts(self):
        for text,key,callback in [('Suche','Ctrl+K',lambda:self.global_search.setFocus()),('Neues Kapitel','Ctrl+Shift+N',self.add_doc),('Editor','Ctrl+1',lambda:self.navigate('editor')),('Timeline','Ctrl+2',lambda:self.navigate('timeline')),('Welt','Ctrl+3',lambda:self.navigate('world')),('Tab schließen','Ctrl+W',lambda:self.close_tab(self.tabs.currentIndex())),('Nächster Tab','Ctrl+Tab',lambda:self.tabs.setCurrentIndex((self.tabs.currentIndex()+1)%max(1,self.tabs.count()))),('Vorheriger Tab','Ctrl+Shift+Tab',lambda:self.tabs.setCurrentIndex((self.tabs.currentIndex()-1)%max(1,self.tabs.count()))),('Bearbeiten','Ctrl+E',self.edit_current_world)]:
            action=QAction(tr(text),self);action.setShortcut(key);action.triggered.connect(callback);self.addAction(action)
        self.nav.setAccessibleName(tr('Projektnavigation'));self.global_search.setAccessibleName(tr('Projekt durchsuchen'));self.tabs.setAccessibleName(tr('Geöffnete Dokumente'))
    def edit_current_world(self):
        page=self.tabs.currentWidget()
        if page and getattr(page,'obj',None) in self.p['entries']:
            if getattr(page,'world_edit',False):self.refresh();self.render_world_page(page,False)
            else:self.render_world_page(page,True);editor=page.findChild(Rich);editor.setFocus() if editor else None
    def check_recovery(self):
        candidates=list((self.data_root/'sessions').glob('*.storynator'));legacy=self.data_root/'recovery.storynator'
        if legacy.exists():candidates.append(legacy)
        found=False
        for path in candidates:
            if path==self.recovery:continue
            lock=QLockFile(str(path)+'.lock');lock.setStaleLockTime(0)
            if not lock.tryLock(0):continue
            try:
                self.backups.create(load_project(path),reason='Nach unerwartetem Ende');path.unlink();found=True
            except Exception as error:logging.exception('Recovery could not be indexed');self.statusBar().showMessage(tr('Wiederherstellung fehlgeschlagen: ')+str(error))
            finally:lock.unlock()
        if found:BackupDialog(self,True).exec()
    def lock_path(self,path):
        if self.path and Path(path).resolve()==Path(self.path).resolve() and self._project_lock:return self._project_lock
        lock=QLockFile(str(Path(path).resolve())+'.lock');lock.setStaleLockTime(0)
        if not lock.tryLock(0):raise OSError(tr('Dieses Projekt ist bereits geöffnet oder der Ordner ist nicht beschreibbar. Andere Instanz schließen oder eine Kopie verwenden.'))
        return lock
    def adopt_project(self,p,path=None,lock=None):
        self.backup_pool.waitForDone();self._backup_busy=False
        if self._project_lock and self._project_lock is not lock:self._project_lock.unlock()
        self._writing_id=uid();self._writing_start=authoring.now();self._writing_base=sum(authoring.words(d['html']) for d in p['documents']);self._writing_seconds=0;self._last_typing=None
        self._project_lock=lock;self.p=p;self.path=str(path) if path else None;self.active_editor=None;self.tabs.clear();self.revision+=1;self._search_revision=-1;self.dirty=False;self.refresh();self.open_object(p['documents'][0]['id']) if p['documents'] else self.home()
        self.recovery.unlink(missing_ok=True)
    def refresh_open_views(self):
        if self._syncing:return
        self._syncing=True
        try:
            lookup={o['id']:o for o in objects(self.p)};category_lookup={c['id']:c for c in self.p['categories']}
            for i in range(self.tabs.count()):
                page=self.tabs.widget(i);obj=getattr(page,'obj',None)
                if obj:
                    self.tabs.setTabText(i,obj['name']);self.update_note_sidebar(page);heading=page.findChild(QLabel,'entryHeading')
                    if heading:heading.setText(obj['name'])
                    status=page.findChild(QComboBox,'manuscriptStatus')
                    if status:
                        with QSignalBlocker(status):status.setCurrentIndex(max(0,status.findData(obj.get('status','draft'))))
                    signature=json.dumps([obj,category_lookup.get(obj.get('category'))],ensure_ascii=False)
                    if getattr(page,'view_signature',None)!=signature or obj in self.p['entries'] and not getattr(page,'world_edit',False) and page==self.tabs.currentWidget() and getattr(page,'reference_revision',-1)!=self.revision:
                        if obj in self.p['entries'] and not getattr(page,'world_edit',False):
                            area=page.findChild(QScrollArea);scroll=area.verticalScrollBar().value() if area else 0;self.render_world_page(page,False);page.findChild(QScrollArea).verticalScrollBar().setValue(scroll)
                        page.view_signature=signature
                    for editor in page.findChildren(Rich):editor.sync_links(lookup)
                    for linked in page.findChildren(QListWidget):
                        for row in range(linked.count()):
                            item=linked.item(row);target=lookup.get(item.data(Qt.UserRole))
                            if target:item.setText(target['name'])
                    for combo in page.findChildren(QComboBox):
                        with QSignalBlocker(combo):
                            for row in range(combo.count()):
                                target=lookup.get(combo.itemData(row))
                                if target:combo.setItemText(row,target['name'])
                if hasattr(page,'timeline_refresh'):
                    signature=tuple((o['id'],o['name'],o['start'],o['end'],o['kind']) for o in self.p['events'])+((repr(self.p['calendar']),),)
                    if getattr(page,'timeline_signature',None)!=signature:page.timeline_refresh();page.timeline_signature=signature
            page=self.tabs.currentWidget()
            if hasattr(page,'refresh_data'):page.refresh_data()
            elif getattr(page,'world_page',False):self.show_world()
        finally:self._syncing=False
    def close_tab(self,index):
        if index<0:return
        page=self.tabs.widget(index)
        for editor in page.findChildren(Rich) if page else []:editor.flush()
        page=self.tabs.widget(index);self.tabs.removeTab(index)
        if page and self.active_editor and page.isAncestorOf(self.active_editor):self.active_editor=None
        if page:page.deleteLater()
        if not self.tabs.count():self.home()
    def navigation_menu(self,pos):
        item=self.nav.itemAt(pos)
        if not item or not item.data(0,Qt.UserRole):return
        self.nav.setCurrentItem(item);menu=QMenu(self)
        for text,fn in [('Öffnen',lambda:self.open_object(item.data(0,Qt.UserRole))),('Umbenennen',self.rename),('Nach oben',lambda:self.move(-1)),('Nach unten',lambda:self.move(1)),('Löschen',self.delete)]:menu.addAction(tr(text)).triggered.connect(fn)
        menu.exec(self.nav.viewport().mapToGlobal(pos))
    def tab_changed(self,index):
        self.decorate_tabs()
        page=self.tabs.widget(index)
        if page:
            section=getattr(page,'section','editor');self.set_section(section)
            if getattr(page,'obj',None):
                self.select_navigation(page.obj['id']);self.breadcrumb.setText((tr('MANUSKRIPT') if section=='editor' else tr('DEINE WELT') if section=='world' else 'TIMELINE')+'   /   '+page.obj['name'])
        self.update_status();self.sync_format();self.adjust_layout()
        if hasattr(self,'views_timer') and not self._syncing:self.views_timer.start(100)
    def decorate_tabs(self):
        for i in range(self.tabs.count()):
            bar=self.tabs.tabBar();existing=bar.tabButton(i,QTabBar.RightSide)
            if existing and existing.objectName()=='tabClose':continue
            page=self.tabs.widget(i);close=QToolButton();close.setObjectName('tabClose');close.setText('×');close.setToolTip(tr('Tab schließen'));close.setAccessibleName(tr('Tab schließen'));close.setFocusPolicy(Qt.StrongFocus);close.setFixedSize(20,20);close.clicked.connect(lambda checked=False,p=page:self.close_tab(self.tabs.indexOf(p)));bar.setTabButton(i,QTabBar.RightSide,close)
    def set_section(self,section):
        self.section=section
        for key,b in self.nav_buttons.items():b.setChecked(key==section)
        for i in range(self.nav.topLevelItemCount()):self.nav.topLevelItem(i).setHidden(i!={'editor':0,'world':1,'timeline':2}[section])
        self.collection_label.setText({'editor':tr('MANUSKRIPT'),'world':tr('KATEGORIEN & EINTRÄGE'),'timeline':tr('EREIGNISSE & ZEITALTER')}[section]);self.add_primary.setText({'editor':tr('+  Neues Kapitel'),'world':tr('+  Neuer Eintrag'),'timeline':tr('+  Neues Ereignis')}[section]);self.add_secondary.setVisible(section=='world');self.formatbar.setVisible(section=='editor' or bool(self.current()) and (section!='world' or getattr(self.tabs.currentWidget(),'world_edit',False)));self.format_area.setVisible(not self.formatbar.isHidden())
    def navigate(self,section):
        self.set_section(section)
        if section=='timeline':self.show_timeline()
        elif section=='world':self.show_world()
        else:
            for i in range(self.tabs.count()):
                if getattr(self.tabs.widget(i),'obj',{}) in self.p['documents']:self.tabs.setCurrentIndex(i);return
            if self.p['documents']:self.open_object(self.p['documents'][0]['id'])
            else:self.add_doc()
    def create_in_section(self):
        {'editor':self.add_doc,'world':self.add_entry,'timeline':self.add_event}[self.section]()
    def error(self,e):
        logging.error('Storynator operation failed: %s',e)
        message=tr(str(e))
        if isinstance(e,PermissionError):message=tr('Zugriff verweigert. Datei schließen oder in einen beschreibbaren Ordner speichern. Der bisherige Projektstand bleibt erhalten.')
        elif isinstance(e,FileNotFoundError):message=tr('Datei nicht gefunden. Pfad prüfen oder einen Sicherungsstand öffnen.')
        QMessageBox.warning(self,'Storynator',message)
    def changed(self):
        self.dirty=True;self.revision+=1;self.setWindowTitle('● '+self.p['name']+' — Storynator');self.status_timer.start(180);self.views_timer.start(650)
    def update_status(self):
        self.setWindowTitle(('● ' if self.dirty else '')+self.p['name']+' — Storynator')
        if hasattr(self,'project_label'):self.project_label.setText(self.p['name'])
        if hasattr(self,'project_cover'):
            key=self.p.get('covers',{}).get('project','');signature=(self.p['project_id'],key)
            if getattr(self,'_cover_signature',None)!=signature:
                self._cover_signature=signature;image=image_from_asset(self.p,key,90);self.project_cover.setPixmap(__import__('PySide6.QtGui',fromlist=['QPixmap']).QPixmap.fromImage(image));self.project_cover.setVisible(not image.isNull())
        e=self.editor();words=0
        if e:
            revision=e.document().revision()
            if getattr(e,'word_revision',None)!=revision:e.word_total=len(e.toPlainText().split());e.word_revision=revision
            words=e.word_total
        self.statusBar().showMessage('   '+(tr('Ungespeicherte Änderungen') if self.dirty else tr('Alle Änderungen gespeichert'))+'   ·   '+tr('Lokal & offline'))
        if not hasattr(self,'word_count'):
            self.word_count=label('','muted');self.statusBar().addPermanentWidget(self.word_count)
        self.word_count.setText((str(words)+' '+tr('Wörter')+'   ·   ' if e else '')+'Storynator   ')
    def refresh(self):
        selected=self.selected() if hasattr(self,'nav') else None;self.nav.setUpdatesEnabled(False);self.nav.clear();by_category={}
        for entry in self.p['entries']:by_category.setdefault(entry['category'],[]).append(entry)
        for title,seq in [('Editor',authoring.ordered_documents(self.p)),('Welt',addons.visible_categories(self.p)),('Timeline',self.p['events'])]:
            root=QTreeWidgetItem([{'Editor':tr('Alle Kapitel'),'Welt':tr('Deine Kategorien'),'Timeline':tr('Alle Ereignisse')}[title]]); self.nav.addTopLevelItem(root)
            doc_items={}
            for o in seq:
                item=QTreeWidgetItem([o['name']]);item.setIcon(0,icon('file' if title=='Editor' else 'folder' if title=='Welt' else 'timeline',theme_colors(CURRENT['mode'],CURRENT['accent'])['muted'],18)); item.setData(0,Qt.UserRole,o['id']);item.setToolTip(0,html.escape(o['name']));parent_item=doc_items.get(o.get('parent')) if title=='Editor' else None
                if parent_item:parent_item.addChild(item)
                else:root.addChild(item)
                if title=='Editor':doc_items[o['id']]=item
                if title=='Welt':
                    for en in by_category.get(o['id'],[]):
                        if True:
                            sub=QTreeWidgetItem([en['name']]);sub.setIcon(0,icon('user',theme_colors(CURRENT['mode'],CURRENT['accent'])['muted'],18));sub.setData(0,Qt.UserRole,en['id']);sub.setToolTip(0,html.escape(en['name'])); item.addChild(sub)
        self.nav.expandAll();self.nav.setUpdatesEnabled(True);self.select_navigation(selected);self.set_section(self.section);self.update_status()
    def menus(self):
        m=self.menuBar().addMenu(tr('Projekt'))
        for name,fn,key in [('Neu',self.new,'Ctrl+N'),('Öffnen',self.open_file,'Ctrl+O'),('Speichern',self.save,'Ctrl+S'),('Speichern unter',lambda:self.save(True),'Ctrl+Shift+S'),('Startseite',self.home,''),('Druckvorschau / PDF',self.printing,'Ctrl+P')]:
            a=m.addAction(tr(name)); a.triggered.connect(fn); a.setShortcut(key)
        for text,callback in [('Projekt & Buchcover',lambda:CoversDialog(self).exec()),('Sicherungen & Wiederherstellung',lambda:BackupDialog(self).exec()),('Sicherungseinstellungen',lambda:backup_preferences(self)),('Projekt prüfen & bereinigen',lambda:IntegrityDialog(self).exec())]:m.addAction(tr(text),callback)
        m=self.menuBar().addMenu(tr('Manuskript'))
        for text,callback in [('Teil anlegen',lambda:self.add_manuscript_item('part')),('Szene anlegen',lambda:self.add_manuscript_item('scene')),('Struktur & Status',lambda:StructureDialog(self).exec()),('Suchen & Ersetzen',lambda:ReplaceDialog(self).exec()),('Schreibziele & Statistik',lambda:GoalsDialog(self).exec()),('Kommentare & Lesezeichen',lambda:NotesDialog(self).exec()),('Kapitelstände',lambda:RevisionsDialog(self).exec()),('Offline-Rechtschreibung',lambda:SpellDialog(self).exec())]:m.addAction(tr(text),callback)
        m=self.menuBar().addMenu(tr('Welt'))
        m.addAction(tr('Beziehungen'),lambda:RelationshipDialog(self,(self.current() or {}).get('id')).exec());m.addAction(tr('Beziehungsgraph'),lambda:GraphDialog(self,(self.current() or {}).get('id')).exec())
        m=self.menuBar().addMenu(tr('Eintrag'))
        for name,fn in [('Umbenennen',self.rename),('Löschen',self.delete),('Nach oben',lambda:self.move(-1)),('Nach unten',lambda:self.move(1))]:m.addAction(tr(name)).triggered.connect(fn)
        m=self.menuBar().addMenu(tr('Ansicht'));m.addAction(tr('Einstellungen'),self.preferences);m.addAction('Editor',lambda:self.navigate('editor'));m.addAction('Timeline',lambda:self.navigate('timeline'));m.addAction(tr('Welt'),lambda:self.navigate('world'));m.addAction(tr('Projektkalender'),self.calendar)
        a=m.addAction(tr('Fokusmodus'));a.setShortcut('F11');a.triggered.connect(self.toggle_focus)
        from community_ui import CommunityDialog
        m=self.menuBar().addMenu('Addon');m.addAction(tr('Addons verwalten'),lambda:AddonManager(self).exec());m.addAction(tr('Kategorien als Preset exportieren'),lambda:export_preset(self));m.addAction(tr('Community · Bibliothek & Austausch'),lambda:CommunityDialog(self).exec())
        m=self.menuBar().addMenu(tr('Hilfe'));m.addAction(tr('Lizenzen & Quellen'),lambda:license_dialog(self))
    def select_navigation(self,id):
        iterator=QTreeWidgetItemIterator(self.nav)
        while iterator.value():
            item=iterator.value()
            if item.data(0,Qt.UserRole)==id:self.nav.setCurrentItem(item);break
            iterator+=1
    def current(self):
        w=self.tabs.currentWidget(); return getattr(w,'obj',None)
    def track_editor(self,old,new):
        if isinstance(new,Rich):self.active_editor=new;self.sync_format(new)
    def editor(self):
        focus=QApplication.focusWidget()
        if isinstance(focus,Rich) and self.tabs.currentWidget() and self.tabs.currentWidget().isAncestorOf(focus):return focus
        page=self.tabs.currentWidget()
        if page and self.active_editor and page.isAncestorOf(self.active_editor):return self.active_editor
        return page.findChild(Rich) if page else None
    def sync_format(self,editor=None):
        if not hasattr(self,'font_control'):return
        editor=editor or self.editor()
        if not editor:return
        if self.tabs.currentWidget() and not self.tabs.currentWidget().isAncestorOf(editor):return
        font=editor.currentFont();size=font.pointSizeF() or editor.document().defaultFont().pointSizeF()
        blockers=[QSignalBlocker(self.font_control),QSignalBlocker(self.size_control)];self.font_control.setCurrentFont(font);self.size_control.setValue(size if size>0 else 14)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.ToolTip:
            id=obj.property('entryId');view=obj.parent()
            if isinstance(view,QTreeWidget):
                item=view.itemAt(event.pos());id=item.data(0,Qt.UserRole) if item else None
            elif isinstance(view,(QListWidget,QTableWidget)):
                item=view.itemAt(event.pos());id=item.data(Qt.UserRole) if item else None
            if id:QToolTip.showText(event.globalPos(),self.preview_html(id),obj);return True
        return super().eventFilter(obj,event)
    def preview_html(self,id):
        o=resolve(self.p,id)
        if not o:return '<p>'+tr('[Gelöschter Eintrag]')+'</p>'
        category=next((c['name'] for c in self.p['categories'] if c['id']==o.get('category')),tr('Timeline') if o in self.p['events'] else tr('Dokument'))
        d=QTextDocument();d.setHtml(render(self.p,o.get('html','')));text=d.toPlainText().strip();text=(text[:450]+'…') if len(text)>450 else text
        details=[]
        if o in self.p['events']:details.append(o['start']+(' – '+o['end'] if o['end'] else ''))
        for f in next((c['fields'] for c in self.p['categories'] if c['id']==o.get('category')),[]):
            value=o.get('values',{}).get(f['id'])
            if value is not None and f['type'] in ['Text','Zahl','Dropdown']:details.append(f['name']+': '+str(value))
        return '<div style="white-space:normal;width:340px"><b>'+html.escape(o['name'])+'</b><br/><small>'+html.escape(category)+'</small><p>'+html.escape(text or '—')+'</p>'+ '<br/>'.join(html.escape(x) for x in details[:3])+'</div>'
    def preferences(self):
        d=QDialog(self);d.setWindowTitle(tr('Einstellungen'));form=QFormLayout(d);form.setContentsMargins(24,24,24,24);form.setVerticalSpacing(18)
        mode=QComboBox();mode.setObjectName('themeMode');mode.addItem(tr('Hell'),'light');mode.addItem(tr('Dunkel'),'dark');mode.setCurrentIndex(mode.findData(self.settings.value('appearance/mode','light')))
        accent=QComboBox();accent.setObjectName('accentChoice')
        for key,name in [('forest','Wald'),('ocean','Ozean'),('lavender','Lavendel'),('amber','Bernstein'),('rose','Rose')]:accent.addItem(icon('world',ACCENTS[key][1]),tr(name),key)
        accent.setCurrentIndex(accent.findData(self.settings.value('appearance/accent','forest')))
        language=QComboBox();language.setObjectName('languageChoice');language.addItem('Deutsch','de');language.addItem('English','en');language.setCurrentIndex(language.findData(self.settings.value('language','de')))
        form.addRow(tr('Erscheinungsbild'),mode);form.addRow(tr('Akzentfarbe'),accent);form.addRow(tr('Sprache'),language);notice=label(tr('Die Sprache wird beim nächsten Start angewendet.'),'muted');notice.setWordWrap(True);form.addRow(notice)
        def apply():
            self.settings.setValue('appearance/mode',mode.currentData());self.settings.setValue('appearance/accent',accent.currentData());self.settings.setValue('language',language.currentData());self.settings.sync();apply_theme(QApplication.instance(),mode.currentData(),accent.currentData())
            for editor in self.findChildren(Rich):editor.update_marks()
            for view in self.findChildren(TimelineView):
                view.scene().setBackgroundBrush(QApplication.palette().base())
                for item in view.scene().items():
                    if isinstance(item,QGraphicsTextItem):item.setDefaultTextColor(QApplication.palette().text().color())
            d.accept()
        form.addRow(primary(tr('Übernehmen'),apply));d.resize(440,300);d.exec()
    def fmt(self,method,value):
        e=self.editor()
        if e:
            f=QTextCharFormat();getattr(f,method)(value);e.mergeCurrentCharFormat(f);e.setFocus()
    def toolbar(self):
        bar=QHBoxLayout(self.formatbar);bar.setContentsMargins(24,9,24,9);bar.setSpacing(4)
        def sep():
            f=QFrame();f.setFrameShape(QFrame.VLine);f.setStyleSheet('color:'+theme_colors(CURRENT['mode'],CURRENT['accent'])['border']+';');bar.addSpacing(8);bar.addWidget(f);bar.addSpacing(8)
        style=QComboBox();style.setProperty('translateItems',True);style.addItems(['Absatz','Überschrift 1','Überschrift 2','Aufzählung','Nummeriert']);style.setFixedWidth(145);style.activated.connect(self.paragraph);bar.addWidget(style);sep()
        font=QFontComboBox();self.font_control=font;font.setToolTip(tr('Schriftart'));font.setCurrentFont(QFont('Georgia'));font.setFixedWidth(158);font.currentFontChanged.connect(lambda f:self.fmt('setFontFamilies',[f.family()]));bar.addWidget(font)
        size=FontSizeSpin();self.size_control=size;size.setToolTip(tr('Schriftgröße'));size.setAccessibleName(tr('Schriftgröße'));size.setRange(6,96);size.setValue(14);size.setFixedWidth(85);size.valueChanged.connect(lambda v:self.fmt('setFontPointSize',v));bar.addWidget(size);sep()
        for text,tip,method,value in [('B','Fett','setFontWeight',None),('I','Kursiv','setFontItalic',None),('U','Unterstrichen','setFontUnderline',None)]:
            b=QToolButton();b.setText(text);b.setToolTip(tr(tip));b.setFocusPolicy(Qt.StrongFocus);b.setAccessibleName(b.toolTip());f=QFont('Georgia',12);f.setBold(text=='B');f.setItalic(text=='I');f.setUnderline(text=='U');b.setFont(f)
            def toggle(checked=False,t=text):
                e=self.editor()
                if e:self.fmt('setFontWeight',QFont.Normal if e.fontWeight()==QFont.Bold else QFont.Bold) if t=='B' else self.fmt('setFontItalic',not e.fontItalic()) if t=='I' else self.fmt('setFontUnderline',not e.fontUnderline())
            b.clicked.connect(toggle);bar.addWidget(b)
        b=QToolButton();b.setText('A');b.setToolTip(tr('Textfarbe'));b.setFocusPolicy(Qt.StrongFocus);b.setAccessibleName(b.toolTip());b.clicked.connect(self.color);bar.addWidget(b);sep()
        for name,align,tip in [('left',Qt.AlignLeft,'Linksbündig'),('center',Qt.AlignHCenter,'Zentriert'),('right',Qt.AlignRight,'Rechtsbündig'),('justify',Qt.AlignJustify,'Blocksatz')]:bar.addWidget(tool(name,tip,lambda checked=False,a=align:self.editor() and self.editor().setAlignment(a)))
        sep();bar.addWidget(tool('image','Bild einfügen',self.image));bar.addWidget(tool('link','Eintrag verknüpfen · @',lambda:self.editor() and self.editor().link()));bar.addWidget(tool('break','Seitenumbruch einfügen',self.pagebreak));bar.addStretch()
        bar.addWidget(tool('undo','Rückgängig · Strg+Z',lambda:self.editor() and self.editor().undo()));bar.addWidget(tool('redo','Wiederholen · Strg+Y',lambda:self.editor() and self.editor().redo()));bar.addWidget(tool('focus','Fokusmodus · F11',self.toggle_focus))
    def resizeEvent(self,event):
        super().resizeEvent(event);self.adjust_layout()
    def adjust_layout(self):
        if not hasattr(self,'tabs') or not self.centralWidget():return
        sidebar=self.centralWidget().widget(0)
        for context in self.tabs.findChildren(QFrame,'context'):context.setVisible(self.width()>=1150 and not sidebar.isHidden())
    def toggle_focus(self):
        sidebar=self.centralWidget().widget(0);visible=not sidebar.isVisible();sidebar.setVisible(visible)
        page=self.tabs.currentWidget()
        if page:
            context=page.findChild(QFrame,'context')
            if context:context.setVisible(visible)
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
            path,_=QFileDialog.getOpenFileName(self,tr('Bild einbetten'),'','Bilder (*.png *.jpg *.jpeg *.webp *.bmp)')
            if path:
                try:e.add_image(import_image(self.p,path))
                except (OSError,ValueError) as error:self.error(error)
    def pagebreak(self):
        e=self.editor()
        if e:
            cur=e.textCursor();cur.insertBlock();f=cur.blockFormat();f.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore);cur.setBlockFormat(f)
    def home(self):
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i),'home_page',False):self.tabs.setCurrentIndex(i);return
        page=QWidget();page.home_page=True;page.section='editor';root=QVBoxLayout(page);root.setContentsMargins(0,0,0,0);area=QScrollArea();area.setWidgetResizable(True);content=QWidget();area.setWidget(content);root.addWidget(area);outer=QVBoxLayout(content);outer.setContentsMargins(45,34,45,35);outer.setSpacing(24)
        intro=QHBoxLayout();intro.addWidget(label('DEIN PERSÖNLICHES SCHREIBATELIER','eyebrow'));intro.addStretch();intro.addWidget(label('Offline. Unabhängig. Dein.','muted'));outer.addLayout(intro)
        hero=QFrame();hero.setObjectName('hero');h=QHBoxLayout(hero);h.setContentsMargins(42,38,38,38);text=QVBoxLayout();text.setSpacing(18);text.addWidget(label('Raum für deine\nnächste große Geschichte.','serif'));subtitle=label('Ein Ort für deine Worte, deine Figuren und die Welt dazwischen.');subtitle.setWordWrap(True);text.addWidget(subtitle)
        actions=QHBoxLayout();actions.addWidget(primary('Neues Projekt',self.new,'plus'));actions.addWidget(button('Projekt öffnen',self.open_file));actions.addStretch();text.addLayout(actions);h.addLayout(text,1)
        art=QLabel();art.setObjectName('heroMark');art.setPixmap(icon('feather',CURRENT['link'],180).pixmap(180,180));h.addWidget(art);outer.addWidget(hero)
        outer.addWidget(label('ZULETZT GEÖFFNET','eyebrow'));recent=self.settings.value('recent',[],type=list)
        valid=[path for path in recent if Path(path).exists()]
        if not valid:
            card=QFrame();card.setObjectName('card');cl=QHBoxLayout(card);cl.setContentsMargins(22,20,22,20);cl.addWidget(label('Deine Geschichten warten auf dich.'));cl.addStretch();cl.addWidget(button('Beispiel entdecken',self.open_example));outer.addWidget(card)
        for path in valid[:5]:
            card=QFrame();card.setObjectName('card');cl=QHBoxLayout(card);cl.setContentsMargins(22,17,22,17);mark=QLabel();mark.setPixmap(icon('book',CURRENT['link'],30).pixmap(30,30));cl.addWidget(mark);cl.addSpacing(12);details=QVBoxLayout();details.addWidget(label(Path(path).stem,translate=False));details.addWidget(label(str(Path(path).parent),'muted'));cl.addLayout(details);cl.addStretch();cl.addWidget(button('Öffnen',lambda checked=False,p=path:self.open_file(p)));card.setCursor(Qt.PointingHandCursor);card.mouseReleaseEvent=lambda event,p=path:self.open_file(p);outer.addWidget(card)
        outer.addStretch();foot=QHBoxLayout()
        for name,title,desc in [('book','Schreibe deine Geschichte','Ein ruhiger Platz für jedes Kapitel.'),('world','Erschaffe deine Welt','Figuren, Orte und ihre Verbindungen.'),('timeline','Verbinde die Ereignisse','Dein Kalender. Deine Geschichte.')]:
            box=QVBoxLayout();row=QHBoxLayout();im=QLabel();im.setPixmap(icon(name,CURRENT['link'],23).pixmap(23,23));row.addWidget(im);row.addWidget(label(title));row.addStretch();box.addLayout(row);box.addWidget(label(desc,'muted'));foot.addLayout(box)
        outer.addLayout(foot);self.tabs.addTab(page,tr('Willkommen'));self.tabs.setCurrentWidget(page);self.breadcrumb.setText(tr('DEIN SCHREIBATELIER'));self.formatbar.hide();self.format_area.hide()
    def open_example(self):
        if not self.guard():return
        try:
            p=load_project(Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'Beispiel.storynator');p['project_id']=uid();self.adopt_project(p);self.changed()
        except Exception as error:self.error(error)
    def show_world(self):
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i),'world_page',False):self.tabs.setCurrentIndex(i);self.tabs.widget(i).refresh_data();return
        page=WorldBrowser(self);self.tabs.addTab(page,tr('Deine Welt'));self.tabs.setCurrentWidget(page);self.breadcrumb.setText(tr('DEINE WELT'))
    def guard(self):
        if not self.dirty:return True
        r=QMessageBox.question(self,tr('Ungespeicherte Änderungen'),tr('Änderungen speichern?'),QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        return self.save() if r==QMessageBox.Save else r==QMessageBox.Discard
    def new(self):
        if not self.guard():return
        name=ask(self,'Neues Projekt')
        if name:self.adopt_project(project_for_language(name));self.changed()
    def open_file(self,path=None):
        if not self.guard():return
        if not isinstance(path,str):path=QFileDialog.getOpenFileName(self,tr('Projekt öffnen'),'','Storynator (*.storynator *.bak)')[0]
        if not path:return
        lock=None
        try:
            lock=self.lock_path(path);p=load_project(path);Calendar(p['calendar']).validate();copy=migration_copy(path);self.adopt_project(p,path,lock);self.remember(path)
            if copy:self.changed();self.statusBar().showMessage(tr('Format aktualisiert. Original gesichert: ')+str(copy),12000)
        except Exception as e:
            if lock and lock is not self._project_lock:lock.unlock()
            self.error(e)
    def remember(self,path):
        recent=self.settings.value('recent',[],type=list);self.settings.setValue('recent',([str(path)]+[p for p in recent if p!=str(path)])[:10])
    def save(self,as_new=False):
        self.flush_editors();self.record_writing_session();self.backup_pool.waitForDone();self._backup_busy=False
        path=self.path
        if as_new or not path:path=QFileDialog.getSaveFileName(self,tr('Projekt speichern'),path or self.p['name']+'.storynator','Storynator (*.storynator)')[0]
        if not path:return False
        if not path.endswith('.storynator'):path+='.storynator'
        lock=None
        try:
            Path(path).parent.mkdir(parents=True,exist_ok=True);lock=self.lock_path(path)
            if Path(path).exists():
                migration_copy(path);previous=load_project(path);self.backups.create(previous,path,'Vor Speichern')
            save_project(self.p,path)
            if self._project_lock and self._project_lock is not lock:self._project_lock.unlock()
            self._project_lock=lock;self.path=path;self.dirty=False;self.remember(path);self.update_status();self.recovery.unlink(missing_ok=True)
            try:self.backups.create(self.p,path,'Gespeichert')
            except Exception as error:self.statusBar().showMessage(tr('Projekt gespeichert; zusätzliche Sicherung fehlgeschlagen: ')+str(error),15000)
            return True
        except Exception as e:
            if lock and lock is not self._project_lock:lock.unlock()
            self.error(e);return False
    def flush_editors(self):
        for editor in self.tabs.findChildren(Rich):
            if editor.store_timer.isActive():editor.flush()
    def autosave_background(self):
        self.flush_editors()
        if not self.dirty or self._backup_busy:return
        self.record_writing_session();snapshot=copy.deepcopy(self.p);source=self.path;recovery=self.recovery;store=self.backups
        def work():save_project(snapshot,recovery);store.create(snapshot,source,'Automatisch')
        self._backup_busy=True;self._backup_job=BackupTask(work);self._backup_job.signals.done.connect(self.backup_finished);self.backup_pool.start(self._backup_job)
    def backup_finished(self,error):
        self._backup_busy=False
        if error and not self._closing:self.statusBar().showMessage(tr('Wiederherstellung fehlgeschlagen: ')+error,15000)
    def autosave(self):
        self.flush_editors();self.record_writing_session();self.backup_pool.waitForDone();self._backup_busy=False
        if self.dirty:
            try:save_project(self.p,self.recovery);self.backups.create(self.p,self.path,'Automatisch')
            except Exception as e:self.statusBar().showMessage(tr('Wiederherstellung fehlgeschlagen: ')+str(e),15000);logging.exception('Automatic backup failed')
    def closeEvent(self,e):
        if self.guard():
            self._closing=True;self.timer.stop();self.views_timer.stop();self.status_timer.stop();self.backup_pool.waitForDone();self.recovery.unlink(missing_ok=True)
            if self._project_lock:self._project_lock.unlock();self._project_lock=None
            for editor in self.findChildren(Rich):editor.store_timer.stop();editor.mark_timer.stop();editor.note_cursors.clear()
            self.active_editor=None
            for view in self.findChildren(QGraphicsView):view.setScene(None)
            for scene in self.findChildren(QGraphicsScene):scene.clear()
            self._session_lock.unlock();e.accept()
        else:e.ignore()
    def add_doc(self):self.add_manuscript_item('chapter')
    def add_manuscript_item(self,kind):
        name=ask(self,tr(authoring.KINDS[kind])+' · '+tr('Name:'))
        if not name:return
        selected=resolve(self.p,self.selected());parent=selected['id'] if selected in self.p['documents'] and selected.get('kind','chapter')!='scene' and (kind=='scene' or selected.get('kind')=='part') else selected.get('parent') if selected in self.p['documents'] else None
        item=dict(id=uid(),name=name,html='',kind=kind,parent=parent,status='draft');self.p['documents'].append(item);self.p['documents']=authoring.ordered_documents(self.p);self.changed();self.refresh();self.open_object(item['id'])
    def add_category(self):
        name=ask(self,'Kategorie erstellen')
        if name:c=dict(id=uid(),name=name,fields=[]);self.p['categories'].append(c);self.changed();self.refresh();self.template(c)
    def add_entry(self):
        categories=[c for c in self.p['categories'] if addons.active_category(self.p,c)]
        if not categories:self.add_category();categories=[c for c in self.p['categories'] if addons.active_category(self.p,c)]
        if not categories:return
        names=[]
        for cat in categories:
            name=cat['name'];count=1
            while name in names:count+=1;name=cat['name']+' ('+str(count)+')'
            names.append(name)
        name,ok=QInputDialog.getItem(self,tr('Kategorie'),tr('Kategorie:'),names,0,False)
        if ok:
            cat=categories[names.index(name)];name=ask(self,tr('Eintrag erstellen'))
            if name:
                o=dict(id=uid(),name=name,category=cat['id'],values={},links=[],html='');self.p['entries'].append(o);self.changed();self.refresh();self.open_object(o['id']);page=self.tabs.currentWidget();self.render_world_page(page,True)
    def selected(self):
        i=self.nav.currentItem();return i.data(0,Qt.UserRole) if i else (self.current() or {}).get('id')
    def rename(self):
        self.flush_editors()
        id=self.selected();o=resolve(self.p,id) or next((c for c in self.p['categories'] if c['id']==id),None)
        if not o:return
        name=ask(self,'Umbenennen',o['name'])
        if name:
            o['name']=name;lookup={item['id']:item for item in objects(self.p)}
            for en in objects(self.p):
                if en.get('annotations'):authoring.reconcile_doc_links(en,lookup)
                if 'html' in en:en['html']=render(self.p,en['html'],lookup)
                for f,v in en.get('values',{}).items():
                    if isinstance(v,str) and 'story:' in v:en['values'][f]=render(self.p,v,lookup)
            for i in range(self.tabs.count()):
                page=self.tabs.widget(i)
                for e in page.findChildren(Rich):e.sync_links(lookup)
                for ls in page.findChildren(QListWidget):
                    for j in range(ls.count()):
                        target=resolve(self.p,ls.item(j).data(Qt.UserRole))
                        if target:ls.item(j).setText(target['name']);ls.item(j).setToolTip(self.preview_html(target['id']))
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
                if QMessageBox.question(self,tr('Kategorie löschen'),tr('Leere Kategorie und Vorlage löschen?'))==QMessageBox.Yes:self.p['categories'].remove(cat);self.changed();self.refresh()
            return
        refs=references(self.p,id);message=tr('Eintrag löschen?')+'\n'+o['name']
        if refs:message+=tr('\nVorhandene Verweise in: ')+', '.join(refs)+tr('\nSie bleiben als gelöschte Verweise erkennbar.')
        if QMessageBox.question(self,tr('Löschen'),message)!=QMessageBox.Yes:return
        for child in self.p['documents']:
            if child.get('parent')==id:child['parent']=o.get('parent')
        for seq in [self.p['entries'],self.p['events'],self.p['documents']]:
            if o in seq:seq.remove(o)
        for i in reversed(range(self.tabs.count())):
            if getattr(self.tabs.widget(i),'obj',{}).get('id')==id:self.tabs.removeTab(i)
        self.changed();self.refresh()
    def move(self,delta):
        id=self.selected()
        if any(doc['id']==id for doc in self.p['documents']):
            if authoring.move_sibling(self.p,id,delta):self.changed();self.refresh()
            return
        for seq in [self.p['documents'],self.p['entries'],self.p['categories']]:
            for i,o in enumerate(seq):
                if o['id']==id and 0<=i+delta<len(seq):seq[i],seq[i+delta]=seq[i+delta],seq[i];self.changed();self.refresh();return
    def search(self,text):
        self.flush_editors()
        if self._search_revision!=self.revision:self.search_index=SearchIndex(self.p);self._search_revision=self.revision
        d=QDialog(self);d.setWindowTitle(tr('Suchergebnisse'));l=QVBoxLayout(d);query=QLineEdit(text);query.setAccessibleName(tr('Suchbegriff'));l.addWidget(query);ls=QListWidget();ls.viewport().installEventFilter(self);l.addWidget(ls);count=QLabel();l.addWidget(count)
        def refresh():
            results=self.search_index.search(query.text());ls.clear()
            for id,name in results[:500]:item=QListWidgetItem(name);item.setData(Qt.UserRole,id);ls.addItem(item)
            count.setText(str(len(results))+' '+tr('Treffer')+(' · '+tr('Erste 500 anzeigen; Suche eingrenzen.') if len(results)>500 else ''))
            if ls.count():ls.setCurrentRow(0)
        def choose():
            if ls.currentItem():self.open_object(ls.currentItem().data(Qt.UserRole));d.accept()
        debounce=QTimer(d);debounce.setSingleShot(True);debounce.timeout.connect(refresh);query.textChanged.connect(lambda _:debounce.start(150));ls.itemDoubleClicked.connect(choose);ls.itemActivated.connect(choose);query.returnPressed.connect(choose);l.addWidget(primary(tr('Öffnen'),choose));refresh();d.resize(620,500);d.exec()
    def open_object(self,id):
        cat=next((c for c in self.p['categories'] if c['id']==id),None)
        if cat:self.template(cat);return
        o=resolve(self.p,id)
        if o:
            self.remember_object(id)
            if o.get('annotations'):authoring.reconcile_doc_links(o,{item['id']:item for item in objects(self.p)})
        if o and o in self.p['entries'] and not any(c['id']==o['category'] for c in self.p['categories']):self.error('Kategorie fehlt. Projekt prüfen und eine Sicherung öffnen.');return
        if not o:self.error('Dieser Eintrag wurde gelöscht.');return
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i),'obj',{}).get('id')==id:
                page=self.tabs.widget(i)
                if o in self.p['entries'] and not getattr(page,'world_edit',False):self.render_world_page(page,False)
                self.tabs.setCurrentIndex(i);return
        page=QWidget();page.obj=o;page.section='editor' if o in self.p['documents'] else 'timeline' if o in self.p['events'] else 'world'
        l=QVBoxLayout(page);l.setContentsMargins(0,0,0,0);l.setSpacing(0)
        if o in self.p['documents']:
            body=QHBoxLayout();body.setContentsMargins(25,24,0,18);body.setSpacing(25)
            canvas=QWidget();canvas_l=QVBoxLayout(canvas);canvas_l.setContentsMargins(0,0,0,0);canvas_l.setSpacing(13)
            meta=QHBoxLayout();meta.addWidget(label('MANUSKRIPT  /  '+str(self.p['documents'].index(o)+1).zfill(2),'eyebrow'));meta.addStretch();status=QComboBox();status.setObjectName('manuscriptStatus')
            for key,text in authoring.STATUSES.items():status.addItem(tr(text),key)
            status.setCurrentIndex(max(0,status.findData(o.get('status','draft'))));status.currentIndexChanged.connect(lambda _: (o.update(status=status.currentData()),self.changed()));meta.addWidget(status);meta.addWidget(label('Deine Worte haben Raum.','muted'));canvas_l.addLayout(meta)
            paper=QFrame();paper.setObjectName('paper');paper.setMaximumWidth(880);paper_l=QVBoxLayout(paper);paper_l.setContentsMargins(32,28,32,24);paper_l.setSpacing(17)
            heading=label(o['name'],'title',False);heading.setObjectName('entryHeading');heading.setFont(QFont('Georgia',23));paper_l.addWidget(heading)
            e=Rich(self,o);e.blockSignals(True);e.setObjectName('manuscript');e.document().setDocumentMargin(0);e.setPlaceholderText(tr('Jede Geschichte beginnt mit einem ersten Satz …'));e.blockSignals(False);paper_l.addWidget(e,1);shadow(paper)
            centered=QHBoxLayout();centered.addStretch(1);centered.addWidget(paper,12);centered.addStretch(1);canvas_l.addLayout(centered,1);body.addWidget(canvas,1)
            context=QFrame();context.setObjectName('context');context.setMinimumWidth(170);context.setMaximumWidth(225);context_root=QVBoxLayout(context);context_root.setContentsMargins(0,0,0,0);context_area=QScrollArea();context_area.setWidgetResizable(True);context_body=QWidget();context_area.setWidget(context_body);context_root.addWidget(context_area);cx=QVBoxLayout(context_body);cx.setContentsMargins(0,2,22,18);cx.setSpacing(15);cx.addWidget(label('DEINE GESCHICHTE','eyebrow'));cx.addSpacing(5);cx.addWidget(label('Alles ist verbunden.'));hint=label('Verknüpfe beim Schreiben deine Figuren, Orte und Ereignisse.','muted');hint.setWordWrap(True);cx.addWidget(hint)
            chip=button('@  Eintrag verknüpfen',e.link);chip.setProperty('role','chip');cx.addWidget(chip);cx.addSpacing(15);cx.addWidget(label('AUS DEINER WELT','eyebrow'))
            for en in self.p['entries'][:6]:
                b=button(en['name']+'   ↗',lambda checked=False,id=en['id']:self.open_object(id));b.setProperty('role','subtle');b.setProperty('entryId',en['id']);b.installEventFilter(self);b.setToolTip(self.preview_html(en['id']));cx.addWidget(b)
            if not self.p['entries']:cx.addWidget(label('Noch keine Einträge.','muted'))
            cx.addWidget(button('Welt entdecken',self.show_world));cx.addWidget(label('Randnotizen','eyebrow'));notes=QWidget();notes.setObjectName('noteSidebar');notes_layout=QVBoxLayout(notes);notes_layout.setContentsMargins(0,0,0,0);cx.addWidget(notes);cx.addWidget(button('Kommentare öffnen',lambda:NotesDialog(self).exec()));self.update_note_sidebar(page);cx.addStretch();cx.addWidget(label('DEIN SCHREIBMOMENT','eyebrow'));tip=label('Blende mit F11 alles aus, was dich vom Schreiben ablenkt.','muted');tip.setWordWrap(True);cx.addWidget(tip);body.addWidget(context);l.addLayout(body,1)
        elif o in self.p['entries']:
            self.render_world_page(page,False)
        else:
            scroll=QScrollArea();scroll.setWidgetResizable(True);container=QWidget();outer=QVBoxLayout(container);outer.setContentsMargins(40,32,40,32);outer.setSpacing(20)
            outer.addWidget(label('WELTENBAU' if page.section=='world' else 'TIMELINE','eyebrow'));heading=label(o['name'],'title',False);heading.setObjectName('entryHeading');outer.addWidget(heading)
            card=QFrame();card.setObjectName('card');form=QFormLayout(card);form.setContentsMargins(28,26,28,26);form.setVerticalSpacing(22);form.setHorizontalSpacing(24);form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow);form.setLabelAlignment(Qt.AlignLeft|Qt.AlignVCenter)
            desc=Rich(self,o);desc.setObjectName('fieldEditor');desc.setMinimumHeight(190);form.addRow(tr('Beschreibung'),desc)
            if o in self.p['events']:
                form.addRow(tr('Zeitliche Zuordnung'),QLabel(o['start']+(' bis '+o['end'] if o['end'] else '')+' · '+o['kind']));form.addRow(button(tr('Zeit ändern'),lambda:self.edit_time(o,page)))
            else:
                cat=next(c for c in self.p['categories'] if c['id']==o['category']);form.addRow(button(tr('Kategorievorlage bearbeiten'),lambda:self.template(cat)))
                for f in cat['fields']:form.addRow(f['name'],self.field(o,f))
            form.addRow(tr('Verknüpfungen'),self.link_field(o,'links'));outer.addWidget(card);outer.addStretch();scroll.setWidget(container);l.addWidget(scroll)
        self.tabs.addTab(page,o['name']);self.tabs.setCurrentWidget(page)
    def update_note_sidebar(self,page):
        box=page.findChild(QWidget,'noteSidebar');doc=getattr(page,'obj',{})
        if not box:return
        notes=[n for n in doc.get('annotations',[]) if n['kind']=='comment' and not n.get('resolved')];signature=repr(notes)
        if getattr(box,'signature',None)==signature:return
        box.signature=signature;layout=box.layout()
        while layout.count():
            item=layout.takeAt(0);widget=item.widget()
            if widget:widget.deleteLater()
        for note in notes:
            text=QFontMetrics(self.font()).elidedText(note['text'].replace('\n',' '),Qt.ElideRight,175);b=button(text,lambda checked=False,id=note['id'],page=page:self.jump_note(page,id));b.setProperty('role','subtle');b.setToolTip(note['text']);layout.addWidget(b)
        if not notes:layout.addWidget(label('Noch keine Randnotizen.','muted'))
    def jump_note(self,page,id):
        editor=page.findChild(Rich)
        if not editor:return
        cursor=editor.note_cursors.get(id)
        if cursor:editor.setTextCursor(QTextCursor(cursor));editor.ensureCursorVisible();editor.setFocus()
    def render_world_page(self,page,editing=False):
        for editor in page.findChildren(Rich):
            if editor.store_timer.isActive():editor.flush()
        if self.active_editor and page.isAncestorOf(self.active_editor):self.active_editor=None
        layout=page.layout()
        while layout.count():
            item=layout.takeAt(0)
            widget=item.widget()
            if widget:widget.setParent(None);widget.deleteLater()
        page.world_edit=editing;o=page.obj;scroll=QScrollArea();scroll.setWidgetResizable(True);layout.addWidget(scroll)
        if not editing:
            reader=WorldReader(self,o,lambda:self.render_world_page(page,True));scroll.setWidget(reader);page.reference_revision=self.revision
        else:
            container=QWidget();outer=QVBoxLayout(container);outer.setContentsMargins(36,26,36,30);outer.setSpacing(20);top=QHBoxLayout();heading=label(o['name'],'title',False);heading.setObjectName('entryHeading');top.addWidget(heading);top.addStretch()
            def finish():
                self.flush_editors();missing=worldmodel.missing_required(self.p,o)
                if missing:self.error(tr('Pflichtfelder fehlen: ')+', '.join(missing));return
                self.refresh();self.render_world_page(page,False)
            top.addWidget(primary(tr('Fertig'),finish,'check'));outer.addLayout(top);notice=label(tr('Bearbeitungsmodus · Änderungen gehören zum Projekt und werden mit ihm gespeichert.'),'muted');notice.setWordWrap(True);outer.addWidget(notice);card=QFrame();card.setObjectName('card');form=QFormLayout(card);form.setContentsMargins(24,24,24,24);form.setVerticalSpacing(20);form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow);desc=Rich(self,o);form.addRow(tr('Beschreibung'),desc);cat=next(c for c in self.p['categories'] if c['id']==o['category']);form.addRow(button(tr('Kategorievorlage bearbeiten'),lambda:self.template(cat)))
            outer.addWidget(card);outer.addWidget(fields_layout(self,o,cat,True));links=QFrame();links.setObjectName('card');links_layout=QVBoxLayout(links);links_layout.addWidget(label(tr('Verknüpfungen'),'eyebrow'));links_layout.addWidget(self.link_field(o,'links'));outer.addWidget(links);outer.addStretch();scroll.setWidget(container)
        if self.tabs.currentWidget()==page:self.set_section('world');self.sync_format()
    def edit_time(self,o,page):
        if self.time_dialog(o):self.tabs.removeTab(self.tabs.indexOf(page));self.open_object(o['id']);self.changed();self.refresh()
    def link_field(self,o,key,values=None):
        data=o if values is None else values; data.setdefault(key,[]);box=QWidget();l=QVBoxLayout(box);ls=QListWidget();ls.viewport().installEventFilter(self);l.addWidget(ls)
        def refresh():
            ls.clear()
            for id in data[key]:
                target=resolve(self.p,id);i=QListWidgetItem(target['name'] if target else '[Gelöschter Eintrag]');i.setData(Qt.UserRole,id);i.setToolTip(self.preview_html(id));ls.addItem(i)
        def add():
            p=Picker(self)
            if p.exec() and p.id not in data[key]:data[key].append(p.id);refresh();self.changed()
        def remove():
            if ls.currentItem():data[key].remove(ls.currentItem().data(Qt.UserRole));refresh();self.changed()
        row=QHBoxLayout();row.addWidget(button('@ Verknüpfen',add));row.addWidget(button('Verweis entfernen',remove));l.addLayout(row);ls.itemDoubleClicked.connect(lambda i:self.open_object(i.data(Qt.UserRole)));ls.itemActivated.connect(lambda i:self.open_object(i.data(Qt.UserRole)));refresh();return box
    def field(self,o,f):
        values=o['values'];key=f['id'];v=values.get(key);t=f['type'];opts=f.get('options',[])
        if t in FIELD_RENDERERS:return FIELD_RENDERERS[t](self,o,f)
        if t not in TYPES:return QLabel(tr('Unbekannter Feldtyp · Wert bleibt gespeichert: ')+str(v))
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
                preview.setToolTip(str(len(ids))+tr(' eingebettete Bilder'))
            def add():
                paths,_=QFileDialog.getOpenFileNames(self,tr('Bilder einbetten'),'','Bilder (*.png *.jpg *.jpeg *.webp *.bmp)')
                if paths:
                    try:ids=[import_image(self.p,p) for p in paths];put((values.get(key,[])+ids) if t=='Galerie' else ids[:1]);refresh()
                    except (OSError,ValueError) as error:self.error(error)
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
            w=QComboBox();w.addItem('',None);source=f.get('source_category')
            if source:
                targets=worldmodel.filtered_entries(self.p,f)
                for entry in targets:w.addItem(entry['name'],entry['id'])
                if v and not any(entry['id']==v for entry in targets):w.addItem(tr('Bisheriger oder fehlender Wert')+': '+str(resolve(self.p,v)['name'] if resolve(self.p,v) else v),v)
                w.setCurrentIndex(max(0,w.findData(v)));w.currentIndexChanged.connect(lambda _:put(w.currentData() or ''))
            else:
                w.addItems(list(dict.fromkeys(opts+([v] if v and v not in opts else []))));w.setCurrentText(v or '');w.currentTextChanged.connect(put)
            return w
        if t=='Mehrfachauswahl':
            w=QListWidget();source=f.get('source_category')
            pairs=[(entry['id'],entry['name']) for entry in worldmodel.filtered_entries(self.p,f)] if source else [(opt,opt) for opt in opts];known={id for id,name in pairs}
            for old in v or []:
                if old not in known:pairs.append((old,(resolve(self.p,old) or {}).get('name',str(old))))
            for id,name in pairs:
                item=QListWidgetItem(name);item.setData(Qt.UserRole,id);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if id in (v or []) else Qt.Unchecked);w.addItem(item)
            w.itemChanged.connect(lambda _:put([w.item(i).data(Qt.UserRole) for i in range(w.count()) if w.item(i).checkState()==Qt.Checked]));return w
        if t=='Slider':
            box=QWidget();l=QHBoxLayout(box);w=QSlider(Qt.Horizontal);lo=f.get('min',0);hi=f.get('max',100);step=f.get('step',1);w.setRange(0,round((hi-lo)/step));w.setValue(round(((v if v is not None else lo)-lo)/step));lab=QLabel(str(v if v is not None else lo));l.addWidget(w);l.addWidget(lab);w.valueChanged.connect(lambda n:(lab.setText(str(lo+n*step)),put(lo+n*step)));return box
        w=QLineEdit(str(v or ''))
        if t in ['Datum','Zeitspanne']:
            w.setPlaceholderText(tr('Jahr/Monat/Tag')+(tr(' .. Jahr/Monat/Tag') if t=='Zeitspanne' else '')+tr(' · Jahreskalender: Jahr'))
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
        d=QDialog(self);d.setWindowTitle(tr('Vorlage · ')+cat['name']);d.resize(850,500);l=QVBoxLayout(d);l.addWidget(QLabel(tr('Felder haben stabile IDs. Entfernte Felder bleiben als archivierte Werte im Projekt erhalten.')))
        table=QTableWidget(0,3);table.setHorizontalHeaderLabels([tr('Feldname'),tr('Typ'),tr('Einstellungen · Doppelklick')]);table.horizontalHeader().setStretchLastSection(True);l.addWidget(table)
        fields=json.loads(json.dumps(cat['fields']))
        def add_row(f=None):
            f=f or dict(id=uid(),name=tr('Neues Feld'),type='Text');r=table.rowCount();table.insertRow(r);i=QTableWidgetItem(f['name']);i.setData(Qt.UserRole,f['id']);table.setItem(r,0,i);cb=QComboBox();cb.setProperty('translateItems',True);cb.addItems(TYPES+([f['type']] if f['type'] not in TYPES else []));cb.setCurrentText(f['type']);table.setCellWidget(r,1,cb);settings={k:v for k,v in f.items() if k not in ['id','name','type']};item=QTableWidgetItem(tr('Einstellungen öffnen'));item.setData(Qt.UserRole,settings);item.setFlags(item.flags() & ~Qt.ItemIsEditable);table.setItem(r,2,item)
        for f in fields:add_row(f)
        def settings_dialog(r,col):
            if col!=2:return
            t=table.cellWidget(r,1).currentText();item=table.item(r,2);settings=item.data(Qt.UserRole) or {};dialog=QDialog(d);dialog.setWindowTitle(tr('Feldeinstellungen'));outer=QVBoxLayout(dialog);scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();scroll.setWidget(inner);outer.addWidget(scroll);form=QFormLayout(inner);dialog.resize(620,650)
            group=QLineEdit(settings.get('group',''));column=QComboBox();column.addItem(tr('Linke Spalte'),0);column.addItem(tr('Rechte Spalte'),1);column.setCurrentIndex(settings.get('column',0));required=QCheckBox(tr('Pflichtfeld'));required.setChecked(settings.get('required',False));help_text=QPlainTextEdit(settings.get('help',''));help_text.setMaximumHeight(90);form.addRow(tr('Feldgruppe · optional'),group);form.addRow(tr('Spalte'),column);form.addRow(required);form.addRow(tr('Hilfetext'),help_text)
            options=QPlainTextEdit('\n'.join(settings.get('options',[])));lo=QDoubleSpinBox();hi=QDoubleSpinBox();step=QDoubleSpinBox()
            for widget in [lo,hi,step]:widget.setRange(-1e9,1e9);widget.setDecimals(4)
            lo.setValue(settings.get('min',0));hi.setValue(settings.get('max',100));step.setValue(settings.get('step',1))
            if t in ['Dropdown','Mehrfachauswahl']:
                source=QComboBox();source.setObjectName('categorySource');source.addItem(tr('Eigene Auswahloptionen'),None)
                for category in self.p['categories']:source.addItem(category['name'],category['id'])
                if settings.get('source_category') and source.findData(settings['source_category'])<0:source.addItem(tr('Fehlende Kategorie'),settings['source_category'])
                source.setCurrentIndex(max(0,source.findData(settings.get('source_category'))));form.addRow(tr('Auswahlquelle'),source);form.addRow(tr('Eine Option pro Zeile'),options);options.setEnabled(not source.currentData());source.currentIndexChanged.connect(lambda _:options.setEnabled(not source.currentData()))
                filter_field=QComboBox();filter_field.addItem(tr('Kein Auswahlfilter'),None);filter_op=QComboBox();filter_op.addItem(tr('Ist gleich'),'eq');filter_op.addItem(tr('Enthält'),'contains');filter_value=QLineEdit((settings.get('source_filter') or {}).get('value',''))
                def filter_fields(*args):
                    old=filter_field.currentData() or (settings.get('source_filter') or {}).get('field');filter_field.clear();filter_field.addItem(tr('Kein Auswahlfilter'),None);filter_field.addItem(tr('Anzeigename'),'name');category=next((c for c in self.p['categories'] if c['id']==source.currentData()),{})
                    for field in category.get('fields',[]):filter_field.addItem(field['name'],field['id'])
                    filter_field.setCurrentIndex(max(0,filter_field.findData(old)))
                filter_fields();source.currentIndexChanged.connect(filter_fields);filter_op.setCurrentIndex(max(0,filter_op.findData((settings.get('source_filter') or {}).get('op','eq'))));form.addRow(tr('Auswahlfilter · Feld'),filter_field);form.addRow(tr('Bedingung'),filter_op);form.addRow(tr('Vergleichswert'),filter_value)
            elif t=='Slider':form.addRow(tr('Minimum'),lo);form.addRow(tr('Maximum'),hi);form.addRow(tr('Schrittweite'),step)
            else:form.addRow(QLabel(tr('Dieser Feldtyp benötigt keine zusätzlichen Einstellungen.')))
            def apply():
                if t in ['Dropdown','Mehrfachauswahl']:
                    new_settings={**settings,'options':list(dict.fromkeys(s.strip() for s in options.toPlainText().splitlines() if s.strip()))}
                    if source.currentData():new_settings['source_category']=source.currentData()
                    else:new_settings.pop('source_category',None)
                    if source.currentData() and filter_field.currentData():new_settings['source_filter']=dict(field=filter_field.currentData(),op=filter_op.currentData(),value=filter_value.text())
                    else:new_settings.pop('source_filter',None)
                    item.setData(Qt.UserRole,new_settings)
                elif t=='Slider':
                    if hi.value()<lo.value() or step.value()<=0:self.error('Maximum muss mindestens Minimum sein; Schrittweite muss positiv sein.');return
                    item.setData(Qt.UserRole,{**settings,'min':lo.value(),'max':hi.value(),'step':step.value()})
                extra=item.data(Qt.UserRole) or dict(settings);extra.update(group=group.text().strip(),column=column.currentData(),required=required.isChecked(),help=help_text.toPlainText());item.setData(Qt.UserRole,extra);dialog.accept()
            form.addRow(button(tr('Übernehmen'),apply));dialog.exec()
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
            names=[f['name'] for f in archived];name,ok=QInputDialog.getItem(d,tr('Archiviertes Feld wiederherstellen'),tr('Feld:'),names,0,False)
            if ok:
                f=archived[names.index(name)]
                if not any(table.item(r,0).data(Qt.UserRole)==f['id'] for r in range(table.rowCount())):add_row(f)
        row.addWidget(button('Aus Archiv',restore))
        row.addWidget(button('↑',lambda:move(-1)));row.addWidget(button('↓',lambda:move(1)));l.addLayout(row)
        l.addWidget(QLabel(tr('Doppelklick auf Einstellungen: Auswahloptionen oder Sliderbereich bearbeiten.')))
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
        c=json.loads(json.dumps(self.p['calendar']));d=QDialog(self);d.setWindowTitle(tr('Projektkalender'));d.resize(760,680);outer=QVBoxLayout(d);scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();l=QVBoxLayout(inner);scroll.setWidget(inner);outer.addWidget(scroll);form=QFormLayout();l.addLayout(form)
        name=QLineEdit(c['name']);epoch=QSpinBox();epoch.setRange(-1000000,1000000);epoch.setValue(c['epoch']);zero=QCheckBox(tr('Jahr null verwenden'));zero.setChecked(c['year_zero']);yearonly=QCheckBox(tr('Nur Jahreszahlen verwenden'));yearonly.setChecked(not c['months']);week=QLineEdit(', '.join(c.get('week',[])));fmt=QLineEdit(c['format']);units=[]
        form.addRow(tr('Name der Zeitrechnung'),name);form.addRow(tr('Ausgangsjahr'),epoch);form.addRow(zero);form.addRow(yearonly)
        for key,label in [('year','Jahreseinheit'),('month','Monatseinheit'),('day','Tageseinheit')]:
            w=QLineEdit(c.get('units',{}).get(key,label));units.append((key,w));form.addRow(tr(label),w)
        form.addRow(tr('Wochentage (Komma-getrennt, optional)'),week);form.addRow(tr('Datumsdarstellung'),fmt);form.addRow(QLabel(tr('Platzhalter: {year}, {month}, {day}, {weekday}')))
        months=QTableWidget(0,2);months.setHorizontalHeaderLabels([tr('Monatsname'),tr('Tage')]);months.horizontalHeader().setStretchLastSection(True)
        def add_month(n='Neuer Mond',days=30):
            r=months.rowCount();months.insertRow(r);months.setItem(r,0,QTableWidgetItem(n));months.setItem(r,1,QTableWidgetItem(str(days)))
        for m in c['months']:add_month(m['name'],m['days'])
        l.addWidget(QLabel(tr('Monate in ihrer Reihenfolge')));l.addWidget(months);row=QHBoxLayout();row.addWidget(button('Monat hinzufügen',lambda:add_month()));row.addWidget(button('Monat entfernen',lambda:months.removeRow(months.currentRow()) if months.currentRow()>=0 else None));l.addLayout(row)
        leaps=QTableWidget(0,4);leaps.setHorizontalHeaderLabels([tr('Alle … Jahre'),tr('Versatz'),tr('Monatsnummer'),tr('Zusätzliche Tage')])
        def add_leap(rule=None):
            rule=rule or dict(every=4,offset=0,month=1,days=1);r=leaps.rowCount();leaps.insertRow(r)
            for i,k in enumerate(['every','offset','month','days']):leaps.setItem(r,i,QTableWidgetItem(str(rule.get(k,0))))
        for rule in c.get('leaps',[]):add_leap(rule)
        l.addWidget(QLabel(tr('Schaltregeln (optional, mehrere Regeln werden addiert)')));l.addWidget(leaps);row=QHBoxLayout();row.addWidget(button('Schaltregel hinzufügen',lambda:add_leap()));row.addWidget(button('Schaltregel entfernen',lambda:leaps.removeRow(leaps.currentRow()) if leaps.currentRow()>=0 else None));l.addLayout(row)
        def commit():
            try:
                if not name.text().strip():raise ValueError('Kalendername fehlt.')
                c.update(name=name.text().strip(),epoch=epoch.value(),year_zero=zero.isChecked(),months=[] if yearonly.isChecked() else [dict(name=months.item(r,0).text(),days=int(months.item(r,1).text())) for r in range(months.rowCount())],week=[s.strip() for s in week.text().split(',') if s.strip()],format=fmt.text(),units={key:w.text() for key,w in units},leaps=[] if yearonly.isChecked() else [{k:int(leaps.item(r,i).text()) for i,k in enumerate(['every','offset','month','days'])} for r in range(leaps.rowCount())]);cal=Calendar(c);cal.validate()
                if not yearonly.isChecked() and not c['months']:raise ValueError('Mindestens einen Monat anlegen oder nur Jahreszahlen wählen.')
                for en in self.p['events']:cal.span(en['start'],en['end'])
                for relation in self.p.get('relationships',[]):
                    if relation.get('start'):cal.span(relation['start'],relation.get('end',''))
                for en in self.p['entries']:
                    cat=next(x for x in self.p['categories'] if x['id']==en['category'])
                    for f in cat['fields']:
                        if f['type'] in ['Datum','Zeitspanne'] and en['values'].get(f['id']):
                            parts=en['values'][f['id']].split('..');cal.span(parts[0].strip(),parts[1].strip() if len(parts)>1 else '')
                if self.p['events'] and QMessageBox.question(d,tr('Kalenderänderung'),tr('Bestehende Datumswerte werden im neuen Kalender interpretiert. Übernehmen?'))!=QMessageBox.Yes:return
                self.p['calendar']=c;self.changed();self.refresh_open_views();d.accept()
            except Exception as e:self.error(e)
        l.addWidget(button('Kalender prüfen und übernehmen',commit));d.exec()
    def time_dialog(self,o):
        d=QDialog(self);d.setWindowTitle(tr('Zeitliche Zuordnung'));l=QFormLayout(d);name=QLineEdit(o.get('name',''));start=QLineEdit(o.get('start','1/1/1' if self.p['calendar']['months'] else '1'));end=QLineEdit(o.get('end',''));kind=QComboBox();kind.setProperty('translateItems',True);kind.addItems(['Ereignis','Zeitalter','Notiz','Geschichte']);kind.setCurrentText(o.get('kind','Ereignis'));era=QComboBox();era.addItem(tr('Keinem Zeitalter zugeordnet'),None)
        for en in self.p['events']:
            if en['kind']=='Zeitalter' and en['id']!=o.get('id'):era.addItem(en['name'],en['id'])
        era.setCurrentIndex(max(0,era.findData(o.get('era'))));l.addRow(tr('Name'),name);l.addRow(tr('Art'),kind);units=self.p['calendar'].get('units',{});hint='/'.join(units.get(k,k) for k in ['year','month','day']) if self.p['calendar']['months'] else units.get('year','Jahr');l.addRow(tr('Anfang (')+hint+')',start);l.addRow(tr('Ende (optional)'),end);l.addRow(tr('Zeitalter (optional)'),era)
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
        l.addRow(button(tr('Übernehmen'),commit));return d.exec()==QDialog.Accepted
    def add_event(self):
        o=dict(id=uid(),html='',links=[])
        if self.time_dialog(o):self.p['events'].append(o);self.changed();self.refresh();self.open_object(o['id'])
    def show_timeline(self):
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i),'timeline_page',False):self.tabs.removeTab(i);break
        page=QWidget();page.section='timeline';page.timeline_page=True;root=QVBoxLayout(page);root.setContentsMargins(0,0,0,0);area=QScrollArea();area.setWidgetResizable(True);content=QWidget();area.setWidget(content);root.addWidget(area);layout=QVBoxLayout(content);layout.setContentsMargins(30,25,30,25);layout.setSpacing(20)
        top=QHBoxLayout();titles=QVBoxLayout();titles.addWidget(label(tr('ZEIT & ZUSAMMENHÄNGE'),'eyebrow'));titles.addWidget(label(tr('Deine Welt. Ihre Geschichte.'),'title'));titles.addWidget(label(self.p['calendar']['name'],translate=False));top.addLayout(titles);top.addStretch();top.addWidget(primary(tr('Ereignis anlegen'),self.add_event,'plus'));layout.addLayout(top)
        controls=QHBoxLayout();controls.addStretch();chart_button=QPushButton(tr('Zeitstrahl'));list_button=QPushButton(tr('Liste'));controls.addWidget(chart_button);controls.addWidget(list_button);refresh=QPushButton(tr('Aktualisieren'));controls.addWidget(refresh);layout.addLayout(controls)
        stack=QStackedWidget();panel=TimelinePanel(self);stack.addWidget(panel);table=QTableWidget(0,4);table.setHorizontalHeaderLabels([tr('Name'),tr('Art'),tr('Anfang'),tr('Ende')]);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);table.verticalHeader().hide();table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setShowGrid(False);stack.addWidget(table);layout.addWidget(stack,1)
        def update():
            try:
                panel.canvas.set_project(True);cal=Calendar(self.p['calendar']);table.setRowCount(0)
                def sort_key(event):
                    try:return cal.ordinal(event['start'])
                    except (ValueError,KeyError,IndexError):return float('inf')
                for row,event in enumerate(sorted(self.p['events'],key=sort_key)):
                    table.insertRow(row)
                    try:start=cal.display(event['start']);end=cal.display(event['end']) if event['end'] else '—'
                    except (ValueError,KeyError,IndexError):start=event['start'];end=event['end']
                    for col,text in enumerate([event['name'],tr(event['kind']),start,end]):item=QTableWidgetItem(text);item.setData(Qt.UserRole,event['id']);table.setItem(row,col,item)
            except Exception as error:self.error(error)
        chart_button.clicked.connect(lambda:stack.setCurrentIndex(0));list_button.clicked.connect(lambda:stack.setCurrentIndex(1));refresh.clicked.connect(update);table.itemDoubleClicked.connect(lambda item:self.open_object(item.data(Qt.UserRole)));table.itemActivated.connect(lambda item:self.open_object(item.data(Qt.UserRole)));page.timeline_refresh=update;table.viewport().installEventFilter(self);update();self.tabs.addTab(page,'Timeline');self.tabs.setCurrentWidget(page);self.breadcrumb.setText('TIMELINE')
    def export_document(self,docs,titles=True,pdf=False,printer=None,cover_kinds=None):
        self.flush_editors()
        return printing.manuscript_document(self.p,docs,titles,pdf,printer,cover_kinds,self.settings)
    def printing(self):
        d=QDialog(self);d.setWindowTitle(tr('Drucken & PDF'));outer=QVBoxLayout(d);outer.setContentsMargins(0,0,0,0);area=QScrollArea();area.setWidgetResizable(True);content=QWidget();area.setWidget(content);outer.addWidget(area);l=QVBoxLayout(content);l.setContentsMargins(24,24,24,24);l.setSpacing(14);l.addWidget(QLabel(tr('Kapitel in Projekt-Reihenfolge auswählen:')));saved=printing.options(self.p,self.settings);selected=saved.get('chapters');ls=print_selection_tree(self.p,selected);ls.viewport().installEventFilter(self);l.addWidget(ls)
        titles=QCheckBox(tr('Kapitelnamen als Überschrift drucken'));titles.setChecked(saved['titles']);l.addWidget(titles);printer=printing.make_printer(self.p,self.settings)
        pdf_covers={}
        for kind,text in [('project','Projektcover im PDF'),('book','Buchcover im PDF')]:
            check=QCheckBox(tr(text));check.setChecked(saved.get('pdf_cover_'+kind,True));check.setEnabled(bool(self.p.get('covers',{}).get(kind)));pdf_covers[kind]=check;l.addWidget(check)
        def ids():return selected_document_ids(ls)
        def remember():
            if printing.persist(self.p,self.settings,printer,titles.isChecked(),ids(),**{'pdf_cover_'+kind:check.isChecked() for kind,check in pdf_covers.items()}):self.changed()
        def doc(for_pdf=False):
            if not ids():self.error(tr('Mindestens ein Kapitel auswählen.'));return None
            return self.export_document([o for o in authoring.ordered_documents(self.p) if o['id'] in ids()],titles.isChecked(),pdf=for_pdf,printer=printer,cover_kinds=[kind for kind,check in pdf_covers.items() if check.isChecked()])
        def page_setup():
            if QPageSetupDialog(printer,d).exec():remember()
        def preview():
            document=doc()
            if document is None:return
            remember();p=QPrintPreviewDialog(printer,d);p.paintRequested.connect(document.print_);p.exec();remember()
        def preview_pdf():
            document=doc(True)
            if document is not None:remember();printing.pdf_preview(self,document,printer)
        def pdf():
            document=doc(True)
            if document is None:return
            chosen=[o for o in authoring.ordered_documents(self.p) if o['id'] in ids()];name=chosen[0]['name'] if len(chosen)==1 else self.p['name'];name=re.sub(r'[<>:"/\\|?*]','_',name).strip(' .') or 'Storynator';directory=Path(self.settings.value('printing/pdf_directory',str(Path.home())));path,_=QFileDialog.getSaveFileName(d,tr('PDF speichern'),str(directory/(name+'.pdf')),'PDF (*.pdf)')
            if path:
                printing.write_pdf(document,path if path.lower().endswith('.pdf') else path+'.pdf',printer);self.settings.setValue('printing/pdf_directory',str(Path(path).parent));remember();self.statusBar().showMessage(tr('PDF exportiert: ')+path)
        def print_now():
            document=doc()
            if document is None:return
            printer.setOutputFormat(QPrinter.NativeFormat)
            if QPrintDialog(printer,d).exec():document.print_(printer);remember()
        changes=QTimer(d);changes.setSingleShot(True);changes.timeout.connect(remember);ls.itemChanged.connect(lambda *args:changes.start(120));titles.toggled.connect(lambda _:remember())
        for check in pdf_covers.values():check.toggled.connect(lambda _:remember())
        for text,fn in [('Papier & Seitenränder',page_setup),('Druckvorschau',preview),('PDF-Vorschau · mit Cover',preview_pdf),('PDF exportieren',pdf),('Drucken',print_now)]:l.addWidget(button(text,fn))
        l.addWidget(button(tr('Übernehmen'),lambda:(remember(),d.accept())));d.resize(620,650);d.exec();changes.stop();remember()

from PySide6.QtCore import QStandardPaths

def main():
    app=QApplication(sys.argv);app.setApplicationName('Storynator');app.setOrganizationName('Storynator');set_language(QSettings('Storynator','Storynator').value('language','de'));install_qt_translations(app);apply_theme(app)
    from logging.handlers import RotatingFileHandler
    logdir=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation));logdir.mkdir(parents=True,exist_ok=True);handler=RotatingFileHandler(logdir/'errors.log',maxBytes=256*1024,backupCount=3,encoding='utf-8');logging.getLogger().addHandler(handler);logging.getLogger().setLevel(logging.WARNING)
    smoke='--smoke-test' in sys.argv;w=Main(recover=not smoke)
    handling=[False]
    def exception_hook(kind,error,tb):
        logging.error('Unexpected application error',exc_info=(kind,error,tb))
        if smoke:
            Path(os.environ.get('STORYNATOR_SMOKE_LOG','smoke-error.txt')).write_text(''.join(traceback.format_exception(kind,error,tb)),encoding='utf-8');app.exit(1);return
        if handling[0]:return
        handling[0]=True
        try:w.autosave();QMessageBox.warning(w,'Storynator',tr('Ein unerwarteter Fehler ist aufgetreten. Der letzte gültige Projektstand bleibt erhalten. Bitte speichern Sie unter einem neuen Namen oder öffnen Sie einen Sicherungsstand. Details stehen lokal in errors.log.'))
        finally:handling[0]=False
    sys.excepthook=exception_hook
    screen=app.primaryScreen()
    if screen:
        area=screen.availableGeometry();w.resize(min(1500,max(1050,area.width()-40)),min(960,max(700,area.height()-60)))
    w.show()
    if smoke:
        def check():
            try:
                import tempfile
                w.p=load_project(Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'Beispiel.storynator');w.tabs.clear();w.refresh();w.open_object(w.p['documents'][0]['id']);w.show_timeline()
                from spelling import dictionary
                assert dictionary('de_DE').lookup('Geschichte') and dictionary('en_US').lookup('story')
                parent=w.p['documents'][0];parent['status']='revision';authoring.snapshot(parent,'Smoke checkpoint');w.p['documents'].append(dict(id=uid(),name='Smoke scene',kind='scene',parent=parent['id'],status='draft',html='<p>Scene smoke test.</p>'))
                if len(w.p['entries'])>=2:
                    type_id=uid();w.p['relationship_types']=[dict(id=type_id,name='Smoke relation',inverse='Inverse',directed=True)];worldmodel.add_relation(w.p,w.p['entries'][0]['id'],w.p['entries'][1]['id'],type_id)
                graph=GraphDialog(w,w.p['entries'][0]['id'] if w.p['entries'] else None);QTimer.singleShot(350,graph.accept);graph.exec()
                with tempfile.TemporaryDirectory() as folder:
                    path=Path(folder)/'smoke.storynator';save_project(w.p,path);assert load_project(path)==w.p
                    first=next(iter(w.p['assets']));w.p['covers'].update(project=first,book=first);save_project(w.p,path);assert load_project(path)['covers']==w.p['covers'];history=BackupStore(Path(folder)/'history');meta=history.create(w.p);assert history.read(meta)==w.p
                    pdf=Path(folder)/'smoke.pdf';printer=printing.make_printer(w.p,w.settings);document=w.export_document(w.p['documents'],pdf=True,printer=printer);printing.write_pdf(document,pdf,printer);assert pdf.stat().st_size>500
                    from PySide6.QtPdf import QPdfDocument
                    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
                    buffer=QBuffer();buffer.setData(QByteArray(pdf.read_bytes()));buffer.open(QIODevice.ReadOnly);check_pdf=QPdfDocument();check_pdf.load(buffer);assert check_pdf.pageCount()>=3;check_pdf.close();del check_pdf;buffer.close()
                    QTimer.singleShot(600,lambda:[dialog.accept() for dialog in app.topLevelWidgets() if isinstance(dialog,QDialog)])
                    printing.pdf_preview(w,document,printer)
                from community_ui import CommunityDialog,ReaderDialog
                import community as exchange
                manager=CommunityDialog(w);assert manager.list.count()>=2;manager.accept()
                sample=exchange.create(w.p,'reading',exchange.metadata('Smoke reading'),[w.p['documents'][0]['id']]);reader=ReaderDialog(w,sample);assert reader.docs.count()==1;reader.accept()
                w.dirty=False;w.close();app.processEvents();app.exit(0)
            except Exception:
                import traceback
                Path(os.environ.get('STORYNATOR_SMOKE_LOG','smoke-error.txt')).write_text(traceback.format_exc(),encoding='utf-8');app.exit(1)
        QTimer.singleShot(400,check)
    elif '--import-pack' in sys.argv or len(sys.argv)>1 and Path(sys.argv[1]).suffix.lower()=='.storynator-pack':
        index=sys.argv.index('--import-pack')+1 if '--import-pack' in sys.argv else 1
        if index<len(sys.argv):
            def import_pack():
                from community_ui import CommunityDialog
                manager=CommunityDialog(w);manager.add(sys.argv[index]);manager.exec()
            QTimer.singleShot(0,import_pack)
    elif '--import-preset' in sys.argv:
        index=sys.argv.index('--import-preset')
        if index+1<len(sys.argv):
            def import_preset():
                manager=AddonManager(w);manager.import_file(sys.argv[index+1]);manager.exec()
            QTimer.singleShot(0,import_preset)
    elif len(sys.argv)>1 and Path(sys.argv[1]).suffix.lower()=='.storynator':w.open_file(sys.argv[1])
    exit_code=app.exec();w.backup_pool.waitForDone()
    for child in w.findChildren(QObject):child.blockSignals(True)
    w.blockSignals(True)
    from shiboken6 import delete
    delete(w)
    from design import cached_icon
    cached_icon.cache_clear();app.processEvents();sys.exit(exit_code)
if __name__=='__main__':main()

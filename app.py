import sys, json, base64, os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QSettings, QMarginsF, QSize, QEvent, QSignalBlocker
from PySide6.QtGui import QAction, QFont, QTextCharFormat, QTextCursor, QTextDocument, QImage, QTextImageFormat, QTextFormat, QTextListFormat, QColor, QPageSize, QTextBlockFormat, QFontInfo
from PySide6.QtWidgets import *
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog, QPageSetupDialog
from core import *
from i18n import tr,set_language,install_qt_translations
import printing
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
        def choose():
            if self.list.currentItem(): self.id=self.list.currentItem().data(Qt.UserRole); self.accept()
        self.list.viewport().installEventFilter(w);self.search.textChanged.connect(refresh); self.list.itemDoubleClicked.connect(choose); lay.addWidget(button('Verknüpfen',choose)); refresh()

class Rich(QTextEdit):
    def __init__(self,w,obj,key='html'):
        super().__init__(); self.w=w; self.obj=obj; self.key=key; self.setAcceptRichText(True); self.setFont(QFont('Georgia',14)); self.document().setDocumentMargin(35)
        self.setMinimumHeight(190);self.document().setDefaultFont(QFont('Georgia',14));self.load_assets();self.setHtml(render(w.p,obj.get(key,'')));self.setMouseTracking(True)
        self.cursorPositionChanged.connect(lambda:w.sync_format(self));self.currentCharFormatChanged.connect(lambda _:w.sync_format(self))
        self.textChanged.connect(self.store);self.mark_timer=QTimer(self);self.mark_timer.setSingleShot(True);self.mark_timer.timeout.connect(self.update_marks);self.textChanged.connect(lambda:self.mark_timer.start(60));self.update_marks()
    def load_assets(self):
        for k,v in self.w.p['assets'].items(): self.document().addResource(QTextDocument.ImageResource,QUrl('asset:'+k),QImage.fromData(base64.b64decode(v)))
    def store(self): self.obj[self.key]=self.toHtml(); self.w.changed()
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
            a=QByteArray(); b=QBuffer(a); b.open(QIODevice.WriteOnly); image.save(b,'PNG'); key=uid()+'.png'; self.w.p['assets'][key]=base64.b64encode(bytes(a)).decode(); self.add_image(key)
        else: self.insertPlainText(m.text())
    def add_image(self,key):
        self.load_assets(); f=QTextImageFormat(); f.setName('asset:'+key); img=QImage.fromData(base64.b64decode(self.w.p['assets'][key])); f.setWidth(min(550,img.width())); f.setHeight(min(550,img.width())*img.height()/max(1,img.width())); self.textCursor().insertImage(f)

class TimelineView(QGraphicsView):
    def wheelEvent(self,e):
        if e.modifiers()&Qt.ControlModifier: self.scale(1.2 if e.angleDelta().y()>0 else 1/1.2,1); e.accept()
        else: super().wheelEvent(e)

class StudioTabs(QTabWidget):
    def __init__(self,owner):super().__init__(owner);self.owner=owner
    def addTab(self,*args):
        index=super().addTab(*args);self.owner.decorate_tabs();return index

def project_for_language(name=None):
    p=new_project(name or tr('Meine Geschichte'));p['documents'][0]['name']=tr('Kapitel 1');c=p['calendar'];c['name']=tr('Weltzeit')
    for month in c['months']:month['name']=tr(month['name'])
    c['week']=[tr(day) for day in c['week']];c['units']={k:tr(v) for k,v in c['units'].items()};return p

class Main(QMainWindow):
    def __init__(self, recover=True):
        super().__init__()
        self.p=project_for_language();self.path=None;self.dirty=False;self.section='editor'
        self.settings=QSettings('Storynator','Storynator');self.resize(1500,960);self.setMinimumSize(1050,700)
        self.setWindowIcon(icon('feather','#426a45',64))
        self.recovery=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))/'recovery.storynator'
        self.tabs=StudioTabs(self);self.tabs.setTabsClosable(True);self.tabs.setDocumentMode(True);self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab);self.tabs.currentChanged.connect(self.tab_changed)
        self.nav=QTreeWidget();self.nav.setObjectName('projectTree');self.nav.setHeaderHidden(True);self.nav.setIndentation(14);self.nav.setAnimated(True)
        self.nav.setRootIsDecorated(False);self.nav.itemClicked.connect(lambda i,c:self.open_object(i.data(0,Qt.UserRole)) if i.data(0,Qt.UserRole) else None)
        self.nav.viewport().installEventFilter(self);self.nav.setContextMenuPolicy(Qt.CustomContextMenu);self.nav.customContextMenuRequested.connect(self.navigation_menu)
        sidebar=QWidget();sidebar.setObjectName('sidebar');sl=QVBoxLayout(sidebar);sl.setContentsMargins(18,18,18,14);sl.setSpacing(5)
        brand=QHBoxLayout();mark=QLabel();mark.setPixmap(icon('feather','#b5ce9d',40).pixmap(36,36));brand.addWidget(mark);brand.addWidget(label('Storynator','title'));brand.itemAt(1).widget().setObjectName('brand');brand.addStretch();sl.addLayout(brand);sl.addSpacing(23)
        project=QFrame();project.setObjectName('projectCard');pl=QVBoxLayout(project);pl.setContentsMargins(15,14,15,14);pl.setSpacing(5);pl.addWidget(label('AKTUELLES PROJEKT','eyebrow'));self.project_label=label(self.p['name'],translate=False);self.project_label.setWordWrap(True);pl.addWidget(self.project_label);sl.addWidget(project);sl.addSpacing(12)
        sl.addWidget(label('ARBEITSBEREICH','eyebrow'));sl.addSpacing(3);self.nav_buttons={}
        for section,text,name in [('editor','Editor','book'),('timeline','Timeline','timeline'),('world','Welt','world')]:
            btn=QPushButton('  '+tr(text));btn.setObjectName('navButton');btn.setCheckable(True);btn.setIcon(icon(name,'#b8c9b4'));btn.setIconSize(QSize(21,21));btn.setCursor(Qt.PointingHandCursor);btn.clicked.connect(lambda checked=False,key=section:self.navigate(key));self.nav_buttons[section]=btn;sl.addWidget(btn)
        sl.addSpacing(12);self.collection_label=label('MANUSKRIPT','eyebrow');sl.addWidget(self.collection_label);sl.addSpacing(4);sl.addWidget(self.nav,1)
        self.add_primary=button('+  Neues Kapitel',self.create_in_section);self.add_primary.setProperty('role','subtle');sl.addWidget(self.add_primary)
        self.add_secondary=button('+  Neue Kategorie',self.add_category);self.add_secondary.setProperty('role','subtle');self.add_secondary.hide();sl.addWidget(self.add_secondary);sl.addSpacing(15)
        sl.addWidget(tool('settings','Projektkalender',self.calendar,'Projektkalender'));sl.addWidget(tool('settings','Einstellungen',self.preferences,'Einstellungen'));sl.addWidget(tool('home','Startseite',self.home,'Startseite'))
        workspace=QWidget();wl=QVBoxLayout(workspace);wl.setContentsMargins(0,0,0,0);wl.setSpacing(0)
        header=QFrame();header.setObjectName('header');hl=QHBoxLayout(header);hl.setContentsMargins(28,14,26,14);hl.setSpacing(14)
        self.breadcrumb=label('DEIN SCHREIBATELIER','eyebrow');hl.addWidget(self.breadcrumb);hl.addStretch()
        self.global_search=QLineEdit();self.global_search.setObjectName('globalSearch');self.global_search.setPlaceholderText(tr('Projekt durchsuchen …'));self.global_search.addAction(icon('search'),QLineEdit.LeadingPosition);self.global_search.setFixedWidth(250);self.global_search.returnPressed.connect(lambda:self.search(self.global_search.text()));hl.addWidget(self.global_search)
        hl.addWidget(tool('print','Drucken und als PDF exportieren · Strg+P',self.printing));self.save_button=primary('Speichern',lambda:self.save(),'save');hl.addWidget(self.save_button);wl.addWidget(header)
        self.formatbar=QFrame();self.formatbar.setObjectName('formatbar');wl.addWidget(self.formatbar);wl.addWidget(self.tabs,1)
        split=QSplitter();split.setChildrenCollapsible(False);side_scroll=QScrollArea();side_scroll.setObjectName('sidebarScroll');side_scroll.setWidgetResizable(True);side_scroll.setWidget(sidebar);side_scroll.setMinimumWidth(235);side_scroll.setMaximumWidth(330);split.addWidget(side_scroll);split.addWidget(workspace);split.setSizes([258,1242]);self.setCentralWidget(split)
        self.active_editor=None;QApplication.instance().focusChanged.connect(self.track_editor)
        self.toolbar();self.menus();self.refresh();self.home()
        self.timer=QTimer(self);self.timer.timeout.connect(self.autosave);self.timer.start(30000)
        if recover and self.recovery.exists() and QMessageBox.question(self,tr('Wiederherstellung'),tr('Wiederherstellungssicherung öffnen?'))==QMessageBox.Yes:
            try:self.p=load_project(self.recovery);self.tabs.clear();self.refresh();self.changed();self.open_object(self.p['documents'][0]['id']) if self.p['documents'] else self.home()
            except Exception as e:self.error(e)
    def close_tab(self,index):
        if index<0:return
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
            if getattr(page,'obj',None):self.breadcrumb.setText((tr('MANUSKRIPT') if section=='editor' else tr('DEINE WELT') if section=='world' else 'TIMELINE')+'   /   '+page.obj['name'])
        self.update_status();self.sync_format()
    def decorate_tabs(self):
        for i in range(self.tabs.count()):
            bar=self.tabs.tabBar();existing=bar.tabButton(i,QTabBar.RightSide)
            if existing and existing.objectName()=='tabClose':continue
            page=self.tabs.widget(i);close=QToolButton();close.setObjectName('tabClose');close.setText('×');close.setToolTip(tr('Tab schließen'));close.setAccessibleName(tr('Tab schließen'));close.setFocusPolicy(Qt.NoFocus);close.setFixedSize(20,20);close.clicked.connect(lambda checked=False,p=page:self.close_tab(self.tabs.indexOf(p)));bar.setTabButton(i,QTabBar.RightSide,close)
    def set_section(self,section):
        self.section=section
        for key,b in self.nav_buttons.items():b.setChecked(key==section)
        for i in range(self.nav.topLevelItemCount()):self.nav.topLevelItem(i).setHidden(i!={'editor':0,'world':1,'timeline':2}[section])
        self.collection_label.setText({'editor':tr('MANUSKRIPT'),'world':tr('KATEGORIEN & EINTRÄGE'),'timeline':tr('EREIGNISSE & ZEITALTER')}[section]);self.add_primary.setText({'editor':tr('+  Neues Kapitel'),'world':tr('+  Neuer Eintrag'),'timeline':tr('+  Neues Ereignis')}[section]);self.add_secondary.setVisible(section=='world');self.formatbar.setVisible(section=='editor' or bool(self.current()))
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
    def error(self,e): QMessageBox.warning(self,'Storynator',tr(str(e)))
    def changed(self): self.dirty=True; self.update_status()
    def update_status(self):
        self.setWindowTitle(('● ' if self.dirty else '')+self.p['name']+' — Storynator')
        if hasattr(self,'project_label'):self.project_label.setText(self.p['name'])
        e=self.editor();words=len(e.toPlainText().split()) if e else 0
        self.statusBar().showMessage('   '+(tr('Ungespeicherte Änderungen') if self.dirty else tr('Alle Änderungen gespeichert'))+'   ·   '+tr('Lokal & offline'))
        if not hasattr(self,'word_count'):
            self.word_count=label('','muted');self.statusBar().addPermanentWidget(self.word_count)
        self.word_count.setText((str(words)+' '+tr('Wörter')+'   ·   ' if e else '')+'Storynator   ')
    def refresh(self):
        self.nav.clear()
        for title,seq in [('Editor',self.p['documents']),('Welt',self.p['categories']),('Timeline',self.p['events'])]:
            root=QTreeWidgetItem([{'Editor':tr('Alle Kapitel'),'Welt':tr('Deine Kategorien'),'Timeline':tr('Alle Ereignisse')}[title]]); self.nav.addTopLevelItem(root)
            for o in seq:
                item=QTreeWidgetItem([o['name']]);item.setIcon(0,icon('file' if title=='Editor' else 'folder' if title=='Welt' else 'timeline','#9bb49a',18)); item.setData(0,Qt.UserRole,o['id']);item.setToolTip(0,self.preview_html(o['id']) if title!='Welt' else html.escape(o['name'])); root.addChild(item)
                if title=='Welt':
                    for en in self.p['entries']:
                        if en['category']==o['id']:
                            sub=QTreeWidgetItem([en['name']]);sub.setIcon(0,icon('user','#9bb49a',18));sub.setData(0,Qt.UserRole,en['id']);sub.setToolTip(0,self.preview_html(en['id'])); item.addChild(sub)
        self.nav.expandAll(); self.set_section(self.section); self.update_status()
    def menus(self):
        m=self.menuBar().addMenu(tr('Projekt'))
        for name,fn,key in [('Neu',self.new,'Ctrl+N'),('Öffnen',self.open_file,'Ctrl+O'),('Speichern',self.save,'Ctrl+S'),('Speichern unter',lambda:self.save(True),'Ctrl+Shift+S'),('Startseite',self.home,''),('Druckvorschau / PDF',self.printing,'Ctrl+P')]:
            a=m.addAction(tr(name)); a.triggered.connect(fn); a.setShortcut(key)
        m=self.menuBar().addMenu(tr('Eintrag'))
        for name,fn in [('Umbenennen',self.rename),('Löschen',self.delete),('Nach oben',lambda:self.move(-1)),('Nach unten',lambda:self.move(1))]:m.addAction(tr(name)).triggered.connect(fn)
        m=self.menuBar().addMenu(tr('Ansicht'));m.addAction(tr('Einstellungen'),self.preferences);m.addAction('Editor',lambda:self.navigate('editor'));m.addAction('Timeline',lambda:self.navigate('timeline'));m.addAction(tr('Welt'),lambda:self.navigate('world'));m.addAction(tr('Projektkalender'),self.calendar)
        a=m.addAction(tr('Fokusmodus'));a.setShortcut('F11');a.triggered.connect(self.toggle_focus)
    def current(self):
        w=self.tabs.currentWidget(); return getattr(w,'obj',None)
    def track_editor(self,old,new):
        if isinstance(new,Rich):self.active_editor=new;self.sync_format(new)
    def editor(self):
        focus=QApplication.focusWidget()
        if isinstance(focus,Rich):return focus
        page=self.tabs.currentWidget()
        if page and self.active_editor and page.isAncestorOf(self.active_editor):return self.active_editor
        return page.findChild(Rich) if page else None
    def sync_format(self,editor=None):
        if not hasattr(self,'font_control'):return
        editor=editor or self.editor()
        if not editor:return
        font=editor.currentFont();size=font.pointSizeF() or editor.document().defaultFont().pointSizeF()
        blockers=[QSignalBlocker(self.font_control),QSignalBlocker(self.size_control)];self.font_control.setCurrentFont(font);self.size_control.setValue(size if size>0 else 14)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.ToolTip:
            id=obj.property('entryId');view=obj.parent()
            if isinstance(view,QTreeWidget):
                item=view.itemAt(event.pos());id=item.data(0,Qt.UserRole) if item else None
            elif isinstance(view,QListWidget):
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
            f=QFrame();f.setFrameShape(QFrame.VLine);f.setStyleSheet('color:#dce3d6;');bar.addSpacing(8);bar.addWidget(f);bar.addSpacing(8)
        style=QComboBox();style.setProperty('translateItems',True);style.addItems(['Absatz','Überschrift 1','Überschrift 2','Aufzählung','Nummeriert']);style.setFixedWidth(145);style.activated.connect(self.paragraph);bar.addWidget(style);sep()
        font=QFontComboBox();self.font_control=font;font.setToolTip(tr('Schriftart'));font.setCurrentFont(QFont('Georgia'));font.setFixedWidth(158);font.currentFontChanged.connect(lambda f:self.fmt('setFontFamilies',[f.family()]));bar.addWidget(font)
        size=FontSizeSpin();self.size_control=size;size.setToolTip(tr('Schriftgröße'));size.setAccessibleName(tr('Schriftgröße'));size.setRange(6,96);size.setValue(14);size.setFixedWidth(85);size.valueChanged.connect(lambda v:self.fmt('setFontPointSize',v));bar.addWidget(size);sep()
        for text,tip,method,value in [('B','Fett','setFontWeight',None),('I','Kursiv','setFontItalic',None),('U','Unterstrichen','setFontUnderline',None)]:
            b=QToolButton();b.setText(text);b.setToolTip(tr(tip));b.setFocusPolicy(Qt.NoFocus);f=QFont('Georgia',12);f.setBold(text=='B');f.setItalic(text=='I');f.setUnderline(text=='U');b.setFont(f)
            def toggle(checked=False,t=text):
                e=self.editor()
                if e:self.fmt('setFontWeight',QFont.Normal if e.fontWeight()==QFont.Bold else QFont.Bold) if t=='B' else self.fmt('setFontItalic',not e.fontItalic()) if t=='I' else self.fmt('setFontUnderline',not e.fontUnderline())
            b.clicked.connect(toggle);bar.addWidget(b)
        b=QToolButton();b.setText('A');b.setToolTip(tr('Textfarbe'));b.setFocusPolicy(Qt.NoFocus);b.clicked.connect(self.color);bar.addWidget(b);sep()
        for name,align,tip in [('left',Qt.AlignLeft,'Linksbündig'),('center',Qt.AlignHCenter,'Zentriert'),('right',Qt.AlignRight,'Rechtsbündig'),('justify',Qt.AlignJustify,'Blocksatz')]:bar.addWidget(tool(name,tip,lambda checked=False,a=align:self.editor() and self.editor().setAlignment(a)))
        sep();bar.addWidget(tool('image','Bild einfügen',self.image));bar.addWidget(tool('link','Eintrag verknüpfen · @',lambda:self.editor() and self.editor().link()));bar.addWidget(tool('break','Seitenumbruch einfügen',self.pagebreak));bar.addStretch()
        bar.addWidget(tool('undo','Rückgängig · Strg+Z',lambda:self.editor() and self.editor().undo()));bar.addWidget(tool('redo','Wiederholen · Strg+Y',lambda:self.editor() and self.editor().redo()));bar.addWidget(tool('focus','Fokusmodus · F11',self.toggle_focus))
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
            if path:e.add_image(embed(self.p,path))
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
        art=QLabel();art.setPixmap(icon('feather','#668458',180).pixmap(180,180));h.addWidget(art);outer.addWidget(hero)
        outer.addWidget(label('ZULETZT GEÖFFNET','eyebrow'));recent=self.settings.value('recent',[],type=list)
        valid=[path for path in recent if Path(path).exists()]
        if not valid:
            card=QFrame();card.setObjectName('card');cl=QHBoxLayout(card);cl.setContentsMargins(22,20,22,20);cl.addWidget(label('Deine Geschichten warten auf dich.'));cl.addStretch();cl.addWidget(button('Beispiel entdecken',self.open_example));outer.addWidget(card)
        for path in valid[:5]:
            card=QFrame();card.setObjectName('card');cl=QHBoxLayout(card);cl.setContentsMargins(22,17,22,17);mark=QLabel();mark.setPixmap(icon('book','#617f50',30).pixmap(30,30));cl.addWidget(mark);cl.addSpacing(12);details=QVBoxLayout();details.addWidget(label(Path(path).stem,translate=False));details.addWidget(label(str(Path(path).parent),'muted'));cl.addLayout(details);cl.addStretch();cl.addWidget(button('Öffnen',lambda checked=False,p=path:self.open_file(p)));card.setCursor(Qt.PointingHandCursor);card.mouseReleaseEvent=lambda event,p=path:self.open_file(p);outer.addWidget(card)
        outer.addStretch();foot=QHBoxLayout()
        for name,title,desc in [('book','Schreibe deine Geschichte','Ein ruhiger Platz für jedes Kapitel.'),('world','Erschaffe deine Welt','Figuren, Orte und ihre Verbindungen.'),('timeline','Verbinde die Ereignisse','Dein Kalender. Deine Geschichte.')]:
            box=QVBoxLayout();row=QHBoxLayout();im=QLabel();im.setPixmap(icon(name,'#6f8b60',23).pixmap(23,23));row.addWidget(im);row.addWidget(label(title));row.addStretch();box.addLayout(row);box.addWidget(label(desc,'muted'));foot.addLayout(box)
        outer.addLayout(foot);self.tabs.addTab(page,tr('Willkommen'));self.tabs.setCurrentWidget(page);self.breadcrumb.setText(tr('DEIN SCHREIBATELIER'));self.formatbar.hide()
    def open_example(self):
        path=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'Beispiel.storynator'
        if path.exists():self.open_file(str(path));self.path=None;self.changed()
        else:self.error('Beispielprojekt nicht gefunden.')
    def show_world(self):
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i),'world_page',False):self.tabs.removeTab(i);break
        page=QWidget();page.world_page=True;page.section='world';l=QVBoxLayout(page);l.setContentsMargins(36,30,36,30);l.setSpacing(20)
        row=QHBoxLayout();col=QVBoxLayout();col.addWidget(label('WELTENBAU','eyebrow'));col.addWidget(label('Eine Welt voller Möglichkeiten.','title'));col.addWidget(label('Alles, was deine Geschichte lebendig macht.'));row.addLayout(col);row.addStretch();row.addWidget(primary('Neuer Eintrag',self.add_entry,'plus'));l.addLayout(row)
        scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();grid=QGridLayout(inner);grid.setContentsMargins(0,0,0,0);grid.setSpacing(18)
        for index,cat in enumerate(self.p['categories']):
            card=QFrame();card.setObjectName('card');cl=QVBoxLayout(card);cl.setContentsMargins(24,22,24,22);cl.setSpacing(13);entries=[e for e in self.p['entries'] if e['category']==cat['id']];r=QHBoxLayout();r.addWidget(label(cat['name'],'title',False));r.addStretch();r.addWidget(tool('settings','Kategorievorlage bearbeiten',lambda checked=False,c=cat:self.template(c)));cl.addLayout(r);cl.addWidget(label(str(len(entries))+tr(' Einträge · ')+str(len(cat['fields']))+tr(' eigene Felder'),'muted'))
            for en in entries[:5]:
                b=button(en['name']+'    →',lambda checked=False,id=en['id']:self.open_object(id));b.setProperty('role','subtle');b.setProperty('entryId',en['id']);b.installEventFilter(self);b.setToolTip(self.preview_html(en['id']));cl.addWidget(b)
            if not entries:cl.addWidget(label('Hier beginnt ein neuer Teil deiner Welt.','muted'))
            cl.addStretch();grid.addWidget(card,index//2,index%2)
        if not self.p['categories']:grid.addWidget(label('Lege deine erste Kategorie an – zum Beispiel Charaktere, Orte oder Länder.'),0,0)
        grid.setRowStretch((len(self.p['categories'])+1)//2,1);scroll.setWidget(inner);l.addWidget(scroll,1);l.addWidget(button('+ Eigene Kategorie anlegen',self.add_category));self.tabs.addTab(page,tr('Deine Welt'));self.tabs.setCurrentWidget(page);self.breadcrumb.setText(tr('DEINE WELT'))
    def guard(self):
        if not self.dirty:return True
        r=QMessageBox.question(self,tr('Ungespeicherte Änderungen'),tr('Änderungen speichern?'),QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        return self.save() if r==QMessageBox.Save else r==QMessageBox.Discard
    def new(self):
        if not self.guard():return
        name=ask(self,'Neues Projekt')
        if name:self.p=project_for_language(name);self.path=None;self.tabs.clear();self.refresh();self.changed();self.open_object(self.p['documents'][0]['id'])
    def open_file(self,path=None):
        if not self.guard():return
        if not isinstance(path,str):path=QFileDialog.getOpenFileName(self,tr('Projekt öffnen'),'','Storynator (*.storynator)')[0]
        if not path:return
        try:
            p=load_project(path);self.p=p;self.path=path;self.dirty=False;self.tabs.clear();self.refresh();self.remember(path);self.open_object(p['documents'][0]['id']) if p['documents'] else self.home()
        except Exception as e:self.error(e)
    def remember(self,path):
        recent=self.settings.value('recent',[],type=list);self.settings.setValue('recent',([str(path)]+[p for p in recent if p!=str(path)])[:10])
    def save(self,as_new=False):
        path=self.path
        if as_new or not path:path=QFileDialog.getSaveFileName(self,tr('Projekt speichern'),path or self.p['name']+'.storynator','Storynator (*.storynator)')[0]
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
        names=[c['name'] for c in self.p['categories']];name,ok=QInputDialog.getItem(self,tr('Kategorie'),tr('Kategorie:'),names,0,False)
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
        d=QDialog(self);d.setWindowTitle(tr('Suchergebnisse'));l=QVBoxLayout(d);ls=QListWidget();ls.viewport().installEventFilter(self);l.addWidget(ls)
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
        page=QWidget();page.obj=o;page.section='editor' if o in self.p['documents'] else 'timeline' if o in self.p['events'] else 'world'
        l=QVBoxLayout(page);l.setContentsMargins(0,0,0,0);l.setSpacing(0)
        if o in self.p['documents']:
            body=QHBoxLayout();body.setContentsMargins(25,24,0,18);body.setSpacing(25)
            canvas=QWidget();canvas_l=QVBoxLayout(canvas);canvas_l.setContentsMargins(0,0,0,0);canvas_l.setSpacing(13)
            meta=QHBoxLayout();meta.addWidget(label('MANUSKRIPT  /  '+str(self.p['documents'].index(o)+1).zfill(2),'eyebrow'));meta.addStretch();meta.addWidget(label('Deine Worte haben Raum.','muted'));canvas_l.addLayout(meta)
            paper=QFrame();paper.setObjectName('paper');paper.setMaximumWidth(880);paper_l=QVBoxLayout(paper);paper_l.setContentsMargins(65,40,65,24);paper_l.setSpacing(17)
            heading=label(o['name'],'title',False);heading.setObjectName('entryHeading');heading.setFont(QFont('Georgia',23));paper_l.addWidget(heading)
            e=Rich(self,o);e.blockSignals(True);e.setObjectName('manuscript');e.document().setDocumentMargin(0);e.setPlaceholderText(tr('Jede Geschichte beginnt mit einem ersten Satz …'));e.blockSignals(False);paper_l.addWidget(e,1);shadow(paper)
            centered=QHBoxLayout();centered.addStretch(1);centered.addWidget(paper,12);centered.addStretch(1);canvas_l.addLayout(centered,1);body.addWidget(canvas,1)
            context=QFrame();context.setObjectName('context');context.setFixedWidth(225);context_root=QVBoxLayout(context);context_root.setContentsMargins(0,0,0,0);context_area=QScrollArea();context_area.setWidgetResizable(True);context_body=QWidget();context_area.setWidget(context_body);context_root.addWidget(context_area);cx=QVBoxLayout(context_body);cx.setContentsMargins(0,2,22,18);cx.setSpacing(15);cx.addWidget(label('DEINE GESCHICHTE','eyebrow'));cx.addSpacing(5);cx.addWidget(label('Alles ist verbunden.'));hint=label('Verknüpfe beim Schreiben deine Figuren, Orte und Ereignisse.','muted');hint.setWordWrap(True);cx.addWidget(hint)
            chip=button('@  Eintrag verknüpfen',e.link);chip.setProperty('role','chip');cx.addWidget(chip);cx.addSpacing(15);cx.addWidget(label('AUS DEINER WELT','eyebrow'))
            for en in self.p['entries'][:6]:
                b=button(en['name']+'   ↗',lambda checked=False,id=en['id']:self.open_object(id));b.setProperty('role','subtle');b.setProperty('entryId',en['id']);b.installEventFilter(self);b.setToolTip(self.preview_html(en['id']));cx.addWidget(b)
            if not self.p['entries']:cx.addWidget(label('Noch keine Einträge.','muted'))
            cx.addWidget(button('Welt entdecken',self.show_world));cx.addStretch();cx.addWidget(label('DEIN SCHREIBMOMENT','eyebrow'));tip=label('Blende mit F11 alles aus, was dich vom Schreiben ablenkt.','muted');tip.setWordWrap(True);cx.addWidget(tip);body.addWidget(context);l.addLayout(body,1)
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
        row=QHBoxLayout();row.addWidget(button('@ Verknüpfen',add));row.addWidget(button('Verweis entfernen',remove));l.addLayout(row);ls.itemDoubleClicked.connect(lambda i:self.open_object(i.data(Qt.UserRole)));refresh();return box
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
            w.itemChanged.connect(lambda _:put([w.item(i).text() for i in range(w.count()) if w.item(i).checkState()==Qt.Checked]));return w
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
            t=table.cellWidget(r,1).currentText();item=table.item(r,2);settings=item.data(Qt.UserRole) or {};dialog=QDialog(d);dialog.setWindowTitle(tr('Feldeinstellungen'));form=QFormLayout(dialog)
            options=QPlainTextEdit('\n'.join(settings.get('options',[])));lo=QDoubleSpinBox();hi=QDoubleSpinBox();step=QDoubleSpinBox()
            for widget in [lo,hi,step]:widget.setRange(-1e9,1e9);widget.setDecimals(4)
            lo.setValue(settings.get('min',0));hi.setValue(settings.get('max',100));step.setValue(settings.get('step',1))
            if t in ['Dropdown','Mehrfachauswahl']:form.addRow(tr('Eine Option pro Zeile'),options)
            elif t=='Slider':form.addRow(tr('Minimum'),lo);form.addRow(tr('Maximum'),hi);form.addRow(tr('Schrittweite'),step)
            else:form.addRow(QLabel(tr('Dieser Feldtyp benötigt keine zusätzlichen Einstellungen.')))
            def apply():
                if t in ['Dropdown','Mehrfachauswahl']:item.setData(Qt.UserRole,{'options':list(dict.fromkeys(s.strip() for s in options.toPlainText().splitlines() if s.strip()))})
                elif t=='Slider':
                    if hi.value()<lo.value() or step.value()<=0:self.error('Maximum muss mindestens Minimum sein; Schrittweite muss positiv sein.');return
                    item.setData(Qt.UserRole,{'min':lo.value(),'max':hi.value(),'step':step.value()})
                dialog.accept()
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
                for en in self.p['entries']:
                    cat=next(x for x in self.p['categories'] if x['id']==en['category'])
                    for f in cat['fields']:
                        if f['type'] in ['Datum','Zeitspanne'] and en['values'].get(f['id']):
                            parts=en['values'][f['id']].split('..');cal.span(parts[0].strip(),parts[1].strip() if len(parts)>1 else '')
                if self.p['events'] and QMessageBox.question(d,tr('Kalenderänderung'),tr('Bestehende Datumswerte werden im neuen Kalender interpretiert. Übernehmen?'))!=QMessageBox.Yes:return
                self.p['calendar']=c;self.changed();d.accept()
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
        cal=Calendar(self.p['calendar']);page=QWidget();page.section='timeline';page.timeline_page=True;root=QVBoxLayout(page);root.setContentsMargins(0,0,0,0);area=QScrollArea();area.setWidgetResizable(True);content=QWidget();area.setWidget(content);root.addWidget(area);l=QVBoxLayout(content);l.setContentsMargins(32,28,32,24);l.setSpacing(20)
        row=QHBoxLayout();col=QVBoxLayout();col.setSpacing(8);col.addWidget(label('ZEIT & ZUSAMMENHÄNGE','eyebrow'));col.addWidget(label('Jede Geschichte hinterlässt Spuren.','title'));col.addWidget(label(self.p['calendar']['name']+' · Ereignisse, Zeitalter und die Verbindungen dazwischen.'));row.addLayout(col);row.addStretch();row.addWidget(primary('Ereignis anlegen',self.add_event,'plus'));l.addLayout(row)
        card=QFrame();card.setObjectName('card');cl=QVBoxLayout(card);cl.setContentsMargins(20,14,20,20);tools=QHBoxLayout();tools.addWidget(label('ZEITSTRAHL','eyebrow'));tools.addStretch();tools.addWidget(label('Strg + Mausrad zum Zoomen','muted'));cl.addLayout(tools)
        scene=QGraphicsScene();scene.setBackgroundBrush(QApplication.palette().base());view=TimelineView(scene);view.setStyleSheet('border:0;');view.setDragMode(QGraphicsView.ScrollHandDrag);view.setMinimumHeight(350);cl.addWidget(view,1);l.addWidget(card,3)
        table=QTableWidget(0,4);table.setHorizontalHeaderLabels([tr('Ereignis / Zeitalter'),tr('Art'),tr('Anfang'),tr('Ende')]);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents);table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents);table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents);table.verticalHeader().hide();table.setShowGrid(False);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setEditTriggers(QAbstractItemView.NoEditTriggers);l.addWidget(table,2)
        def draw():
            try:
                scene.clear();table.setRowCount(0);events=sorted(self.p['events'],key=lambda e:cal.ordinal(e['start']));spans=[cal.span(e['start'],e['end']) for e in events];lo=min((a for a,b in spans),default=0);hi=max((b for a,b in spans),default=1);factor=760/max(1,hi-lo)
                unit='Jahre' if not self.p['calendar']['months'] else 'Tage';axis=scene.addText(unit+tr(' seit dem Kalenderursprung'));axis.setDefaultTextColor(QColor(theme_colors(CURRENT['mode'],CURRENT['accent'])['muted']));axis.setPos(220,-67)
                for tick in range(6):
                    x=220+tick*152;scene.addLine(x,-10,x,max(60,len(events)*56),QColor('#e7ecdf'));t=scene.addText(str(round(lo+(hi-lo)*tick/5)));t.setDefaultTextColor(QColor(theme_colors(CURRENT['mode'],CURRENT['accent'])['muted']));t.setPos(x-4,-36)
                for row,(en,(a,b)) in enumerate(zip(events,spans)):
                    y=18+row*56;x=220+(a-lo)*factor;width=max(13,(b-a)*factor);name=scene.addText(en['name']);name.setDefaultTextColor(QApplication.palette().text().color());name.setPos(0,y-3)
                    date=scene.addText(cal.display(en['start']));date.setDefaultTextColor(QColor(theme_colors(CURRENT['mode'],CURRENT['accent'])['muted']));date.setFont(QFont('Segoe UI',8));date.setPos(0,y+18)
                    color=QColor('#b7c79a') if en['kind']=='Zeitalter' else QColor('#5c8051');rect=scene.addRect(x,y,width,26,Qt.NoPen,color) if en['end'] else scene.addEllipse(x-6,y+5,15,15,Qt.NoPen,color);rect.setFlag(QGraphicsItem.ItemIsSelectable);rect.setData(0,en['id']);rect.setCursor(Qt.PointingHandCursor);rect.setToolTip(en['name']+' · '+cal.display(en['start'])+(' – '+cal.display(en['end']) if en['end'] else ''))
                    table.insertRow(row);table.setRowHeight(row,43)
                    for col,text in enumerate([en['name'],en['kind'],cal.display(en['start']),cal.display(en['end']) if en['end'] else '—']):i=QTableWidgetItem(text);i.setData(Qt.UserRole,en['id']);table.setItem(row,col,i)
                if not events:
                    text=scene.addText(tr('Die Geschichte deiner Welt beginnt mit dem ersten Ereignis.'));text.setDefaultTextColor(QColor('#87977c'));text.setPos(0,20)
                scene.setSceneRect(scene.itemsBoundingRect().adjusted(-10,-10,25,25))
            except Exception as e:self.error(e)
        scene.selectionChanged.connect(lambda:[self.open_object(i.data(0)) for i in scene.selectedItems() if i.data(0)]);table.itemDoubleClicked.connect(lambda i:self.open_object(i.data(Qt.UserRole)))
        tools.addWidget(tool('plus','Vergrößern',lambda:view.scale(1.2,1.2)));zoom=QToolButton();zoom.setText('−');zoom.setToolTip(tr('Verkleinern'));zoom.clicked.connect(lambda:view.scale(1/1.2,1/1.2));tools.addWidget(zoom);tools.addWidget(button('Aktualisieren',draw));draw();self.tabs.addTab(page,'Timeline');self.tabs.setCurrentWidget(page);self.breadcrumb.setText('TIMELINE')
    def export_document(self,docs,titles=True):
        doc=QTextDocument();doc.setDefaultFont(QFont('Georgia',14));doc.setMetaInformation(QTextDocument.DocumentTitle,docs[0]['name'] if len(docs)==1 else self.p['name'])
        for k,v in self.p['assets'].items():doc.addResource(QTextDocument.ImageResource,QUrl('asset:'+k),QImage.fromData(base64.b64decode(v)))
        cur=QTextCursor(doc)
        for index,o in enumerate(docs):
            if index:
                cur.insertBlock();bf=cur.blockFormat();bf.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore);cur.setBlockFormat(bf)
            if titles:
                title=QTextCharFormat();title.setFontFamilies(['Georgia']);title.setFontPointSize(22);title.setFontWeight(QFont.Bold);cur.insertText(o['name'],title);cur.insertBlock(QTextBlockFormat(),QTextCharFormat())
            cur.insertHtml(render(self.p,o['html']))
        # Remove only link marking; retain italic/bold/font and all non-link formatting.
        block=doc.begin()
        while block.isValid():
            it=block.begin()
            while not it.atEnd():
                f=it.fragment()
                if f.isValid() and f.charFormat().isAnchor():
                    cur=QTextCursor(doc);cur.setPosition(f.position());cur.setPosition(f.position()+f.length(),QTextCursor.KeepAnchor);fmt=f.charFormat();fmt.setAnchor(False);fmt.setAnchorHref('')
                    if fmt.foreground().color().name().lower()=='#7461bb':fmt.setForeground(QColor('black'));fmt.setFontUnderline(False)
                    cur.setCharFormat(fmt)
                it+=1
            block=block.next()
        return doc
    def printing(self):
        d=QDialog(self);d.setWindowTitle(tr('Drucken & PDF'));l=QVBoxLayout(d);l.setContentsMargins(24,24,24,24);l.setSpacing(14);l.addWidget(QLabel(tr('Kapitel in Projekt-Reihenfolge auswählen:')));ls=QListWidget();ls.viewport().installEventFilter(self);l.addWidget(ls)
        saved=printing.options(self.p,self.settings);selected=saved.get('chapters')
        for o in self.p['documents']:
            i=QListWidgetItem(o['name']);i.setFlags(i.flags()|Qt.ItemIsUserCheckable);i.setCheckState(Qt.Checked if selected is None or o['id'] in selected else Qt.Unchecked);i.setData(Qt.UserRole,o['id']);ls.addItem(i)
        titles=QCheckBox(tr('Kapitelnamen als Überschrift drucken'));titles.setChecked(saved['titles']);l.addWidget(titles);printer=printing.make_printer(self.p,self.settings)
        def ids():return [ls.item(i).data(Qt.UserRole) for i in range(ls.count()) if ls.item(i).checkState()==Qt.Checked]
        def remember():
            if printing.persist(self.p,self.settings,printer,titles.isChecked(),ids()):self.changed()
        def doc():
            if not ids():self.error(tr('Mindestens ein Kapitel auswählen.'));return None
            return self.export_document([o for o in self.p['documents'] if o['id'] in ids()],titles.isChecked())
        def page_setup():
            if QPageSetupDialog(printer,d).exec():remember()
        def preview():
            document=doc()
            if document is None:return
            remember();p=QPrintPreviewDialog(printer,d);p.paintRequested.connect(document.print_);p.exec();remember()
        def pdf():
            document=doc()
            if document is None:return
            chosen=[o for o in self.p['documents'] if o['id'] in ids()];name=chosen[0]['name'] if len(chosen)==1 else self.p['name'];name=re.sub(r'[<>:"/\\|?*]','_',name).strip(' .') or 'Storynator';directory=Path(self.settings.value('printing/pdf_directory',str(Path.home())));path,_=QFileDialog.getSaveFileName(d,tr('PDF speichern'),str(directory/(name+'.pdf')),'PDF (*.pdf)')
            if path:
                printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(path if path.lower().endswith('.pdf') else path+'.pdf');printer.setDocName(name);document.print_(printer);self.settings.setValue('printing/pdf_directory',str(Path(path).parent));remember();self.statusBar().showMessage(tr('PDF exportiert: ')+path)
        def print_now():
            document=doc()
            if document is None:return
            printer.setOutputFormat(QPrinter.NativeFormat)
            if QPrintDialog(printer,d).exec():document.print_(printer);remember()
        ls.itemChanged.connect(lambda _:remember());titles.toggled.connect(lambda _:remember())
        for text,fn in [('Papier & Seitenränder',page_setup),('Druckvorschau',preview),('PDF exportieren',pdf),('Drucken',print_now)]:l.addWidget(button(text,fn))
        l.addWidget(button(tr('Übernehmen'),lambda:(remember(),d.accept())));d.resize(560,650);d.exec()

from PySide6.QtCore import QStandardPaths

def main():
    app=QApplication(sys.argv);app.setApplicationName('Storynator');app.setOrganizationName('Storynator');set_language(QSettings('Storynator','Storynator').value('language','de'));install_qt_translations(app);apply_theme(app)
    smoke='--smoke-test' in sys.argv;w=Main(recover=not smoke)
    screen=app.primaryScreen()
    if screen:
        area=screen.availableGeometry();w.resize(min(1500,max(1050,area.width()-40)),min(960,max(700,area.height()-60)))
    w.show()
    if smoke:
        def check():
            try:
                import tempfile
                w.p=load_project(Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'Beispiel.storynator');w.tabs.clear();w.refresh();w.open_object(w.p['documents'][0]['id']);w.show_timeline()
                with tempfile.TemporaryDirectory() as folder:
                    path=Path(folder)/'smoke.storynator';save_project(w.p,path);assert load_project(path)==w.p
                    pdf=Path(folder)/'smoke.pdf';printer=QPrinter();printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(str(pdf));w.export_document(w.p['documents']).print_(printer);assert pdf.stat().st_size>500
                w.dirty=False;app.exit(0)
            except Exception:
                import traceback
                Path(os.environ.get('STORYNATOR_SMOKE_LOG','smoke-error.txt')).write_text(traceback.format_exc(),encoding='utf-8');app.exit(1)
        QTimer.singleShot(400,check)
    elif len(sys.argv)>1 and Path(sys.argv[1]).suffix=='.storynator':w.open_file(sys.argv[1])
    sys.exit(app.exec())
if __name__=='__main__':main()

"""Offline Hunspell dictionaries and explicit review, never a network service."""
import sys,re,threading
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QObject,QRunnable,Signal,QThreadPool,Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QPushButton,QLabel,QListWidgetItem,QInputDialog
from ui import RoomyList,ArrowCombo as QComboBox
from i18n import tr
from authoring import snapshot,find_ranges,replace_cursor
from manuscript_ui import current_doc
LOCK=threading.RLock()
@lru_cache(maxsize=2)
def dictionary(language):
    from spylls.hunspell import Dictionary
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).parent));return Dictionary.from_zip(str(root/'assets'/'dictionaries'/((language if language in ['de_DE','en_US'] else 'de_DE')+'.zip')))

def misspellings(text,language,ignored=(),cancel=None):
    with LOCK:
        checker=dictionary(language);seen=set();out=[];ignored={x.casefold() for x in ignored}
        for match in re.finditer(r"[^\W\d_]+(?:['’][^\W\d_]+)*",text,re.UNICODE):
            if cancel and cancel.is_set():break
            word=match.group();key=word.casefold()
            if key in seen or key in ignored:continue
            seen.add(key)
            if not checker.lookup(word):out.append((word,match.start(),match.end()))
        return out
class Signals(QObject):
    done=Signal(object,str)
class CheckTask(QRunnable):
    def __init__(self,text,language,ignored):super().__init__();self.text=text;self.language=language;self.ignored=ignored;self.signals=Signals();self.cancel=threading.Event()
    def run(self):
        try:self.signals.done.emit(misspellings(self.text,self.language,self.ignored,self.cancel),'')
        except Exception as error:self.signals.done.emit([],str(error))
class SpellDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.doc=current_doc(host);self.setWindowTitle(tr('Offline-Rechtschreibung'));self.resize(650,520);layout=QVBoxLayout(self);self.language=QComboBox();self.language.addItem('Deutsch','de_DE');self.language.addItem('English','en_US');self.language.setCurrentIndex(max(0,self.language.findData(host.p.get('spelling_language','de_DE'))));layout.addWidget(self.language);self.list=RoomyList();layout.addWidget(self.list,1);self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);row=QHBoxLayout();self.check_button=QPushButton(tr('Kapitel prüfen'));self.check_button.clicked.connect(self.check);row.addWidget(self.check_button);replace=QPushButton(tr('Alle Vorkommen ersetzen'));replace.clicked.connect(self.replace);row.addWidget(replace);ignore=QPushButton(tr('Zum Projektwörterbuch'));ignore.clicked.connect(self.ignore);row.addWidget(ignore);layout.addLayout(row);manage=QPushButton(tr('Projektwörterbuch verwalten'));manage.clicked.connect(self.manage_dictionary);layout.addWidget(manage);self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1);self.check()
    def editor(self):
        if not self.doc:return None
        self.host.open_object(self.doc['id']);return self.host.editor()
    def check(self):
        editor=self.editor()
        if not editor:return
        self.host.flush_editors();self.text=editor.toPlainText();self.list.clear();self.status.setText(tr('Wörterbuch wird lokal geladen und Text geprüft …'));self.check_button.setEnabled(False);ignored=list(self.host.p.get('personal_dictionary',[]))+[word for o in self.host.p['entries'] for word in o['name'].split()];self.job=CheckTask(self.text,self.language.currentData(),ignored);self.job.signals.done.connect(self.on_checked);self.pool.start(self.job)
    def on_checked(self,items,error):
        self.check_button.setEnabled(True);self.status.setText(error or str(len(items))+' '+tr('mögliche Schreibfehler · Eigennamen können ergänzt werden.'))
        for word,start,end in items:
            item=QListWidgetItem(word);item.setData(Qt.UserRole,(word,start,end));self.list.addItem(item)
        if self.list.count():self.list.setCurrentRow(0)
    def ignore(self):
        item=self.list.currentItem()
        if item:self.host.p.setdefault('personal_dictionary',[]).append(item.data(Qt.UserRole)[0]);self.host.changed();self.list.takeItem(self.list.row(item))
    def manage_dictionary(self):
        dialog=QDialog(self);dialog.setWindowTitle(tr('Projektwörterbuch'));layout=QVBoxLayout(dialog);items=RoomyList();items.addItems(sorted(set(self.host.p.get('personal_dictionary',[]))));layout.addWidget(items);remove=QPushButton(tr('Ausgewähltes Wort entfernen'))
        def erase():
            if items.currentItem():word=items.currentItem().text();self.host.p['personal_dictionary']=[x for x in self.host.p.get('personal_dictionary',[]) if x!=word];items.takeItem(items.currentRow());self.host.changed()
        remove.clicked.connect(erase);layout.addWidget(remove);dialog.resize(450,350);dialog.exec();self.check()
    def replace(self):
        item=self.list.currentItem();editor=self.editor()
        if not item or not editor:return
        word,start,end=item.data(Qt.UserRole)
        if editor.toPlainText()!=self.text:self.check();return
        text,ok=QInputDialog.getText(self,tr('Wort ersetzen'),word,text=word)
        if not ok or text==word:return
        snapshot(self.doc,'Vor Rechtschreibkorrektur',True);matches=find_ranges(editor.document(),word,True,True)
        for start,end in reversed([(cursor.selectionStart(),cursor.selectionEnd()) for cursor in matches]):
            cursor=QTextCursor(editor.document());cursor.setPosition(start);cursor.setPosition(end,QTextCursor.KeepAnchor);replace_cursor(editor.note_cursors,cursor,text)
        editor.flush();self.host.p['spelling_language']=self.language.currentData();self.host.changed();self.check()
    def done(self,result):
        if hasattr(self,'job'):self.job.cancel.set()
        self.pool.waitForDone();super().done(result)

def license_dialog(host):
    from PySide6.QtWidgets import QTabWidget,QPlainTextEdit
    dialog=QDialog(host);dialog.setWindowTitle(tr('Lizenzen & Quellen'));layout=QVBoxLayout(dialog);tabs=QTabWidget();layout.addWidget(tabs);root=Path(getattr(sys,'_MEIPASS',Path(__file__).parent));paths=[root/'LICENSE']+[root/'assets'/'dictionaries'/name for name in ['SOURCES.txt','LICENSE-spylls.txt','LICENSE-de.txt','GPL-2.0.txt','README-en.txt','LICENSE-en.txt']]
    for path in paths:
        if path.exists():view=QPlainTextEdit(path.read_text(encoding='utf-8'));view.setReadOnly(True);tabs.addTab(view,path.name)
    close=QPushButton(tr('Schließen'));close.clicked.connect(dialog.accept);layout.addWidget(close);dialog.resize(850,650);dialog.exec()

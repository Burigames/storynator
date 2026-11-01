import copy
from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QTextEdit,QCheckBox,QPushButton,QFileDialog,QInputDialog,QMessageBox,QDialogButtonBox,QSplitter
from ui import RoomyList
from design import label,primary
from i18n import tr
import conlangs

def edit_word(parent,word=None):
    d=QDialog(parent);d.setWindowTitle(tr('Wörterbucheintrag'));d.resize(620,650);box=QVBoxLayout(d);form=QFormLayout();editors={};source=word or {}
    for key,name in [('word','Wort'),('translation','Übersetzung'),('pronunciation','Aussprache'),('part_of_speech','Wortart'),('forms','Weitere Wortformen · durch | trennen'),('definition','Definition'),('examples','Beispiele')]:
        value='|'.join(source.get(key,[])) if key=='forms' else source.get(key,'');editor=QTextEdit() if key in ['definition','examples'] else QLineEdit(value)
        if isinstance(editor,QTextEdit):editor.setPlainText(value);editor.setAcceptRichText(False);editor.setMaximumHeight(110)
        form.addRow(tr(name),editor);editors[key]=editor
    box.addLayout(form);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);box.addWidget(buttons);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject)
    if d.exec()!=QDialog.Accepted:return None
    from core import uid
    result=dict(id=source.get('id',uid()))
    for key,e in editors.items():
        text=e.toPlainText() if isinstance(e,QTextEdit) else e.text();result[key]=[x.strip() for x in text.split('|') if x.strip()] if key=='forms' else text.strip()
    if not result['word']:raise ValueError('Ein Wort wird benötigt.')
    return result
class LexiconDialog(QDialog):
    def __init__(self,host,selected=None):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Erfundene Sprachen & Wörterbücher'));self.resize(1050,730);layout=QVBoxLayout(self);layout.addWidget(label(tr('Worte für deine Welt'),'title'));split=QSplitter();self.languages=RoomyList();self.languages.setMaximumWidth(260);split.addWidget(self.languages);right=QVBoxLayout();from PySide6.QtWidgets import QWidget
        pane=QWidget();pane.setLayout(right);split.addWidget(pane);split.setStretchFactor(1,1);self.search=QLineEdit();self.search.setPlaceholderText(tr('Wort, Übersetzung oder Aussprache suchen'));right.addWidget(self.search);self.words=RoomyList();right.addWidget(self.words,1);self.preview=QTextEdit();self.preview.setReadOnly(True);right.addWidget(self.preview,1);layout.addWidget(split,1)
        for items in [[('Sprache anlegen',self.new_language),('Sprache bearbeiten',self.settings),('Sprache löschen',self.delete_language)],[('Wort hinzufügen',self.add_word),('Wort bearbeiten',self.edit_current),('Wort löschen',self.delete_word)],[('Wörterbuch importieren',self.import_file),('Wörterbuch exportieren',self.export_file),('CSV importieren',self.import_csv),('CSV exportieren',self.export_csv)]]:
            row=QHBoxLayout()
            for name,fn in items:b=QPushButton(tr(name));b.clicked.connect(fn);row.addWidget(b)
            layout.addLayout(row)
        self.languages.currentRowChanged.connect(self.refresh_words);self.words.currentRowChanged.connect(self.show_word);self.words.itemDoubleClicked.connect(lambda _:self.edit_current());self.search.textChanged.connect(self.refresh_words);self.refresh(selected);from community_ui import scroll_content;scroll_content(self,layout)
    def current(self):
        row=self.languages.currentRow();items=self.host.p.get('lexicons',[]);return items[row] if 0<=row<len(items) else None
    def refresh(self,selected=None):
        selected=selected or (self.current() or {}).get('id');self.languages.clear();items=self.host.p.get('lexicons',[]);self.languages.addItems([x['name'] for x in items]);row=next((i for i,x in enumerate(items) if x['id']==selected),0);self.languages.setCurrentRow(row if items else -1);self.refresh_words()
    def refresh_words(self,*_):
        self.words.clear();language=self.current();query=self.search.text().casefold();self.visible=[]
        if language:
            self.visible=sorted([w for w in language['words'] if query in ' '.join(str(w.get(k,'')) for k in conlangs.FIELDS).casefold()],key=lambda w:w['word'].casefold());self.words.addItems([w['word']+' · '+w.get('translation','') for w in self.visible])
        for i in range(self.words.count()):self.words.item(i).setSizeHint(QSize(0,40))
        if self.visible:self.words.setCurrentRow(0)
        else:self.preview.clear()
    def selected_word(self):
        row=self.words.currentRow();return self.visible[row] if 0<=row<len(self.visible) else None
    def show_word(self,*_):
        word=self.selected_word();names=dict(word='Wort',translation='Übersetzung',pronunciation='Aussprache',part_of_speech='Wortart',definition='Definition',examples='Beispiele',forms='Weitere Wortformen · durch | trennen');self.preview.setPlainText('\n\n'.join(tr(names[k])+': '+('|'.join(word.get(k,[])) if k=='forms' else word.get(k,'')) for k in conlangs.FIELDS) if word else '')
    def new_language(self):
        name,ok=QInputDialog.getText(self,tr('Sprache anlegen'),tr('Name:'))
        if ok and name.strip():language=conlangs.new_language(name);self.host.p.setdefault('lexicons',[]).append(language);self.host.changed();self.refresh(language['id'])
    def settings(self):
        language=self.current()
        if not language:return
        d=QDialog(self);d.setWindowTitle(tr('Sprache bearbeiten'));d.resize(600,470);box=QVBoxLayout(d);form=QFormLayout();name=QLineEdit(language['name']);alphabet=QLineEdit(language['alphabet']);notes=QTextEdit();notes.setPlainText(language['notes']);case=QCheckBox(tr('Groß-/Kleinschreibung unterscheiden'));case.setChecked(language['case_sensitive'])
        for title,widget in [('Name',name),('Alphabet / Schriftzeichen',alphabet),('Sprachnotizen',notes)]:form.addRow(tr(title),widget)
        box.addLayout(form);box.addWidget(case);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);box.addWidget(buttons)
        if d.exec()==QDialog.Accepted:
            if not name.text().strip():return
            language.update(name=name.text().strip(),alphabet=alphabet.text(),notes=notes.toPlainText(),case_sensitive=case.isChecked());self.host.changed();self.refresh(language['id'])
    def delete_language(self):
        language=self.current()
        if language and QMessageBox.question(self,tr('Sprache löschen'),tr('Sprache und alle Wörter entfernen?'))==QMessageBox.Yes:self.host.backups.create(self.host.p,self.host.path,'Vor Wörterbuch-Löschung');self.host.p['lexicons'].remove(language);self.host.changed();self.refresh()
    def add_word(self):
        language=self.current()
        if not language:self.new_language();language=self.current()
        if not language:return
        try:
            word=edit_word(self)
            if word:language['words'].append(word);self.host.changed();self.refresh_words()
        except Exception as e:self.host.error(e)
    def edit_current(self):
        word=self.selected_word()
        if not word:return
        try:
            new=edit_word(self,word)
            if new:word.update(new);self.host.changed();self.refresh_words()
        except Exception as e:self.host.error(e)
    def delete_word(self):
        word=self.selected_word()
        if word and QMessageBox.question(self,tr('Wort löschen'),tr('Wörterbucheintrag entfernen?'))==QMessageBox.Yes:self.current()['words'].remove(word);self.host.changed();self.refresh_words()
    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,tr('Wörterbuch importieren'),'','Storynator Wörterbuch (*.storynator-lexicon *.json)')
        if path:
            try:language=conlangs.import_language(self.host.p,conlangs.load(path));self.host.changed();self.refresh(language['id'])
            except Exception as e:self.host.error(e)
    def export_file(self):
        language=self.current()
        if not language:return
        path,_=QFileDialog.getSaveFileName(self,tr('Wörterbuch exportieren'),language['name']+'.storynator-lexicon','Storynator Wörterbuch (*.storynator-lexicon)')
        if path:
            try:conlangs.save(language,path)
            except Exception as e:self.host.error(e)
    def import_csv(self):
        language=self.current()
        if not language:return
        path,_=QFileDialog.getOpenFileName(self,tr('CSV importieren'),'','CSV (*.csv)')
        if path:
            try:
                words=conlangs.read_csv(path)
                if QMessageBox.question(self,tr('CSV importieren'),str(len(words))+' '+tr('Wörter einlesen? Bereits vorhandene Wörter bleiben unverändert.'))!=QMessageBox.Yes:return
                self.host.backups.create(self.host.p,self.host.path,'Vor Wörterbuch-Import');conlangs.merge_words(language,words);self.host.changed();self.refresh_words()
            except Exception as e:self.host.error(e)
    def export_csv(self):
        language=self.current()
        if not language:return
        path,_=QFileDialog.getSaveFileName(self,tr('CSV exportieren'),language['name']+'.csv','CSV (*.csv)')
        if path:
            try:conlangs.export_csv(language,path)
            except Exception as e:self.host.error(e)

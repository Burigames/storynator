"""Offline sharing workspace, separate from category-only Addons."""
import copy,json
from pathlib import Path
from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices,QTextDocument
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QFileDialog,QMessageBox,QListWidgetItem,QTextBrowser,QTextEdit,QInputDialog,QSplitter,QCheckBox,QTabWidget
from ui import RoomyList,ArrowCombo
from design import label,primary
from PySide6.QtWidgets import QScrollArea,QWidget
def scroll_content(dialog,layout):
    body=QWidget();inner=QVBoxLayout(body)
    while layout.count():
        stretch=layout.stretch(0);item=layout.takeAt(0)
        if item.widget():inner.addWidget(item.widget(),stretch)
        elif item.layout():inner.addLayout(item.layout())
        else:inner.addItem(item)
    area=QScrollArea();area.setWidgetResizable(True);area.setWidget(body);area.setFrameShape(QScrollArea.NoFrame);layout.addWidget(area)
from i18n import tr
import community as exchange
import exchange_reading as reading
KINDS={'categories':'Kategorievorlagen','calendar':'Kalender','starter':'Projekt-Starter','world':'Weltpaket','reading':'Lesefassung','challenge':'Challenge','showcase':'Welt-Schaufenster'}
def check_list(items):
    ls=RoomyList()
    for id,name in items:
        item=QListWidgetItem(name);item.setData(Qt.UserRole,id);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);ls.addItem(item)
    return ls
def selected(ls):return [ls.item(i).data(Qt.UserRole) for i in range(ls.count()) if ls.item(i).checkState()==Qt.Checked]
def apply(host,p,reason):
    host.flush_editors();host.backup_pool.waitForDone();host.record_writing_session()
    if 'writing_sessions' in host.p:p['writing_sessions']=copy.deepcopy(host.p['writing_sessions'])
    host.backups.create(host.p,host.path,reason)
    current=getattr(host.tabs.currentWidget(),'obj',{}).get('id')
    from authoring import words
    host._writing_base+=sum(words(d['html']) for d in p['documents'])-sum(words(d['html']) for d in host.p['documents'])
    # Editors retain model-object references. Close them before adopting the planned copy.
    while host.tabs.count():
        widget=host.tabs.widget(0);host.tabs.removeTab(0);widget.deleteLater()
    host.active_editor=None;host.p=p;host.changed();host.refresh()
    target=next((o for group in ['documents','entries','events'] for o in p[group] if o['id']==current),None)
    if target:host.open_object(target['id'])
    elif p['documents']:host.open_object(p['documents'][0]['id'])
class ExportDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Community · Paket erstellen'));self.resize(850,760);layout=QVBoxLayout(self)
        layout.addWidget(label(tr('Etwas weitergeben'),'title'));layout.addWidget(label(tr('Nur ausdrücklich gewählte Inhalte werden geteilt. Prüfe die Vorschau vor dem Export.')))
        form=QFormLayout();self.previous=ArrowCombo();self.previous.addItem(tr('Neues Paket'),None)
        for record in host.p.get('community_exports',[]):self.previous.addItem(record['metadata']['title']+' · '+record['metadata']['release'],record)
        form.addRow(tr('Eigene Pakete'),self.previous);self.export_meta=None;self.release=QLineEdit('1.0');form.addRow(tr('Version'),self.release);self.kind=ArrowCombo();[self.kind.addItem(tr(v),k) for k,v in KINDS.items()];form.addRow(tr('Pakettyp'),self.kind)
        self.title=QLineEdit(host.p['name']);self.author=QLineEdit();self.license=ArrowCombo();self.license.setEditable(True);self.license.addItems(['Private Nutzung','CC-BY-4.0','CC-BY-SA-4.0','CC0-1.0']);self.description=QLineEdit();self.language=ArrowCombo();self.language.addItems(['de','en']);self.tags=QLineEdit()
        for n,w in [('Titel',self.title),('Autor',self.author),('Lizenz',self.license),('Beschreibung / Aufgabe',self.description),('Sprache',self.language),('Tags, kommasepariert',self.tags)]:form.addRow(tr(n),w)
        layout.addLayout(form);split=QSplitter();self.items=check_list([]);self.fields=check_list([]);split.addWidget(self.items);split.addWidget(self.fields);layout.addWidget(label(tr('Links: Inhalte auswählen · Rechts: private Felder vom Export ausschließen')));layout.addWidget(split,1)
        self.deps=QCheckBox(tr('Verknüpfte Welt-Einträge ebenfalls aufnehmen (in Vorschau kontrollieren)'));layout.addWidget(self.deps)
        self.cover=QCheckBox(tr('Buchcover einschließen'));layout.addWidget(self.cover);layout.addWidget(primary(tr('Vorschau & Export'),self.export,'save'));self.kind.currentIndexChanged.connect(self.populate);self.previous.currentIndexChanged.connect(self.load_export);self.populate();scroll_content(self,layout)
    def load_export(self):
        record=self.previous.currentData();self.export_meta=copy.deepcopy(record['metadata']) if record else None
        if not record:self.release.setText('1.0');return
        meta=record['metadata'];self.kind.setCurrentIndex(max(0,self.kind.findData(record['kind'])));self.populate();self.title.setText(meta['title']);self.author.setText(meta['author']);self.description.setText(meta['description']);self.license.setCurrentText(meta['license']);self.language.setCurrentText(meta['language']);self.tags.setText(', '.join(meta['tags']));self.release.setText(meta['release'])
        for ls,key in [(self.items,'ids'),(self.fields,'excluded')]:
            for i in range(ls.count()):ls.item(i).setCheckState(Qt.Checked if ls.item(i).data(Qt.UserRole) in record.get(key,[]) else Qt.Unchecked)
        self.deps.setChecked(record.get('dependencies',False));self.cover.setChecked(record.get('cover',False))
    def populate(self):
        kind=self.kind.currentData();self.items.clear();self.fields.clear();group='categories' if kind=='categories' else 'documents' if kind=='reading' else 'entries' if kind in ['world','showcase'] else None
        if group:
            for o in self.host.p[group]:
                item=QListWidgetItem(o['name']);item.setData(Qt.UserRole,o['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.items.addItem(item)
        self.items.setEnabled(group is not None);self.deps.setEnabled(kind in ['world','showcase'])
        for c in self.host.p['categories']:
            for f in c['fields']:
                item=QListWidgetItem(c['name']+' / '+f['name']);item.setData(Qt.UserRole,f['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.fields.addItem(item)
        self.fields.setEnabled(kind in ['world','showcase']);self.cover.setEnabled(kind in ['reading','showcase','world'])
    def export(self):
        try:
            self.host.flush_editors();kind=self.kind.currentData();ids=selected(self.items)
            if kind in ['categories','world','showcase','reading'] and not ids:raise ValueError('Mindestens einen Inhalt auswählen.')
            meta=exchange.metadata(self.title.text(),self.author.text(),self.license.currentText(),self.description.text(),self.language.currentText(),[x.strip() for x in self.tags.text().split(',') if x.strip()])
            meta['release']=self.release.text().strip()
            if not meta['release']:raise ValueError('Eine Versionsbezeichnung wird benötigt.')
            if self.export_meta:meta['id']=self.export_meta['id']
            spec=exchange.create(self.host.p,kind,meta,ids,selected(self.fields),self.deps.isChecked(),self.host.p['covers'].get('book','') if self.cover.isEnabled() and self.cover.isChecked() else '')
            if PreviewDialog(self,spec).exec()!=QDialog.Accepted:return
            path,_=QFileDialog.getSaveFileName(self,tr('Paket speichern'),self.title.text()+'.storynator-pack','Storynator Paket (*.storynator-pack)')
            if path:
                exchange.save(spec,path);records=self.host.p.setdefault('community_exports',[]);records[:]=[r for r in records if r['metadata']['id']!=meta['id']];records.append(dict(metadata=meta,kind=kind,ids=ids,excluded=selected(self.fields),dependencies=self.deps.isChecked(),cover=self.cover.isChecked()));self.host.changed();self.accept()
        except Exception as e:self.host.error(e)

def preview_payload(spec):
    payload=copy.deepcopy(spec['payload'])
    if 'project' in payload:payload['project']['assets']={k:f'{len(v)*3//4} Bytes (eingebettet)' for k,v in payload['project']['assets'].items()}
    return json.dumps(payload,ensure_ascii=False,indent=2)

class PreviewDialog(QDialog):
    def __init__(self,parent,spec):
        super().__init__(parent);self.setWindowTitle(tr('Freigabevorschau'));self.resize(760,650);layout=QVBoxLayout(self);view=QTextEdit();view.setReadOnly(True);view.setPlainText(exchange.summary(spec)+'\n\n'+preview_payload(spec));tabs=QTabWidget();tabs.addTab(view,tr('Inhalte'));layout.addWidget(tabs)
        p=spec['payload'].get('project')
        if p and p['assets']:
            from PySide6.QtGui import QIcon,QPixmap
            from PySide6.QtCore import QSize
            from media import image_from_asset
            images=RoomyList();images.setIconSize(QSize(96,96))
            for index,key in enumerate(p['assets']):
                item=QListWidgetItem(key)
                if index<200:
                    image=image_from_asset(p,key,120)
                    if not image.isNull():item.setIcon(QIcon(QPixmap.fromImage(image)))
                images.addItem(item)
            tabs.addTab(images,tr('Bilder / Ressourcen'))
        layout.addWidget(label(tr('Kontrolliere Namen, Feldwerte und Texte auf private Inhalte und Spoiler.')))
        row=QHBoxLayout();yes=QPushButton(tr('Inhalt freigeben'));yes.clicked.connect(self.accept);no=QPushButton(tr('Abbrechen'));no.clicked.connect(self.reject);row.addWidget(yes);row.addWidget(no);layout.addLayout(row)
class ImportSelection(QDialog):
    def __init__(self,parent,spec):
        super().__init__(parent);self.spec=spec;self.setWindowTitle(tr('Importauswahl'));self.resize(700,520);layout=QVBoxLayout(self)
        layout.addWidget(label(tr('Inhalte einzeln auswählen. Benötigte Kategorievorlagen werden mit übernommen.')))
        kind=spec['kind'];p=spec['payload'].get('project',{})
        items=[(c['key'],c['name']) for c in spec['payload']['preset']['categories']] if kind=='categories' else [(o['id'],o['name']) for o in p.get('entries' if kind=='world' else 'documents',[])]
        self.list=check_list(items);layout.addWidget(self.list)
        for i in range(self.list.count()):self.list.item(i).setCheckState(Qt.Checked)
        layout.addWidget(primary(tr('Auswahl prüfen'),self.accept,'check'))
    def result_spec(self):
        if self.list.count() and not selected(self.list):raise ValueError('Mindestens einen Inhalt auswählen.')
        return exchange.select_import(self.spec,selected(self.list))

class CommunityDialog(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.catalog_rows=[];self.fetch_mode='';self.catalog_cache=host.data_root/'community-catalog.json';self.library=exchange.Library(host.data_root/'community');self.setWindowTitle(tr('Community · Bibliothek & Austausch'));self.resize(1040,900);layout=QVBoxLayout(self);layout.addWidget(label(tr('Ideen weitergeben. Welten entdecken.'),'title'));notice=label(tr('Lokale Bibliothek · Ohne Konto und ohne Internet nutzbar. Eingebaute Challenges sind freie Starter.'));notice.setWordWrap(True);layout.addWidget(notice)
        row=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText(tr('Titel, Autor oder Tags suchen'));self.kind=ArrowCombo();self.kind.addItem(tr('Alle Pakettypen'),'');[self.kind.addItem(tr(v),k) for k,v in KINDS.items()];row.addWidget(self.search);row.addWidget(self.kind);self.language=ArrowCombo();self.language.addItems([tr('Alle Sprachen'),'de','en']);self.license_filter=ArrowCombo();self.license_filter.addItems([tr('Alle Lizenzen'),'CC0-1.0','CC-BY-4.0','CC-BY-SA-4.0','Private Nutzung']);row.addWidget(self.language);row.addWidget(self.license_filter);layout.addLayout(row)
        split=QSplitter();self.list=RoomyList();self.detail=QTextEdit();self.detail.setReadOnly(True);split.addWidget(self.list);split.addWidget(self.detail);layout.addWidget(split,1)
        for captions in [[('Paket hinzufügen',self.add),('Paket erstellen',lambda:ExportDialog(host).exec()),('In Projekt importieren',self.import_current),('Projektpaket aktualisieren',self.update_current)],[('Lesen / Feedback',self.read),('HTML veröffentlichen',self.web),('PDF-Leseprobe',self.pdf)],[('Feedback übernehmen',self.feedback),('Aus Bibliothek entfernen',self.remove),('Einreichung vorbereiten',self.submission)]]:
            row=QHBoxLayout()
            for text,fn in captions:b=QPushButton(tr(text));b.clicked.connect(fn);row.addWidget(b)
            layout.addLayout(row)
        self.search.textChanged.connect(self.refresh);self.kind.currentIndexChanged.connect(self.refresh);self.language.currentIndexChanged.connect(self.refresh);self.license_filter.currentIndexChanged.connect(self.refresh);self.list.currentRowChanged.connect(self.selection);
        from community_catalog import Fetcher
        self.fetcher=Fetcher(self);self.fetcher.complete.connect(self.fetched);self.fetcher.failed.connect(lambda msg:host.error(ValueError(msg)))
        row=QHBoxLayout()
        for text,fn in [('Online-Katalog laden',self.online),('Katalog-Paket herunterladen',self.download)]:
            b=QPushButton(tr(text));b.clicked.connect(fn);row.addWidget(b)
        layout.addLayout(row);self.catalog_list=RoomyList();layout.addWidget(self.catalog_list)
        if self.catalog_cache.exists():
            try:
                from community_catalog import catalog
                self.catalog_rows=catalog(self.catalog_cache.read_bytes());self.show_catalog()
            except (ValueError,OSError):pass
        self.refresh();scroll_content(self,layout)
    def show_catalog(self):
        self.catalog_list.setVisible(bool(self.catalog_rows));self.catalog_list.clear()
        for index,item in enumerate(self.catalog_rows):
            if self.kind.currentData() and item['kind']!=self.kind.currentData():continue
            if self.language.currentIndex() and item['language']!=self.language.currentText():continue
            if self.license_filter.currentIndex() and item['license']!=self.license_filter.currentText():continue
            if self.search.text().casefold() not in json.dumps(item,ensure_ascii=False).casefold():continue
            versions=[s['metadata']['release'] for _,s in self.library.items() if s['metadata']['id']==item['id']]
            marker=' · Update / andere Version' if versions and item['release'] not in versions else ' · Heruntergeladen' if versions else ''
            entry=QListWidgetItem(item['title']+' · '+item['release']+' · '+item['language']+' · '+item['license']+marker);entry.setData(Qt.UserRole,index);self.catalog_list.addItem(entry)
    def online(self):
        from community_catalog import CATALOG
        if QMessageBox.question(self,tr('Online-Katalog'),tr('Zum Laden des Katalogs wird GitHub kontaktiert. Projektinhalte werden nicht übertragen. Fortfahren?'))!=QMessageBox.Yes:return
        try:self.fetch_mode='catalog';self.fetcher.fetch(CATALOG)
        except Exception as e:self.host.error(e)
    def download(self):
        current=self.catalog_list.currentItem()
        if not current:return
        item=self.catalog_rows[current.data(Qt.UserRole)]
        try:self.fetch_mode='package';self.fetcher.fetch(item['url'],exchange.LIMIT,item['sha256'])
        except Exception as e:self.host.error(e)
    def fetched(self,raw):
        try:
            if self.fetch_mode=='catalog':
                from community_catalog import catalog
                self.catalog_rows=catalog(raw);self.catalog_cache.write_bytes(raw);self.show_catalog()
            else:
                spec=exchange.validate(json.loads(raw))
                old=[s for _,s in self.library.items() if s['metadata']['id']==spec['metadata']['id'] and s!=spec]
                if old:
                    import difflib
                    diff='\n'.join(difflib.unified_diff(preview_payload(old[-1]).splitlines(),preview_payload(spec).splitlines(),fromfile=old[-1]['metadata']['release'],tofile=spec['metadata']['release']))
                    compare=QDialog(self);compare.setWindowTitle(tr('Versionsvergleich · bestehende Projekte bleiben erhalten'));box=QVBoxLayout(compare);text=QTextEdit();text.setReadOnly(True);text.setPlainText(diff);box.addWidget(text);close=QPushButton(tr('Weiter'));close.clicked.connect(compare.accept);box.addWidget(close);compare.resize(800,650);compare.exec()
                if PreviewDialog(self,spec).exec()==QDialog.Accepted:self.library.install(spec);self.focus_package(spec);self.show_catalog()
        except Exception as e:self.host.error(e)
    def done(self,result):
        self.fetcher.complete.disconnect();self.fetcher.failed.disconnect();self.fetcher.cancel();super().done(result)
    def refresh(self):
        self.rows=[];self.list.clear();query=self.search.text().casefold();kind=self.kind.currentData()
        for path,spec in [(None,s) for s in exchange.builtin_packages()]+self.library.items():
            if kind and spec['kind']!=kind:continue
            if self.language.currentIndex() and spec['metadata']['language']!=self.language.currentText():continue
            if self.license_filter.currentIndex() and spec['metadata']['license']!=self.license_filter.currentText():continue
            if query and query not in json.dumps(spec['metadata'],ensure_ascii=False).casefold():continue
            self.rows.append((path,spec));self.list.addItem(spec['metadata']['title']+' · '+spec['metadata']['release'])
        if self.rows:self.list.setCurrentRow(0)
        else:self.detail.clear()
        self.show_catalog()
    def current(self):
        row=self.list.currentRow();return self.rows[row] if 0<=row<len(self.rows) else (None,None)
    def selection(self,*_):
        _,spec=self.current();self.detail.setPlainText(exchange.summary(spec) if spec else '')
    def add(self,path=None):
        if not isinstance(path,str):path,_=QFileDialog.getOpenFileName(self,tr('Paket hinzufügen'),'','Storynator Paket (*.storynator-pack)')
        if not path:return
        try:
            spec=exchange.load(path)
            if PreviewDialog(self,spec).exec()==QDialog.Accepted:self.library.install(spec);self.focus_package(spec)
        except Exception as e:self.host.error(e)
    def focus_package(self,spec):
        self.search.clear();self.kind.setCurrentIndex(0);self.language.setCurrentIndex(0);self.license_filter.setCurrentIndex(0);self.refresh()
        for row,(_,item) in enumerate(self.rows):
            if exchange.digest(item)==exchange.digest(spec):self.list.setCurrentRow(row);break
    def import_current(self):
        _,spec=self.current()
        if not spec:return
        try:
            selection=ImportSelection(self,spec)
            if selection.exec()!=QDialog.Accepted:return
            spec=selection.result_spec();self.host.flush_editors();p,warnings=exchange.plan_import(self.host.p,spec)
            previous=[x for x in self.host.p.get('community_imports',[]) if x['package']==spec['metadata']['id']]
            message=exchange.summary(spec)+'\n\n'+('\n'.join(warnings) or 'Neue Inhalte erhalten neue Kennungen.')
            if previous:message+='\nDieses Paket wurde bereits importiert. Erneuter Import erzeugt eine separate Kopie. Eigene Änderungen bleiben erhalten.'
            if QMessageBox.question(self,tr('Import mit vorheriger Sicherung'),message)!=QMessageBox.Yes:return
            apply(self.host,p,'Vor Community-Import');self.accept()
        except Exception as e:self.host.error(e)
    def update_current(self):
        _,spec=self.current()
        if not spec:return
        try:
            if PreviewDialog(self,spec).exec()!=QDialog.Accepted:return
            self.host.flush_editors();planned,conflicts=exchange.plan_update(self.host.p,spec);choices={}
            if conflicts:
                d=QDialog(self);d.setWindowTitle(tr('Update-Konflikte · eigene Änderungen schützen'));box=QVBoxLayout(d);box.addWidget(label(tr('Je Objekt entscheiden. Standard: lokale Fassung behalten. Nicht mehr enthaltene Objekte werden nicht gelöscht.')));form=QFormLayout()
                for conflict in conflicts:
                    combo=ArrowCombo();combo.addItem(tr('Lokale Fassung behalten'),'local');combo.addItem(tr('Paketfassung übernehmen'),'package');form.addRow(conflict['name'],combo);choices[conflict['id']]=combo
                box.addLayout(form);button=QPushButton(tr('Entscheidungen übernehmen'));button.clicked.connect(d.accept);box.addWidget(button)
                if d.exec()!=QDialog.Accepted:return
                planned,_=exchange.plan_update(self.host.p,spec,{id:combo.currentData() for id,combo in choices.items()})
            if QMessageBox.question(self,tr('Paket aktualisieren'),tr('Unveränderte importierte Objekte aktualisieren und ausgewählte Konfliktentscheidungen übernehmen? Vorher wird eine Sicherung erstellt. Nicht mehr enthaltene Objekte bleiben erhalten.'))!=QMessageBox.Yes:return
            apply(self.host,planned,'Vor Paketaktualisierung');self.accept()
        except Exception as e:self.host.error(e)
    def remove(self):
        path,spec=self.current()
        if not path:return
        if QMessageBox.question(self,tr('Paket entfernen'),tr('Nur aus der lokalen Bibliothek entfernen? Importierte Projektinhalte bleiben erhalten.'))==QMessageBox.Yes:self.library.remove(path);self.refresh()
    def read(self):
        _,spec=self.current()
        if not spec:return
        if spec['kind']!='reading':self.host.error(ValueError('Bitte eine Lesefassung auswählen.'));return
        ReaderDialog(self.host,spec).exec()
    def web(self):
        _,spec=self.current()
        if not spec:return
        try:
            if PreviewDialog(self,spec).exec()!=QDialog.Accepted:return
            path,_=QFileDialog.getSaveFileName(self,tr('Offline-Website exportieren'),spec['metadata']['title']+'.html','HTML (*.html)')
            if path:reading.website(spec,path)
        except Exception as e:self.host.error(e)
    def pdf(self):
        _,spec=self.current()
        if not spec or spec['kind']!='reading':return
        try:
            from printing import write_pdf,make_printer,manuscript_document
            path,_=QFileDialog.getSaveFileName(self,tr('PDF-Leseprobe'),spec['metadata']['title']+'.pdf','PDF (*.pdf)')
            if not path:return
            p=spec['payload']['project'];printer=make_printer(p,self.host.settings)
            doc=manuscript_document(p,p['documents'],pdf=True,printer=printer,cover_kinds=['book'],settings=self.host.settings)
            write_pdf(doc,path,printer)
        except Exception as e:self.host.error(e)
    def feedback(self):
        path,_=QFileDialog.getOpenFileName(self,tr('Feedback übernehmen'),'','Storynator Feedback (*.storynator-feedback)')
        if not path:return
        try:
            if Path(path).stat().st_size>4*1024*1024:raise ValueError('Feedback-Datei zu groß.')
            self.host.flush_editors();p,count,uncertain=reading.import_feedback(self.host.p,json.loads(Path(path).read_text(encoding='utf-8')))
            if QMessageBox.question(self,tr('Feedback-Vorschau'),f'{count} neue Kommentare. {uncertain} Textstellen sind wegen Änderungen abgelöst und müssen geprüft werden. Übernehmen?')==QMessageBox.Yes:apply(self.host,p,'Vor Feedback-Import');self.accept()
        except Exception as e:self.host.error(e)
    def submission(self):
        _,spec=self.current()
        if not spec:return
        folder=QFileDialog.getExistingDirectory(self,tr('Einreichung vorbereiten'))
        if not folder:return
        try:
            target=Path(folder)/('Storynator-Einreichung-'+exchange.digest(spec)[:10]);target.mkdir(exist_ok=False);exchange.save(spec,target/'Paket.storynator-pack');(target/'README.txt').write_text(exchange.summary(spec)+'\n\nEinreichung: https://github.com/Burigames/storynator/issues\nBitte Paket anhängen und Nutzungsrechte/Herkunft angeben. Freigabe erfolgt manuell.\nKeine automatische Veröffentlichung.\nProbleme können über dieselbe Adresse gemeldet werden.',encoding='utf-8');QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        except Exception as e:self.host.error(e)
class ReaderDialog(QDialog):
    def __init__(self,host,spec):
        super().__init__(host);self.host=host;self.spec=spec;self.comments=[];self.dirty=False;self.setWindowTitle(tr('Lesefassung · '+spec['metadata']['title']));self.resize(920,760);layout=QVBoxLayout(self);self.docs=ArrowCombo();[self.docs.addItem(d['name'],d) for d in spec['payload']['project']['documents']];layout.addWidget(self.docs);self.view=QTextBrowser();self.view.setOpenLinks(False);self.view.setOpenExternalLinks(False);layout.addWidget(self.view,1);self.notes=RoomyList();layout.addWidget(self.notes);row=QHBoxLayout()
        for text,fn in [('Auswahl kommentieren',self.comment),('Kommentar entfernen',self.remove),('Feedback speichern',self.save)]:b=QPushButton(tr(text));b.clicked.connect(fn);row.addWidget(b)
        layout.addLayout(row);self.docs.currentIndexChanged.connect(self.show_doc);self.show_doc()
    def show_doc(self):
        d=self.docs.currentData()
        if not d:return
        # QTextDocument resource loading is restricted to embedded project images.
        from media import image_from_asset
        p=self.spec['payload']['project'];self.view.document().clear()
        for k in p['assets']:self.view.document().addResource(QTextDocument.ImageResource,QUrl('asset:'+k),image_from_asset(p,k,1600))
        self.view.setHtml(d['html'])
    def comment(self):
        if not self.docs.currentData():return
        text,ok=QInputDialog.getMultiLineText(self,tr('Kommentar'),tr('Dein Feedback:'))
        if ok and text.strip():
            self.dirty=True;c=self.view.textCursor();self.comments.append(dict(document=self.docs.currentData()['id'],start=c.selectionStart(),end=c.selectionEnd(),text=text));self.notes.addItem(self.docs.currentText()+': '+text)
    def remove(self):
        row=self.notes.currentRow()
        if row>=0:self.dirty=True;self.comments.pop(row);self.notes.takeItem(row)
    def save(self):
        try:
            name,ok=QInputDialog.getText(self,tr('Feedback'),tr('Dein Anzeigename:'))
            if not ok:return
            data=reading.feedback(self.spec,self.comments,name);path,_=QFileDialog.getSaveFileName(self,tr('Feedback speichern'),tr('Feedback.storynator-feedback'),'Storynator Feedback (*.storynator-feedback)')
            if path:Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');self.dirty=False
        except Exception as e:self.host.error(e)

    def done(self,result):
        if self.dirty and QMessageBox.question(self,tr('Ungespeichertes Feedback'),tr('Feedback wurde noch nicht gespeichert. Verwerfen und schließen?'))!=QMessageBox.Yes:return
        super().done(result)

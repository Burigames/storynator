"""Explicit Markdown editing for every Rich editor, with preview and reversible replacement."""
import copy,re
from PySide6.QtCore import QTimer,QUrl,Qt,Signal
from PySide6.QtGui import QTextDocument,QTextCursor,QTextDocumentFragment,QFont,QTextFormat
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPlainTextEdit,QTextBrowser,QPushButton,QSplitter,QMessageBox
from design import label
from i18n import tr
from core import objects,render
from media import image_from_asset

def markdown_html(project,text,font=None,aliases=None):
    # No embedded raw HTML: Markdown is content, not an executable extension.
    class LocalDocument(QTextDocument):
        def loadResource(self,type,url):return None
    doc=LocalDocument();doc.setDefaultFont(font or QFont('Georgia',14));doc.setMarkdown(text,QTextDocument.MarkdownDialectGitHub|QTextDocument.MarkdownNoHTML)
    aliases=aliases or {};block=doc.begin();ranges=[];images=[]
    while block.isValid():
        it=block.begin()
        while not it.atEnd():
            fragment=it.fragment()
            if fragment.isValid():
                fmt=fragment.charFormat();href=fmt.anchorHref()
                if href in aliases:fmt.setAnchorHref(aliases[href]);href=aliases[href]
                if href.startswith('entry:'):raise ValueError('Diese Markdown-Verknüpfung stammt aus einer anderen Bearbeitung. Bitte erneut über @ auswählen.')
                if href.startswith('story:'):ranges.append((fragment.position(),fragment.length(),fmt))
                if fmt.isImageFormat():
                    image=fmt.toImageFormat()
                    if image.name() in aliases:image.setName(aliases[image.name()])
                    url=image.name()
                    if not url.startswith('asset:') or url[6:] not in project['assets']:raise ValueError('Markdown-Bilder müssen eingebettete Projektbilder verwenden (asset:…).')
                    picture=image_from_asset(project,url[6:],1600)
                    if picture.isNull():raise ValueError('Ein Markdown-Bild konnte nicht gelesen werden.')
                    width=min(550,picture.width());image.setWidth(width);image.setHeight(width*picture.height()/max(1,picture.width()));images.append((fragment.position(),fragment.length(),image))
            it+=1
        block=block.next()
    for start,length,fmt in ranges:
        cursor=QTextCursor(doc);cursor.setPosition(start);cursor.setPosition(start+length,QTextCursor.KeepAnchor);fmt.clearProperty(QTextFormat.ForegroundBrush);fmt.setFontUnderline(False);cursor.setCharFormat(fmt)
    for start,length,fmt in images:
        cursor=QTextCursor(doc);cursor.setPosition(start);cursor.setPosition(start+length,QTextCursor.KeepAnchor);cursor.setCharFormat(fmt)
    result=doc.toHtml()
    assets=set(re.findall(r'<img[^>]*src="([^"]+)"',result));known={o['id'] for o in objects(project)}
    if any(not src.startswith('asset:') or src[6:] not in project['assets'] for src in assets):raise ValueError('Markdown-Bilder müssen eingebettete Projektbilder verwenden (asset:…).')
    for target in re.findall(r'href="story:([^"]+)"',result):
        if target not in known:raise ValueError('Ein Markdown-Verknüpfungsziel fehlt im Projekt.')
    return render(project,result)

def apply_markdown(editor,text,aliases=None,assets=None):
    host=editor.w;host.flush_editors();project={**host.p,'assets':{**host.p['assets'],**(assets or {})}};converted=markdown_html(project,text,editor.document().defaultFont(),aliases)
    host.backups.create(host.p,host.path,'Vor Markdown-Bearbeitung')
    if editor.key=='html' and any(d is editor.obj for d in host.p['documents']):
        from authoring import snapshot
        snapshot(editor.obj,'Vor Markdown-Bearbeitung',True)
    for key in set(re.findall(r'asset:([^\s\"<>]+)',converted)):
        if key in project['assets']:host.p['assets'][key]=project['assets'][key]
    # Replace in a single undo block. Existing text notes become detached, with their quotes retained.
    cursor=QTextCursor(editor.document());cursor.beginEditBlock();cursor.select(QTextCursor.Document);cursor.insertHtml(converted);cursor.endEditBlock()
    for note in editor.obj.get('annotations',[]):note.update(start=0,end=0,detached=True)
    editor.reload_annotations();editor.flush();host.changed()

class MarkdownSource(QPlainTextEdit):
    link_requested=Signal()
    def keyPressEvent(self,event):
        if event.text()=='@':self.link_requested.emit();return
        super().keyPressEvent(event)

class MarkdownDialog(QDialog):
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor;self.setWindowTitle(tr('Markdown bearbeiten'));self.resize(1100,740);layout=QVBoxLayout(self);notice=label(tr('Markdown mit Live-Vorschau. Nicht darstellbare Word-Formatierungen können beim Übernehmen vereinfacht werden. Der bisherige Text bleibt gesichert. Bestehende Textkommentare werden als abgelöst markiert.'));notice.setWordWrap(True);layout.addWidget(notice);split=QSplitter();self.aliases={};self.staged_assets=dict(editor.w.p['assets']);self.source=MarkdownSource();self.source.link_requested.connect(self.link);self.source.setPlainText(self.source_text());self.original=self.source.toPlainText();self.preview=QTextBrowser();self.preview.setOpenLinks(False);self.preview.setOpenExternalLinks(False);split.addWidget(self.source);split.addWidget(self.preview);layout.addWidget(split,1);self.status=label('');self.status.setWordWrap(True);layout.addWidget(self.status);row=QHBoxLayout();link=QPushButton(tr('@ Verknüpfen'));link.clicked.connect(self.link);row.addWidget(link);image=QPushButton(tr('Bild einfügen'));image.clicked.connect(self.image);row.addWidget(image);self.save=QPushButton(tr('Übernehmen'));self.save.clicked.connect(self.apply);row.addWidget(self.save);cancel=QPushButton(tr('Abbrechen'));cancel.clicked.connect(self.reject);row.addWidget(cancel);layout.addLayout(row);self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.update_preview);self.source.textChanged.connect(lambda:self.timer.start(150));self.update_preview()
    def alias(self,url):
        from core import uid
        existing=next((key for key,value in self.aliases.items() if value==url),None)
        if existing:return existing
        token=('entry:' if url.startswith('story:') else 'image:')+uid().replace('-','')[:12];self.aliases[token]=url;return token
    def source_text(self):
        document=self.editor.document().clone();block=document.begin();changes=[]
        while block.isValid():
            it=block.begin()
            while not it.atEnd():
                fragment=it.fragment()
                if fragment.isValid():
                    fmt=fragment.charFormat()
                    if fmt.anchorHref().startswith('story:'):fmt.setAnchorHref(self.alias(fmt.anchorHref()));changes.append((fragment.position(),fragment.length(),fmt))
                    if fmt.isImageFormat():
                        image=fmt.toImageFormat()
                        if image.name().startswith('asset:'):image.setName(self.alias(image.name()));changes.append((fragment.position(),fragment.length(),image))
                it+=1
            block=block.next()
        for start,length,fmt in changes:
            cursor=QTextCursor(document);cursor.setPosition(start);cursor.setPosition(start+length,QTextCursor.KeepAnchor);cursor.setCharFormat(fmt)
        return document.toMarkdown(QTextDocument.MarkdownDialectGitHub)
    def update_preview(self):
        try:
            project={**self.editor.w.p,'assets':self.staged_assets};result=markdown_html(project,self.source.toPlainText(),self.editor.document().defaultFont(),self.aliases);self.preview.document().clear()
            for key in set(re.findall(r'asset:([^\s\"<>]+)',result)):self.preview.document().addResource(QTextDocument.ImageResource,QUrl('asset:'+key),image_from_asset(project,key,1200))
            self.preview.setHtml(result);self.status.setText('');self.save.setEnabled(True)
        except ValueError as e:self.status.setText(tr(str(e)));self.save.setEnabled(False)
    def link(self):
        from app import Picker
        picker=Picker(self.editor.w)
        if picker.exec():
            from core import resolve
            name=resolve(self.editor.w.p,picker.id)['name'];name=re.sub(r'([\\\[\]])',r'\\\1',name);self.source.insertPlainText('['+name+']('+self.alias('story:'+picker.id)+')')
    def image(self):
        from PySide6.QtWidgets import QFileDialog
        from media import import_image
        path,_=QFileDialog.getOpenFileName(self,tr('Bild einfügen'),'','Bilder (*.png *.jpg *.jpeg *.webp *.bmp)')
        if path:
            try:key=import_image({'assets':self.staged_assets},path);self.source.insertPlainText('![Bild]('+self.alias('asset:'+key)+')')
            except Exception as e:self.editor.w.error(e)
    def apply(self):
        try:
            if self.source.toPlainText()!=self.original:apply_markdown(self.editor,self.source.toPlainText(),self.aliases,self.staged_assets)
            self.accept()
        except Exception as e:self.editor.w.error(e)
    def done(self,result):
        if result==QDialog.Rejected and self.source.toPlainText()!=self.original and QMessageBox.question(self,tr('Ungespeicherte Änderungen'),tr('Markdown-Änderungen verwerfen?'))!=QMessageBox.Yes:return
        self.timer.stop();self.staged_assets.clear();super().done(result)

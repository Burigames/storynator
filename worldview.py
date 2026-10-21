"""Read-first world entry pages, with expandable rich text and linked field values."""
import base64,html
from PySide6.QtCore import Qt,QUrl,QSize
from PySide6.QtGui import QImage,QPixmap,QTextDocument,QIcon,QTextCursor,QTextFormat,QColor
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QHBoxLayout,QGridLayout,QFrame,QTextBrowser,QPushButton,QProgressBar,QDialog,QScrollArea,QSizePolicy,QTextEdit
from core import resolve,render,Calendar
from design import label,primary,icon,CURRENT
from i18n import tr

class RichDisplay(QTextBrowser):
    def __init__(self,host,text):
        super().__init__();self.setReadOnly(True);self.setOpenLinks(False);self.setFrameShape(QFrame.NoFrame);self.setStyleSheet('QTextBrowser{border:0;background:transparent;padding:0;}');self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        for key,value in host.p['assets'].items():self.document().addResource(QTextDocument.ImageResource,QUrl('asset:'+key),QImage.fromData(base64.b64decode(value)))
        self.setHtml(render(host.p,text));self.update_marks();self.anchorClicked.connect(lambda url:host.open_object(url.toString()[6:]) if url.toString().startswith('story:') else None);self.document().documentLayout().documentSizeChanged.connect(lambda _:self.fit_text());self.fit_text()
    def update_marks(self):
        selections=[];block=self.document().begin()
        while block.isValid():
            it=block.begin()
            while not it.atEnd():
                frag=it.fragment()
                if frag.isValid():
                    fmt=frag.charFormat();anchor=fmt.isAnchor() and fmt.anchorHref().startswith('story:');black=CURRENT['mode']=='dark' and fmt.hasProperty(QTextFormat.ForegroundBrush) and fmt.foreground().color().lightness()<45
                    if anchor or black:
                        selection=QTextEdit.ExtraSelection();selection.cursor=QTextCursor(self.document());selection.cursor.setPosition(frag.position());selection.cursor.setPosition(frag.position()+frag.length(),QTextCursor.KeepAnchor);selection.format.setForeground(QColor(CURRENT['link'] if anchor else '#e0e7ed'));selections.append(selection)
                it+=1
            block=block.next()
        self.setExtraSelections(selections)
    def fit_text(self):
        height=max(28,int(self.document().size().height())+14)
        if self.height()!=height:self.setFixedHeight(height)
    def resizeEvent(self,event):super().resizeEvent(event);self.document().setTextWidth(max(80,self.viewport().width()));self.fit_text()

def linked_button(host,id):
    target=resolve(host.p,id);b=QPushButton((target['name']+'  ↗') if target else tr('[Gelöschter Eintrag]'));b.setProperty('role','subtle');b.setProperty('entryId',id);b.installEventFilter(host);b.setCursor(Qt.PointingHandCursor);b.clicked.connect(lambda:host.open_object(id));return b

def image_grid(host,ids):
    box=QWidget();grid=QGridLayout(box);grid.setContentsMargins(0,0,0,0);grid.setSpacing(16)
    for i,key in enumerate(ids):
        image=QImage.fromData(base64.b64decode(host.p['assets'].get(key,'')));b=QPushButton();b.setMinimumSize(180,145);b.setIcon(QIcon(QPixmap.fromImage(image)));b.setIconSize(QSize(210,170));b.setToolTip(tr('Bild öffnen'));b.setCursor(Qt.PointingHandCursor)
        def show(checked=False,img=image):
            d=QDialog(host);d.setWindowTitle(tr('Bild'));outer=QVBoxLayout(d);area=QScrollArea();lab=QLabel();lab.setPixmap(QPixmap.fromImage(img));area.setWidget(lab);outer.addWidget(area);d.resize(min(950,img.width()+45),min(750,img.height()+65));d.exec()
        b.clicked.connect(show);grid.addWidget(b,i//3,i%3)
    return box

def read_field(host,field,value):
    type=field['type']
    if value is None or value=='' or value==[]:return label(tr('Nicht ausgefüllt'),'muted')
    if type=='Richtext':return RichDisplay(host,str(value))
    if type in ['Bild','Galerie']:return image_grid(host,value if isinstance(value,list) else [value])
    if type=='Verknüpfung' or field.get('source_category'):
        box=QWidget();layout=QVBoxLayout(box);layout.setContentsMargins(0,0,0,0)
        for id in value if isinstance(value,list) else [value]:layout.addWidget(linked_button(host,id) if resolve(host.p,id) or len(str(id))==36 else label(str(id),translate=False))
        return box
    if type=='Checkbox':return label(tr('Ja') if value else tr('Nein'))
    if type=='Mehrfachauswahl':return label(' · '.join(str(v) for v in value),translate=False)
    if type=='Slider':
        box=QWidget();layout=QHBoxLayout(box);layout.setContentsMargins(0,0,0,0);bar=QProgressBar();bar.setRange(0,1000);lo=field.get('min',0);hi=field.get('max',100);bar.setValue(round(1000*(value-lo)/(hi-lo)) if hi>lo else 0);bar.setTextVisible(False);bar.setMaximumWidth(350);layout.addWidget(bar);layout.addWidget(label(str(value)+' / '+str(hi),translate=False));layout.addStretch();return box
    text=str(value)
    if type in ['Datum','Zeitspanne']:
        try:text=' — '.join(Calendar(host.p['calendar']).display(part.strip()) for part in text.split('..'))
        except (ValueError,KeyError,IndexError):pass
    result=label(text,translate=False);result.setWordWrap(True);result.setTextFormat(Qt.PlainText);result.setTextInteractionFlags(Qt.TextSelectableByMouse);return result

class WorldReader(QWidget):
    def __init__(self,host,entry,edit):
        super().__init__();self.setObjectName('worldReader');outer=QVBoxLayout(self);outer.setContentsMargins(38,28,38,32);outer.setSpacing(22);category=next(c for c in host.p['categories'] if c['id']==entry['category'])
        top=QHBoxLayout();titles=QVBoxLayout();titles.addWidget(label(category['name'].upper(),'eyebrow',False));heading=label(entry['name'],'title',False);heading.setObjectName('entryHeading');titles.addWidget(heading);top.addLayout(titles);top.addStretch();top.addWidget(primary(tr('Bearbeiten'),edit,'edit'));outer.addLayout(top)
        if entry.get('html'):
            card=QFrame();card.setObjectName('card');layout=QVBoxLayout(card);layout.setContentsMargins(24,20,24,22);layout.addWidget(label(tr('Beschreibung'),'eyebrow'));layout.addWidget(RichDisplay(host,entry['html']));outer.addWidget(card)
        for f in category['fields']:
            card=QFrame();card.setObjectName('card');layout=QVBoxLayout(card);layout.setContentsMargins(24,19,24,21);layout.setSpacing(10);layout.addWidget(label(f['name'],'eyebrow',False));layout.addWidget(read_field(host,f,entry.get('values',{}).get(f['id'])));outer.addWidget(card)
        card=QFrame();card.setObjectName('card');layout=QVBoxLayout(card);layout.setContentsMargins(24,20,24,20);layout.addWidget(label(tr('Verknüpfungen'),'eyebrow'))
        for id in entry.get('links',[]):layout.addWidget(linked_button(host,id))
        if not entry.get('links'):layout.addWidget(label(tr('Noch keine Verknüpfungen.'),'muted'))
        outer.addWidget(card);outer.addStretch()

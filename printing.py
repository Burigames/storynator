"""Portable project print settings with local defaults."""
import json
from PySide6.QtCore import QMarginsF,QSizeF
from PySide6.QtGui import QPageLayout,QPageSize,QTextDocument
from PySide6.QtPrintSupport import QPrinter,QPrinterInfo
DEFAULTS={'paper':QPageSize.A4.value,'width':210.,'height':297.,'orientation':QPageLayout.Portrait.value,'margins':[20.,20.,20.,20.],'titles':True,'chapters':None}
def options(project,settings):
    try:saved=json.loads(settings.value('printing/defaults','{}'))
    except (ValueError,TypeError):saved={}
    return {**DEFAULTS,**saved,**project.get('print_settings',{})}
def make_printer(project,settings):
    printer=QPrinter(QPrinter.HighResolution);data=options(project,settings)
    name=settings.value('printing/printer','')
    if name in QPrinterInfo.availablePrinterNames():printer.setPrinterName(name)
    try:
        paper=QPageSize(QPageSize.PageSizeId(data['paper'])) if data['paper']!=QPageSize.Custom.value else QPageSize(QSizeF(data['width'],data['height']),QPageSize.Millimeter)
        layout=QPageLayout(paper,QPageLayout.Orientation(data['orientation']),QMarginsF(*data['margins']),QPageLayout.Millimeter)
        if not layout.isValid():raise ValueError('Invalid print layout')
        printer.setPageLayout(layout)
    except (ValueError,TypeError):printer.setPageSize(QPageSize(QPageSize.A4));printer.setPageMargins(QMarginsF(20,20,20,20))
    printer.setCopyCount(max(1,int(data.get('copies',1))));printer.setCollateCopies(bool(data.get('collate',False)))
    try:printer.setDuplex(QPrinter.DuplexMode(data.get('duplex',QPrinter.DuplexNone.value)));printer.setColorMode(QPrinter.ColorMode(data.get('color',QPrinter.Color.value)))
    except ValueError:pass
    return printer

def capture(printer,titles=True,chapters=None):
    layout=printer.pageLayout();size=layout.pageSize().size(QPageSize.Millimeter);m=layout.margins(QPageLayout.Millimeter)
    return dict(paper=layout.pageSize().id().value,width=size.width(),height=size.height(),orientation=layout.orientation().value,margins=[m.left(),m.top(),m.right(),m.bottom()],titles=bool(titles),chapters=chapters,copies=printer.copyCount(),collate=printer.collateCopies(),duplex=printer.duplex().value,color=printer.colorMode().value)

def persist(project,settings,printer,titles=True,chapters=None,**extra):
    data={**{k:v for k,v in project.get('print_settings',{}).items() if k.startswith('pdf_cover_')},**capture(printer,titles,chapters),**extra};changed=project.get('print_settings')!=data;project['print_settings']=data;settings.setValue('printing/defaults',json.dumps({k:v for k,v in data.items() if k!='chapters'}));settings.setValue('printing/printer',printer.printerName());settings.sync();return changed

def write_pdf(document,path,layout_printer):
    """Use a short-lived print engine so Windows does not retain the exported file."""
    printer=QPrinter(QPrinter.HighResolution);printer.setOutputFormat(QPrinter.PdfFormat);printer.setPageLayout(layout_printer.pageLayout());printer.setOutputFileName(str(path));printer.setDocName(document.metaInformation(QTextDocument.DocumentTitle));document.print_(printer)
    del printer

def pdf_preview(host,document,printer):
    import tempfile
    from pathlib import Path
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    from PySide6.QtWidgets import QDialog,QVBoxLayout,QPushButton
    from i18n import tr
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'preview.pdf';write_pdf(document,path,printer);data=QByteArray(path.read_bytes());buffer=QBuffer(data);buffer.open(QIODevice.ReadOnly);pdf=QPdfDocument();pdf.load(buffer)
        d=QDialog(host);d.setWindowTitle(tr('PDF-Vorschau · mit Cover'));layout=QVBoxLayout(d);view=QPdfView(d);view.setDocument(pdf);view.setPageMode(QPdfView.PageMode.MultiPage);view.setZoomMode(QPdfView.ZoomMode.FitToWidth);layout.addWidget(view);close=QPushButton(tr('Schließen'));close.clicked.connect(d.accept);layout.addWidget(close);d.resize(800,850);d.exec();from shiboken6 import delete
        delete(d);pdf.close();del pdf;buffer.close()


def manuscript_document(project,docs,titles=True,pdf=False,printer=None,cover_kinds=None,settings=None):
    import re,authoring
    from core import render
    from media import image_from_asset
    from PySide6.QtCore import Qt,QUrl
    from PySide6.QtGui import QFont,QImage,QTextCursor,QTextImageFormat,QTextBlockFormat,QTextCharFormat,QTextFormat,QColor
    selected_ids={d['id'] for d in docs};docs=[d for d in authoring.ordered_documents(project) if d['id'] in selected_ids]
    doc=QTextDocument();doc.setDefaultFont(QFont('Georgia',14));doc.setMetaInformation(QTextDocument.DocumentTitle,docs[0]['name'] if len(docs)==1 else project['name'])
    keys={key for obj in docs for key in re.findall(r'asset:([^\s\"<>]+)',obj['html'])}
    if pdf:keys.update(project.get('covers',{}).values())
    for key in keys:
        if key in project['assets']:doc.addResource(QTextDocument.ImageResource,QUrl('asset:'+key),image_from_asset(project,key,4096))
    cur=QTextCursor(doc);cover_count=0
    if pdf:
        printer=printer or make_printer(project,settings);rect=printer.pageLayout().paintRectPoints();doc.setPageSize(QSizeF(rect.width(),rect.height()));available_width=max(1,rect.width()-2*doc.documentMargin());available_height=max(1,rect.height()-2*doc.documentMargin()-35)
        for kind in cover_kinds if cover_kinds is not None else ['project','book']:
            key=project.get('covers',{}).get(kind);image=image_from_asset(project,key,4096) if key else QImage()
            if image.isNull():continue
            if cover_count:cur.insertBlock()
            block=QTextBlockFormat();block.setAlignment(Qt.AlignCenter)
            if cover_count:block.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore)
            cur.setBlockFormat(block);size=QSizeF(image.size());size.scale(available_width,available_height,Qt.KeepAspectRatio);fmt=QTextImageFormat();fmt.setName('asset:'+key);fmt.setWidth(size.width());fmt.setHeight(size.height());cur.insertImage(fmt);cover_count+=1
    for index,o in enumerate(docs):
        if index or cover_count:
            cur.insertBlock();bf=QTextBlockFormat()
            if o.get('kind','chapter')!='scene' or not index:bf.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore)
            cur.setBlockFormat(bf)
        if titles:
            title=QTextCharFormat();title.setFontFamilies(['Georgia']);title.setFontPointSize(28 if o.get('kind')=='part' else 16 if o.get('kind')=='scene' else 22);title.setFontWeight(QFont.Bold);cur.insertText(o['name'],title);cur.insertBlock(QTextBlockFormat(),QTextCharFormat())
        cur.insertHtml(render(project,o['html']))
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
    frame=doc.rootFrame();fmt=frame.frameFormat();fmt.setBackground(QColor('white'));frame.setFrameFormat(fmt)
    block=doc.begin()
    while block.isValid():
        cursor=QTextCursor(block);fmt=block.blockFormat();fmt.clearBackground();cursor.setBlockFormat(fmt);block=block.next()
    return doc

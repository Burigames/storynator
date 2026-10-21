"""Portable project print settings with local defaults."""
import json
from PySide6.QtCore import QMarginsF,QSizeF
from PySide6.QtGui import QPageLayout,QPageSize
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

def persist(project,settings,printer,titles=True,chapters=None):
    data=capture(printer,titles,chapters);changed=project.get('print_settings')!=data;project['print_settings']=data;settings.setValue('printing/defaults',json.dumps({k:v for k,v in data.items() if k!='chapters'}));settings.setValue('printing/printer',printer.printerName());settings.sync();return changed

import os, base64, json, pytest
os.environ['QT_QPA_PLATFORM']='offscreen'
from app import *
from PySide6.QtGui import QPixmap, QPen, QBrush
from pypdf import PdfReader

@pytest.fixture(scope='session')
def qt():return QApplication.instance() or QApplication([])

def sample():
    p=new_project('Die Welt von Aster');c=dict(id=uid(),name='Charaktere',fields=[dict(id=uid(),name=n,type=t,**settings) for n,t,settings in [('Beruf','Text',{}),('Porträt','Bild',{}),('Rolle','Dropdown',{'options':['Held','Gegner']}),('Mut','Slider',{'min':0,'max':10,'step':0.5})]])
    land=dict(id=uid(),name='Länder',fields=[]);p['categories']=[c,land];e=dict(id=uid(),name='Mira',category=c['id'],values={},links=[],html='<p>Eine Reisende.</p>');country=dict(id=uid(),name='Aster',category=land['id'],values={},links=[e['id']],html='');e['links']=[country['id']];p['entries']=[e,country]
    image=QImage(30,40,QImage.Format_RGB32);image.fill(QColor('red'));from PySide6.QtCore import QBuffer,QByteArray,QIODevice
    ba=QByteArray();buf=QBuffer(ba);buf.open(QIODevice.WriteOnly);image.save(buf,'PNG');key=uid()+'.png';p['assets'][key]=base64.b64encode(bytes(ba)).decode()
    for f,value in zip(c['fields'],['Reisende',[key],'Held',7.5]):e['values'][f['id']]=value
    p['documents'][0]['html']='<p><b>Prolog</b> <a href="story:'+e['id']+'" style="color:#7461bb">Mira</a> betritt <i>Aster</i>.</p><p><img src="asset:'+key+'" /></p>'
    p['calendar'].update(name='Mondzeit',months=[{'name':'Asche','days':20},{'name':'Blüte','days':24}],leaps=[{'every':4,'month':2,'days':1}])
    for name,start,end,kind in [('Magie','-2/1/1','10/2/24','Zeitalter'),('Königreich','1/1/1','5/2/24','Zeitalter'),('Ankunft','2/1/5','','Ereignis'),('Sturm','2/1/5','','Ereignis')]:p['events'].append(dict(id=uid(),name=name,start=start,end=end,kind=kind,html='',links=[],era=None))
    return p

def test_roundtrip_link_rename_image_pdf(qt,tmp_path):
    p=sample();file=tmp_path/'world.storynator';save_project(p,file);q=load_project(file);assert q==p
    w=Main();w.error=lambda e:(_ for _ in ()).throw(AssertionError(str(e)));w.p=q;w.refresh();w.tabs.clear()
    for o in objects(q):w.open_object(o['id'])
    w.show_timeline(); assert w.tabs.count()==len(objects(q))+1
    entry=q['entries'][0];entry['name']='Mira Sonnenfels';htmltext=render(q,q['documents'][0]['html']);assert 'Mira Sonnenfels' in htmltext;assert references(q,entry['id'])
    doc=w.export_document(q['documents']);assert 'Mira Sonnenfels' in doc.toPlainText();assert not doc.resource(QTextDocument.ImageResource,QUrl('asset:'+next(iter(q['assets'])))).isNull()
    block=doc.begin();bold=False
    while block.isValid():
        it=block.begin()
        while not it.atEnd():
            fragment=it.fragment()
            if fragment.isValid():
                assert not fragment.charFormat().isAnchor()
                if 'Prolog' in fragment.text():bold=fragment.charFormat().fontWeight()>=QFont.Bold
                if 'Mira Sonnenfels' in fragment.text():assert fragment.charFormat().foreground().color()==QColor('black')
            it+=1
        block=block.next()
    assert bold
    printer=QPrinter();printer.setOutputFormat(QPrinter.PdfFormat);out=tmp_path/'story.pdf';printer.setOutputFileName(str(out));doc.print_(printer);assert 'Mira Sonnenfels' in ' '.join(PdfReader(out).pages[0].extract_text().split())
    save_project(q,file);assert load_project(file)['entries'][0]['name']=='Mira Sonnenfels'
    w.dirty=False

def test_calendar():
    c=new_project()['calendar'];c['months']=[dict(name='Mond',days=10)];cal=Calendar(c)
    assert cal.ordinal('1/1/1')-cal.ordinal('-1/1/10')==1
    with pytest.raises(ValueError):cal.ordinal('0/1/1')
    with pytest.raises(ValueError):cal.span('2/1/1','1/1/1')
    c['leaps']=[dict(every=4,month=1,days=1)]
    assert cal.ordinal('5/1/1')-cal.ordinal('4/1/1')==11
    assert cal.ordinal('-3/1/1')-cal.ordinal('-4/1/1')==11
    c['year_zero']=True;c['epoch']=0
    assert cal.ordinal('1/1/1')-cal.ordinal('0/1/1')==11
    c['months']=[];c['leaps']=[];assert Calendar(c).ordinal('-10')==-10

def test_atomic_failure_preserves_previous(tmp_path,monkeypatch):
    p=new_project();path=tmp_path/'p.storynator';save_project(p,path);before=path.read_bytes();p['name']='Changed'
    import core
    def fail(a,b):raise OSError('Simulierter Abbruch')
    monkeypatch.setattr(core.os,'replace',fail)
    with pytest.raises(OSError):save_project(p,path)
    assert path.read_bytes()==before;assert len(list(tmp_path.iterdir()))==1

def test_editor_mention_and_actual_rename(qt,monkeypatch,tmp_path):
    import app as module
    from PySide6.QtTest import QTest
    w=Main();w.p=sample();w.tabs.clear();w.refresh();doc=w.p['documents'][0];doc['html']='';target=w.p['entries'][0]
    w.open_object(doc['id']);editor=w.editor()
    def choose():
        dialog=qt.activeModalWidget();assert isinstance(dialog,Picker);dialog.search.setText('Mira');dialog.list.setCurrentRow(0);QTest.mouseDClick(dialog.list.viewport(),Qt.LeftButton,pos=dialog.list.visualItemRect(dialog.list.item(0)).center())
        if dialog.isVisible():dialog.id=target['id'];dialog.accept()
    QTimer.singleShot(0,choose);QTest.keyClicks(editor,'@');assert 'Mira' in editor.toPlainText();assert 'story:'+target['id'] in doc['html']
    for i in w.nav.findItems('Mira',Qt.MatchRecursive):w.nav.setCurrentItem(i)
    monkeypatch.setattr(module,'ask',lambda *args:'Mira Neu');w.rename();assert 'Mira Neu' in editor.toPlainText();assert target['id'] in doc['html']
    w.recovery=tmp_path/'recovery.storynator';w.autosave();assert load_project(w.recovery)['entries'][0]['name']=='Mira Neu'
    path=tmp_path/'story.storynator';w.path=str(path);assert w.save();w.tabs.clear();w.open_file(str(path));assert w.p['entries'][0]['name']=='Mira Neu';assert 'Mira Neu' in w.editor().toPlainText();w.dirty=False

def test_multiple_chapters_and_pages(qt,tmp_path):
    w=Main();w.p=new_project();w.p['documents']=[dict(id=uid(),name='Eins',html='<p>Kapitel Eins</p>'),dict(id=uid(),name='Zwei',html='<p>Kapitel Zwei</p>')]
    doc=w.export_document(w.p['documents']);p=QPrinter();p.setOutputFormat(QPrinter.PdfFormat);path=tmp_path/'chapters.pdf';p.setOutputFileName(str(path));doc.print_(p);reader=PdfReader(path)
    assert len(reader.pages)==2;assert 'Zwei' in reader.pages[1].extract_text();w.dirty=False

def test_template_and_calendar_dialogs(qt,monkeypatch):
    import app as module
    w=Main();w.error=lambda e:(_ for _ in ()).throw(AssertionError(str(e)));monkeypatch.setattr(module,'ask',lambda *a:'Charaktere')
    def fill_template():
        d=qt.activeModalWidget();table=d.findChild(QTableWidget)
        for n,t in [('Beruf','Text'),('Porträt','Bild'),('Rolle','Dropdown'),('Mut','Slider')]:
            next(b for b in d.findChildren(QPushButton) if b.text()=='＋ Feld').click();r=table.rowCount()-1;table.item(r,0).setText(n);table.cellWidget(r,1).setCurrentText(t)
            if t=='Dropdown':table.item(r,2).setData(Qt.UserRole,{'options':['Held','Gegner']})
            if t=='Slider':table.item(r,2).setData(Qt.UserRole,{'min':0,'max':10,'step':0.5})
        next(b for b in d.findChildren(QPushButton) if b.text()=='Vorlage übernehmen').click()
    QTimer.singleShot(0,fill_template);w.add_category();assert len(w.p['categories'][0]['fields'])==4
    def fill_calendar():
        d=qt.activeModalWidget();d.findChildren(QLineEdit)[0].setText('Sonnenzeit');tables=d.findChildren(QTableWidget);tables[0].item(0,0).setText('Sonnenmond');tables[0].item(0,1).setText('40');next(b for b in d.findChildren(QPushButton) if b.text()=='Kalender prüfen und übernehmen').click()
    QTimer.singleShot(0,fill_calendar);w.calendar();assert w.p['calendar']['name']=='Sonnenzeit';assert w.p['calendar']['months'][0]['days']==40;w.dirty=False

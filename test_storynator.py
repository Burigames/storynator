import os, sys, base64, json, pytest
os.environ.setdefault('QT_QPA_PLATFORM','windows' if sys.platform=='win32' else 'offscreen')
from app import *
from PySide6.QtGui import QPixmap, QPen, QBrush
from PySide6.QtCore import QPoint
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

def test_studio_navigation_focus_and_packaged_example(qt):
    from design import apply_theme
    apply_theme(qt);w=Main(recover=False);w.tabs.clear();w.p=sample();w.refresh();w.show();qt.processEvents()
    before=w.p['documents'][0]['html'];w.dirty=False;w.navigate('editor');assert not w.dirty;assert w.p['documents'][0]['html']==before;editor=w.editor();assert editor is not None;assert editor.objectName()=='manuscript';assert w.nav_buttons['editor'].isChecked()
    cursor=editor.textCursor();cursor.setPosition(3);editor.setTextCursor(cursor)
    w.toggle_focus();assert not w.centralWidget().widget(0).isVisible();assert not w.tabs.currentWidget().findChild(QFrame,'context').isVisible()
    w.toggle_focus();assert w.centralWidget().widget(0).isVisible();assert editor.textCursor().position()==3
    w.navigate('world');assert w.nav_buttons['world'].isChecked();assert w.tabs.currentWidget().world_page
    w.open_object(w.p['entries'][0]['id']);assert w.section=='world';assert w.editor() is not None
    w.navigate('timeline');assert w.tabs.currentWidget().timeline_page;assert w.nav_buttons['timeline'].isChecked()
    w.navigate('editor');assert w.editor() is editor;assert editor.textCursor().position()==3
    w.dirty=False;w.hide();w.deleteLater();qt.processEvents()

@pytest.fixture(autouse=True)
def isolated_preferences(qt,tmp_path):
    from i18n import set_language
    from design import apply_theme
    QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(tmp_path/'settings'));set_language('de');apply_theme(qt,'light','forest')
    yield
    set_language('de');QSettings.setDefaultFormat(QSettings.NativeFormat)

def test_font_toolbar_and_link_inherit_roundtrip(qt,tmp_path):
    from PySide6.QtTest import QTest
    w=Main(recover=False);w.tabs.clear();w.open_object(w.p['documents'][0]['id']);e=w.editor()
    assert e.font().pointSize()==14;assert e.currentFont().pointSize()==w.size_control.value();assert e.font().family()==e.document().defaultFont().family()
    w.fmt('setFontFamilies',['Georgia']);w.fmt('setFontPointSize',19);w.fmt('setFontWeight',QFont.Bold);w.fmt('setFontItalic',True);w.fmt('setFontUnderline',True);w.fmt('setForeground',QColor('#ab3456'));e.insertPlainText('Before ')
    entry=dict(id=uid(),name='Linked character',category='unused',values={},html='<p>Preview text</p>',links=[]);w.p['entries'].append(entry)
    def choose():
        d=qt.activeModalWidget();d.id=entry['id'];d.accept()
    QTimer.singleShot(0,choose);e.link();e.insertPlainText('After');assert w.size_control.value()==19
    def check(editor):
        cur=editor.document().find('Linked character');fmt=cur.charFormat();assert fmt.isAnchor();assert fmt.fontPointSize()==19;assert fmt.fontWeight()==QFont.Bold;assert fmt.fontItalic();assert fmt.fontUnderline();assert fmt.foreground().color()==QColor('#ab3456')
        cur=editor.document().find('After');fmt=cur.charFormat();assert not fmt.isAnchor();assert fmt.fontPointSize()==19;assert fmt.fontItalic();assert fmt.foreground().color()==QColor('#ab3456')
    check(e);path=tmp_path/'format.storynator';save_project(w.p,path);w.p=load_project(path);w.tabs.clear();w.open_object(w.p['documents'][0]['id']);check(w.editor())
    cur=w.editor().document().find('After');w.editor().setTextCursor(cur);qt.processEvents();assert w.size_control.value()==19;w.dirty=False

def test_lists_and_tables_show_four_rows(qt):
    from ui import RoomyList,RoomyTable
    for widget in [RoomyList(),RoomyTable(6,2)]:
        if isinstance(widget,RoomyList):widget.addItems(['One','Two','Three','Four','Five','Six'])
        else:
            for row in range(6):widget.setItem(row,0,QTableWidgetItem(str(row)));widget.setRowHeight(row,43)
        widget.resize(450,1);widget.show();qt.processEvents()
        rect=widget.visualItemRect(widget.item(3)) if isinstance(widget,RoomyList) else widget.visualItemRect(widget.item(3,0))
        assert rect.bottom()<widget.viewport().height();widget.hide();widget.deleteLater()
    w=Main(recover=False);w.tabs.clear();w.p=sample();w.open_object(w.p['entries'][0]['id']);w.show();qt.processEvents();ls=w.tabs.currentWidget().findChild(QListWidget);assert ls.minimumHeight()>=160;assert ls.maximumHeight()>ls.minimumHeight();w.dirty=False;w.hide()

def test_print_preferences_titles_and_exported_format(qt,tmp_path):
    import printing
    from PySide6.QtGui import QPageLayout
    w=Main(recover=False);w.p=sample();pr=printing.make_printer(w.p,w.settings);pr.setPageSize(QPageSize(QPageSize.Letter));pr.setPageOrientation(QPageLayout.Landscape);pr.setPageMargins(QMarginsF(12,13,14,15));ids=[w.p['documents'][0]['id']];assert printing.persist(w.p,w.settings,pr,True,ids)
    path=tmp_path/'print.storynator';save_project(w.p,path);w.p=load_project(path);reloaded=printing.make_printer(w.p,w.settings);layout=reloaded.pageLayout();assert layout.pageSize().id()==QPageSize.Letter;assert layout.orientation()==QPageLayout.Landscape;assert layout.margins(QPageLayout.Millimeter).left()==pytest.approx(12,abs=.1);assert w.p['print_settings']['chapters']==ids
    doc=w.export_document(w.p['documents']);assert doc.toPlainText().startswith(w.p['documents'][0]['name']);pdf=tmp_path/'titles.pdf';reloaded.setOutputFormat(QPrinter.PdfFormat);reloaded.setOutputFileName(str(pdf));doc.print_(reloaded);text=' '.join(PdfReader(pdf).pages[0].extract_text().split());assert w.p['documents'][0]['name'] in text
    assert not w.export_document(w.p['documents'],False).toPlainText().startswith(w.p['documents'][0]['name']);w.dirty=False

def test_theme_language_preferences_and_user_content(qt):
    from design import apply_theme,CURRENT
    from i18n import set_language
    from PySide6.QtGui import QPalette
    w=Main(recover=False)
    def configure():
        d=qt.activeModalWidget();d.findChild(QComboBox,'themeMode').setCurrentIndex(1);accent=d.findChild(QComboBox,'accentChoice');accent.setCurrentIndex(accent.findData('ocean'));language=d.findChild(QComboBox,'languageChoice');language.setCurrentIndex(language.findData('en'));next(b for b in d.findChildren(QPushButton) if b.text()=='Übernehmen').click()
    QTimer.singleShot(0,configure);w.preferences();assert CURRENT['mode']=='dark';assert CURRENT['accent']=='ocean';assert w.settings.value('language')=='en';assert qt.palette().color(QPalette.Base).lightness()<80
    set_language(w.settings.value('language'));en=Main(recover=False);en.p['name']='Welt';en.refresh();assert en.nav_buttons['world'].text().strip()=='World';assert en.project_label.text()=='Welt';assert en.save_button.text()=='Save';assert en.p['documents'][0]['name']=='Chapter 1'
    en.tabs.clear();en.open_object(en.p['documents'][0]['id']);e=en.editor();before=e.toHtml();apply_theme(qt,'light','rose');e.update_marks();assert before==e.toHtml();w.dirty=False;en.dirty=False

def test_preview_and_whole_navigation_click(qt):
    from PySide6.QtTest import QTest
    w=Main(recover=False);w.p=sample();w.tabs.clear();w.refresh();w.show();qt.processEvents();root=w.nav.topLevelItem(0);item=root.child(0);rect=w.nav.visualItemRect(item);QTest.mouseClick(w.nav.viewport(),Qt.LeftButton,pos=rect.topLeft()+QPoint(rect.width()-12,rect.height()//2));assert w.current()['id']==item.data(0,Qt.UserRole)
    entry=w.p['entries'][0];preview=w.preview_html(entry['id']);assert entry['name'] in preview;assert 'Eine Reisende' in preview;assert entry['id'] not in preview;assert 'Mira' in w.nav.topLevelItem(1).child(0).child(0).toolTip(0);w.dirty=False;w.hide()

def test_visible_arrows_and_live_hover(qt):
    from PySide6.QtTest import QTest
    from PySide6.QtGui import QHelpEvent
    w=Main(recover=False);w.p=sample();w.tabs.clear();w.refresh();w.open_object(w.p['documents'][0]['id']);w.show();qt.processEvents();e=w.editor();w.fmt('setFontPointSize',17.5);assert w.size_control.value()==17.5
    spin=w.size_control;opt=QStyleOptionSpinBox();spin.initStyleOption(opt);rect=spin.style().subControlRect(QStyle.CC_SpinBox,opt,QStyle.SC_SpinBoxUp,spin);QTest.mouseClick(spin,Qt.LeftButton,pos=rect.center());assert spin.value()==18.5;assert e.currentFont().pointSizeF()==18.5
    QTest.mouseClick(w.font_control,Qt.LeftButton,pos=QPoint(w.font_control.width()-14,w.font_control.height()//2));assert w.font_control.view().isVisible();w.font_control.hidePopup()
    button=next(b for b in w.findChildren(QPushButton) if b.property('entryId')==w.p['entries'][0]['id']);w.p['entries'][0]['html']='<p>Updated hover preview</p>';event=QHelpEvent(QEvent.ToolTip,button.rect().center(),button.mapToGlobal(button.rect().center()));QApplication.sendEvent(button,event);assert 'Updated hover preview' in QToolTip.text();QToolTip.hideText();w.dirty=False;w.hide()

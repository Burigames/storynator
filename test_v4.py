import copy,json
import pytest
from test_storynator import qt,sample
from core import Calendar,new_project,uid,save_project,load_project
from app import Main,Rich
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox
import addons
from timeline import TimelinePanel,cluster_points,era_lanes

@pytest.mark.parametrize('zero',[True,False])
@pytest.mark.parametrize('epoch',[-5,1,20])
def test_inverse_calendar(zero,epoch):
    c=new_project()['calendar'];c.update(year_zero=zero,epoch=epoch,months=[dict(name='A',days=17),dict(name='B',days=31)],leaps=[dict(every=4,month=2,days=2,offset=1)])
    cal=Calendar(c)
    for day in range(-6000,6000,13):assert cal.ordinal(cal.date_from_ordinal(day))==day
    c['months']=[];c['leaps']=[]
    for day in range(-100,100):assert cal.ordinal(cal.date_from_ordinal(day))==day

def test_presets_are_templates_and_preserve_data(qt,tmp_path):
    p=new_project();settings=QSettings(str(tmp_path/'prefs.ini'),QSettings.IniFormat)
    assert not p.get('addons');assert addons.library(settings)[0]['id']==addons.BUILTIN['id']
    state=addons.enable(p,addons.BUILTIN);assert not p['entries'];assert len(p['categories'])==14
    ids=[c['id'] for c in p['categories']];character=p['categories'][0];race=next(c for c in p['categories'] if c['name']=='Rassen');f=next(f for f in character['fields'] if f['name']=='Rasse');assert f['source_category']==race['id']
    p['entries']=[dict(id=uid(),name='Private secret',category=character['id'],values={f['id']:'secret'},links=[],html='secret prose')]
    spec=addons.export(p,[character['id']],'Export');assert 'Private secret' not in json.dumps(spec);assert 'secret prose' not in json.dumps(spec)
    q=new_project();addons.enable(q,spec);assert not q['entries'];assert q['categories'][0]['id']!=character['id']
    addons.disable(p,state['id']);assert character in addons.visible_categories(p);addons.enable(p,addons.BUILTIN);assert ids==[c['id'] for c in p['categories']]
    path=tmp_path/'test.storynator';save_project(p,path);p=load_project(path);assert p['addons'][0]['enabled']
    addons.remove(p,settings,state['id']);assert p['entries'][0]['name']=='Private secret';assert any(c['id']==character['id'] for c in p['categories']);assert any(c['id']==race['id'] for c in p['categories'])
    bad=copy.deepcopy(addons.BUILTIN);bad['categories'][2]['fields'][-1]['max']=float('inf')
    with pytest.raises(ValueError):addons.validate(bad)
    for placement in ['root','category','field']:
        bad=copy.deepcopy(addons.BUILTIN)
        target=bad if placement=='root' else bad['categories'][0] if placement=='category' else bad['categories'][0]['fields'][0]
        target['entries']=[{'name':'forbidden'}]
        with pytest.raises(ValueError):addons.validate(bad)

def test_timeline_range_clusters_and_ticks(qt):
    w=Main(recover=False);w.p=new_project();w.p['calendar'].update(months=[],leaps=[],year_zero=False)
    def event(name,start,end='',kind='Ereignis'):return dict(id=uid(),name=name,start=str(start),end=str(end),kind=kind,links=[],html='',era='')
    w.p['events']=[event('era',-100,100,'Zeitalter'),event('other',-20,150,'Zeitalter')]+[event(str(i),i) for i in range(1,11)]+[event('same',2)]
    panel=TimelinePanel(w);panel.resize(1100,550);panel.show();qt.processEvents();c=panel.canvas
    assert c.total_lanes==2;assert sum(len(g) for g in c.clusters())==11;assert any(len(g)>1 for g in c.clusters())
    span=c.end-c.begin;c.zoom(4);assert c.end-c.begin==pytest.approx(span/4);before=c.begin;panel.scroll.setValue(0);assert c.begin<before;panel.scroll.setValue(100000);assert c.end==pytest.approx(c.maximum)
    c.fit()
    for value,label in c.ticks():assert c.cal.ordinal(label)==value;assert label!='0'
    panel.close();w.dirty=False;w.close()

def test_world_read_edit_and_related_selection(qt):
    w=Main(recover=False);w.tabs.clear();w.p=sample();character=w.p['entries'][0];country=w.p['entries'][1];f=dict(id=uid(),name='Herkunft',type='Dropdown',source_category=country['category']);w.p['categories'][0]['fields'].append(f);character['values'][f['id']]=country['id'];w.refresh();w.show();w.open_object(character['id']);qt.processEvents();page=w.tabs.currentWidget();assert not page.world_edit;assert page.findChild(Rich) is None
    w.render_world_page(page,True);qt.processEvents();boxes=page.findChildren(QComboBox);box=next(b for b in boxes if b.findData(country['id'])>=0);assert box.currentData()==country['id'];country['name']='Neues Land';w.render_world_page(page,False);qt.processEvents();assert not page.world_edit
    w.dirty=False;w.close()

def test_print_background_white_even_dark(qt):
    from design import apply_theme
    w=Main(recover=False);w.p=new_project();w.p['documents'][0]['html']='<html><body bgcolor="#cceeff"><p style="background-color:#cceeff">Text</p></body></html>';apply_theme(qt,'dark','lavender');doc=w.export_document(w.p['documents']);assert doc.rootFrame().frameFormat().background().color()==QColor('white');assert doc.begin().blockFormat().background().style().value==0
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtPdf import QPdfDocument
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        path=folder+'/white.pdf';printer=QPrinter();printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(path);doc.print_(printer);del printer
        from PySide6.QtCore import QBuffer,QByteArray,QIODevice
        data=QByteArray(__import__('pathlib').Path(path).read_bytes());buffer=QBuffer(data);buffer.open(QIODevice.ReadOnly);pdf=QPdfDocument();pdf.load(buffer);image=pdf.render(0,__import__('PySide6.QtCore',fromlist=['QSize']).QSize(600,800));assert not image.isNull();assert image.pixelColor(300,400)==QColor('white');pdf.close();del pdf;buffer.close()
    from worldview import RichDisplay
    view=RichDisplay(w,'<p><span style="color:#000000">Dark text</span></p>');assert view.extraSelections();assert view.document().begin().begin().fragment().charFormat().foreground().color()==QColor('black');apply_theme(qt,'light','ocean');assert not view.extraSelections();view.close()
    w.dirty=False;w.close();apply_theme(qt)

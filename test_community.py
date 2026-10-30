import base64,copy,json
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument
from core import new_project,uid
import community as c
import exchange_reading as r
@pytest.fixture(scope='module',autouse=True)
def qt():
    app=QApplication.instance() or QApplication([]);yield app
@pytest.fixture
def project():
    p=new_project('Test');p['categories']=[dict(id='cat',name='Charaktere',fields=[dict(id='portrait',name='Porträt',type='Bild'),dict(id='secret',name='Geheimnis',type='Text'),dict(id='race',name='Rasse',type='Dropdown',source_category='cat')])]
    p['entries']=[dict(id='a',name='Ada',category='cat',html='<p>Hallo <a href="story:b">Bert</a></p>',values={'portrait':'face.png','secret':'VERTRAULICH','race':'b'},links=['b']),dict(id='b',name='Bert',category='cat',html='',values={},links=['a'])]
    p['assets']['face.png']=base64.b64encode(b'testimage').decode();p['documents'][0]['html']='<p><b>Hallo</b> <a href="story:a">Ada</a></p>';return p
def test_private_world_dependency_and_roundtrip(project,tmp_path):
    s=c.create(project,'world',c.metadata('Welt'),['a'],['secret'],True);p=s['payload']['project']
    assert len(p['entries'])==2 and 'VERTRAULICH' not in json.dumps(s) and len(p['assets'])==1
    c.save(s,tmp_path/'pack');assert c.load(tmp_path/'pack')==s
    target=new_project();q,_=c.plan_import(target,s)
    assert target['entries']==[] and len(q['entries'])==2
    a,b=q['entries'];assert a['id']!='a' and a['links']==[b['id']] and a['values'][q['categories'][0]['fields'][1]['id']]==b['id']
    assert 'asset:face.png' not in a.get('html','') and a['values'][q['categories'][0]['fields'][0]['id']] in q['assets']
def test_explicit_omission_redacts_targets(project):
    s=c.create(project,'world',c.metadata('One'),['a'],['secret']);text=json.dumps(s)
    assert 'Bert' not in text and 'VERTRAULICH' not in text
    assert s['payload']['project']['entries'][0]['links']==[]
def test_no_history_notes_or_unknown_payload(project):
    project['entries'][0]['field_archive']=[{'secret':'HISTORY'}]
    project['documents'][0]['annotations']=[{'private':'NOTE'}]
    s=c.create(project,'reading',c.metadata('Leseprobe'),[project['documents'][0]['id']]);assert 'NOTE' not in json.dumps(s) and 'HISTORY' not in json.dumps(s)
    bad=copy.deepcopy(s);bad['payload']['project']['code']='bad'
    with pytest.raises(ValueError):c.validate(bad)
def test_starter_no_content_and_hierarchy(project):
    project['documents'].append(dict(id='scene',parent=project['documents'][0]['id'],kind='scene',name='Szene',html='private'))
    s=c.create(project,'starter',c.metadata('Start'));p=s['payload']['project'];assert not p['entries'];assert not any(d['html'] for d in p['documents']);assert p['documents'][1]['parent']==p['documents'][0]['id']
def test_calendar_refuses_reinterpretation(project):
    s=c.create(project,'calendar',c.metadata('Zeit'));project['events']=[dict(id='event',name='Event',start='1/1/1',end='',kind='event',links=[])]
    with pytest.raises(ValueError):c.plan_import(project,s)
def test_category_stays_data_only(project):
    s=c.create(project,'categories',c.metadata('Vorlage'),['cat']);assert 'entries' not in s['payload']['preset']
    q,_=c.plan_import(new_project(),s);assert not q['entries'] and q['categories']
def test_feedback_exact_changed_duplicate_foreign(project):
    d=project['documents'][0];s=c.create(project,'reading',c.metadata('Lesen'),[d['id']]);f=r.feedback(s,[dict(document=d['id'],text='Gut',start=0,end=5)],'Leser')
    q,n,uncertain=r.import_feedback(project,f);assert n==1 and uncertain==0 and q['documents'][0]['annotations'][0]['quote']=='Hallo'
    q,n,_=r.import_feedback(q,f);assert n==0
    project['documents'][0]['html']='<p>Geändert</p>';q,n,u=r.import_feedback(project,f);assert u==1 and q['documents'][0]['annotations'][0]['detached']
    with pytest.raises(ValueError):r.import_feedback(new_project(),f)
def test_html_no_active_content(project,tmp_path):
    s=c.create(project,'reading',c.metadata('<Titel>'),[project['documents'][0]['id']]);path=tmp_path/'index.html';r.website(s,path);text=path.read_text();assert '&lt;Titel&gt;' in text and 'VERTRAULICH' not in text and 'search' in text
    assert '<script>' not in r.safe_html('<script>alert(1)</script><p onclick="x">Okay</p><img src="file:///etc/passwd">',{})
    s['payload']['project']['documents'][0]['html']='<img src="file:///etc/passwd">'
    with pytest.raises(ValueError):c.validate(s)
def test_library_versions_non_destructive(project,tmp_path):
    lib=c.Library(tmp_path);s=c.create(project,'calendar',c.metadata('Zeit'));a=lib.install(s);s['metadata']['release']='2.0';b=lib.install(s);assert a!=b and len(lib.items())==2
    with pytest.raises(ValueError):lib.remove(tmp_path.parent/'other')
    lib.remove(a);assert len(lib.items())==1
def test_names_collide_without_overwriting(project):
    s=c.create(project,'world',c.metadata('Welt'),['a'],include_dependencies=True);q,w=c.plan_import(project,s);assert w and q['entries'][0]==project['entries'][0] and q['entries'][2]['name']=='Ada (Import)'
def test_ui_opens(project,tmp_path):
    from PySide6.QtWidgets import QWidget,QTabWidget
    from community_ui import CommunityDialog,ExportDialog,ReaderDialog
    class Host(QWidget):
        def __init__(self):super().__init__();self.p=project;self.data_root=tmp_path
    h=Host();library=CommunityDialog(h);assert library.list.count()==2;ex=ExportDialog(h);ex.kind.setCurrentIndex(3);assert ex.items.count()==2
    s=c.create(project,'reading',c.metadata('Lesen'),[project['documents'][0]['id']]);reader=ReaderDialog(h,s);assert 'Ada' in reader.view.toPlainText();reader.close();ex.close();library.close();h.close()

def test_catalog_sources_and_checksums():
    import community_catalog as cat
    from pathlib import Path
    import hashlib
    raw=Path('community/catalog.json').read_bytes();items=cat.catalog(raw)
    assert len(items)==4
    for item in items:
        path=Path('community')/item['url'].split('/')[-1];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'];c.load(path)
    bad=json.loads(raw);bad['packages'][0]['url']='https://example.com/evil'
    with pytest.raises(ValueError):cat.catalog(json.dumps(bad))
def test_selective_import(project):
    s=c.create(project,'world',c.metadata('Welt'),['a'],include_dependencies=True);filtered=c.select_import(s,['a']);assert len(filtered['payload']['project']['entries'])==1
    q,_=c.plan_import(new_project(),filtered);assert len(q['entries'])==1 and not q['entries'][0]['links']
def test_link_formatting_and_real_pdf(project,tmp_path):
    from PySide6.QtGui import QTextCursor,QColor
    from PySide6.QtCore import QSettings
    from printing import manuscript_document,make_printer,write_pdf
    from pypdf import PdfReader
    d=project['documents'][0];d['html']='<p><span style="font-family:Arial;font-size:18pt;font-weight:700">Hallo </span><a href="story:a"><span style="color:#7461bb;text-decoration:underline;font-family:Arial;font-size:18pt">Ada</span></a></p>'
    s=c.create(project,'reading',c.metadata('Lesen'),[d['id']]);p=s['payload']['project'];doc=QTextDocument();doc.setHtml(p['documents'][0]['html']);cur=QTextCursor(doc);cur.setPosition(7);assert not cur.charFormat().isAnchor() and cur.charFormat().fontPointSize()==18 and cur.charFormat().foreground().color()!=QColor('#7461bb')
    settings=QSettings(str(tmp_path/'settings.ini'),QSettings.IniFormat);printer=make_printer(p,settings);pdf=manuscript_document(p,p['documents'],pdf=True,printer=printer,settings=settings);path=tmp_path/'out.pdf';write_pdf(pdf,path,printer);assert 'Ada' in PdfReader(path).pages[0].extract_text();assert 'font-size:18pt' in r.safe_html(p['documents'][0]['html'],{})
def test_external_and_active_inputs_rejected(project):
    s=c.create(project,'world',c.metadata('Welt'),['a'])
    for text in ['<script>x</script>','<p onclick="x">X</p>','<p style="background:url(file:///secret)">x</p>']:
        bad=copy.deepcopy(s);bad['payload']['project']['entries'][0]['html']=text
        with pytest.raises(ValueError):c.validate(bad)
def test_apply_real_project_keeps_unsaved_and_backup(tmp_path):
    from app import Main
    from community_ui import apply
    from PySide6.QtCore import QSettings
    w=Main();w.autosave_timer.stop() if hasattr(w,'autosave_timer') else None
    old=copy.deepcopy(w.p);s=c.create(old,'calendar',c.metadata('Zeit'));q,_=c.plan_import(old,s)
    try:
        apply(w,q,'Test Import');assert w.dirty and w.p['community_imports'] and w.backups.list(old['project_id'])
        w.dirty=False
    finally:w.dirty=False;w.close();QApplication.processEvents()

def test_three_way_updates_and_conflict_resolution(project):
    s=c.create(project,'world',c.metadata('Welt'),['a'],include_dependencies=True);q,_=c.plan_import(new_project(),s);aid=q['entries'][0]['id'];bid=q['entries'][1]['id'];q['entries'][0]['name']='Meine Ada'
    newer=copy.deepcopy(s);newer['metadata']['release']='2';newer['payload']['project']['entries'][0]['name']='Neue Ada';newer['payload']['project']['entries'][1]['name']='Neuer Bert'
    updated,conflicts=c.plan_update(q,newer);assert len(conflicts)==1 and updated['entries'][0]['name']=='Meine Ada' and updated['entries'][1]['name']=='Neuer Bert'
    updated,_=c.plan_update(q,newer,{aid:'package'});assert updated['entries'][0]['name']=='Neue Ada' and updated['entries'][0]['id']==aid and updated['entries'][0]['links']==[bid]
    assert q['entries'][0]['name']=='Meine Ada'

def test_layout_hit_targets_and_english(project,tmp_path):
    from PySide6.QtWidgets import QWidget
    from community_ui import CommunityDialog,ExportDialog
    from i18n import set_language
    from design import apply_theme
    class Host(QWidget):
        def __init__(self):super().__init__();self.p=project;self.data_root=tmp_path
    h=Host();set_language('en');apply_theme(QApplication.instance())
    try:
        d=CommunityDialog(h);d.resize(1000,700);d.show();QApplication.processEvents();assert 'Library' in d.windowTitle() and d.list.width()>300 and d.list.height()>150 and d.list.parent() is not d
        e=ExportDialog(h);e.show();QApplication.processEvents();assert e.items.width()>250;e.reject();d.reject()
    finally:set_language('de');h.close()

def test_feedback_repeated_exports_have_stable_identity(project):
    d=project['documents'][0];s=c.create(project,'reading',c.metadata('Lesen'),[d['id']]);notes=[dict(document=d['id'],start=0,end=5,text='Gut')]
    first=r.feedback(s,notes,'Leser');second=r.feedback(s,notes,'Leser');assert first==second
    q,_,_=r.import_feedback(project,first);_,n,_=r.import_feedback(q,second);assert n==0

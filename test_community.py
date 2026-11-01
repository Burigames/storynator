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

def test_package_cannot_bind_to_unrelated_project_targets(project):
    s=c.create(project,'world',c.metadata('Welt'),['a'],include_dependencies=True)
    for mutate in [lambda p:p['entries'][0]['links'].append('outside'),lambda p:p['entries'][0]['values'].update(portrait='outside.png'),lambda p:p['entries'][0].update(html='<a href="story:outside">Other</a>')]:
        bad=copy.deepcopy(s);mutate(bad['payload']['project'])
        with pytest.raises(ValueError):c.validate(bad)

def test_export_identity_and_selection_can_be_resumed(project,tmp_path):
    from PySide6.QtWidgets import QWidget
    from community_ui import ExportDialog
    meta=c.metadata('Mein Paket');meta['release']='1.2';project['community_exports']=[dict(metadata=meta,kind='world',ids=['a'],excluded=['secret'],dependencies=True,cover=False)]
    class Host(QWidget):
        def __init__(self):super().__init__();self.p=project
    h=Host();d=ExportDialog(h);d.previous.setCurrentIndex(1);assert d.export_meta['id']==meta['id'] and d.release.text()=='1.2' and d.deps.isChecked()
    from community_ui import selected
    assert selected(d.items)==['a'] and selected(d.fields)==['secret'];d.reject();h.close()

def test_template_update_rename_reorder_and_archive_values(project):
    s=c.create(project,'categories',c.metadata('Vorlagen'),['cat']);assert s['version']==2
    q,_=c.plan_import(new_project(),s);cat=q['categories'][0];fieldids={f['name']:f['id'] for f in cat['fields']};portrait=fieldids['Porträt'];secret=fieldids['Geheimnis']
    q['entries'].append(dict(id='mine',name='Meine Figur',category=cat['id'],values={portrait:'photo.png',secret:'Bleibt erhalten'},links=[],html=''))
    project['categories'][0]['name']='Figuren';project['categories'][0]['fields'][1]['name']='Biografie';project['categories'][0]['fields'].reverse()
    meta=copy.deepcopy(s['metadata']);meta['release']='2';s2=c.create(project,'categories',meta,['cat']);updated,conflicts=c.plan_update(q,s2);assert not conflicts
    assert updated['categories'][0]['name']=='Figuren' and next(f for f in updated['categories'][0]['fields'] if f['name']=='Biografie')['id']==secret
    project['categories'][0]['fields']=[f for f in project['categories'][0]['fields'] if f['id']!='portrait'];s3=c.create(project,'categories',meta,['cat']);final,conflicts=c.plan_update(updated,s3)
    assert not conflicts and portrait in {f['id'] for f in final['categories'][0]['archived']};assert final['entries'][0]['values'][portrait]=='photo.png'
def test_template_type_change_gets_new_identity_and_keeps_values(project):
    s=c.create(project,'categories',c.metadata('Vorlagen'),['cat']);q,_=c.plan_import(new_project(),s);cat=q['categories'][0];old=cat['fields'][1]['id'];q['entries'].append(dict(id='my',name='Ich',category=cat['id'],values={old:'42'},links=[],html=''))
    project['categories'][0]['fields'][1]['type']='Zahl';new=c.create(project,'categories',s['metadata'],['cat']);result,conflicts=c.plan_update(q,new);assert not conflicts
    assert result['categories'][0]['fields'][1]['id']!=old and result['categories'][0]['archived'][0]['id']==old and result['entries'][0]['values'][old]=='42'
def test_template_local_conflict_and_selective_identity(project):
    s=c.create(project,'categories',c.metadata('Vorlagen'),['cat']);selected=c.select_import(s,[s['payload']['preset']['categories'][0]['key']]);assert selected['payload']['identities']==s['payload']['identities']
    q,_=c.plan_import(new_project(),selected);q['categories'][0]['name']='Mein Name';project['categories'][0]['name']='Paketname';new=c.create(project,'categories',s['metadata'],['cat'])
    result,conflicts=c.plan_update(q,new);assert len(conflicts)==1 and result['categories'][0]['name']=='Mein Name'
    chosen,_=c.plan_update(q,new,{q['categories'][0]['id']:'package'});assert chosen['categories'][0]['name']=='Paketname'
def test_starter_reexports_keep_source_ids_and_dont_duplicate(project):
    s=c.create(project,'starter',c.metadata('Start'));s2=c.create(project,'starter',s['metadata']);assert s['payload']['project']['documents']==s2['payload']['project']['documents'];assert s['payload']['project']['categories']==s2['payload']['project']['categories']
    q,_=c.plan_import(new_project(),s);updated,conflicts=c.plan_update(q,s2);assert not conflicts and len(updated['documents'])==len(q['documents']) and len(updated['categories'])==len(q['categories'])
def test_template_v2_rejects_duplicate_ids_and_supports_legacy(project):
    s=c.create(project,'categories',c.metadata('Vorlagen'),['cat']);bad=copy.deepcopy(s);identity=next(iter(bad['payload']['identities'].values()));identity['fields'][0]=identity['id']
    with pytest.raises(ValueError):c.validate(bad)
    legacy=copy.deepcopy(s);legacy['version']=1;legacy['payload'].pop('identities');q,_=c.plan_import(new_project(),legacy);assert q['categories']
    with pytest.raises(ValueError,match='andere Feldkennungen'):c.plan_update(q,s)

def test_builtin_challenges_are_stable_across_refreshes():
    assert c.builtin_packages()==c.builtin_packages()
def test_world_update_archives_removed_fields_and_keeps_local_values(project):
    s=c.create(project,'world',c.metadata('Welt'),['a'],include_dependencies=True);q,_=c.plan_import(new_project(),s);cat=q['categories'][0];old=cat['fields'][1]['id'];project['categories'][0]['fields']=[f for f in project['categories'][0]['fields'] if f['id']!='secret'];project['entries'][0]['values'].pop('secret')
    new=c.create(project,'world',s['metadata'],['a'],include_dependencies=True);result,conflicts=c.plan_update(q,new);assert not conflicts and old in {f['id'] for f in result['categories'][0]['archived']} and result['entries'][0]['values'][old]=='VERTRAULICH'
def test_repeated_template_type_update_does_not_duplicate_archive(project):
    s=c.create(project,'categories',c.metadata('T'),['cat']);q,_=c.plan_import(new_project(),s);project['categories'][0]['fields'][1]['type']='Zahl';new=c.create(project,'categories',s['metadata'],['cat']);q,_=c.plan_update(q,new);again,conflicts=c.plan_update(q,new);assert not conflicts and q['categories']==again['categories']

def test_dependent_template_conflicts_cannot_apply_broken_filter(project):
    project['categories'].append(dict(id='other',name='Andere',fields=[dict(id='choice',name='Auswahl',type='Dropdown',source_category='cat',source_filter={'field':'secret','op':'eq','value':'yes'})]))
    s=c.create(project,'categories',c.metadata('Vorlagen'),['other']);q,_=c.plan_import(new_project(),s);cat=next(x for x in q['categories'] if x['name']=='Charaktere');cat['name']='Mein lokaler Name';project['categories'][0]['fields'][1]['type']='Zahl';new=c.create(project,'categories',s['metadata'],['other']);preview,conflicts=c.plan_update(q,new);assert conflicts
    with pytest.raises(ValueError,match='Auswahlfilter'):c.plan_update(q,new,{cat['id']:'local'})
    updated,_=c.plan_update(q,new,{cat['id']:'package'});assert next(x for x in updated['categories'] if x['id']==cat['id'])['name']=='Charaktere'
def test_starter_overwrite_keeps_snapshot_and_detaches_comments(project):
    s=c.create(project,'starter',c.metadata('Starter'));q,_=c.plan_import(new_project(),s);doc=q['documents'][-1];doc['html']='<p>Mein Text</p>';doc['annotations']=[dict(id='note',kind='comment',text='Notiz',start=0,end=4,quote='Mein')]
    new=c.create(project,'starter',s['metadata']);updated,conflicts=c.plan_update(q,new,{doc['id']:'package'});target=next(d for d in updated['documents'] if d['id']==doc['id']);assert target['html']=='' and target['annotations'][0]['detached'];assert target['history'][-1]['content']['html']=='<p>Mein Text</p>'
def test_template_archives_and_receipts_survive_save_reopen(project,tmp_path):
    from storage import save_project,load_project
    s=c.create(project,'categories',c.metadata('Vorlagen'),['cat']);q,_=c.plan_import(new_project(),s);project['categories'][0]['fields'].pop(1);new=c.create(project,'categories',s['metadata'],['cat']);updated,_=c.plan_update(q,new);path=tmp_path/'world.storynator';save_project(updated,path);reopened=load_project(path);assert reopened==updated;again,conflicts=c.plan_update(reopened,new);assert not conflicts and again['categories']==updated['categories']

def test_public_packages_do_not_disclose_archived_field_values(project):
    project['categories'][0]['archived']=[dict(id='old_private',name='Früheres Geheimnis',type='Text')];project['entries'][0]['values']['old_private']='ARCHIVGEHEIMNIS';project['entries'][0]['values']['unknown']='UNBEKANNTGEHEIM'
    s=c.create(project,'world',c.metadata('Welt'),['a'],include_dependencies=True);text=json.dumps(s);assert 'ARCHIVGEHEIMNIS' not in text and 'UNBEKANNTGEHEIM' not in text
    assert project['entries'][0]['values']['old_private']=='ARCHIVGEHEIMNIS'

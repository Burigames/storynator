"""M12/M13 regression, migration, persistence and real PDF output tests."""
import base64,copy,io,json,time,zipfile,hashlib
from pathlib import Path
import pytest
from test_storynator import qt,isolated_preferences,sample
from app import Main,Rich
from core import new_project,uid,save_project,load_project
from safety import BackupStore,migration_copy,project_report,used_assets,SearchIndex
from storage import CURRENT_VERSION
from media import store_image,import_image,image_from_asset
from PySide6.QtCore import Qt,QLockFile,QTimer,QSize
from PySide6.QtGui import QImage,QColor,QTextCursor
from PySide6.QtWidgets import QFileDialog,QMessageBox,QLabel,QPushButton
from pypdf import PdfReader
import printing

def studio(tmp_path):
    w=Main(recover=False);w.backups=BackupStore(tmp_path/'history',3);w.recovery=tmp_path/'session.storynator';w.tabs.clear();return w

def test_history_rotation_dedup_and_verified_restore(tmp_path):
    store=BackupStore(tmp_path/'history',3);p=sample()
    for i in range(6):p['name']='Stand '+str(i);store.create(p,'world.storynator','Manuell')
    items=store.list(p['project_id']);assert len(items)==3;assert items[0]['name']=='Stand 5';assert store.read(items[-1])['name']=='Stand 3';store.create(p);assert len(store.list())==3
    broken=Path(items[0]['path']);broken.write_bytes(broken.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='beschädigt'):store.read(items[0])
    (tmp_path/'history'/p['project_id']/'invalid.json').write_text('{}');assert len(store.list())==3

def test_version1_migration_is_lossless_and_backup_exact(tmp_path):
    p=sample();p['version']=1;p.pop('project_id');p.pop('covers');path=tmp_path/'legacy.storynator'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('project.json',json.dumps({**p,'assets':{}}))
        for key,value in p['assets'].items():z.writestr('assets/'+key,base64.b64decode(value))
    before=path.read_bytes();q=load_project(path);assert q['version']==2;assert path.read_bytes()==before;assert q['documents']==p['documents'];assert q['assets']==p['assets'];assert load_project(path)['project_id']==q['project_id']
    backup=migration_copy(path);assert backup.read_bytes()==before;assert migration_copy(path)==backup
    save_project(q,path);assert migration_copy(path) is None;assert backup.read_bytes()==before;assert load_project(path)==q

def test_duplicate_ids_future_versions_and_corrupt_archives_rejected(tmp_path):
    path=tmp_path/'bad.storynator';p=new_project();p['documents'].append(copy.deepcopy(p['documents'][0]))
    with pytest.raises(ValueError,match='Doppelte'):save_project(p,path)
    path.write_bytes(b'not a zip')
    with pytest.raises(ValueError,match='beschädigt'):load_project(path)
    with zipfile.ZipFile(path,'w') as z:z.writestr('project.json',json.dumps({'version':999}))
    with pytest.raises(ValueError,match='Dateiversion'):load_project(path)

def test_archive_detects_changed_asset_and_json(tmp_path):
    p=sample();path=tmp_path/'good.storynator';save_project(p,path)
    with zipfile.ZipFile(path) as z:data={name:z.read(name) for name in z.namelist()}
    for target in ['project.json','assets/'+next(iter(p['assets']))]:
        bad=tmp_path/'bad.storynator'
        with zipfile.ZipFile(bad,'w') as z:
            for name,value in data.items():z.writestr(name,(value.replace(b'Aster',b'Other') if target=='project.json' else value+b'x') if name==target else value)
        with pytest.raises(ValueError,match='beschädigt|Beschädigte'):load_project(bad)

def test_integrity_protects_covers_archived_values_and_unknown_fields():
    p=sample();original=next(iter(p['assets']));p['covers']['book']=original;p['assets']['unused.png']=p['assets'][original];p['assets']['archive.png']=p['assets'][original];p['entries'][0]['values']['archived-unknown-field']=['archive.png'];p['entries'][0]['links'].append('missing-id');p['covers']['project']='missing-cover.png'
    report=project_report(p);assert any(i['kind']=='Fehlender Verweis' for i in report);assert any(i['kind']=='Fehlendes Bild' and i['detail']=='missing-cover.png' for i in report)
    assert {i['detail'] for i in report if i['kind']=='Unbenutzte Ressource'}=={'unused.png'};assert {'archive.png',original}<=used_assets(p)

def test_project_lock_blocks_other_instance_then_releases(qt,tmp_path,monkeypatch):
    path=tmp_path/'lock.storynator';save_project(new_project(),path);one=studio(tmp_path/'one');two=studio(tmp_path/'two');errors=[];two.error=errors.append;one.open_file(str(path));two.open_file(str(path));assert two.path is None;assert errors;assert Path(str(path)+'.lock').exists();one.dirty=False;one.close();two.open_file(str(path));assert two.path==str(path);two.dirty=False;two.close();assert not Path(str(path)+'.lock').exists()

def test_failed_save_keeps_original_and_dirty_state(qt,tmp_path,monkeypatch):
    w=studio(tmp_path);path=tmp_path/'safe.storynator';save_project(w.p,path);w.open_file(str(path));before=path.read_bytes();w.p['name']='Changed';w.changed();errors=[];w.error=errors.append
    import storage
    replace=storage.os.replace
    def fail(src,dest):
        if Path(dest)==path:raise OSError('Disk unavailable')
        return replace(src,dest)
    monkeypatch.setattr(storage.os,'replace',fail);assert not w.save();assert w.dirty;assert path.read_bytes()==before;assert errors;assert w.backups.list();w.dirty=False;w.close()

def test_background_backup_uses_snapshot_and_gui_remains_live(qt,tmp_path):
    from PySide6.QtTest import QTest
    w=studio(tmp_path);w.p['name']='Before';w.changed();w.autosave_background();w.p['name']='After';w.changed();ticks=[];QTimer.singleShot(0,lambda:ticks.append(True));QTest.qWait(30);w.backup_pool.waitForDone();qt.processEvents();assert ticks;assert load_project(w.recovery)['name']=='Before';assert w.dirty;w.autosave();assert load_project(w.recovery)['name']=='After';w.dirty=False;w.close()

def test_backup_restoration_opens_copy_without_overwriting(qt,tmp_path,monkeypatch):
    from project_ui import BackupDialog
    w=studio(tmp_path);path=tmp_path/'source.storynator';save_project(w.p,path);w.open_file(str(path));w.p['name']='Recovered';w.backups.create(w.p,path,'Manuell');before=path.read_bytes();d=BackupDialog(w);d.restore();assert w.path is None;assert w.dirty;assert w.p['name']=='Recovered';assert path.read_bytes()==before;assert not Path(str(path)+'.lock').exists();w.dirty=False;w.close()

def test_actual_pdf_has_two_covers_but_print_document_has_none(qt,tmp_path):
    w=studio(tmp_path);w.p['documents'][0]['html']='<p>Manuscript content</p>'
    for kind,color in [('project','red'),('book','blue')]:
        img=QImage(180,260,QImage.Format_RGB32);img.fill(QColor(color));w.p['covers'][kind]=store_image(w.p,img)
    printer=printing.make_printer(w.p,w.settings)
    for pdf,expected_pages in [(False,1),(True,3)]:
        doc=w.export_document(w.p['documents'],pdf=pdf,printer=printer);path=tmp_path/('pdf.pdf' if pdf else 'print.pdf');printing.write_pdf(doc,path,printer);reader=PdfReader(io.BytesIO(path.read_bytes()));assert len(reader.pages)==expected_pages
        assert 'Manuscript content' in ' '.join(reader.pages[-1].extract_text().split())
        assert bool(list(reader.pages[0].images))==pdf
    doc=w.export_document(w.p['documents'],pdf=True,printer=printer,cover_kinds=['book']);printing.write_pdf(doc,tmp_path/'book.pdf',printer);assert len(PdfReader(io.BytesIO((tmp_path/'book.pdf').read_bytes())).pages)==2
    save_project(w.p,tmp_path/'covers.storynator');assert load_project(tmp_path/'covers.storynator')['covers']==w.p['covers'];w.dirty=False;w.close()

def test_cover_dialog_cancel_does_not_leave_images(qt,tmp_path,monkeypatch):
    from project_ui import CoversDialog
    w=studio(tmp_path);img=QImage(30,40,QImage.Format_RGB32);img.fill(QColor('blue'));path=tmp_path/'cover.png';img.save(str(path));monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''));d=CoversDialog(w);next(b for b in d.findChildren(QPushButton) if b.text()=='Bild auswählen').click();assert w.p['assets'];d.reject();assert not w.p['assets'];assert not any(w.p['covers'].values());w.dirty=False;w.close()

def test_large_image_import_is_bounded_and_deduplicated(qt,tmp_path):
    p=new_project();image=QImage(5000,100,QImage.Format_RGB32);image.fill(QColor('green'));path=tmp_path/'wide.png';image.save(str(path));first=import_image(p,path);second=import_image(p,path);assert first==second;assert image_from_asset(p,first,100).width()<=100
    loaded=QImage.fromData(base64.b64decode(p['assets'][first]));assert loaded.width()<=4096;assert loaded.height()>0

def test_large_document_flushes_before_save_and_closing_tab(qt,tmp_path):
    w=studio(tmp_path);w.p['documents'][0]['html']='<p>'+('Long manuscript '*9000)+'</p>';w.open_object(w.p['documents'][0]['id']);e=w.editor();e.moveCursor(QTextCursor.End);e.insertPlainText('END_MARKER');assert e.store_timer.isActive();w.path=str(tmp_path/'long.storynator');assert w.save();assert 'END_MARKER' in load_project(w.path)['documents'][0]['html'];e.insertPlainText('CLOSED_MARKER');w.close_tab(w.tabs.currentIndex());assert 'CLOSED_MARKER' in w.p['documents'][0]['html'];w.dirty=False;w.close()

def test_views_refresh_without_losing_editor_cursor(qt,tmp_path):
    w=studio(tmp_path);w.p=sample();w.refresh();w.open_object(w.p['documents'][0]['id']);e=w.editor();cur=e.textCursor();cur.setPosition(3);e.setTextCursor(cur);docpage=w.tabs.currentWidget();w.open_object(w.p['entries'][0]['id']);worldpage=w.tabs.currentWidget();entry=w.p['entries'][0];entry['values'][w.p['categories'][0]['fields'][0]['id']]='New profession';w.changed();w.refresh_open_views();assert any(label.text()=='New profession' for label in worldpage.findChildren(QLabel));w.tabs.setCurrentWidget(docpage);assert e.textCursor().position()==3;w.dirty=False;w.close()

def test_timeline_keyboard_and_invalid_dates_are_recoverable(qt,tmp_path):
    from timeline import TimelineCanvas
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    w=studio(tmp_path);w.p['calendar']['months']=[];w.p['events']=[dict(id=uid(),name='ok',start='100',end='200',kind='Zeitalter',links=[],html='',era=None),dict(id=uid(),name='bad',start='0',end='',kind='Ereignis',links=[],html='',era=None)];canvas=TimelineCanvas(w);assert len(canvas.invalid)==1;before=canvas.end-canvas.begin;canvas.keyPressEvent(QKeyEvent(QEvent.KeyPress,Qt.Key_Plus,Qt.NoModifier));assert canvas.end-canvas.begin<before;w.dirty=False;w.close()

def test_stress_search_archive_and_timeline_10000_objects(qt,tmp_path,monkeypatch):
    from timeline import TimelineCanvas,era_lanes
    p=new_project();cat=dict(id=uid(),name='People',fields=[]);p['categories']=[cat];p['calendar']['months']=[]
    p['entries']=[dict(id=uid(),name='Person '+str(i),category=cat['id'],html='<p>North kingdom</p>',values={},links=[]) for i in range(5000)]
    p['events']=[dict(id=uid(),name='Event '+str(i),start=str(i+1),end='',kind='Ereignis',era=None,html='',links=[]) for i in range(5000)]
    started=time.perf_counter();index=SearchIndex(p);assert len(index.search('person north'))==5000;assert len(index.search('person 4999'))==1;path=tmp_path/'large.storynator';save_project(p,path);assert load_project(path)==p
    w=studio(tmp_path);w.p=p;w.refresh();assert w.nav.topLevelItem(1).child(0).childCount()==5000;canvas=TimelineCanvas(w);canvas.resize(1200,500);assert sum(map(len,canvas.clusters()))==5000;canvas.zoom(100);assert sum(map(len,canvas.clusters()))<100
    eras=[(0,100,dict(id=str(i))) for i in range(5000)];assert era_lanes(eras)[1]==5000
    import app
    p['documents'][0]['html']='<a href="story:'+p['entries'][0]['id']+'">Person 0</a>';w.nav.setCurrentItem(w.nav.topLevelItem(1).child(0).child(0));monkeypatch.setattr(app,'ask',lambda *args:'Renamed');w.rename();assert 'Renamed' in p['documents'][0]['html']
    elapsed=time.perf_counter()-started;print(f'10000 objects: search/save/load/timeline {elapsed:.2f}s');assert elapsed<30;w.dirty=False;w.close()

def test_keyboard_navigation_and_small_window(qt,tmp_path):
    from PySide6.QtTest import QTest
    w=studio(tmp_path);w.p=sample();w.refresh();w.open_object(w.p['documents'][0]['id']);w.resize(1000,700);w.show();qt.processEvents();assert w.width()<=1000;assert w.height()<=700;assert w.format_area.horizontalScrollBar().maximum()>0
    QTest.keyClick(w,Qt.Key_3,Qt.ControlModifier);qt.processEvents();assert w.section=='world';w.open_object(w.p['entries'][0]['id']);QTest.keyClick(w,Qt.Key_E,Qt.ControlModifier);qt.processEvents();assert w.tabs.currentWidget().world_edit;QTest.keyClick(w,Qt.Key_E,Qt.ControlModifier);qt.processEvents();assert not w.tabs.currentWidget().world_edit
    QTest.keyClick(w,Qt.Key_K,Qt.ControlModifier);assert w.global_search.hasFocus();QTest.keyClick(w,Qt.Key_2,Qt.ControlModifier);qt.processEvents();assert w.section=='timeline';assert w.width()<=1000;assert w.height()<=700;w.dirty=False;w.close()

def test_theme_text_contrast_and_focus_names(qt,tmp_path):
    from design import theme_colors,ACCENTS
    def luminance(color):
        color=QColor(color);parts=[n/255 for n in [color.red(),color.green(),color.blue()]];linear=[n/12.92 if n<=.04045 else ((n+.055)/1.055)**2.4 for n in parts];return sum(n*w for n,w in zip(linear,[.2126,.7152,.0722]))
    for mode in ['light','dark']:
        for accent in ACCENTS:
            colors=theme_colors(mode,accent)
            for role in ['text','muted']:
                values=sorted([luminance(colors[role]),luminance(colors['paper'])]);assert (values[1]+.05)/(values[0]+.05)>=4.5
    w=studio(tmp_path);assert w.nav.accessibleName();assert w.global_search.accessibleName();assert w.tabs.accessibleName();w.dirty=False;w.close()

@pytest.mark.parametrize('version',[1,2])
def test_fixed_format_fixtures_remain_compatible(version,tmp_path):
    raw=(Path(__file__).parent/'tests'/'fixtures'/f'project-v{version}.json').read_bytes();path=tmp_path/'fixture.storynator'
    with zipfile.ZipFile(path,'w') as z:z.writestr('project.json',raw)
    p=load_project(path);assert p['version']==2;assert p['future_metadata']['keep']=='unbekannte Felder bleiben erhalten';assert '<b>Erhaltener Text</b>' in p['documents'][0]['html'];save_project(p,path);assert load_project(path)==p

def test_stale_lock_from_crashed_process_can_be_reclaimed(tmp_path):
    import subprocess,sys
    path=str(tmp_path/'crashed.lock');script='import os;from PySide6.QtCore import QLockFile;lock=QLockFile('+repr(path)+');lock.setStaleLockTime(0);assert lock.tryLock(0);os._exit(0)';subprocess.run([sys.executable,'-c',script],check=True,timeout=20);lock=QLockFile(path);lock.setStaleLockTime(0);assert lock.tryLock(0);lock.unlock()

def test_failed_migration_copy_keeps_current_project(qt,tmp_path,monkeypatch):
    import app
    w=studio(tmp_path);before=w.p;raw=(Path(__file__).parent/'tests'/'fixtures'/'project-v1.json').read_bytes();path=tmp_path/'old.storynator'
    with zipfile.ZipFile(path,'w') as z:z.writestr('project.json',raw)
    unchanged=path.read_bytes();errors=[];w.error=errors.append
    def fail(*args):raise PermissionError('Backup denied')
    monkeypatch.setattr(app,'migration_copy',fail);w.open_file(str(path));assert errors;assert w.p is before;assert w.path is None;assert path.read_bytes()==unchanged;assert not Path(str(path)+'.lock').exists();w.dirty=False;w.close()

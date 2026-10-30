import copy,io,json
from pathlib import Path
import pytest
from test_storynator import qt,isolated_preferences,sample
from test_safety import studio
from core import new_project,uid,save_project,load_project,references
from authoring import *
from worldmodel import *
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QTextCursor,QTextDocument,QColor,QFont
from PySide6.QtWidgets import QInputDialog,QMessageBox,QLabel,QPushButton,QComboBox,QGridLayout
from pypdf import PdfReader
import printing,addons

def document(name,kind='chapter',parent=None,text=''):
    return dict(id=uid(),name=name,kind=kind,parent=parent,status='draft',html='<p>'+text+'</p>')

def test_structure_reorder_reject_cycle_and_preserve_export_order(qt,tmp_path):
    p=new_project();part=document('Part','part');chapter=document('Chapter','chapter',part['id']);scene=document('Scene','scene',chapter['id']);other=document('Other');p['documents']=[other,scene,part,chapter]
    assert [d['name'] for d in ordered_documents(p)]==['Other','Part','Chapter','Scene'];set_structure(p,[(part['id'],None),(chapter['id'],part['id']),(scene['id'],chapter['id']),(other['id'],None)])
    with pytest.raises(ValueError):set_structure(p,[(part['id'],scene['id']),(chapter['id'],part['id']),(scene['id'],chapter['id']),(other['id'],None)])
    assert move_sibling(p,other['id'],-1);assert [d['name'] for d in ordered_documents(p)]==['Other','Part','Chapter','Scene'];path=tmp_path/'hierarchy.storynator';save_project(p,path);assert load_project(path)==p

def test_structure_dialog_edits_status_name_and_parent(qt,tmp_path):
    from manuscript_ui import StructureDialog
    w=studio(tmp_path);a=document('A','part');b=document('B');w.p['documents']=[a,b];dialog=StructureDialog(w);first=dialog.tree.topLevelItem(0);second=dialog.tree.topLevelItem(1);second.setText(0,'Renamed');dialog.tree.itemWidget(second,2).setCurrentIndex(2);dialog.apply();assert b['name']=='Renamed';assert b['status']=='done';assert w.dirty;w.dirty=False;w.close()

def test_format_preserving_replace_skips_refs_and_tracks_comments(qt,tmp_path):
    p=sample();doc=p['documents'][0];target=p['entries'][0];key=next(iter(p['assets']));doc['html']='<p><b>Blue</b> Blue <a href="story:'+target['id']+'">Blue</a><img src="asset:'+key+'" width="30" height="40"/></p>';doc['annotations']=[dict(id=uid(),kind='comment',text='Keep',start=5,end=9,quote='Blue')]
    assert replacement_preview([doc],'Blue')==[(doc['id'],2)];assert replace_all([doc],'Blue','Azure')==2;assert len(doc['history'])==1;assert 'asset:'+key in doc['html'];assert 'story:'+target['id'] in doc['html'];q=QTextDocument();q.setHtml(doc['html']);cursor=QTextCursor(q);cursor.setPosition(0);cursor.setPosition(5,QTextCursor.KeepAnchor);assert cursor.charFormat().fontWeight()>=QFont.Bold;note=doc['annotations'][0];cursor.setPosition(note['start']);cursor.setPosition(note['end'],QTextCursor.KeepAnchor);assert cursor.selectedText()=='Azure';restore_snapshot(doc,doc['history'][0]['id']);assert 'Azure' not in doc['html'];assert len(doc['history'])==2;save_project(p,tmp_path/'replace.storynator');assert load_project(tmp_path/'replace.storynator')==p

def test_notes_follow_typing_deletion_and_persist(qt,tmp_path,monkeypatch):
    from manuscript_ui import NotesDialog
    w=studio(tmp_path);doc=w.p['documents'][0];doc['html']='<p>One coast story</p>';w.open_object(doc['id']);editor=w.editor();cursor=editor.textCursor();cursor.setPosition(4);cursor.setPosition(9,QTextCursor.KeepAnchor);editor.setTextCursor(cursor);monkeypatch.setattr(QInputDialog,'getMultiLineText',lambda *a,**k:('Comment',True));dialog=NotesDialog(w);dialog.add('comment');note=doc['annotations'][0];assert note['quote']=='coast';cursor=QTextCursor(editor.document());cursor.setPosition(0);cursor.insertText('New ');editor.flush();assert note['start']==8;assert note['end']==13;assert editor.extraSelections()
    cursor.setPosition(8);cursor.setPosition(13,QTextCursor.KeepAnchor);cursor.removeSelectedText();editor.flush();assert note['detached'];save_project(w.p,tmp_path/'notes.storynator');assert load_project(tmp_path/'notes.storynator')['documents'][0]['annotations'][0]['text']=='Comment';w.dirty=False;w.close()

def test_closed_document_notes_follow_renamed_targets(qt,tmp_path,monkeypatch):
    import app
    w=studio(tmp_path);w.p=sample();doc=w.p['documents'][0];target=w.p['entries'][0];doc['html']='<p><a href="story:'+target['id']+'">Mira</a> coast</p>';doc['annotations']=[dict(id=uid(),kind='comment',text='Note',start=5,end=10,quote='coast')];w.refresh();w.open_object(target['id']);monkeypatch.setattr(app,'ask',lambda *args:'Mira Longname');w.nav.setCurrentItem(w.nav.topLevelItem(1).child(0).child(0));w.rename();w.open_object(doc['id']);editor=w.editor();note=doc['annotations'][0];cursor=QTextCursor(editor.document());cursor.setPosition(note['start']);cursor.setPosition(note['end'],QTextCursor.KeepAnchor);assert cursor.selectedText()=='coast';w.dirty=False;w.close()

def test_revision_restores_format_images_and_protects_assets(qt,tmp_path):
    from safety import used_assets
    p=sample();doc=p['documents'][0];key=next(iter(p['assets']));first=snapshot(doc,'First');doc['html']='<p>Different</p>';assert key in used_assets(p);restore_snapshot(doc,first['id']);assert 'asset:'+key in doc['html'];assert len(doc['history'])==2;save_project(p,tmp_path/'history.storynator');assert load_project(tmp_path/'history.storynator')==p

def test_scene_pdf_continues_chapter_and_uses_hierarchy(qt,tmp_path):
    w=studio(tmp_path);a=document('Chapter',text='Chapter body');b=document('Scene','scene',a['id'],'Scene body');w.p['documents']=[b,a];doc=w.export_document(w.p['documents']);printer=printing.make_printer(w.p,w.settings);path=tmp_path/'scene.pdf';printing.write_pdf(doc,path,printer);reader=PdfReader(io.BytesIO(path.read_bytes()));assert len(reader.pages)==1;text=' '.join(reader.pages[0].extract_text().split());assert text.index('Chapter body')<text.index('Scene body');w.dirty=False;w.close()

def test_offline_dictionaries_and_project_words():
    from spelling import misspellings
    assert [w for w,a,b in misspellings('A story with wrld and Aster.','en_US',['Aster'])]==['wrld']
    result=[w for w,a,b in misspellings('Eine Geschichte mit Geschichtte und Aster.','de_DE',['Aster'])];assert 'Geschichtte' in result;assert 'Geschichte' not in result;assert 'Aster' not in result

def test_writing_session_and_goals_roundtrip(qt,tmp_path):
    w=studio(tmp_path);p=new_project();p['documents'][0]['html']='<p>One</p>';p['writing_goals']=dict(total=100,daily=10,track=True);w.adopt_project(p);editor=w.editor();editor.moveCursor(QTextCursor.End);editor.insertPlainText(' two three');w.flush_editors();w.record_writing_session();assert len(p['writing_sessions'])==1;assert p['writing_sessions'][0]['words_added']==2;w.record_writing_session();assert len(p['writing_sessions'])==1;save_project(p,tmp_path/'goals.storynator');assert load_project(tmp_path/'goals.storynator')==p;w.dirty=False;w.close()

def world():
    p=sample();cat=p['categories'][0];country=p['categories'][1];alive=dict(id=uid(),name='Active',type='Checkbox');country['fields']=[alive];p['entries'][1]['values'][alive['id']]=True;f=dict(id=uid(),name='Country',type='Dropdown',source_category=country['id'],source_filter=dict(field=alive['id'],op='eq',value='True'),group='Identity',column=1,required=True,help='Choose a country');cat['fields'].append(f);return p,f,alive

def test_required_fields_and_filtered_choices_preserve_old_values(qt,tmp_path):
    w=studio(tmp_path);p,f,alive=world();w.p=p;entry=p['entries'][0];country=p['entries'][1];assert f['name'] in missing_required(p,entry);assert filtered_entries(p,f)==[country];entry['values'][f['id']]=country['id'];assert f['name'] not in missing_required(p,entry);country['values'][alive['id']]=False;assert filtered_entries(p,f)==[];combo=w.field(entry,f);assert combo.currentData()==country['id'];assert entry['values'][f['id']]==country['id'];w.dirty=False;w.close()

def test_template_layout_and_filter_preset_remaps_ids(qt,tmp_path):
    from worldlayout import fields_layout
    w=studio(tmp_path);p,f,alive=world();w.p=p;box=fields_layout(w,p['entries'][0],p['categories'][0],True);assert any(label.text()=='Identity' for label in box.findChildren(QLabel));assert any('Country *'==label.text() for label in box.findChildren(QLabel));assert any(label.text()=='Choose a country' for label in box.findChildren(QLabel));preset=addons.export(p,[p['categories'][0]['id']],'Grouped');assert 'field_index' in json.dumps(preset);q=new_project();addons.enable(q,preset);new_f=next(field for c in q['categories'] for field in c['fields'] if field['name']=='Country');new_source=next(c for c in q['categories'] if c['id']==new_f['source_category']);assert new_f['source_filter']['field']==new_source['fields'][0]['id'];assert new_f['source_filter']['field']!=alive['id'];assert new_f['group']=='Identity';assert new_f['column']==1;assert not q['entries'];w.dirty=False;w.close()

def test_relationships_inverse_dates_backlinks_delete_warning(qt,tmp_path):
    p=sample();p['calendar']['months']=[];p['relationship_types']=[dict(id=uid(),name='Lives in',inverse='Home of',directed=True)];a,b=p['entries'];relation=add_relation(p,a['id'],b['id'],p['relationship_types'][0]['id'],'Reason','-10','10');assert relations_for(p,a['id'],'1')[0][1]=='Lives in';assert relations_for(p,b['id'],'1')[0][1]=='Home of';assert relations_for(p,a['id'],'11')==[];assert references(p,b['id']);assert a in backlinks(p,b['id']);save_project(p,tmp_path/'relations.storynator');assert load_project(tmp_path/'relations.storynator')==p
    with pytest.raises(ValueError):add_relation(p,a['id'],b['id'],p['relationship_types'][0]['id'],start='10',end='-10')

def test_duplicate_transfer_preserves_ids_archives_and_images(qt,tmp_path):
    from safety import used_assets
    p=sample();entry=p['entries'][0];source=p['categories'][0];target=dict(id=uid(),name='Travellers',fields=[dict(id=uid(),name='Job',type='Text')]);p['categories'].append(target);before=copy.deepcopy(entry);clone=duplicate_entry(p,entry,'Copy');assert clone['id']!=entry['id'];assert clone['values']==entry['values'];clone['values'][source['fields'][0]['id']]='Changed';assert entry['values']==before['values'];transfer_entry(p,entry,target['id'],{source['fields'][0]['id']:target['fields'][0]['id']});assert entry['id']==before['id'];assert entry['links']==before['links'];assert entry['values'][target['fields'][0]['id']]=='Reisende';assert entry['field_archive'][0]['values']==before['values'];assert next(iter(p['assets'])) in used_assets(p);save_project(p,tmp_path/'transfer.storynator');assert load_project(tmp_path/'transfer.storynator')==p

def test_transfer_rejects_invalid_mapping_atomically():
    p=sample();entry=p['entries'][0];before=copy.deepcopy(entry);source=p['categories'][0];target=dict(id=uid(),name='Other',fields=[dict(id=uid(),name='Number',type='Zahl')]);p['categories'].append(target)
    with pytest.raises(ValueError):transfer_entry(p,entry,target['id'],{source['fields'][0]['id']:target['fields'][0]['id']})
    assert entry==before

def test_saved_views_favorites_recent_and_graph(qt,tmp_path,monkeypatch):
    from world_ui import WorldBrowser,GraphDialog,toggle_favorite
    w=studio(tmp_path);w.p=sample();entry=w.p['entries'][0];toggle_favorite(w,entry['id']);w.remember_object(entry['id']);assert w.recent_ids()[0]==entry['id'];page=WorldBrowser(w);page.favorite.setChecked(True);assert len(page.entries)==1;monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:('Saved',True));page.save_view();assert w.p['saved_views'][0]['filters']['favorites'];page.favorite.setChecked(False);page.saved.setCurrentIndex(1);page.load_view();assert page.favorite.isChecked();graph=GraphDialog(w,entry['id']);assert graph.scene.items();save_project(w.p,tmp_path/'views.storynator');assert load_project(tmp_path/'views.storynator')==w.p;w.dirty=False;w.close()

def test_real_template_settings_apply_general_fields_and_filter(qt,tmp_path):
    import app
    w=studio(tmp_path);p,f,alive=world();w.p=p;cat=p['categories'][0]
    def fill_settings():
        dialog=qt.activeModalWidget();lines=dialog.findChildren(app.QLineEdit);lines[0].setText('New group');dialog.findChild(app.QCheckBox).setChecked(True);dialog.findChild(app.QPlainTextEdit).setPlainText('New help')
        # The first plain text box is help, the second is the custom option list.
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Übernehmen').click()
    def open_settings():
        dialog=qt.activeModalWidget();table=dialog.findChild(app.QTableWidget);QTimer.singleShot(0,fill_settings);table.cellDoubleClicked.emit(table.rowCount()-1,2);next(b for b in dialog.findChildren(QPushButton) if b.text()=='Vorlage übernehmen').click()
    QTimer.singleShot(0,open_settings);w.template(cat);updated=cat['fields'][-1];assert updated['group']=='New group';assert updated['required'];assert updated['help']=='New help';assert updated['source_filter']['field']==alive['id'];w.dirty=False;w.close()

def test_spell_dialog_async_works_and_cancels(qt,tmp_path):
    from spelling import SpellDialog
    from PySide6.QtTest import QTest
    w=studio(tmp_path);w.p['documents'][0]['html']='<p>Eine Geschichtte</p>';w.open_object(w.p['documents'][0]['id']);dialog=SpellDialog(w);dialog.pool.waitForDone();qt.processEvents();assert dialog.check_button.isEnabled();assert dialog.list.count()>=1;dialog.reject();w.dirty=False;w.close()

def test_graph_labels_open_objects(qt,tmp_path):
    from world_ui import GraphDialog
    from PySide6.QtTest import QTest
    w=studio(tmp_path);w.p=sample();entry=w.p['entries'][0];graph=GraphDialog(w,entry['id']);graph.show();qt.processEvents();label=next(i for i in graph.scene.items() if isinstance(i,__import__('PySide6.QtWidgets',fromlist=['QGraphicsTextItem']).QGraphicsTextItem) and i.data(0)==entry['id']);point=graph.view.mapFromScene(label.sceneBoundingRect().center());QTest.mouseDClick(graph.view.viewport(),Qt.LeftButton,pos=point);qt.processEvents();assert w.current()['id']==entry['id'];assert graph.view.scene() is None;w.dirty=False;w.close()

def test_required_field_done_stays_in_edit_mode(qt,tmp_path):
    w=studio(tmp_path);p,f,alive=world();w.p=p;errors=[];w.error=errors.append;w.open_object(p['entries'][0]['id']);page=w.tabs.currentWidget();w.render_world_page(page,True);next(b for b in page.findChildren(QPushButton) if b.text()=='Fertig').click();assert errors;assert page.world_edit;assert save_project(p,tmp_path/'draft.storynator') is None;w.dirty=False;w.close()

def test_adjacent_replacements_do_not_swallow_neighbors(qt):
    doc=document('Replace',text='aaaa tail');doc['annotations']=[dict(id=uid(),kind='comment',text='tail',start=5,end=9,quote='tail')];assert replace_all([doc],'aa','X')==2;parsed=QTextDocument();parsed.setHtml(doc['html']);assert parsed.toPlainText()=='XX tail';note=doc['annotations'][0];cursor=QTextCursor(parsed);cursor.setPosition(note['start']);cursor.setPosition(note['end'],QTextCursor.KeepAnchor);assert cursor.selectedText()=='tail'


def test_version3_fixture_and_older_formats(qt,tmp_path):
    import zipfile
    for version in [1,2,3]:
        path=tmp_path/f'v{version}.storynator';raw=(Path(__file__).parent/'tests'/'fixtures'/f'project-v{version}.json').read_bytes()
        with zipfile.ZipFile(path,'w') as z:z.writestr('project.json',raw)
        p=load_project(path);assert p['version']==3;save_project(p,path);assert load_project(path)==p

def test_structure_reparent_recreates_controls_and_applies(qt,tmp_path):
    from manuscript_ui import StructureDialog
    w=studio(tmp_path);part=document('Part','part');chapter=document('Chapter');w.p['documents']=[part,chapter];dialog=StructureDialog(w);item=dialog.tree.takeTopLevelItem(1);dialog.tree.topLevelItem(0).addChild(item);dialog.restore_controls();assert dialog.tree.itemWidget(item,2) is not None;dialog.apply();assert chapter['parent']==part['id'];w.dirty=False;w.close()

def test_edit_missing_relation_target_does_not_redirect(qt,tmp_path):
    from world_ui import RelationshipDialog
    from PySide6.QtCore import QTimer
    w=studio(tmp_path);w.p=sample();a,b=w.p['entries'];type_id=uid();w.p['relationship_types']=[dict(id=type_id,name='Link',inverse='',directed=True)];relation=add_relation(w.p,a['id'],b['id'],type_id);w.p['entries'].remove(b);dialog=RelationshipDialog(w,a['id'])
    found=[]
    def inspect():
        modal=qt.activeModalWidget()
        try:
            combos=modal.findChildren(QComboBox);found.extend([(combo.currentData(),combo.currentText()) for combo in combos])
        finally:modal.reject()
    QTimer.singleShot(0,inspect);dialog.edit(relation);assert (b['id'],'[Gelöschter Eintrag]') in found;assert relation['target']==b['id'];w.dirty=False;w.close()

def test_print_tree_selects_chapters_and_scenes_together(qt):
    from manuscript_ui import print_selection_tree,selected_document_ids
    p=new_project();a=document('Chapter');b=document('Scene','scene',a['id']);c=document('Other');p['documents']=[a,b,c];tree=print_selection_tree(p);parent=tree.topLevelItem(0);assert set(selected_document_ids(tree))=={a['id'],b['id'],c['id']};parent.setCheckState(0,Qt.Unchecked);assert selected_document_ids(tree)==[c['id']];parent.setCheckState(0,Qt.Checked);parent.child(1).setCheckState(0,Qt.Unchecked);assert set(selected_document_ids(tree))=={a['id'],c['id']};restored=print_selection_tree(p,selected_document_ids(tree));assert selected_document_ids(restored)==selected_document_ids(tree)

def test_print_dialog_persists_tree_selection(qt,tmp_path):
    import app
    w=studio(tmp_path);a=document('Chapter');b=document('Scene','scene',a['id']);c=document('Other');w.p['documents']=[a,b,c]
    def select():
        dialog=qt.activeModalWidget()
        try:
            tree=dialog.findChild(app.QTreeWidget);tree.topLevelItem(0).setCheckState(0,Qt.Unchecked);next(button for button in dialog.findChildren(QPushButton) if button.text()=='Übernehmen').click()
        finally:dialog.reject()
    QTimer.singleShot(0,select);w.printing();assert w.p['print_settings']['chapters']==[c['id']];w.dirty=False;w.close()

def test_export_flushes_delayed_manuscript_changes(qt,tmp_path):
    w=studio(tmp_path);doc=w.p['documents'][0];doc['html']='<p>'+('word '*22000)+'</p>';w.open_object(doc['id']);editor=w.editor();editor.moveCursor(QTextCursor.End);editor.insertPlainText('FINAL_EXPORT_MARKER');assert editor.store_timer.isActive();export=w.export_document([doc]);assert 'FINAL_EXPORT_MARKER' in export.toPlainText();w.dirty=False;w.close()

def test_open_reader_updates_new_relationships_and_backlinks(qt,tmp_path):
    w=studio(tmp_path);w.p=sample();a,b=w.p['entries'];w.open_object(a['id']);page=w.tabs.currentWidget();type_id=uid();w.p['relationship_types']=[dict(id=type_id,name='New relationship',inverse='',directed=True)];add_relation(w.p,a['id'],b['id'],type_id);w.p['documents'][0]['html']='<a href="story:'+a['id']+'">'+a['name']+'</a>';w.changed();w.refresh_open_views();assert any(label.text()=='New relationship' for label in page.findChildren(QLabel));assert any(w.p['documents'][0]['name'] in button.text() for button in page.findChildren(QPushButton));w.dirty=False;w.close()

import base64,copy,json,zipfile
from pathlib import Path
import pytest
from test_storynator import qt,isolated_preferences,sample
from test_safety import studio
from PySide6.QtCore import Qt,QBuffer,QByteArray,QIODevice,QUrl
from PySide6.QtGui import QImage,QColor,QTextDocument,QTextCursor
from PySide6.QtWidgets import QApplication
from core import new_project,uid,save_project,load_project,references
import community,starters,conlangs,mapmodel
from docx_import import read_docx
from markdown_ui import markdown_html,apply_markdown
from safety import used_assets,project_report

def png():
    image=QImage(50,30,QImage.Format_RGB32);image.fill(QColor('red'));data=QByteArray();buf=QBuffer(data);buf.open(QIODevice.WriteOnly);image.save(buf,'PNG');buf.close();return bytes(data)
def docx(tmp_path):
    path=tmp_path/'Roman.docx'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('word/document.xml','''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Erstes Kapitel</w:t></w:r></w:p><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:i/><w:u w:val="single"/><w:sz w:val="36"/><w:rFonts w:ascii="Arial"/><w:color w:val="AA0033"/></w:rPr><w:t>Hallo Welt</w:t></w:r><w:r><w:drawing><a:blip r:embed="image1"/></w:drawing></w:r></w:p><w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Erster Punkt</w:t></w:r></w:p><w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Zweiter Punkt</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Zweites Kapitel</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Zelle</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><w:hyperlink r:id="external"><w:r><w:t>Externes Label</w:t></w:r></w:hyperlink></w:p></w:body></w:document>''')
        z.writestr('word/_rels/document.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="image1" Target="media/a.png"/><Relationship Id="external" Target="https://example.invalid" TargetMode="External"/></Relationships>''')
        z.writestr('word/media/a.png',png());z.writestr('word/numbering.xml','''<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>''');z.writestr('word/header1.xml','<header/>')
    return path

def test_builtin_starters_and_importable_new_project(qt,tmp_path):
    specs=starters.builtin_starters();assert len(specs)==5 and specs==starters.builtin_starters()
    fantasy=specs[1];p=starters.instantiate(fantasy,'Mein Roman');assert not p['entries'] and p['categories'] and len(p['documents'])==len(fantasy['payload']['project']['documents']);assert p['project_id']!=fantasy['payload']['project']['project_id'];assert p['name']=='Mein Roman'
    community.save(fantasy,tmp_path/'starter.storynator-pack');q=starters.instantiate(community.load(tmp_path/'starter.storynator-pack'),'Andere Welt');assert q['project_id']!=p['project_id'] and q['documents'][0]['id']!=p['documents'][0]['id']
    save_project(q,tmp_path/'world.storynator');assert load_project(tmp_path/'world.storynator')==q

def test_starter_dialog_blank_and_preset(qt,tmp_path):
    from starter_ui import StarterDialog
    w=studio(tmp_path);d=StarterDialog(w);assert d.list.count()>=6;d.name.setText('Neues Buch');d.list.setCurrentRow(2);d.create();assert d.project['name']=='Neues Buch' and d.project['categories'];d.reject();w.dirty=False;w.close()

def test_markdown_format_links_images_and_reversible_change(qt,tmp_path):
    from media import store_image
    w=studio(tmp_path);w.p=sample();doc=w.p['documents'][0];w.refresh();w.open_object(doc['id']);editor=w.editor();target=w.p['entries'][0];key=next(iter(w.p['assets']));source='# Titel\n\n**Fett** und *kursiv*. ['+target['name']+'](story:'+target['id']+')\n\n![Karte](asset:'+key+')\n\n- Eintrag\n- Zweiter'
    before=editor.toPlainText();apply_markdown(editor,source);assert editor.document().find('Fett').charFormat().fontWeight()>=700;pdf_doc=w.export_document([doc]);fragment=pdf_doc.find(target['name']).charFormat();assert not fragment.isAnchor() and fragment.foreground().color()!=QColor('#0000ff') and not fragment.fontUnderline();assert 'story:'+target['id'] in doc['html'] and 'asset:'+key in doc['html'] and doc['history'];editor.undo();assert editor.toPlainText()==before;w.dirty=False;w.close()

def test_markdown_works_in_rich_world_fields(qt,tmp_path):
    from app import Rich
    w=studio(tmp_path);w.p=sample();values=w.p['entries'][0]['values'];values['field']='<p>Alt</p>';editor=Rich(w,values,'field');apply_markdown(editor,'## Feld\n\n**Neu**');assert 'Neu' in values['field'];backup=w.backups.read(w.backups.list(w.p['project_id'])[0]);assert backup['entries'][0]['values']['field']=='<p>Alt</p>';editor.deleteLater();w.dirty=False;w.close()

def test_markdown_no_external_images_or_missing_references(qt):
    p=new_project()
    for text in ['![x](file:///etc/passwd)','![x](https://example.invalid/a.png)','[x](story:missing)']:
        with pytest.raises(ValueError):markdown_html(p,text)
    assert '<script>' not in markdown_html(p,'<script>alert(1)</script>')

def test_docx_format_chapters_tables_images_lists_and_warnings(qt,tmp_path):
    result=read_docx(docx(tmp_path));assert [d['name'] for d in result['documents']]==['Erstes Kapitel','Zweites Kapitel'];assert len(result['assets'])==1;doc=QTextDocument();doc.setHtml(result['documents'][0]['html']);cursor=doc.find('Hallo Welt');fmt=cursor.charFormat();assert fmt.fontPointSize()==18 and fmt.fontWeight()>=700 and fmt.fontItalic() and fmt.fontUnderline() and fmt.foreground().color()==QColor('#aa0033');assert 'start="2"' in result['documents'][0]['html'];assert '<table' in result['documents'][1]['html'] and 'Zelle' in result['documents'][1]['html'];assert len(result['warnings'])>=2
    one=read_docx(tmp_path/'Roman.docx',False);assert len(one['documents'])==1 and '<h1' in one['documents'][0]['html']
    p=new_project();p['documents']=result['documents'];p['assets']=result['assets'];save_project(p,tmp_path/'Imported.storynator');assert load_project(tmp_path/'Imported.storynator')==p

def test_docx_rejects_bad_xml_and_bounded_archives(qt,tmp_path):
    path=tmp_path/'bad.docx';path.write_bytes(b'bad')
    with pytest.raises(ValueError):read_docx(path)
    for content in [b'<!DOCTYPE x [<!ENTITY y "abc">]><x/>',('<x>'*140+'</x>'*140).encode(),b'<!DOCTYPE x><x/>'.decode().encode('utf-16')]:
        with zipfile.ZipFile(path,'w') as z:z.writestr('word/document.xml',content)
        with pytest.raises(ValueError):read_docx(path)

def test_lexicon_edit_check_forms_case_and_roundtrip(qt,tmp_path):
    language=conlangs.new_language('Eldarin');language['alphabet']='aeiou';language['words']=[dict(id=uid(),word='Súla',translation='Wind',pronunciation='su:la',part_of_speech='Nomen',definition='Eine Brise',examples='Súla na.',forms=['Súlar'])]
    assert [x[0] for x in conlangs.unknown_words('súla Súlar unbekannt',language)]==['unbekannt'];language['case_sensitive']=True;assert [x[0] for x in conlangs.unknown_words('súla Súlar',language)]==['súla'];conlangs.save(language,tmp_path/'lang.storynator-lexicon');assert conlangs.load(tmp_path/'lang.storynator-lexicon')==language
    conlangs.export_csv(language,tmp_path/'words.csv');words=conlangs.read_csv(tmp_path/'words.csv');assert words[0]['translation']=='Wind' and words[0]['forms']==['Súlar'];assert conlangs.merge_words(language,words)==0
    p=new_project();created=conlangs.import_language(p,language);assert created['id']!=language['id'] and created['words'][0]['id']!=language['words'][0]['id'];save_project(p,tmp_path/'lang.storynator');assert load_project(tmp_path/'lang.storynator')['lexicons']==p['lexicons']

def test_custom_spelling_job_uses_lexicon_without_hunspell(qt,tmp_path):
    from spelling import CheckTask,SpellDialog
    language=conlangs.new_language('Lunisch');language['words']=[dict(id=uid(),word='nara',forms=['nari'])];job=CheckTask('nara nari unbekannt','conlang:'+language['id'],[],language);result=[];job.signals.done.connect(lambda items,error:result.extend(items));job.run();assert [x[0] for x in result]==['unbekannt']
    w=studio(tmp_path);w.p['lexicons']=[language];w.p['documents'][0]['html']='<p>nara nari unbekannt</p>';w.p['spelling_language']='conlang:'+language['id'];w.refresh();w.open_object(w.p['documents'][0]['id']);d=SpellDialog(w);d.pool.waitForDone();QApplication.processEvents();assert d.language.currentData().startswith('conlang:') and d.list.count()==1;d.ignore();assert any(x['word']=='unbekannt' for x in language['words']);d.reject();w.dirty=False;w.close()

def test_maps_references_and_resource_integrity_roundtrip(qt,tmp_path):
    p=sample();key=next(iter(p['assets']));m=mapmodel.new_map('Kontinent',key);pin=mapmodel.add_pin(m,'Hauptstadt',.2,.8,p['entries'][0]['id'],'Am Meer');p['maps']=[m];assert any('Karte:' in r for r in references(p,p['entries'][0]['id']));assert key in used_assets(p);save_project(p,tmp_path/'map.storynator');assert load_project(tmp_path/'map.storynator')==p
    p['entries'].clear();assert any(i['kind']=='Fehlender Verweis' and 'Kontinent' in i['name'] for i in project_report(p));p['assets'].clear();assert any(i['kind']=='Fehlendes Bild' and i['name']=='Kontinent' for i in project_report(p))
    bad=copy.deepcopy(p);bad['maps'][0]['pins'][0]['x']=float('nan')
    with pytest.raises(ValueError):mapmodel.validate_maps(bad)

def test_world_map_scene_zoom_refresh_selection_and_open(qt,tmp_path):
    w=studio(tmp_path);w.p=sample();m=mapmodel.new_map('Welt',next(iter(w.p['assets'])));pin=mapmodel.add_pin(m,'Mira',.5,.5,w.p['entries'][0]['id']);w.p['maps']=[m];w.refresh();w.show_maps();page=w.tabs.currentWidget();page.resize(1000,650);page.show();QApplication.processEvents();assert page.view.items_by_id[pin['id']].pos().x()>0;page.select_pin(pin['id']);page.view.scale(2,2);scale=page.view.transform().m11();w.p['entries'][0]['name']='Neuer Name';w.changed();page.refresh_data();assert page.list.item(0).text()=='Neuer Name' and page.view.transform().m11()==pytest.approx(scale);page.open_target();assert w.current()['name']=='Neuer Name';w.show_maps();assert w.tabs.currentWidget() is page;w.dirty=False;w.close()

def test_map_drag_commits_normalized_coordinates(qt,tmp_path):
    from PySide6.QtCore import QEvent,QPointF,QPoint
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    w=studio(tmp_path);w.p=sample();m=mapmodel.new_map('Karte',next(iter(w.p['assets'])));pin=mapmodel.add_pin(m,'Ort',.5,.5);w.p['maps']=[m];w.refresh();w.show_maps();w.resize(1500,1000);w.show();QApplication.processEvents();page=w.tabs.currentWidget();page.edit.setChecked(True);QApplication.processEvents();item=page.view.items_by_id[pin['id']];start=page.view.mapFromScene(item.pos());dest=start+QPoint(30,0);viewport=page.view.viewport();QTest.mousePress(viewport,Qt.LeftButton,Qt.NoModifier,start);event=QMouseEvent(QEvent.MouseMove,QPointF(dest),QPointF(viewport.mapToGlobal(dest)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier);QApplication.sendEvent(viewport,event);QTest.mouseRelease(viewport,Qt.LeftButton,Qt.NoModifier,dest);assert pin['x']>.5 and 0<=pin['y']<=1;w.dirty=False;w.close()

def test_docx_import_ui_applies_only_after_preview(qt,tmp_path,monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QFileDialog,QPushButton,QDialog
    from docx_ui import import_docx
    path=docx(tmp_path);w=studio(tmp_path);w.error=lambda e:(_ for _ in ()).throw(AssertionError(str(e)));before=copy.deepcopy(w.p);monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**kw:(str(path),''))
    def accept():
        dialog=QApplication.activeModalWidget();button=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Kapitel importieren');button.click()
    QTimer.singleShot(0,accept);import_docx(w);assert len(w.p['documents'])==len(before['documents'])+2 and w.p['assets'] and w.dirty;assert w.backups.read(w.backups.list(before['project_id'])[0])==before;w.dirty=False;w.close()

def test_lexicon_ui_creates_and_edits_words(qt,tmp_path,monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QInputDialog,QLineEdit,QDialogButtonBox
    from conlang_ui import LexiconDialog
    w=studio(tmp_path);d=LexiconDialog(w);monkeypatch.setattr(QInputDialog,'getText',lambda *a,**kw:('Lunisch',True));d.new_language()
    def word():
        modal=QApplication.activeModalWidget();fields=modal.findChildren(QLineEdit);fields[0].setText('nara');fields[1].setText('Mond');modal.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click()
    QTimer.singleShot(0,word);d.add_word();assert d.current()['words'][0]['translation']=='Mond';d.search.setText('Mond');assert d.words.count()==1;d.reject();w.dirty=False;w.close()

def test_markdown_uses_editor_font_and_preserves_unchanged_document(qt,tmp_path):
    from markdown_ui import MarkdownDialog
    w=studio(tmp_path);w.p=sample();w.refresh();w.open_object(w.p['documents'][0]['id']);e=w.editor();before=e.toHtml();d=MarkdownDialog(e);d.apply();assert e.toHtml()==before;apply_markdown(e,'Normaler Absatz');cursor=e.document().find('Normaler');assert cursor.charFormat().fontPointSize()==14 and cursor.charFormat().fontFamilies()==['Georgia'];w.dirty=False;w.close()

def test_csv_import_failure_does_not_mutate_lexicon(tmp_path):
    lang=conlangs.new_language('Lang');before=copy.deepcopy(lang);path=tmp_path/'bad.csv';path.write_text('translation\nonly\n',encoding='utf-8')
    with pytest.raises(ValueError):conlangs.read_csv(path)
    assert lang==before

def test_markdown_source_hides_internal_ids_and_rejects_foreign_aliases(qt,tmp_path):
    from markdown_ui import MarkdownDialog
    w=studio(tmp_path);w.p=sample();w.refresh();w.open_object(w.p['documents'][0]['id']);e=w.editor();target=w.p['entries'][0]['id'];key=next(iter(w.p['assets']));d=MarkdownDialog(e);source=d.source.toPlainText();assert target not in source and key not in source and 'entry:' in source and 'image:' in source
    output=markdown_html(w.p,source,aliases=d.aliases);assert 'story:'+target in output and 'asset:'+key in output
    with pytest.raises(ValueError):markdown_html(w.p,source,aliases={})
    d.source.appendPlainText('Zusatz');d.apply();assert 'story:'+target in e.obj['html'] and 'entry:' not in e.obj['html'];w.dirty=False;w.close()

def test_markdown_reference_style_survives_save_reload_and_pdf(qt,tmp_path):
    from printing import write_pdf,make_printer
    from pypdf import PdfReader
    w=studio(tmp_path);w.p=sample();w.refresh();w.open_object(w.p['documents'][0]['id']);target=w.p['entries'][0];apply_markdown(w.editor(),'**Anfang** ['+target['name']+'](story:'+target['id']+')')
    path=tmp_path/'md.storynator';save_project(w.p,path);loaded=load_project(path);w.adopt_project(loaded);w.open_object(loaded['documents'][0]['id']);document=w.export_document(loaded['documents']);fmt=document.find(target['name']).charFormat();assert not fmt.isAnchor() and not fmt.fontUnderline() and fmt.foreground().color().name() in ['#000000','#ffffff'];printer=make_printer(w.p,w.settings);pdf=tmp_path/'md.pdf';write_pdf(document,pdf,printer);assert target['name'] in PdfReader(pdf).pages[0].extract_text();w.dirty=False;w.close()

def test_markdown_cancelled_image_import_does_not_modify_project(qt,tmp_path,monkeypatch):
    from markdown_ui import MarkdownDialog
    from PySide6.QtWidgets import QFileDialog,QMessageBox
    path=tmp_path/'new.png';path.write_bytes(png());w=studio(tmp_path);w.p=sample();w.refresh();w.open_object(w.p['documents'][0]['id']);before=copy.deepcopy(w.p);monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**kw:(str(path),''));monkeypatch.setattr(QMessageBox,'question',lambda *a,**kw:QMessageBox.Yes);d=MarkdownDialog(w.editor());d.image();assert len(d.staged_assets)>len(w.p['assets']);d.reject();assert w.p==before
    d=MarkdownDialog(w.editor());d.image();d.apply();assert len(w.p['assets'])>len(before['assets']);w.dirty=False;w.close()

def test_docx_number_override_and_zero_numbering(qt,tmp_path):
    path=docx(tmp_path)
    with zipfile.ZipFile(path) as z:parts={n:z.read(n) for n in z.namelist()}
    parts['word/numbering.xml']=parts['word/numbering.xml'].replace(b'<w:abstractNumId w:val="0"/>',b'<w:abstractNumId w:val="0"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="5"/></w:lvlOverride>')
    with zipfile.ZipFile(path,'w') as z:
        for name,data in parts.items():z.writestr(name,data)
    result=read_docx(path);assert 'start="5"' in result['documents'][0]['html'] and 'start="6"' in result['documents'][0]['html']
    parts['word/document.xml']=parts['word/document.xml'].replace(b'<w:numId w:val="1"/>',b'<w:numId w:val="0"/>')
    with zipfile.ZipFile(path,'w') as z:
        for name,data in parts.items():z.writestr(name,data)
    assert '<ol' not in read_docx(path)['documents'][0]['html']

def test_constructed_language_checks_combining_scripts_and_alphanumeric_words():
    language=conlangs.new_language('Schrift');language['words']=[dict(id=uid(),word='nara7',forms=[]),dict(id=uid(),word='किरा',forms=[]),dict(id=uid(),word='súla',forms=[])]
    text='nara7 किरा su\u0301la 123 unbekannt';items=conlangs.unknown_words(text,language);assert [x[0] for x in items]==['unbekannt'];assert text[items[0][1]:items[0][2]]=='unbekannt'

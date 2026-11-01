"""Executed in both the packaged and the installed Windows EXE, without network access."""
def run_m19(host):
    import tempfile,zipfile
    from pathlib import Path
    from core import uid,save_project,load_project
    import starters,conlangs,mapmodel
    from docx_import import read_docx
    from starter_ui import StarterDialog
    from conlang_ui import LexiconDialog
    from markdown_ui import MarkdownDialog
    starter=starters.instantiate(starters.builtin_starters()[1],'M19 smoke');assert starter['categories'] and not starter['entries']
    choose=StarterDialog(host);assert choose.list.count()>=6;choose.reject();choose.deleteLater()
    language=conlangs.new_language('M19 language');language['words']=[dict(id=uid(),word='nara',translation='moon',forms=['nari'])];host.p['lexicons']=[language];assert not conlangs.unknown_words('nara nari',language)
    lexicon=LexiconDialog(host);assert lexicon.languages.count()==1;lexicon.accept();lexicon.deleteLater()
    host.open_object(host.p['documents'][0]['id']);markdown=MarkdownDialog(host.editor());assert markdown.save.isEnabled();markdown.accept();markdown.deleteLater()
    m=mapmodel.new_map('M19 map',next(iter(host.p['assets'])));mapmodel.add_pin(m,'M19 marker',.5,.5,host.p['entries'][0]['id'] if host.p['entries'] else '');host.p['maps']=[m];host.revision+=1;host.show_maps();assert len(host.tabs.currentWidget().view.items_by_id)==1
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'M19.docx'
        with zipfile.ZipFile(path,'w') as archive:archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>M19 DOCX smoke</w:t></w:r></w:p></w:body></w:document>')
        assert 'M19 DOCX smoke' in read_docx(path)['documents'][0]['html'];project=Path(folder)/'M19.storynator';save_project(host.p,project);assert load_project(project)==host.p

    from update_ui import UpdateDialog
    from versioning import current_version,version_tuple
    version_tuple(current_version());updater=UpdateDialog(host,auto_check=False);assert updater.download.reply is None and host.update_button.accessibleName();updater.reject();updater.deleteLater()
    import os,sys
    if getattr(sys,'frozen',False) and os.environ.get('GITHUB_RUN_NUMBER'):assert current_version()=='0.8.'+os.environ['GITHUB_RUN_NUMBER']

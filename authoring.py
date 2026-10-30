"""Manuscript structure, revision snapshots and format-preserving replacements."""
import copy,re,html
from datetime import datetime,timezone
from html.parser import HTMLParser
from core import uid
from PySide6.QtGui import QTextDocument,QTextCursor,QFont

KINDS={'part':'Teil','chapter':'Kapitel','scene':'Szene'}
STATUSES={'draft':'Entwurf','revision':'Überarbeitung','done':'Fertig'}
def now():return datetime.now(timezone.utc).isoformat()
class PlainParser(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ['head','style','script']:self.hidden+=1
        if tag in ['p','br','li','div','h1','h2','h3']:self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ['head','style','script']:self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)
def plain(text):
    parser=PlainParser();parser.feed(text);return ''.join(parser.parts)
def words(text):return len(re.findall(r"[^\W_]+(?:[-’'][^\W_]+)*",plain(text),re.UNICODE))
def ordered_documents(p):
    by_parent={};lookup={o['id']:o for o in p['documents']}
    for o in p['documents']:by_parent.setdefault(o.get('parent') if o.get('parent') in lookup else None,[]).append(o)
    ordered=[];seen=set()
    def visit(parent,depth=0):
        if depth>64:raise ValueError('Manuskriptstruktur ist zu tief.')
        for o in by_parent.get(parent,[]):
            if o['id'] in seen:continue
            seen.add(o['id']);ordered.append(o);visit(o['id'],depth+1)
    visit(None)
    for o in p['documents']:
        if o['id'] not in seen:ordered.append(o)
    return ordered

def set_structure(p,rows):
    lookup={o['id']:o for o in p['documents']};ids=[id for id,parent in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(lookup):raise ValueError('Struktur muss jedes Dokument genau einmal enthalten.')
    parents=dict(rows)
    for id,parent in rows:
        if parent is not None and (parent not in lookup or lookup[parent].get('kind','chapter')=='scene'):raise ValueError('Szenen können keine Unterdokumente enthalten.')
        seen={id};ancestor=parent
        while ancestor:
            if ancestor in seen or len(seen)>64:raise ValueError('Zyklische oder zu tiefe Manuskriptstruktur.')
            seen.add(ancestor);ancestor=parents.get(ancestor)
    for id,parent in rows:lookup[id]['parent']=parent
    p['documents']=[lookup[id] for id in ids]

def snapshot(doc,name,automatic=False):
    item=dict(id=uid(),name=name.strip(),time=now(),automatic=automatic,content=copy.deepcopy({key:doc.get(key,default) for key,default in [('name',''),('html',''),('status','draft'),('annotations',[])]}))
    doc.setdefault('history',[]).append(item);return item

def restore_snapshot(doc,id):
    item=next((item for item in doc.get('history',[]) if item['id']==id),None)
    if not item:raise ValueError('Kapitelstand nicht gefunden.')
    saved=copy.deepcopy(item['content']);snapshot(doc,'Vor Wiederherstellung',True);doc.update(saved)

def annotation_cursors(doc,text_document):
    cursors={};last=max(0,text_document.characterCount()-1)
    for note in doc.get('annotations',[]):
        start=max(0,min(last,int(note.get('start',0))));end=max(start,min(last,int(note.get('end',start))));cursor=QTextCursor(text_document);cursor.setPosition(start);cursor.setPosition(end,QTextCursor.KeepAnchor);cursors[note['id']]=cursor
    return cursors

def sync_annotations(doc,cursors):
    for note in doc.get('annotations',[]):
        cursor=cursors.get(note['id'])
        if cursor:
            note.update(start=cursor.selectionStart(),end=cursor.selectionEnd());note['detached']=bool(note.get('quote')) and not cursor.hasSelection() and note['kind']=='comment'

def find_ranges(document,query,case=False,whole=False):
    if not query:return []
    flags=QTextDocument.FindFlags()
    if case:flags|=QTextDocument.FindCaseSensitively
    if whole:flags|=QTextDocument.FindWholeWords
    out=[];cursor=QTextCursor(document)
    while True:
        cursor=document.find(query,cursor,flags)
        if cursor.isNull():break
        # A reference's name follows its target, so text replacement must not rename it.
        check=QTextCursor(cursor);linked=False
        for position in range(cursor.selectionStart(),cursor.selectionEnd()):
            check.setPosition(position);check.setPosition(position+1,QTextCursor.KeepAnchor)
            if check.charFormat().isAnchor():linked=True;break
        if not linked:out.append(QTextCursor(cursor))
    return out

def replace_cursor(cursors,edit,text,fmt=None):
    start=edit.selectionStart();end=edit.selectionEnd();length=len(text.encode('utf-16-le'))//2;delta=length-(end-start);ranges={id:(cursor.selectionStart(),cursor.selectionEnd()) for id,cursor in cursors.items()}
    edit.insertText(text,fmt or edit.charFormat())
    for id,(a,b) in ranges.items():
        def position(value,is_end=False):
            if value<=start:return value
            if value>=end:return value+delta
            return start+length if is_end else start
        cursor=cursors[id];new_start=position(a);new_end=position(b,True) if b!=a else new_start;cursor.setPosition(new_start);cursor.setPosition(max(new_start,new_end),QTextCursor.KeepAnchor)

def replacement_preview(docs,query,case=False,whole=False):
    out=[]
    for doc in docs:
        document=QTextDocument();document.setDefaultFont(QFont('Georgia',14));document.setHtml(doc['html']);matches=find_ranges(document,query,case,whole)
        if matches:out.append((doc['id'],len(matches)))
    return out

def replace_all(docs,query,replacement,case=False,whole=False):
    count=0
    if not query:raise ValueError('Suchtext fehlt.')
    for doc in docs:
        document=QTextDocument();document.setDefaultFont(QFont('Georgia',14));document.setHtml(doc['html']);matches=find_ranges(document,query,case,whole)
        if not matches:continue
        snapshot(doc,'Vor Suchen & Ersetzen',True);notes=annotation_cursors(doc,document)
        positions=[(cursor.selectionStart(),cursor.selectionEnd()) for cursor in matches]
        for start,end in reversed(positions):
            cursor=QTextCursor(document);cursor.setPosition(start);cursor.setPosition(end,QTextCursor.KeepAnchor);fmt=QTextCursor(document);fmt.setPosition(start);fmt.setPosition(start+1,QTextCursor.KeepAnchor);replace_cursor(notes,cursor,replacement,fmt.charFormat())
        sync_annotations(doc,notes);doc['html']=document.toHtml();count+=len(matches)
    return count

def reconcile_doc_links(doc,lookup):
    if 'story:' not in doc.get('html','') or not doc.get('annotations'):return
    document=QTextDocument();document.setDefaultFont(QFont('Georgia',14));document.setHtml(doc['html']);notes=annotation_cursors(doc,document);ranges=[];block=document.begin()
    while block.isValid():
        it=block.begin()
        while not it.atEnd():
            fragment=it.fragment();href=fragment.charFormat().anchorHref() if fragment.isValid() else ''
            if href.startswith('story:'):
                start=fragment.position();end=start+fragment.length()
                if ranges and ranges[-1][2]==href and ranges[-1][1]==start:ranges[-1][1]=end
                else:ranges.append([start,end,href,fragment.charFormat()])
            it+=1
        block=block.next()
    changed=False
    for start,end,href,fmt in reversed(ranges):
        cursor=QTextCursor(document);cursor.setPosition(start);cursor.setPosition(end,QTextCursor.KeepAnchor);name=(lookup.get(href[6:]) or {}).get('name','[Gelöschter Eintrag]')
        if cursor.selectedText()!=name:replace_cursor(notes,cursor,name,fmt);changed=True
    if changed:sync_annotations(doc,notes);doc['html']=document.toHtml()

def move_sibling(p,id,delta):
    doc=next((d for d in p['documents'] if d['id']==id),None)
    if not doc:return False
    siblings=[d for d in p['documents'] if d.get('parent')==doc.get('parent')];position=next(i for i,d in enumerate(siblings) if d['id']==id);destination=position+delta
    if not 0<=destination<len(siblings):return False
    a=p['documents'].index(doc);b=p['documents'].index(siblings[destination]);p['documents'][a],p['documents'][b]=p['documents'][b],p['documents'][a];p['documents']=ordered_documents(p);return True

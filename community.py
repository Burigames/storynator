"""Offline, declarative exchange packages. Imports are planned on copies, never in-place."""
import base64,copy,hashlib,html,json,os,re,tempfile,zipfile
from pathlib import Path
from core import uid,new_project,Calendar
from storage import validate as validate_project
import addons
FORMAT='storynator.exchange'
LIMIT=128*1024*1024
KINDS={'categories','calendar','starter','world','reading','challenge','showcase'}
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def metadata(title,author='',license='Private Nutzung',description='',language='de',tags=None):
    return dict(id=uid(),title=title,author=author,license=license,description=description,language=language,tags=tags or [],release='1.0')
def asset_keys(value,assets):
    text=json.dumps(value,ensure_ascii=False);return {k for k in assets if k in text}
def dependencies(p,ids):
    lookup={e['id']:e for e in p['entries']};selected=set(ids)
    if not selected<=lookup.keys():raise ValueError('Eintrag fehlt.')
    while True:
        added=set()
        for id in selected:
            e=lookup[id];text=json.dumps(e,ensure_ascii=False)
            added.update(k for k in lookup if k in text)
            for r in p.get('relationships',[]):
                if id in [r['source'],r['target']]:added.update([r['source'],r['target']])
        added &= lookup.keys()
        if added<=selected:return selected
        selected |= added

def create(p,kind,meta,ids=(),excluded_fields=(),include_dependencies=False,cover=''):
    if kind not in KINDS:raise ValueError('Unbekannter Pakettyp.')
    q=new_project(meta['title']);q['documents']=[];excluded=set(excluded_fields)
    if kind=='categories':payload={'preset':addons.export(p,ids,meta['title'])}
    elif kind=='calendar':payload={'calendar':copy.deepcopy(p['calendar'])}
    else:
        q['calendar']=copy.deepcopy(p['calendar'])
        if kind in ['starter','challenge']:
            preset=addons.export(p,[c['id'] for c in p['categories']],meta['title']) if p['categories'] else None
            if preset:addons.enable(q,preset)
            q.pop('addons',None)
            for c in q['categories']:c.pop('source_addon',None);c.pop('addon_inactive',None)
            docmap={d['id']:uid() for d in p['documents']}
            q['documents']=[dict(id=docmap[d['id']],name=d['name'],kind=d.get('kind','chapter'),parent=docmap.get(d.get('parent')),html='') for d in p['documents']]
        if kind in ['world','showcase']:
            chosen=dependencies(p,ids) if include_dependencies else set(ids)
            q['entries']=[{k:copy.deepcopy(e[k]) for k in ['id','name','category','values','links','html'] if k in e} for e in p['entries'] if e['id'] in chosen]
            cats={e['category'] for e in q['entries']};lookup={c['id']:c for c in p['categories']}
            while True:
                more={f['source_category'] for id in cats for f in lookup[id]['fields'] if f.get('source_category')}
                if more<=cats:break
                cats |= more
            q['categories']=[dict(id=c['id'],name=c['name'],fields=[copy.deepcopy(f) for f in c['fields'] if f['id'] not in excluded]) for c in p['categories'] if c['id'] in cats]
            for cat in q['categories']:
                for field in cat['fields']:
                    if field.get('source_filter',{}).get('field') in excluded:field.pop('source_filter',None)
            for e in q['entries']:
                e['values']={k:v for k,v in e['values'].items() if k not in excluded};e['links']=[k for k in e.get('links',[]) if k in chosen]
            q['relationships']=[copy.deepcopy(r) for r in p.get('relationships',[]) if r['source'] in chosen and r['target'] in chosen]
            types={r['type'] for r in q['relationships']};q['relationship_types']=[copy.deepcopy(t) for t in p.get('relationship_types',[]) if t['id'] in types]
            # Never disclose names of unselected linked objects. Remove their anchors and field references.
            allids={e['id'] for group in ['entries','events','documents'] for e in p[group]};omitted=allids-chosen
            def redact(v):
                if isinstance(v,list):return [redact(x) for x in v if not isinstance(x,str) or x not in omitted]
                if isinstance(v,dict):return {k:redact(x) for k,x in v.items()}
                if isinstance(v,str):
                    if v in omitted:return ''
                    return re.sub(r'<a\b[^>]*href=[\"\']story:([^\"\']+)[\"\'][^>]*>.*?</a>',lambda m:m.group(0) if m[1] in chosen else '[Nicht freigegeben]',v,flags=re.S)
                return v
            q['entries']=redact(q['entries'])
        if kind=='reading':
            from authoring import ordered_documents
            chosen=set(ids);q['project_id']=p['project_id']
            q['documents']=[dict(id=d['id'],name=d['name'],html=d.get('html',''),kind=d.get('kind','chapter'),source_revision=digest(d.get('html',''))) for d in ordered_documents(p) if d['id'] in chosen]
            # References become plain labels; no world content or editing metadata is exported.
            for d in q['documents']:
                from PySide6.QtGui import QTextDocument,QTextCursor,QColor,QFont
                document=QTextDocument();document.setDefaultFont(QFont('Georgia',14));document.setHtml(d['html']);block=document.begin();ranges=[]
                while block.isValid():
                    it=block.begin()
                    while not it.atEnd():
                        f=it.fragment()
                        if f.isValid() and f.charFormat().isAnchor():ranges.append((f.position(),f.length(),f.charFormat()))
                        it+=1
                    block=block.next()
                for pos,length,fmt in ranges:
                    cur=QTextCursor(document);cur.setPosition(pos);cur.setPosition(pos+length,QTextCursor.KeepAnchor);fmt.setAnchor(False);fmt.setAnchorHref('')
                    if fmt.foreground().color().name().lower()=='#7461bb':fmt.setForeground(QColor('black'));fmt.setFontUnderline(False)
                    cur.setCharFormat(fmt)
                d['html']=document.toHtml()
        if cover:
            if cover not in p['assets']:raise ValueError('Cover fehlt.')
            q['covers']['book']=cover
        used=asset_keys(q,p['assets']);q['assets']={k:p['assets'][k] for k in used};payload={'project':q}
    result=dict(format=FORMAT,version=1,kind=kind,metadata=copy.deepcopy(meta),payload=payload)
    return validate(result)

def _validate(spec):
    if not isinstance(spec,dict) or set(spec)!={'format','version','kind','metadata','payload'} or spec['format']!=FORMAT or spec['version']!=1 or spec['kind'] not in KINDS:raise ValueError('Unbekanntes Austauschformat.')
    m=spec['metadata']
    if not isinstance(m,dict) or set(m)-{'id','title','author','license','description','language','tags','release'}:raise ValueError('Ungültige Paketinformationen.')
    if any(not isinstance(m.get(k),str) or len(m[k])>10000 for k in ['id','title','author','license','description','language','release']) or not m['id'] or not m['title'].strip() or not m['license'].strip():raise ValueError('Titel, Kennung und Lizenz werden benötigt.')
    if not isinstance(m.get('tags'),list) or any(not isinstance(t,str) for t in m['tags']):raise ValueError('Ungültige Tags.')
    payload=spec['payload'];kind=spec['kind']
    if not isinstance(payload,dict) or set(payload)!={ 'preset' if kind=='categories' else 'calendar' if kind=='calendar' else 'project'}:raise ValueError('Ungültiger Paketinhalt.')
    if kind=='categories':addons.validate(payload['preset'])
    elif kind=='calendar':Calendar(payload['calendar']).validate()
    else:
        p=payload['project'];validate_project(p);Calendar(p['calendar']).validate()
        allowed={'version','project_id','covers','name','documents','categories','entries','events','assets','calendar','relationships','relationship_types'}
        if set(p)-allowed or p['events']:raise ValueError('Nicht freigegebene Projektmetadaten im Paket.')
        if kind in ['starter','challenge'] and (p['entries'] or any(d.get('html') for d in p['documents'])):raise ValueError('Starter enthalten keine Einträge oder Kapiteltexte.')
        if kind=='reading' and (p['entries'] or p['categories']):raise ValueError('Lesefassungen enthalten keine Welt-Einträge.')
        if kind in ['world','showcase'] and p['documents']:raise ValueError('Weltpakete enthalten keine Kapitel.')
        for d in p['documents']:
            if set(d)-{'id','name','html','kind','parent','source_revision'}:raise ValueError('Lesefassung enthält Bearbeitungsmetadaten.')
        for e in p['entries']:
            if set(e)-{'id','name','category','values','links','html'}:raise ValueError('Nicht freigegebene Eintragsdaten.')
        from html.parser import HTMLParser
        class Resources(HTMLParser):
            def __init__(self):super().__init__();self.in_style=False
            def handle_data(self,data):
                if self.in_style and re.search(r'url\s*\(|expression\s*\(|@import',data,re.I):raise ValueError('Externe Stilressourcen sind nicht erlaubt.')
            def handle_endtag(self,tag):
                if tag=='style':self.in_style=False
            def handle_starttag(self,tag,attrs):
                if tag=='style':self.in_style=True
                if tag in ['script','iframe','object','embed','link','base']:raise ValueError('Aktive Inhalte sind nicht erlaubt.')
                for key,value in attrs:
                    if key.lower().startswith('on'):raise ValueError('Aktive Inhalte sind nicht erlaubt.')
                    if key=='href' and value and not value.startswith(('story:','#')):raise ValueError('Nur interne Verknüpfungen sind erlaubt.')
                    if key in ['src','background'] and (not value or not value.startswith('asset:') or value[6:] not in p['assets']):raise ValueError('Nur eingebettete Bilder sind erlaubt.')
                    if key=='style' and re.search(r'url\s*\(|expression\s*\(',value or '',re.I):raise ValueError('Externe Stilressourcen sind nicht erlaubt.')
        def inspect(value):
            if isinstance(value,str) and '<' in value:Resources().feed(value)
            elif isinstance(value,list):
                for item in value:inspect(item)
            elif isinstance(value,dict):
                for item in value.values():inspect(item)
        inspect(p)
        ids={o['id'] for group in ['entries','documents'] for o in p[group]};cats={c['id']:c for c in p['categories']};types={t['id'] for t in p.get('relationship_types',[])}
        for c in cats.values():
            for f in c['fields']:
                if f.get('source_category') and f['source_category'] not in cats:raise ValueError('Quellkategorie fehlt im Paket.')
        for e in p['entries']:
            if e['category'] not in cats or any(id not in ids for id in e['links']):raise ValueError('Verknüpfungsziel fehlt im Paket.')
            for f in cats[e['category']]['fields']:
                value=e['values'].get(f['id'])
                if f['type'] in ['Bild','Galerie'] and value:
                    values=value if isinstance(value,list) else [value]
                    if any(not isinstance(v,str) or v not in p['assets'] for v in values):raise ValueError('Bild fehlt im Paket.')
                if (f['type']=='Verknüpfung' or f.get('source_category')) and value:
                    values=value if isinstance(value,list) else [value]
                    if any(not isinstance(v,str) or v not in ids for v in values):raise ValueError('Feldauswahl-Ziel fehlt im Paket.')
        for relation in p.get('relationships',[]):
            if relation['source'] not in ids or relation['target'] not in ids or relation['type'] not in types:raise ValueError('Beziehungsziel oder Typ fehlt im Paket.')
        def links(value):
            if isinstance(value,str):
                for id in re.findall(r'href=[\"\']story:([^\"\']+)',value):
                    if id not in ids:raise ValueError('Textverknüpfung zeigt außerhalb des Pakets.')
            elif isinstance(value,list):
                for item in value:links(item)
            elif isinstance(value,dict):
                for item in value.values():links(item)
        links(p)
        if any(k and k not in p['assets'] for k in p['covers'].values()):raise ValueError('Cover fehlt im Paket.')
        for value in p['assets'].values():base64.b64decode(value,validate=True)
    return copy.deepcopy(spec)

def validate(spec):
    try:return _validate(spec)
    except (KeyError,TypeError,AttributeError,IndexError,RecursionError,OverflowError) as e:raise ValueError('Ungültige oder zu tief verschachtelte Paketdaten.') from e

def save(spec,path):
    spec=validate(spec);raw=json.dumps(spec,ensure_ascii=False,allow_nan=False).encode()
    if len(raw)>LIMIT:raise ValueError('Paket zu groß (maximal 128 MB).')
    path=Path(path);fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def load(path):
    with open(path,'rb') as stream:raw=stream.read(LIMIT+1)
    if len(raw)>LIMIT:raise ValueError('Paket zu groß.')
    return validate(json.loads(raw))
def summary(spec):
    spec=validate(spec);m=spec['metadata'];p=spec['payload'].get('project',{})
    names=[x['name'] for group in ['categories','entries','documents'] for x in p.get(group,[])]
    if spec['kind']=='categories':names=[c['name'] for c in spec['payload']['preset']['categories']]
    return '\n'.join([m['title']+' · '+m['release'],spec['kind'],m['author'],m['license'],m['description'],f"{len(p.get('assets',{}))} Bilder/Ressourcen",*names])
def remap(value,mapping):
    if isinstance(value,dict):return {mapping.get(k,k):remap(v,mapping) for k,v in value.items()}
    if isinstance(value,list):return [remap(v,mapping) for v in value]
    if isinstance(value,str):
        if value in mapping:return mapping[value]
        return re.sub(r'(story:|asset:)([A-Za-z0-9_.-]+)',lambda m:m[1]+mapping.get(m[2],m[2]),value)
    return value

def select_import(spec,ids):
    spec=validate(spec);kind=spec['kind'];p=spec['payload'].get('project')
    if kind=='world':return create(p,kind,spec['metadata'],ids)
    if kind in ['starter','challenge']:
        selected=set(ids);spec['payload']['project']['documents']=[d for d in p['documents'] if d['id'] in selected]
        for d in spec['payload']['project']['documents']:
            if d.get('parent') not in selected:d.pop('parent',None)
    elif kind=='categories':
        q=new_project();addons.enable(q,spec['payload']['preset']);cats=q['categories'];wanted={cat['id'] for template,cat in zip(spec['payload']['preset']['categories'],cats) if template['key'] in ids}
        spec['payload']['preset']=addons.export(q,wanted,spec['metadata']['title'])
    return validate(spec)

def plan_import(project,spec):
    spec=validate(spec);q=copy.deepcopy(project);kind=spec['kind'];warnings=[]
    if kind=='calendar':
        # Replacing calendars in populated projects would reinterpret every existing date.
        if q['events'] or q.get('relationships') or any(f['type'] in ['Datum','Zeitspanne'] for c in q['categories'] for f in c['fields']):raise ValueError('Kalender nur vor datierten Inhalten importieren. Neues Projekt verwenden.')
        q['calendar']=copy.deepcopy(spec['payload']['calendar'])
    elif kind=='categories':
        preset=copy.deepcopy(spec['payload']['preset']);preset['id']=uid();addons.enable(q,preset)
    elif kind in ['reading','showcase']:raise ValueError('Lesefassungen/Schaufenster werden separat geöffnet, nicht ins Arbeitsprojekt importiert.')
    else:
        p=spec['payload']['project']
        if kind in ['starter','challenge'] and not q['events'] and not q['entries'] and not q.get('relationships'):q['calendar']=copy.deepcopy(p['calendar'])
        if p['calendar']!=q['calendar'] and (p.get('relationships') or any(f['type'] in ['Datum','Zeitspanne'] for c in p['categories'] for f in c['fields'])):raise ValueError('Beziehungsdaten benötigen denselben Projektkalender.')
        mapping={o['id']:uid() for group in ['documents','categories','entries','relationships','relationship_types'] for o in p.get(group,[])}
        for c in p['categories']:
            for f in c['fields']:mapping[f['id']]=uid()
        for k in p['assets']:mapping[k]=uid()+Path(k).suffix
        incoming=remap(p,mapping)
        for group in ['categories','entries','documents','relationships','relationship_types']:
            existing={x['name'] for x in q.get(group,[]) if 'name' in x}
            for o in incoming.get(group,[]):
                if o.get('name') in existing and 'name' in o:
                    warnings.append(o['name']+' → '+o['name']+' (Import)');o['name']+=' (Import)'
            q.setdefault(group,[]).extend(incoming.get(group,[]))
        q['assets'].update(incoming['assets'])
    receipt=dict(package=spec['metadata']['id'],release=spec['metadata']['release'],hash=digest(spec))
    if kind in ['world','starter','challenge']:
        receipt['mapping']=mapping;receipt['baseline']={group:{o['id']:digest(o) for o in incoming.get(group,[])} for group in ['categories','entries','documents','relationships','relationship_types']}
    q.setdefault('community_imports',[]).append(receipt)
    validate_project(q);return q,warnings

class Library:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def install(self,spec):
        spec=validate(spec);path=self.root/(digest(spec)+'.storynator-pack');save(spec,path);return path
    def items(self):
        result=[]
        for path in sorted(self.root.glob('*.storynator-pack')):
            try:result.append((path,load(path)))
            except (ValueError,OSError):continue
        return result
    def remove(self,path):
        path=Path(path)
        if path.parent.resolve()!=self.root.resolve():raise ValueError('Ungültiger Bibliothekspfad.')
        path.unlink()

def builtin_packages():
    result=[]
    for title,prompt in [('Eine Stadt voller Geheimnisse','Entwirf eine Stadt, deren wichtigstes Gesetz ein Geheimnis schützt.'),('Erster Kontakt','Zwei Kulturen begegnen sich. Beide missverstehen ein Zeichen der anderen.')]:
        p=new_project(title);p['documents']=[dict(id=uid(),name=n,html='') for n in ['Ideen','Figuren','Entwurf']]
        m=metadata(title,'Storynator','CC0-1.0',prompt,tags=['Challenge']);m['id']='storynator.challenge.'+('city' if len(result)==0 else 'contact')
        result.append(create(p,'challenge',m))
    return result


def plan_update(project,spec,choices=None):
    """Three-way object merge. Missing decisions retain local content; never delete objects."""
    spec=validate(spec);choices=choices or {}
    if spec['kind'] not in ['world','starter','challenge']:raise ValueError('Für diesen Pakettyp bitte den geprüften Import verwenden.')
    receipt=next((r for r in reversed(project.get('community_imports',[])) if r['package']==spec['metadata']['id'] and 'mapping' in r),None)
    if receipt is None:raise ValueError('Kein zuordenbarer früherer Import. Als neue Kopie importieren.')
    q=copy.deepcopy(project);p=spec['payload']['project'];mapping=copy.deepcopy(receipt['mapping'])
    if p['calendar']!=q['calendar'] and (p.get('relationships') or any(f['type'] in ['Datum','Zeitspanne'] for c in p['categories'] for f in c['fields'])):raise ValueError('Kalender stimmen nicht überein.')
    groups=['categories','entries','documents','relationships','relationship_types']
    for group in groups:
        for o in p.get(group,[]):mapping.setdefault(o['id'],uid())
    for cat in p['categories']:
        for f in cat['fields']:mapping.setdefault(f['id'],uid())
    for key,value in p['assets'].items():
        if key not in mapping or q['assets'].get(mapping[key])!=value:mapping[key]=uid()+Path(key).suffix
    incoming=remap(p,mapping);conflicts=[];baseline=copy.deepcopy(receipt['baseline'])
    for group in groups:
        old={o['id']:o for o in q.get(group,[])};base=receipt['baseline'].get(group,{})
        for o in incoming.get(group,[]):
            id=o['id'];local=old.get(id);before=base.get(id)
            changed=local is not None and digest(local)!=before and digest(local)!=digest(o)
            removed=local is None and before is not None
            if changed or removed:
                conflicts.append(dict(id=id,group=group,name=o.get('name',id),local=local,incoming=o))
                if choices.get(id,'local')!='package':continue
            if local is not None:q[group]=[o if x['id']==id else x for x in q[group]]
            else:q.setdefault(group,[]).append(o)
            baseline.setdefault(group,{})[id]=digest(o)
    q['assets'].update(incoming['assets'])
    q.setdefault('community_imports',[]).append(dict(package=spec['metadata']['id'],release=spec['metadata']['release'],hash=digest(spec),mapping=mapping,baseline=baseline))
    validate_project(q);return q,conflicts

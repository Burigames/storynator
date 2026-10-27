"""Local history, migration copies and integrity reports. No automatic content removal."""
import base64,hashlib,html,json,os,re,shutil,uuid,threading
from datetime import datetime,timezone
from pathlib import Path
from core import save_project,load_project,objects,Calendar
from storage import archive_version,CURRENT_VERSION

def fingerprint(p):
    digest=hashlib.sha256(json.dumps({k:v for k,v in p.items() if k!='assets'},sort_keys=True,ensure_ascii=False,allow_nan=False).encode())
    for key,value in sorted(p['assets'].items()):digest.update(key.encode());digest.update(value.encode('ascii'))
    return digest.hexdigest()

def file_digest(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()

def migration_copy(path):
    path=Path(path)
    if archive_version(path)==CURRENT_VERSION:return None
    digest=file_digest(path)[:12];target=path.with_name(path.name+'.before-v2-'+digest+'.bak')
    if not target.exists():
        with target.open('xb') as out, path.open('rb') as src:shutil.copyfileobj(src,out);out.flush();os.fsync(out.fileno())
    if file_digest(target)!=file_digest(path):raise OSError('Migrationssicherung konnte nicht geprüft werden.')
    return target

class BackupStore:
    def __init__(self,root,keep=20):self.root=Path(root);self.keep=max(3,min(200,int(keep)));self._mutex=threading.RLock()
    def list(self,project_id=None):
        result=[];folder=self.root/project_id if project_id else self.root
        for path in folder.glob('*.json') if project_id else folder.glob('*/*.json'):
            try:
                meta=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(meta,dict) or not all(isinstance(meta.get(k),str) for k in ['time','name','project_id','reason','digest','sha256']):continue
                datetime.fromisoformat(meta['time']);meta['path']=str(path.with_suffix('.storynator'))
                if Path(meta['path']).exists():result.append(meta)
            except (ValueError,OSError):continue
        return sorted(result,key=lambda item:item['time'],reverse=True)
    def create(self,p,source='',reason='Automatisch'):
        with self._mutex:return self._create(p,source,reason)
    def _create(self,p,source,reason):
        entries=self.list(p['project_id']);digest=fingerprint(p)
        if entries and entries[0].get('digest')==digest:return entries[0]
        now=datetime.now(timezone.utc);folder=self.root/p['project_id'];folder.mkdir(parents=True,exist_ok=True);name=now.strftime('%Y%m%dT%H%M%S%f')+'-'+uuid.uuid4().hex[:6];path=folder/(name+'.storynator');save_project(p,path)
        meta=dict(time=now.isoformat(),name=p['name'],project_id=p['project_id'],source=str(source or ''),reason=reason,digest=digest,sha256=file_digest(path),documents=len(p['documents']),entries=len(p['entries']),events=len(p['events']))
        temporary=path.with_suffix('.json.tmp')
        with temporary.open('w',encoding='utf-8') as file:json.dump(meta,file,ensure_ascii=False);file.flush();os.fsync(file.fileno())
        os.replace(temporary,path.with_suffix('.json'))
        for old in self.list(p['project_id'])[self.keep:]:
            oldpath=Path(old['path']);oldpath.unlink(missing_ok=True);oldpath.with_suffix('.json').unlink(missing_ok=True)
        return {**meta,'path':str(path)}
    def preview(self,meta):
        import zipfile
        with zipfile.ZipFile(meta['path']) as z:
            p=json.loads(z.read('project.json'));p['assets']={}
            for key in p.get('covers',{}).values():
                if key and 'assets/'+key in z.namelist():p['assets'][key]=base64.b64encode(z.read('assets/'+key)).decode()
            return p
    def read(self,meta):
        path=Path(meta['path'])
        if file_digest(path)!=meta['sha256']:raise ValueError('Sicherung beschädigt. Bitte einen anderen Stand wählen.')
        return load_project(path)

ASSET_RE=re.compile(r'asset:([^\s"\'<>]+)')
LINK_RE=re.compile(r'story:([^\s"\'<>]+)')
def used_assets(p):
    used=set(p.get('covers',{}).values())-set([''])
    for o in objects(p):
        used.update(html.unescape(k) for k in ASSET_RE.findall(o.get('html','')))
        for value in o.get('values',{}).values():
            if isinstance(value,str):used.update(html.unescape(k) for k in ASSET_RE.findall(value))
            if isinstance(value,list):used.update(v for v in value if isinstance(v,str) and v in p['assets'])
    # Archived fields and metadata also protect resource IDs, including future field types.
    def walk(value):
        if isinstance(value,str):
            if value in p['assets']:used.add(value)
            used.update(html.unescape(k) for k in ASSET_RE.findall(value))
        elif isinstance(value,list):
            for item in value:walk(item)
        elif isinstance(value,dict):
            for item in value.values():walk(item)
    walk({k:v for k,v in p.items() if k!='assets'})
    return used

def project_report(p,check_image=None):
    issues=[];lookup={o['id']:o for o in objects(p)};cats={c['id']:c for c in p['categories']};cal=Calendar(p['calendar']);entry_ids={o['id'] for o in p['entries']};event_ids={o['id'] for o in p['events']}
    def add(kind,name,detail,id=None):issues.append(dict(kind=kind,name=name,detail=detail,id=id))
    for o in objects(p):
        links=set(o.get('links',[]))|set(LINK_RE.findall(o.get('html','')))
        if o.get('era'):links.add(o['era'])
        cat=cats.get(o.get('category'));fields={f['id']:f for f in (cat or {}).get('fields',[])+(cat or {}).get('archived',[])}
        for key,value in o.get('values',{}).items():
            if isinstance(value,str):links.update(LINK_RE.findall(value))
            f=fields.get(key,{})
            if f.get('source_category') or f.get('type')=='Verknüpfung':links.update(value if isinstance(value,list) else [value] if value else [])
            if f.get('type') in ['Bild','Galerie']:
                for asset in value if isinstance(value,list) else [value] if value else []:
                    if asset not in p['assets']:add('Fehlendes Bild',o['name'],str(asset),o['id'])
        for target in links:
            if target not in lookup:add('Fehlender Verweis',o['name'],str(target),o['id'])
        if o['id'] in entry_ids and not cat:add('Fehlende Kategorie',o['name'],o['category'],o['id'])
        if o['id'] in event_ids:
            try:cal.span(o['start'],o['end'])
            except (ValueError,KeyError,IndexError):add('Ungültiges Datum',o['name'],o.get('start',''),o['id'])
    for c in p['categories']:
        for f in c['fields']:
            if f.get('source_category') and f['source_category'] not in cats:add('Fehlende Quellkategorie',c['name'],f['name'],c['id'])
    used=used_assets(p)
    for key in used-p['assets'].keys():add('Fehlendes Bild','Projekt',key)
    for key,value in p['assets'].items():
        try:
            data=base64.b64decode(value,validate=True)
            if check_image and Path(key).suffix.lower() in ['.png','.jpg','.jpeg','.webp','.bmp','.gif'] and not check_image(data):add('Beschädigtes Bild','Projekt',key)
        except (ValueError,TypeError):add('Beschädigte Ressource','Projekt',key)
    for key in sorted(p['assets'].keys()-used):add('Unbenutzte Ressource','Projekt',key)
    return issues

class SearchIndex:
    def __init__(self,p):
        categories={c['id']:c['name'] for c in p['categories']};lookup={o['id']:o['name'] for o in objects(p)};self.rows=[]
        def names(value):
            if isinstance(value,str):return lookup.get(value,value)
            if isinstance(value,list):return [names(item) for item in value]
            if isinstance(value,dict):return {key:names(item) for key,item in value.items()}
            return value
        for o in objects(p):
            text=' '.join([o['name'],categories.get(o.get('category'),o.get('kind','Dokument')),re.sub('<[^>]*>',' ',html.unescape(o.get('html',''))),json.dumps(names(o.get('values',{})),ensure_ascii=False)])
            self.rows.append((o['id'],o['name'],text.casefold()))
    def search(self,query):
        terms=query.casefold().split();return [(id,name) for id,name,text in self.rows if all(term in text for term in terms)]

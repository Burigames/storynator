"""Versioned, validated and atomic project archives. Never overwrite during loading."""
import base64,copy,hashlib,json,os,re,tempfile,uuid,zipfile
from pathlib import Path
CURRENT_VERSION=2
MAX_ARCHIVE_BYTES=2*1024**3
MAX_JSON_BYTES=64*1024**2

def migrate(project):
    if not isinstance(project,dict):raise ValueError('Projektinhalt ist kein gültiges Objekt.')
    p=copy.deepcopy(project);version=p.get('version')
    if type(version) is not int or version not in (1,2):raise ValueError('Unbekannte Dateiversion. Bitte eine passende Storynator-Version verwenden.')
    if version==1:
        p['version']=2;p.setdefault('project_id',str(uuid.uuid5(uuid.NAMESPACE_URL,'storynator:'+next((o['id'] for group in ['documents','entries','events'] for o in p.get(group,[]) if o.get('id')),json.dumps(p,sort_keys=True)))));p.setdefault('covers',{'project':'','book':''})
    return p

def validate(p):
    if not isinstance(p,dict) or p.get('version')!=CURRENT_VERSION:raise ValueError('Unbekannte Dateiversion')
    if not isinstance(p.get('name'),str) or not isinstance(p.get('project_id'),str):raise ValueError('Projektname oder Projektkennung fehlt.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',p['project_id']):raise ValueError('Ungültige Projektkennung.')
    seen=set()
    for group in ['documents','entries','events','categories']:
        if not isinstance(p.get(group),list):raise ValueError('Projektbereich fehlt: '+group)
        for obj in p[group]:
            if not isinstance(obj,dict) or not isinstance(obj.get('id'),str) or not obj['id'] or not isinstance(obj.get('name'),str):raise ValueError('Ungültiger Eintrag in '+group)
            if obj['id'] in seen:raise ValueError('Doppelte interne Kennung. Datei unverändert lassen und Sicherung verwenden.')
            seen.add(obj['id'])
            if group=='categories':
                if not isinstance(obj.get('fields'),list):raise ValueError('Ungültige Kategorievorlage.')
                fields=set()
                for f in obj['fields']+obj.get('archived',[]):
                    if not isinstance(f,dict) or not all(isinstance(f.get(k),str) for k in ['id','name','type']):raise ValueError('Ungültiges Vorlagenfeld.')
                    if f['id'] in fields:raise ValueError('Doppelte Feldkennung.')
                    fields.add(f['id'])
            else:
                if not isinstance(obj.get('html',''),str):raise ValueError('Ungültiger Beschreibungstext.')
                if group in ['entries','events'] and (not isinstance(obj.get('links'),list) or any(not isinstance(v,str) for v in obj['links'])):raise ValueError('Ungültige Verknüpfungsliste.')
                if group=='entries' and (not isinstance(obj.get('category'),str) or not isinstance(obj.get('values'),dict)):raise ValueError('Ungültige Welt-Feldwerte.')
                if group=='events' and (not all(isinstance(obj.get(k,''),str) for k in ['start','end','kind']) or obj.get('era') is not None and not isinstance(obj.get('era'),str)):raise ValueError('Ungültige Zeitangabe.')
    if not isinstance(p.get('calendar'),dict) or not isinstance(p.get('assets'),dict):raise ValueError('Kalender oder Ressourcen fehlen.')
    if not isinstance(p.get('covers'),dict) or any(not isinstance(v,str) for v in p['covers'].values()):raise ValueError('Ungültige Cover-Zuordnung.')
    for key,value in p['assets'].items():
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}',key) or key in ('.','..') or not isinstance(value,str):raise ValueError('Ungültige Projektressource.')
    return p

def save_project(project,path):
    validate(project);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp');os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
            data={**project,'assets':{}};hashes={}
            project_json=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
            if len(project_json)>MAX_JSON_BYTES:raise ValueError('Projektbeschreibung ist zu groß.')
            total=len(project_json);z.writestr('project.json',project_json)
            for key,value in project['assets'].items():
                raw=base64.b64decode(value,validate=True);total+=len(raw)+300
                if total>MAX_ARCHIVE_BYTES:raise ValueError('Projekt ist zu groß (maximal 2 GB entpackt).')
                z.writestr('assets/'+key,raw);hashes['assets/'+key]=hashlib.sha256(raw).hexdigest()
            hashes['project.json']=hashlib.sha256(project_json).hexdigest()
            z.writestr('integrity.json',json.dumps(hashes))
        with open(tmp,'r+b') as f:os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def load_project(path):
    try:
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            if len(names)!=len(set(names)):raise ValueError('Doppelte Archivdateien. Projekt nicht geöffnet.')
            if sum(info.file_size for info in z.infolist())>MAX_ARCHIVE_BYTES:raise ValueError('Projekt ist zu groß (maximal 2 GB entpackt).')
            if z.getinfo('project.json').file_size>MAX_JSON_BYTES:raise ValueError('Projektbeschreibung ist zu groß.')
            raw=z.read('project.json');p=json.loads(raw)
            checks=json.loads(z.read('integrity.json')) if 'integrity.json' in names else {}
            resources={}
            for name in names:
                if name.startswith('assets/') and not name.endswith('/'):
                    value=z.read(name)
                    if name in checks and hashlib.sha256(value).hexdigest()!=checks[name]:raise ValueError('Beschädigte Ressource: '+name)
                    resources[name[7:]]=base64.b64encode(value).decode()
            if checks.get('project.json') and hashlib.sha256(raw).hexdigest()!=checks['project.json']:raise ValueError('Die Projektbeschreibung ist beschädigt. Bitte eine Sicherung öffnen.')
            p['assets']=resources
    except (zipfile.BadZipFile,KeyError,json.JSONDecodeError,UnicodeDecodeError,RuntimeError) as error:raise ValueError('Projektdatei ist beschädigt oder unvollständig. Original behalten und eine Sicherung öffnen.') from error
    return validate(migrate(p))

def archive_version(path):
    with zipfile.ZipFile(path) as z:return json.loads(z.read('project.json')).get('version')

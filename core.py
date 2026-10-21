import json, uuid, zipfile, os, tempfile, base64, re, html
from pathlib import Path

def uid(): return str(uuid.uuid4())
def new_project(name='Meine Geschichte'):
    return dict(version=1,name=name,documents=[dict(id=uid(),name='Kapitel 1',html='')],categories=[],entries=[],events=[],assets={},calendar=dict(name='Weltzeit',year_zero=False,epoch=1,months=[dict(name='Erster Mond',days=30),dict(name='Zweiter Mond',days=30)],week=['Ersttag','Zweittag','Dritttag','Vierttag','Fünfttag'],format='{day}. {month} {year}',units={'year':'Jahr','month':'Monat','day':'Tag'},leaps=[]))

def save_project(p,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp'); os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            data={**p,'assets':{}}
            z.writestr('project.json',json.dumps(data,ensure_ascii=False))
            for key,value in p['assets'].items(): z.writestr('assets/'+key,base64.b64decode(value))
        # Windows FlushFileBuffers requires a writable handle.
        with open(tmp,'r+b') as f: os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def load_project(path):
    with zipfile.ZipFile(path) as z:
        p=json.loads(z.read('project.json'))
        if p.get('version')!=1: raise ValueError('Unbekannte Dateiversion')
        p['assets']={n[7:]:base64.b64encode(z.read(n)).decode() for n in z.namelist() if n.startswith('assets/') and not n.endswith('/')}
        return p

def objects(p): return p['entries']+p['events']+p['documents']
def resolve(p,id): return next((x for x in objects(p) if x['id']==id),None)
def embed(p,path):
    data=Path(path).read_bytes(); key=uid()+Path(path).suffix.lower(); p['assets'][key]=base64.b64encode(data).decode(); return key

def render(p,text):
    def sub(m):
        item=resolve(p,m.group(2)); return m.group(1)+html.escape(item['name'] if item else '[Gelöschter Eintrag]')+m.group(3)
    return re.sub(r'(<a[^>]*href="story:([^"\s]+)"[^>]*>).*?(</a>)',sub,text,flags=re.S)

def references(p,id):
    return [o['name'] for o in objects(p) if o['id']!=id and (id in o.get('links',[]) or id in json.dumps(o.get('values',{})) or ('story:'+id) in o.get('html',''))]

class Calendar:
    def __init__(self,c): self.c=c
    def index(self,y):
        if not self.c['year_zero'] and y==0: raise ValueError('Dieser Kalender hat kein Jahr null.')
        return y if self.c['year_zero'] or y<0 else y-1
    def month_lengths(self,y):
        lengths=[m['days'] for m in self.c['months']]
        for rule in self.c.get('leaps',[]):
            if (y-rule.get('offset',0))%rule['every']==0: lengths[rule['month']-1]+=rule.get('days',1)
        return lengths
    def ordinal(self,date):
        parts=[int(n.strip()) for n in date.split('/')]; y=parts[0]; yi=self.index(y); ei=self.index(self.c['epoch'])
        months=self.c['months']
        if not months:
            if len(parts)!=1: raise ValueError('Nur Jahreszahlen erlaubt.')
            return yi-ei
        if len(parts)!=3: raise ValueError('Datum: Jahr/Monat/Tag')
        _,m,d=parts; lengths=self.month_lengths(y)
        if not 1<=m<=len(lengths) or not 1<=d<=lengths[m-1]: raise ValueError('Ungültiges Datum')
        base=sum(x['days'] for x in months); total=(yi-ei)*base
        # Count periodic leap years algebraically, including negative years, without iterating through years.
        def count_before(index,rule):
            def multiples(lo,hi):
                k=rule['every']; off=rule.get('offset',0)
                return (hi-1-off)//k-(lo-1-off)//k
            if self.c['year_zero']: return multiples(0,index) if index>=0 else -multiples(index,0)
            return multiples(1,index+1) if index>=0 else -multiples(index,0)
        for rule in self.c.get('leaps',[]): total+=(count_before(yi,rule)-count_before(ei,rule))*rule.get('days',1)
        return total+sum(lengths[:m-1])+d-1
    def span(self,start,end=''):
        a=self.ordinal(start); b=self.ordinal(end) if end else a
        if b<a: raise ValueError('Ende liegt vor Anfang.')
        return a,b
    def display(self,date):
        parts=date.split('/')
        if len(parts)==1:return parts[0]
        y,m,d=map(int,parts); week=self.c.get('week',[]);weekday=week[self.ordinal(date)%len(week)] if week else ''
        return self.c['format'].format(year=y,month=self.c['months'][m-1]['name'],day=d,weekday=weekday)
    def validate(self):
        c=self.c; self.index(c['epoch'])
        if any(m['days']<1 or not m['name'] for m in c['months']):raise ValueError('Monate benötigen Namen und positive Länge.')
        for r in c.get('leaps',[]):
            if r['every']<1 or not 1<=r['month']<=len(c['months']) or r.get('days',1)<0:raise ValueError('Ungültige Schaltregel')
        c['format'].format(year=1,month='Mond',day=1,weekday='Ersttag')

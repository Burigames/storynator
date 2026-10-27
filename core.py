import json, uuid, zipfile, os, tempfile, base64, re, html
from pathlib import Path

def uid(): return str(uuid.uuid4())
def new_project(name='Meine Geschichte'):
    return dict(version=2,project_id=uid(),covers={'project':'','book':''},name=name,documents=[dict(id=uid(),name='Kapitel 1',html='')],categories=[],entries=[],events=[],assets={},calendar=dict(name='Weltzeit',year_zero=False,epoch=1,months=[dict(name='Erster Mond',days=30),dict(name='Zweiter Mond',days=30)],week=['Ersttag','Zweittag','Dritttag','Vierttag','Fünfttag'],format='{day}. {month} {year}',units={'year':'Jahr','month':'Monat','day':'Tag'},leaps=[]))

from storage import save_project,load_project

def objects(p): return p['entries']+p['events']+p['documents']
def resolve(p,id): return next((x for x in objects(p) if x['id']==id),None)
def embed(p,path):
    data=Path(path).read_bytes(); key=uid()+Path(path).suffix.lower(); p['assets'][key]=base64.b64encode(data).decode(); return key

def render(p,text,lookup=None):
    if 'story:' not in text:return text
    if lookup is None:lookup={o['id']:o for o in objects(p)}
    def sub(match):
        item=lookup.get(match.group(2));name=item['name'] if item else '[Gelöschter Eintrag]';body=match.group(3)
        # Qt writes font, size and emphasis into spans inside the anchor.
        # Preserve those spans on load and when changing the target's display name.
        if html.unescape(re.sub(r'<[^>]*>','',body))==name:return match.group(0)
        pieces=re.split(r'(<[^>]*>)',body);written=False
        for i,piece in enumerate(pieces):
            if piece.startswith('<'):continue
            if html.unescape(piece).strip():pieces[i]=html.escape(name) if not written else '';written=True
        if not written:pieces=[html.escape(name)]
        return match.group(1)+''.join(pieces)+match.group(4)
    return re.sub(r'(<a[^>]*href="story:([^"\s]+)"[^>]*>)(.*?)(</a>)',sub,text,flags=re.S)

def references(p,id):
    return [o['name'] for o in objects(p) if o['id']!=id and (o.get('era')==id or id in o.get('links',[]) or id in json.dumps(o.get('values',{})) or ('story:'+id) in o.get('html',''))]

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

    def date_from_ordinal(self,value):
        """Inverse calendar mapping, including negative years and periodic leap days."""
        day=int(value);epoch=self.index(self.c['epoch'])
        def year(index):return index if self.c['year_zero'] or index<0 else index+1
        if not self.c['months']:return str(year(epoch+day))
        base=sum(m['days'] for m in self.c['months']);estimate=epoch+day//base
        lo=estimate-2;hi=estimate+2
        def start(index):return self.ordinal(f'{year(index)}/1/1')
        step=4
        while start(lo)>day:hi=lo;lo-=step;step*=2
        step=4
        while start(hi)<=day:lo=hi;hi+=step;step*=2
        while hi-lo>1:
            mid=(lo+hi)//2
            if start(mid)<=day:lo=mid
            else:hi=mid
        y=year(lo);remaining=day-start(lo)
        for month,length in enumerate(self.month_lengths(y),1):
            if remaining<length:return f'{y}/{month}/{remaining+1}'
            remaining-=length
        raise ValueError('Datum liegt außerhalb des Kalenders.')

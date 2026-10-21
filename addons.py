"""Declarative category presets. No code, entry payloads or project content accepted."""
import copy,json,re,uuid,math
from pathlib import Path
from core import uid
FORMAT='storynator.category-preset'
FIELD_TYPES={'Text','Richtext','Zahl','Checkbox','Dropdown','Mehrfachauswahl','Slider','Bild','Galerie','Datum','Zeitspanne','Verknüpfung'}

def field(name,type='Text',**settings):return dict(name=name,type=type,**settings)
BUILTIN={
 'format':FORMAT,'version':1,'id':'storynator.worldbuilding.v1','name':'Weltenbau · Grundausstattung','description':'Kategorievorlagen für Figuren, Gesellschaften und Geschichtenwelten. Enthält keine Einträge.',
 'categories':[
  dict(key='characters',name='Charaktere',fields=[field('Alias'),field('Porträt','Bild'),field('Rasse','Dropdown',source_category='species'),field('Herkunftsland','Dropdown',source_category='countries'),field('Fraktion','Dropdown',source_category='factions'),field('Alter','Zahl'),field('Persönlichkeit','Richtext'),field('Motivation','Richtext')]),
  dict(key='countries',name='Länder',fields=[field('Flagge','Bild'),field('Hauptstadt','Dropdown',source_category='places'),field('Regierungsform','Dropdown',options=['Monarchie','Republik','Theokratie','Stammesbund','Andere']),field('Bevölkerung','Zahl'),field('Geschichte','Richtext')]),
  dict(key='factions',name='Fraktionen',fields=[field('Symbol','Bild'),field('Ziel'),field('Gesinnung','Dropdown',options=['Verbündet','Neutral','Feindlich','Unbekannt']),field('Einfluss','Slider',min=0,max=100,step=1)]),
  dict(key='species',name='Rassen',fields=[field('Erscheinungsbild','Richtext'),field('Lebensspanne','Zahl'),field('Besonderheiten','Richtext')]),
  dict(key='peoples',name='Völker',fields=[field('Ursprungsland','Dropdown',source_category='countries'),field('Kultur','Dropdown',source_category='cultures'),field('Traditionen','Richtext')]),
  dict(key='items',name='Besondere Gegenstände',fields=[field('Abbildung','Bild'),field('Besitzer','Dropdown',source_category='characters'),field('Seltenheit','Dropdown',options=['Gewöhnlich','Selten','Einzigartig','Legendär']),field('Eigenschaften','Richtext')]),
  dict(key='groups',name='Gruppierungen',fields=[field('Sitz','Dropdown',source_category='places'),field('Zweck'),field('Mitglieder','Mehrfachauswahl',source_category='characters')]),
  dict(key='places',name='Orte',fields=[field('Karte','Bild'),field('Land','Dropdown',source_category='countries'),field('Ortstyp','Dropdown',options=['Stadt','Dorf','Festung','Wildnis','Ruine','Anderer Ort']),field('Atmosphäre','Richtext')]),
  dict(key='religions',name='Religionen',fields=[field('Symbol','Bild'),field('Lehren','Richtext'),field('Rituale','Richtext')]),
  dict(key='alliances',name='Bündnisse',fields=[field('Mitgliedsländer','Mehrfachauswahl',source_category='countries'),field('Ziel'),field('Bedingungen','Richtext')]),
  dict(key='cultures',name='Kulturen',fields=[field('Werte','Richtext'),field('Bräuche','Richtext'),field('Kunst','Richtext')]),
  dict(key='languages',name='Sprachen',fields=[field('Schriftzeichen','Bild'),field('Sprachfamilie'),field('Beispiele','Richtext')]),
  dict(key='magic',name='Magiesysteme',fields=[field('Quelle'),field('Regeln','Richtext'),field('Preis und Grenzen','Richtext')]),
  dict(key='creatures',name='Kreaturen',fields=[field('Abbildung','Bild'),field('Lebensraum','Dropdown',source_category='places'),field('Gefährlichkeit','Slider',min=0,max=10,step=1),field('Verhalten','Richtext')])
 ]}

def validate(spec):
    if not isinstance(spec,dict):raise ValueError('Das Preset muss ein Objekt sein.')
    allowed={'format','version','id','name','description','categories'}
    if set(spec)-allowed:raise ValueError('Presets dürfen ausschließlich Kategorievorlagen enthalten; Einträge und Code sind nicht erlaubt.')
    if spec.get('format')!=FORMAT or spec.get('version')!=1:raise ValueError('Unbekanntes Preset-Format.')
    for key in ['id','name']:
        if not isinstance(spec.get(key),str) or not 0<len(spec[key].strip())<=200:raise ValueError('Preset benötigt ID und Namen.')
    if not re.fullmatch(r'[A-Za-z0-9._-]+',spec['id']):raise ValueError('Ungültige Preset-ID.')
    if 'description' in spec and not isinstance(spec['description'],str):raise ValueError('Ungültige Beschreibung.')
    cats=spec.get('categories')
    if not isinstance(cats,list) or not 1<=len(cats)<=200:raise ValueError('Preset benötigt 1 bis 200 Kategorien.')
    keys=set()
    for cat in cats:
        if not isinstance(cat,dict) or set(cat)-{'key','name','fields'}:raise ValueError('Kategorie darf nur Namen und Felder enthalten, keine Einträge.')
        if not isinstance(cat.get('key'),str) or not cat['key'] or cat['key'] in keys:raise ValueError('Kategorie-Schlüssel fehlen oder sind doppelt.')
        keys.add(cat['key'])
        if not isinstance(cat.get('name'),str) or not cat['name'].strip():raise ValueError('Kategoriename fehlt.')
        fields=cat.get('fields',[])
        if not isinstance(fields,list) or len(fields)>100:raise ValueError('Zu viele oder ungültige Felder.')
        for f in fields:
            if not isinstance(f,dict) or set(f)-{'name','type','options','min','max','step','source_category'}:raise ValueError('Ungültiges Feld. Inhalte und Code sind nicht erlaubt.')
            if not isinstance(f.get('name'),str) or not f['name'].strip() or f.get('type') not in FIELD_TYPES:raise ValueError('Unbekannter Feldtyp oder fehlender Name.')
            if 'options' in f and (not isinstance(f['options'],list) or any(not isinstance(o,str) for o in f['options'])):raise ValueError('Auswahloptionen müssen Texte sein.')
            if f['type']=='Slider':
                try:valid=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in [f.get('min',0),f.get('max',100),f.get('step',1)]) and -1e9<=f.get('min',0)<=f.get('max',100)<=1e9 and f.get('step',1)>0
                except TypeError:valid=False
                if not valid:raise ValueError('Ungültiger Sliderbereich.')
    for cat in cats:
        for f in cat.get('fields',[]):
            if f.get('source_category') and (f['source_category'] not in keys or f['type'] not in ['Dropdown','Mehrfachauswahl','Verknüpfung']):raise ValueError('Verknüpfte Quellkategorie fehlt im Preset.')
    return copy.deepcopy(spec)

def load(path):
    path=Path(path)
    if path.stat().st_size>2*1024*1024:raise ValueError('Preset ist zu groß (maximal 2 MB).')
    return validate(json.loads(path.read_text(encoding='utf-8')))

def library(settings,project=None):
    try:items=json.loads(settings.value('addons/library','[]'));items=[validate(s) for s in items]
    except (ValueError,TypeError):items=[]
    hidden=set(settings.value('addons/hidden',[],type=list))
    merged={s['id']:s for s in [BUILTIN]+items if s['id'] not in hidden}
    for state in (project or {}).get('addons',[]):merged.setdefault(state['id'],state['spec'])
    return list(merged.values())

def import_preset(settings,spec):
    spec=validate(spec);items=library(settings)
    old=next((s for s in items if s['id']==spec['id']),None)
    if old and old!=spec:raise ValueError('Ein anderes Preset mit dieser ID ist bereits vorhanden.')
    items=[s for s in items if s['id']!=spec['id'] and s['id']!=BUILTIN['id']]+[spec];settings.setValue('addons/library',json.dumps(items,ensure_ascii=False));hidden=settings.value('addons/hidden',[],type=list);settings.setValue('addons/hidden',[i for i in hidden if i!=spec['id']]);settings.sync()

def state_for(project,id):return next((s for s in project.get('addons',[]) if s['id']==id),None)
def active_category(project,cat):return not cat.get('addon_inactive',False)
def visible_categories(project):
    used={e['category'] for e in project['entries']}
    return [c for c in project['categories'] if active_category(project,c) or c['id'] in used]

def enable(project,spec):
    spec=validate(spec);state=state_for(project,spec['id'])
    if state:
        state['enabled']=True
        for cat in project['categories']:
            if cat.get('source_addon')==spec['id']:cat['addon_inactive']=False
        return state
    mapping={c['key']:uid() for c in spec['categories']};created=[]
    for c in spec['categories']:
        cat=dict(id=mapping[c['key']],name=c['name'],fields=[],source_addon=spec['id'],addon_inactive=False)
        for f in c.get('fields',[]):
            value=copy.deepcopy(f);value['id']=uid()
            if value.get('source_category'):value['source_category']=mapping[value['source_category']]
            cat['fields'].append(value)
        created.append(cat)
    project['categories'].extend(created);state=dict(id=spec['id'],enabled=True,spec=spec,category_ids=list(mapping.values()));project.setdefault('addons',[]).append(state);return state

def disable(project,id):
    state=state_for(project,id)
    if not state:return
    state['enabled']=False
    for cat in project['categories']:
        if cat.get('source_addon')==id:cat['addon_inactive']=True

def remove(project,settings,id):
    owned={c['id'] for c in project['categories'] if c.get('source_addon')==id};lookup={c['id']:c for c in project['categories']};keep={e['category'] for e in project['entries']} & owned
    for cat in project['categories']:
        if cat['id'] not in owned:keep.update(f['source_category'] for f in cat['fields'] if f.get('source_category') in owned)
    todo=list(keep)
    while todo:
        for f in lookup[todo.pop()]['fields']:
            source=f.get('source_category')
            if source in owned and source not in keep:keep.add(source);todo.append(source)
    project['categories']=[c for c in project['categories'] if c['id'] not in owned or c['id'] in keep];project['addons']=[s for s in project.get('addons',[]) if s['id']!=id]
    for cat in project['categories']:
        if cat['id'] in keep:cat.pop('source_addon',None);cat.pop('addon_inactive',None)
    try:items=json.loads(settings.value('addons/library','[]'))
    except (ValueError,TypeError):items=[]
    settings.setValue('addons/library',json.dumps([s for s in items if s['id']!=id],ensure_ascii=False));settings.setValue('addons/hidden',list(set(settings.value('addons/hidden',[],type=list)+[id])));settings.sync()

def export(project,ids,name):
    selected=set(ids);lookup={c['id']:c for c in project['categories']}
    if not selected:raise ValueError('Mindestens eine Kategorie auswählen.')
    todo=list(selected)
    while todo:
        cat=lookup.get(todo.pop())
        if not cat:raise ValueError('Kategorie nicht gefunden.')
        for f in cat['fields']:
            source=f.get('source_category')
            if source and source not in selected:
                if source not in lookup:raise ValueError('Quellkategorie fehlt. Bitte zuerst das Feld reparieren.')
                selected.add(source);todo.append(source)
    cats=[c for c in project['categories'] if c['id'] in selected];keys={c['id']:f'category_{i+1}' for i,c in enumerate(cats)};result=[]
    for c in cats:
        fields=[]
        for f in c['fields']:
            value={k:copy.deepcopy(v) for k,v in f.items() if k in {'name','type','options','min','max','step','source_category'}}
            if value.get('source_category'):value['source_category']=keys[value['source_category']]
            fields.append(value)
        result.append(dict(key=keys[c['id']],name=c['name'],fields=fields))
    return validate(dict(format=FORMAT,version=1,id=str(uuid.uuid4()),name=name.strip() or 'Mein Kategorien-Preset',description='',categories=result))

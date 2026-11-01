"""Offline project starters, using the existing declarative exchange format."""
import copy,uuid
from core import new_project,uid
import addons,community
from i18n import tr
PRESETS=[
 ('novel','Roman','Kapitelstruktur für einen Roman.', [('part','Teil I',None),('chapter','Kapitel 1',0),('scene','Szene 1',1),('part','Teil II',None),('chapter','Kapitel 2',3),('part','Teil III',None)],[]),
 ('fantasy','Fantasy-Welt','Romanstruktur und Vorlagen für eine fantastische Welt.', [('part','Teil I',None),('chapter','Kapitel 1',0),('scene','Szene 1',1),('part','Teil II',None),('part','Teil III',None)],['characters','countries','places','species','magic','religions','factions']),
 ('crime','Kriminalroman','Platz für Verbrechen, Ermittlungen und Auflösung.', [('chapter','Das Verbrechen',None),('chapter','Die Ermittlungen',None),('chapter','Die Wendung',None),('chapter','Die Auflösung',None)],['characters','places','items','groups']),
 ('scifi','Science-Fiction','Geschichten zwischen Kulturen und fremden Welten.', [('chapter','Aufbruch',None),('chapter','Erster Kontakt',None),('chapter','Die Entscheidung',None)],['characters','places','factions','species','cultures','items']),
 ('short','Kurzgeschichte','Eine kompakte Struktur für eine kurze Geschichte.', [('scene','Anfang',None),('scene','Konflikt',None),('scene','Schluss',None)],[])]
def builtin_starters():
    result=[]
    for key,name,description,rows,categories in PRESETS:
        p=new_project(tr(name));p['documents']=[];ids=[str(uuid.uuid5(uuid.NAMESPACE_URL,'storynator.starter.'+key+':'+str(i))) for i in range(len(rows))]
        for i,(kind,title,parent) in enumerate(rows):p['documents'].append(dict(id=ids[i],name=tr(title),kind=kind,parent=ids[parent] if parent is not None else None,html=''))
        if categories:
            # Include source-category dependencies. This never creates entries.
            source=new_project();addons.enable(source,addons.BUILTIN);wanted={c['id'] for template,c in zip(addons.BUILTIN['categories'],source['categories']) if template['key'] in categories};preset=addons.export(source,wanted,tr(name));addons.enable(p,preset)
            mapping={}
            for index,cat in enumerate(p['categories']):
                mapping[cat['id']]=str(uuid.uuid5(uuid.NAMESPACE_URL,key+':cat:'+str(index)))
                for fi,f in enumerate(cat['fields']):mapping[f['id']]=str(uuid.uuid5(uuid.NAMESPACE_URL,key+':field:'+str(index)+':'+str(fi)))
            p=community.remap(p,mapping)
        for cat in p['categories']:
            cat['name']=tr(cat['name'])
            for field in cat['fields']:
                field['name']=tr(field['name'])
                if 'options' in field:field['options']=[tr(option) for option in field['options']]
        calendar=p['calendar'];calendar['name']=tr(calendar['name'])
        for month in calendar['months']:month['name']=tr(month['name'])
        calendar['week']=[tr(day) for day in calendar['week']];calendar['units']={k:tr(v) for k,v in calendar['units'].items()}
        meta=community.metadata(tr(name),'Storynator','CC0-1.0',tr(description),tags=['Starter']);meta['id']='storynator.starter.'+key
        result.append(community.create(p,'starter',meta))
    return result

def instantiate(spec,name):
    spec=community.validate(spec)
    if spec['kind'] not in ['starter','challenge']:raise ValueError('Bitte einen Projekt-Starter oder eine Challenge auswählen.')
    if not name.strip():raise ValueError('Projektname fehlt.')
    p=new_project(name.strip());p['documents']=[];p,_=community.plan_import(p,spec);p['name']=name.strip()
    mapping=p['community_imports'][-1]['mapping'];covers=spec['payload']['project'].get('covers',{})
    p['covers']={k:mapping.get(v,'') for k,v in covers.items()}
    if not p['documents']:p['documents']=[dict(id=uid(),name=tr('Kapitel 1'),html='')]
    return p

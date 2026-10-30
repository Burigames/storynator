"""Data-only world queries, template constraints and typed relationships."""
import copy,json,re
from core import uid,resolve,objects,Calendar
from authoring import now,plain

def filtered_entries(p,field):
    entries=[o for o in p['entries'] if o['category']==field.get('source_category')];rule=field.get('source_filter') or {}
    if not rule:return entries
    lookup={o['id']:o['name'] for o in objects(p)}
    def accept(o):
        value=o['name'] if rule.get('field')=='name' else o.get('values',{}).get(rule.get('field'),'');needle=str(rule.get('value','')).casefold()
        if rule.get('op')=='eq' and isinstance(value,bool):return needle in (['true','yes','ja','1'] if value else ['false','no','nein','0'])
        if rule.get('op')=='eq' and isinstance(value,(int,float)):
            try:return float(needle.replace(',','.'))==value
            except ValueError:return False
        values=value if isinstance(value,list) else [value]
        values=[str(lookup.get(v,v) if isinstance(v,str) else v).casefold() for v in values]
        return any(needle in v if rule.get('op')=='contains' else needle==v for v in values)
    return [o for o in entries if accept(o)]

def missing_required(p,entry):
    category=next((c for c in p['categories'] if c['id']==entry['category']),{})
    missing=[]
    for field in category.get('fields',[]):
        if not field.get('required'):continue
        value=entry.get('values',{}).get(field['id'])
        if value is None or value==[] or isinstance(value,str) and not (plain(value) if field['type']=='Richtext' else value).strip():missing.append(field['name'])
    return missing

def duplicate_entry(p,entry,name,copy_relationships=False):
    item=copy.deepcopy(entry);item.update(id=uid(),name=name);p['entries'].append(item)
    if copy_relationships:
        for relation in list(p.get('relationships',[])):
            if relation['source']==entry['id']:
                value=copy.deepcopy(relation);value.update(id=uid(),source=item['id']);p['relationships'].append(value)
    return item

def transfer_entry(p,entry,target_id,mapping):
    source=next(c for c in p['categories'] if c['id']==entry['category']);target=next(c for c in p['categories'] if c['id']==target_id)
    if source['id']==target_id:raise ValueError('Bitte eine andere Zielkategorie wählen.')
    src={f['id']:f for f in source['fields']};dst={f['id']:f for f in target['fields']};used=set();values={}
    for before,after in mapping.items():
        if before not in src or after not in dst or src[before]['type']!=dst[after]['type']:raise ValueError('Feldzuordnung benötigt passende Feldtypen.')
        if after in used:raise ValueError('Ein Zielfeld darf nur einmal zugeordnet werden.')
        used.add(after)
        if before in entry['values']:values[after]=copy.deepcopy(entry['values'][before])
    entry.setdefault('field_archive',[]).append(dict(time=now(),category=source['id'],name=source['name'],fields=copy.deepcopy(source['fields']+source.get('archived',[])),values=copy.deepcopy(entry['values'])))
    entry.update(category=target_id,values=values)

def add_relation(p,source,target,type_id,description='',start='',end='',id=None):
    if not resolve(p,source) or not resolve(p,target):raise ValueError('Beide Beziehungsziele müssen vorhanden sein.')
    if not any(t['id']==type_id for t in p.get('relationship_types',[])):raise ValueError('Beziehungstyp fehlt.')
    if end and not start:raise ValueError('Ein Ende benötigt einen Anfang.')
    if start:Calendar(p['calendar']).span(start,end)
    relation=dict(id=id or uid(),source=source,target=target,type=type_id,description=description,start=start,end=end)
    old=next((r for r in p.get('relationships',[]) if r['id']==id),None)
    if old:old.update(relation)
    else:p.setdefault('relationships',[]).append(relation)
    return relation

def relations_for(p,id,date=''):
    result=[];cal=Calendar(p['calendar'])
    for relation in p.get('relationships',[]):
        if id not in [relation['source'],relation['target']]:continue
        if date and relation.get('start'):
            current=cal.ordinal(date);start=cal.ordinal(relation['start']);end=cal.ordinal(relation['end']) if relation.get('end') else float('inf')
            if not start<=current<=end:continue
        incoming=relation['target']==id;type=next((t for t in p.get('relationship_types',[]) if t['id']==relation['type']),{})
        name=type.get('inverse') if incoming and type.get('directed',True) else type.get('name');target=relation['source'] if incoming else relation['target'];result.append((relation,name or type.get('name','[Fehlender Typ]'),target,incoming))
    return result

def backlinks(p,id):
    found=[]
    for o in objects(p):
        if o['id']==id:continue
        referenced=id in o.get('links',[]) or o.get('era')==id or id in re.findall(r'''story:([^\s"'<>]+)''',o.get('html',''))
        for value in o.get('values',{}).values():
            if value==id or isinstance(value,list) and id in value or isinstance(value,str) and id in re.findall(r'''story:([^\s"'<>]+)''',value):referenced=True
        if referenced:found.append(o)
    return found

def query_entries(p,filters,recent=None):
    query=filters.get('query','').casefold().split();category=filters.get('category');favorite=set(p.get('favorites',[]));out=[];lookup={o['id']:o['name'] for o in objects(p)}
    for entry in p['entries']:
        if category and entry['category']!=category:continue
        if filters.get('favorites') and entry['id'] not in favorite:continue
        strings=[entry['name'],plain(entry.get('html',''))]
        for v in entry.get('values',{}).values():strings.extend(str(lookup.get(x,x) if isinstance(x,str) else x) for x in (v if isinstance(v,list) else [v]))
        if any(term not in ' '.join(strings).casefold() for term in query):continue
        if filters.get('field'):
            value=entry.get('values',{}).get(filters['field'],'');values=value if isinstance(value,list) else [value]
            if not any(str(filters.get('value','')).casefold() in str(lookup.get(v,v) if isinstance(v,str) else v).casefold() for v in values):continue
        out.append(entry)
    if filters.get('sort')=='recent':
        order={id:i for i,id in enumerate(recent or [])};out.sort(key=lambda e:(order.get(e['id'],10**9),e['name'].casefold()))
    else:out.sort(key=lambda e:e['name'].casefold())
    return out

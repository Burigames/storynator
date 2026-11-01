"""Stable identities and lossless updates for declarative category exchange packages."""
import copy,re,uuid
from core import new_project,uid
import addons

def category_payload(project,ids,title):
    preset=addons.export(project,ids,title);chosen=set(ids);lookup={c['id']:c for c in project['categories']};todo=list(chosen)
    while todo:
        for f in lookup[todo.pop()]['fields']:
            source=f.get('source_category')
            if source and source not in chosen:chosen.add(source);todo.append(source)
    categories=[c for c in project['categories'] if c['id'] in chosen]
    identities={template['key']:dict(id=category['id'],fields=[f['id'] for f in category['fields']]) for template,category in zip(preset['categories'],categories)}
    return dict(preset=preset,identities=identities)

def validate_identities(preset,identities):
    if not isinstance(identities,dict) or set(identities)!={c['key'] for c in preset['categories']}:raise ValueError('Kategoriekennungen fehlen im Paket.')
    seen=set()
    for cat in preset['categories']:
        item=identities[cat['key']]
        if not isinstance(item,dict) or set(item)!={'id','fields'} or not isinstance(item['fields'],list) or len(item['fields'])!=len(cat['fields']):raise ValueError('Feldkennungen fehlen im Paket.')
        for id in [item['id']]+item['fields']:
            if not isinstance(id,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}',id) or id in seen:raise ValueError('Ungültige oder doppelte Vorlagenkennung.')
            seen.add(id)

def materialize(spec):
    from community import remap
    preset=spec['payload']['preset'];p=new_project(spec['metadata']['title']);p['documents']=[];addons.enable(p,preset);mapping={};identities=spec['payload'].get('identities')
    for template,cat in zip(preset['categories'],p['categories']):
        identity=identities[template['key']] if identities else dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,spec['metadata']['id']+':'+template['key'])),fields=[str(uuid.uuid5(uuid.NAMESPACE_URL,spec['metadata']['id']+':'+template['key']+':'+str(i)+':'+f['name'])) for i,f in enumerate(cat['fields'])])
        mapping[cat['id']]=identity['id']
        for field,id in zip(cat['fields'],identity['fields']):mapping[field['id']]=id
        cat.pop('source_addon',None);cat.pop('addon_inactive',None)
    p.pop('addons',None);return remap(p,mapping)

def import_categories(project,spec):
    from community import remap,digest
    p=materialize(spec);q=copy.deepcopy(project);mapping={};warnings=[]
    for cat in p['categories']:
        mapping[cat['id']]=uid()
        for f in cat['fields']:mapping[f['id']]=uid()
    incoming=remap(p,mapping);names={c['name'] for c in q['categories']}
    for cat in incoming['categories']:
        if cat['name'] in names:warnings.append(cat['name']+' → '+cat['name']+' (Import)');cat['name']+=' (Import)'
        q['categories'].append(cat)
    q.setdefault('community_imports',[]).append(dict(package=spec['metadata']['id'],kind='categories',identity_version=spec['version'],release=spec['metadata']['release'],hash=digest(spec),mapping=mapping,baseline={c['id']:digest(c) for c in incoming['categories']}))
    return q,warnings

def merge_category(local,incoming):
    """Retain removed definitions so existing values remain restorable."""
    result=copy.deepcopy(incoming);active={f['id'] for f in incoming['fields']};archive={f['id']:copy.deepcopy(f) for f in (local or {}).get('archived',[])}
    for f in (local or {}).get('fields',[]):
        if f['id'] not in active:archive[f['id']]=copy.deepcopy(f)
    result['archived']=[f for id,f in archive.items() if id not in active]
    return result

def update_categories(project,spec,choices=None):
    from community import remap,digest
    resolved=choices is not None;choices=choices or {};receipt=next((r for r in reversed(project.get('community_imports',[])) if r['package']==spec['metadata']['id'] and r.get('kind')=='categories' and 'mapping' in r),None)
    if receipt is None:raise ValueError('Für diese Vorlage fehlt die frühere Importzuordnung. Bitte als neue Kopie importieren.')
    if receipt['identity_version']<2 or spec['version']<2 or receipt['identity_version']!=spec['version']:raise ValueError('Diese Vorlagenversion verwendet andere Feldkennungen. Bitte als neue Kopie importieren.')
    q=copy.deepcopy(project);p=materialize(spec);mapping=copy.deepcopy(receipt['mapping']);lookup={c['id']:c for c in q['categories']};new_sources={c['id'] for c in p['categories']};conflicts=[];baseline=copy.deepcopy(receipt['baseline'])
    # A type change gets a new target field; the old definition and values are archived.
    for cat in p['categories']:
        mapping.setdefault(cat['id'],uid());local=lookup.get(mapping[cat['id']]);oldfields={f['id']:f for f in (local or {}).get('fields',[])}
        for field in cat['fields']:
            target=mapping.setdefault(field['id'],uid())
            if target in oldfields and oldfields[target]['type']!=field['type']:mapping[field['id']]=uid()
    incoming=remap(p,mapping)
    for cat in incoming['categories']:
        id=cat['id'];local=lookup.get(id);before=receipt['baseline'].get(id)
        # Archives are intentionally excluded from incoming comparisons; never silently discard them.
        local_active={k:v for k,v in (local or {}).items() if k!='archived'}
        before_local=digest(local) if local else None
        changed=local is not None and before_local!=before and digest(local_active)!=digest(cat)
        removed=local is None and before is not None
        if changed or removed:
            conflicts.append(dict(id=id,group='categories',name=cat['name'],local=local,incoming=cat))
            if choices.get(id,'local')!='package':continue
        merged=merge_category(local,cat)
        if local is None:q['categories'].append(merged)
        else:q['categories']=[merged if c['id']==id else c for c in q['categories']]
        baseline[id]=digest(merged)
    q.setdefault('community_imports',[]).append(dict(package=spec['metadata']['id'],kind='categories',identity_version=spec['version'],release=spec['metadata']['release'],hash=digest(spec),mapping=mapping,baseline=baseline))
    if resolved or not conflicts:check_dependencies(q)
    return q,conflicts


def check_dependencies(project):
    categories={c['id']:c for c in project['categories']}
    for category in categories.values():
        for field in category['fields']:
            source=field.get('source_category')
            if not source:continue
            if source not in categories:raise ValueError('Eine Quellkategorie fehlt. Abhängige Update-Konflikte gemeinsam entscheiden.')
            target=field.get('source_filter',{}).get('field')
            if target and target!='name' and target not in {f['id'] for f in categories[source]['fields']+categories[source].get('archived',[])}:raise ValueError('Ein Auswahlfilter benötigt ein nicht übernommenes Feld. Abhängige Update-Konflikte gemeinsam entscheiden.')

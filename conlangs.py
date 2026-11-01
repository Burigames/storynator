"""Project-local constructed-language lexicons and explicit exact-word spelling checks."""
import copy,csv,io,json,re,unicodedata
from pathlib import Path
from core import uid
FORMAT='storynator.lexicon'
FIELDS=['word','translation','pronunciation','part_of_speech','definition','examples','forms']
def new_language(name):return dict(id=uid(),name=name.strip(),alphabet='',notes='',case_sensitive=False,words=[])
def validate(language):
    if not isinstance(language,dict) or set(language)-{'id','name','alphabet','notes','case_sensitive','words'}:raise ValueError('Ungültiges Sprachwörterbuch.')
    if any(not isinstance(language.get(k),str) for k in ['id','name','alphabet','notes']) or not language['id'] or not language['name'].strip() or type(language.get('case_sensitive')) is not bool or not isinstance(language.get('words'),list) or len(language['words'])>100000:raise ValueError('Ungültiges Sprachwörterbuch.')
    ids=set()
    for word in language['words']:
        if not isinstance(word,dict) or set(word)-set(FIELDS+['id']) or not isinstance(word.get('id'),str) or not word['id'] or word['id'] in ids or any(not isinstance(word.get(k,''),str) for k in FIELDS if k!='forms') or not word.get('word','').strip() or not isinstance(word.get('forms',[]),list) or any(not isinstance(x,str) for x in word.get('forms',[])):raise ValueError('Ungültiger Wörterbucheintrag.')
        ids.add(word['id'])
    return copy.deepcopy(language)
def validate_project(p):
    items=p.get('lexicons',[])
    if not isinstance(items,list):raise ValueError('Ungültige Wörterbuchliste.')
    seen=set()
    for language in items:
        validate(language)
        if language['id'] in seen:raise ValueError('Doppelte Sprachkennung.')
        seen.add(language['id'])
def normal(word,sensitive=False):
    value=unicodedata.normalize('NFC',word);return value if sensitive else value.casefold()
def unknown_words(text,language,ignored=(),cancel=None):
    language=validate(language);case=language['case_sensitive'];known={normal(v,case) for word in language['words'] for v in [word['word']]+word.get('forms',[])};ignored={normal(v,case) for v in ignored};seen=set();result=[]
    def letter(ch):return unicodedata.category(ch)[0] in ['L','M','N']
    index=0
    while index<len(text):
        if cancel and cancel.is_set():break
        if not letter(text[index]):index+=1;continue
        start=index;index+=1
        while index<len(text):
            if letter(text[index]):index+=1
            elif text[index] in "-'’" and index+1<len(text) and letter(text[index+1]):index+=1
            else:break
        word=text[start:index]
        if not any(ch.isalpha() for ch in word):continue
        key=normal(word,case)
        if key not in known and key not in ignored and key not in seen:result.append((word,start,index))
        seen.add(key)
    return result

def save(language,path):
    from community import LIMIT
    from tempfile import NamedTemporaryFile
    import os
    data=json.dumps(dict(format=FORMAT,version=1,language=validate(language)),ensure_ascii=False,indent=2).encode();path=Path(path)
    if len(data)>16*1024*1024:raise ValueError('Wörterbuch ist zu groß (maximal 16 MB).')
    with NamedTemporaryFile(dir=path.parent,delete=False) as stream:
        tmp=Path(stream.name);stream.write(data);stream.flush();os.fsync(stream.fileno())
    try:os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)
def load(path):
    if Path(path).stat().st_size>16*1024*1024:raise ValueError('Wörterbuch ist zu groß (maximal 16 MB).')
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or set(data)!={'format','version','language'} or data['format']!=FORMAT or data['version']!=1:raise ValueError('Unbekanntes Wörterbuchformat.')
    return validate(data['language'])
def import_language(p,language):
    language=validate(language);language['id']=uid()
    for word in language['words']:word['id']=uid()
    p.setdefault('lexicons',[]).append(language);return language

def export_csv(language,path):
    language=validate(language)
    with open(path,'w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader()
        for item in language['words']:writer.writerow({k:'|'.join(item.get(k,[])) if k=='forms' else item.get(k,'') for k in FIELDS})
def read_csv(path):
    if Path(path).stat().st_size>16*1024*1024:raise ValueError('CSV ist zu groß.')
    with open(path,encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or 'word' not in reader.fieldnames or set(reader.fieldnames)-set(FIELDS):raise ValueError('CSV benötigt die Spalte word; weitere Spalten: translation, pronunciation, part_of_speech, definition, examples, forms.')
        result=[]
        for row in reader:
            if None in row:raise ValueError('Ungültige CSV-Zeile.')
            if not (row.get('word') or '').strip():continue
            result.append(dict(id=uid(),**{k:([x.strip() for x in (row.get(k) or '').split('|') if x.strip()] if k=='forms' else row.get(k,'') or '') for k in FIELDS}))
            if len(result)>100000:raise ValueError('Zu viele Wörterbucheinträge.')
    test=new_language('CSV');test['words']=result;validate(test);return result
def merge_words(language,words):
    draft=validate(language);known={normal(w['word'],draft['case_sensitive']) for w in draft['words']};added=0
    for word in words:
        key=normal(word['word'],draft['case_sensitive'])
        if key not in known:copyword=copy.deepcopy(word);copyword['id']=uid();draft['words'].append(copyword);known.add(key);added+=1
    validate(draft);language['words']=draft['words'];return added

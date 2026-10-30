"""Public HTML and feedback exchange with explicit version matching."""
import copy,html,json,re
from html.parser import HTMLParser
from pathlib import Path
from PySide6.QtGui import QTextDocument,QTextCursor
from core import uid
from community import digest,validate
class SafeHTML(HTMLParser):
    allowed={'p','br','div','span','b','strong','i','em','u','h1','h2','h3','h4','ul','ol','li','table','tr','td','th','blockquote','img','a'}
    def __init__(self,assets,targets=None):super().__init__(convert_charrefs=True);self.out=[];self.assets=assets;self.targets=targets or set();self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ['head','script','style']:self.hidden+=1;return
        if self.hidden or tag not in self.allowed:return
        attrs=dict(attrs);extra=''
        allowed_styles={'font-family','font-size','font-weight','font-style','text-decoration','color','text-align','white-space'}
        declarations=[]
        for declaration in attrs.get('style','').split(';'):
            key,sep,value=declaration.partition(':');key=key.strip().lower();value=value.strip()
            if sep and key in allowed_styles and not re.search(r'url|expression|[<>\\@]',value,re.I):declarations.append(key+':'+value)
        if declarations:extra+=' style="'+html.escape(';'.join(declarations),quote=True)+'"'

        if tag=='a' and attrs.get('href','').startswith('story:') and attrs['href'][6:] in self.targets:extra+=' href="#'+html.escape(attrs['href'][6:],quote=True)+'"'
        if tag=='img':
            src=attrs.get('src','');key=src[6:] if src.startswith('asset:') else ''
            if key not in self.assets:return
            data=self.assets[key]
            import base64
            from PySide6.QtGui import QImage
            image=QImage.fromData(base64.b64decode(data))
            if image.isNull():return
            from PySide6.QtCore import QBuffer,QByteArray,QIODevice
            raw=QByteArray();buf=QBuffer(raw);buf.open(QIODevice.WriteOnly);image.save(buf,'PNG');buf.close()
            extra+=' src="data:image/png;base64,'+base64.b64encode(bytes(raw)).decode()+'"'
        self.out.append('<'+tag+extra+'>')
    def handle_endtag(self,tag):
        if tag in ['head','script','style']:self.hidden=max(0,self.hidden-1);return
        if not self.hidden and tag in self.allowed and tag not in ['img','br']:self.out.append('</'+tag+'>')
    def handle_data(self,data):
        if not self.hidden:self.out.append(html.escape(data))
def safe_html(text,assets,targets=None):
    parser=SafeHTML(assets,targets);parser.feed(text);return ''.join(parser.out)
def website(spec,path):
    spec=validate(spec);p=spec['payload'].get('project')
    if p is None:raise ValueError('Dieses Paket enthält keine Lesefassung oder Welt.')
    m=spec['metadata'];cards=[];targets={e['id'] for e in p['entries']}
    from authoring import plain
    for o in p['documents']+p['entries']:
        fields=[]
        cat=next((c for c in p['categories'] if c['id']==o.get('category')),None)
        if cat:
            names={e['id']:e['name'] for e in p['entries']}
            for f in cat['fields']:
                v=o['values'].get(f['id'],'')
                if not v:continue
                if f['type'] in ['Bild','Galerie']:
                    keys=v if isinstance(v,list) else [v];body=''.join(safe_html('<img src="asset:'+str(k)+'">',p['assets']) for k in keys)
                elif f['type']=='Richtext':body=safe_html(str(v),p['assets'],targets)
                else:body=html.escape(', '.join(names.get(str(x),str(x)) for x in v) if isinstance(v,list) else names.get(str(v),str(v)))
                fields.append('<dt>'+html.escape(f['name'])+'</dt><dd>'+body+'</dd>')
        links=''.join('<a href="#'+html.escape(k,quote=True)+'">'+html.escape(next(e['name'] for e in p['entries'] if e['id']==k))+'</a> ' for k in o.get('links',[]) if any(e['id']==k for e in p['entries']))
        cards.append('<article data-category="'+html.escape((cat or {}).get('name',''),quote=True)+'" id="'+html.escape(o['id'],quote=True)+'" data-search="'+html.escape((o['name']+' '+(cat or {}).get('name','')+' '+plain(o.get('html',''))).lower(),quote=True)+'"><small>'+html.escape((cat or {}).get('name',''))+'</small><h2>'+html.escape(o['name'])+'</h2>'+safe_html(o.get('html',''),p['assets'],targets)+'<dl>'+''.join(fields)+'</dl>'+links+'<ul>'+''.join('<li>'+html.escape(next((t['name'] for t in p.get('relationship_types',[]) if t['id']==rel['type']),'Beziehung'))+': <a href="#'+html.escape(rel['target'] if rel['source']==o['id'] else rel['source'],quote=True)+'">'+html.escape(next((e['name'] for e in p['entries'] if e['id']==(rel['target'] if rel['source']==o['id'] else rel['source'])),'?'))+'</a> '+html.escape(rel.get('description',''))+'</li>' for rel in p.get('relationships',[]) if o['id'] in [rel['source'],rel['target']])+'</ul></article>')
    cover=p['covers'].get('book','');coverhtml=safe_html('<img src="asset:'+cover+'">',p['assets']) if cover else ''
    options='<option value="">Alle Kategorien / All categories</option>'+''.join('<option>'+html.escape(name)+'</option>' for name in sorted({c['name'] for c in p['categories']}))
    data='''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"><title>'''+html.escape(m['title'])+'''</title><style>body{font:18px/1.7 Georgia,serif;background:#f5f3ef;color:#25282d;max-width:880px;margin:40px auto;padding:24px}input{box-sizing:border-box;width:100%;padding:14px;font:inherit;border:1px solid #ccc;border-radius:8px}article{background:white;padding:28px;margin:24px 0;border-radius:12px}img{max-width:100%;max-height:700px}dt{font-weight:bold}dd{margin:0 0 18px}small,footer{color:#666}a{color:#3153a3}</style><h1>'''+html.escape(m['title'])+'</h1>'+coverhtml+'<p>'+html.escape(m['description'])+'</p><input id="search" placeholder="Suchen / Search" aria-label="Suchen"><select id="category" aria-label="Kategorie">'+options+'</select>'+''.join(cards)+'<footer>'+html.escape(m['author']+' · '+m['license'])+'''</footer><script>function filter(){const q=document.getElementById('search').value.toLowerCase(),c=document.getElementById('category').value;document.querySelectorAll('article').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q)||(c&&a.dataset.category!==c))}document.getElementById('search').addEventListener('input',filter);document.getElementById('category').addEventListener('change',filter)</script></html>'''
    Path(path).write_text(data,encoding='utf-8')
def feedback(spec,comments,reviewer):
    validate(spec)
    if spec['kind']!='reading':raise ValueError('Eine Lesefassung wird benötigt.')
    docs={d['id']:d for d in spec['payload']['project']['documents']};result=[]
    for c in comments:
        if c['document'] not in docs or not isinstance(c['text'],str) or not c['text'].strip():raise ValueError('Ungültiger Kommentar.')
        doc=QTextDocument();doc.setHtml(docs[c['document']]['html']);length=doc.characterCount()-1
        a,b=c['start'],c['end']
        if type(a) is not int or type(b) is not int or not 0<=a<=b<=length:raise ValueError('Ungültige Textstelle.')
        cur=QTextCursor(doc);cur.setPosition(a);cur.setPosition(b,QTextCursor.KeepAnchor)
        result.append(dict(id=digest([spec['metadata']['id'],reviewer,c['document'],a,b,c['text']]),document=c['document'],text=c['text'],start=a,end=b,quote=cur.selectedText(),revision=docs[c['document']].get('source_revision',digest(docs[c['document']]['html']))))
    return dict(format='storynator.feedback',version=1,project=spec['payload']['project']['project_id'],package=spec['metadata']['id'],reviewer=reviewer,comments=result)
def import_feedback(p,data):
    if not isinstance(data,dict) or data.get('format')!='storynator.feedback' or data.get('version')!=1 or not isinstance(data.get('comments'),list) or not isinstance(data.get('reviewer'),str):raise ValueError('Ungültige Feedback-Datei.')
    if data.get('project')!=p['project_id']:raise ValueError('Feedback gehört zu einem anderen Projekt.')
    q=copy.deepcopy(p);lookup={d['id']:d for d in q['documents']};uncertain=0;count=0
    for c in data['comments']:
        if not isinstance(c,dict) or not all(isinstance(c.get(k),str) for k in ['id','document','text','quote','revision']) or any(type(c.get(k)) is not int or c[k]<0 for k in ['start','end']) or c['end']<c['start']:raise ValueError('Ungültiger Feedback-Kommentar.')
        if c['document'] not in lookup:raise ValueError('Ein kommentiertes Kapitel fehlt. Feedback bleibt unverändert.')
        d=lookup[c['document']];notes=d.setdefault('annotations',[])
        if any(n.get('feedback_id')==c['id'] for n in notes):continue
        exact=digest(d.get('html',''))==c['revision']
        if exact:
            document=QTextDocument();document.setHtml(d.get('html',''))
            if c['end']>document.characterCount()-1:raise ValueError('Feedback-Textstelle liegt außerhalb des Kapitels.')
        uncertain+=not exact
        notes.append(dict(id=uid(),kind='comment',text=data['reviewer']+': '+c['text'],start=c['start'] if exact else 0,end=c['end'] if exact else 0,quote=c['quote'],detached=not exact,resolved=False,feedback_id=c['id']));count+=1
    return q,count,uncertain

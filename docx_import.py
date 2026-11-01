"""Bounded, offline WordprocessingML importer. Never extracts files or follows external links."""
import html,posixpath,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from core import uid
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A='{http://schemas.openxmlformats.org/drawingml/2006/main}'
P='{http://schemas.openxmlformats.org/package/2006/relationships}'
LIMIT=128*1024*1024

def xml(raw):
    if len(raw)>32*1024*1024 or b'<!DOCTYPE' in raw.upper().replace(b'\0',b'') or b'<!ENTITY' in raw.upper().replace(b'\0',b''):raise ValueError('Unsichere oder zu große DOCX-XML-Datei.')
    root=ET.fromstring(raw)
    count=0;stack=[(root,0)]
    while stack:
        node,depth=stack.pop();count+=1
        if depth>128 or count>500000:raise ValueError('DOCX-Dokument ist zu komplex.')
        stack.extend((child,depth+1) for child in node)
    return root

def image_bytes(project,data):
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice,Qt
    from PySide6.QtGui import QImageReader
    from media import store_image
    raw=QByteArray(data);buffer=QBuffer(raw);buffer.open(QIODevice.ReadOnly);reader=QImageReader(buffer);reader.setAutoTransform(True);size=reader.size()
    if not size.isValid():raise ValueError('DOCX-Bildformat wird nicht unterstützt.')
    if max(size.width(),size.height())>4096:reader.setScaledSize(size.scaled(4096,4096,Qt.KeepAspectRatio))
    return store_image(project,reader.read())

def read_docx(path,split=True):
    path=Path(path)
    if path.stat().st_size>64*1024*1024:raise ValueError('DOCX-Datei ist zu groß (maximal 64 MB komprimiert).')
    warnings=set();project={'assets':{}};documents=[]
    try:
        with zipfile.ZipFile(path) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)) or len(names)>20000 or sum(i.file_size for i in archive.infolist())>LIMIT:raise ValueError('DOCX-Archiv ist ungültig oder zu groß.')
            def part(name):return xml(archive.read(name)) if name in names else None
            document=part('word/document.xml')
            if document is None:raise ValueError('Keine Word-Dokumentdatei gefunden.')
            rels={};relroot=part('word/_rels/document.xml.rels')
            if relroot is not None:
                for rel in relroot:
                    if rel.get('TargetMode')=='External':warnings.add('Externe Verknüpfungen werden als Text übernommen; externe Bilder werden nicht geladen.');continue
                    raw_target=rel.get('Target','');target=posixpath.normpath(raw_target.lstrip('/') if raw_target.startswith('/') else posixpath.join('word',raw_target));rels[rel.get('Id')]=target
            styles={};defaults={};style_root=part('word/styles.xml')
            def properties(node):
                out={}
                if node is None:return out
                for child in node:
                    tag=child.tag[len(W):] if child.tag.startswith(W) else ''
                    if tag in ['b','i','u']:out[tag]=child.get(W+'val','1') not in ['0','false','none','off']
                    elif tag=='rFonts':out['font']=child.get(W+'ascii') or child.get(W+'hAnsi')
                    elif tag=='sz':
                        try:out['size']=max(1,min(200,float(child.get(W+'val'))/2))
                        except (ValueError,TypeError):pass
                    elif tag=='color' and re.fullmatch('[A-Fa-f0-9]{6}',child.get(W+'val','')):out['color']='#'+child.get(W+'val')
                    elif tag=='vertAlign':out['vertical']=child.get(W+'val')
                return out
            if style_root is not None:
                defaults=properties(style_root.find(W+'docDefaults/'+W+'rPrDefault/'+W+'rPr'))
                for st in style_root.findall(W+'style'):
                    parent=st.find(W+'basedOn');name=st.find(W+'name');styles[st.get(W+'styleId')]={'parent':parent.get(W+'val') if parent is not None else None,'run':properties(st.find(W+'rPr')),'name':name.get(W+'val','') if name is not None else '', 'paragraph':st.find(W+'pPr')}
            def effective(style):
                chain=[];seen=set()
                while style in styles and style not in seen and len(seen)<64:seen.add(style);chain.append(styles[style]);style=styles[style]['parent']
                run=dict(defaults)
                for st in reversed(chain):run.update(st['run'])
                return run
            levels={};nums={};overrides={};numbering=part('word/numbering.xml');counts={}
            if numbering is not None:
                for item in numbering.findall(W+'abstractNum'):
                    for level in item.findall(W+'lvl'):
                        fmt=level.find(W+'numFmt');start=level.find(W+'start');levels[(item.get(W+'abstractNumId'),level.get(W+'ilvl','0'))]=(fmt.get(W+'val','decimal') if fmt is not None else 'decimal',int(start.get(W+'val','1')) if start is not None and start.get(W+'val','1').isdigit() else 1)
                for item in numbering.findall(W+'num'):
                    abstract=item.find(W+'abstractNumId')
                    if abstract is not None:nums[item.get(W+'numId')]=abstract.get(W+'val')
                    for override in item.findall(W+'lvlOverride'):
                        start=override.find(W+'startOverride')
                        if start is not None and start.get(W+'val','').isdigit():overrides[(item.get(W+'numId'),override.get(W+'ilvl','0'))]=int(start.get(W+'val'))
            cache={}
            def picture(node,width=None,height=None):
                rid=node.get(R+'embed') or node.get(R+'id');target=rels.get(rid,'')
                if not target.startswith('word/media/') or target not in names:warnings.add('Ein verknüpftes oder nicht verfügbares Bild wurde ausgelassen.');return '[Bild nicht verfügbar]'
                if target not in cache:
                    try:cache[target]=image_bytes(project,archive.read(target))
                    except ValueError:warnings.add('Ein Bildformat konnte nicht übernommen werden.');return '[Bild nicht unterstützt]'
                from media import image_from_asset
                image=image_from_asset(project,cache[target],4096);w=min(550,width or image.width());h=w*(height/width if width and height else image.height()/max(1,image.width()))
                return '<img src="asset:'+cache[target]+'" width="'+str(w)+'" height="'+str(h)+'">'
            def inline(node,run):
                if node.tag in [W+'del',W+'moveFrom']:warnings.add('Änderungsverfolgung wird als endgültiger Text importiert.');return ''
                if node.tag==W+'r':
                    rpr=node.find(W+'rPr');rstyle=rpr.find(W+'rStyle') if rpr is not None else None;fmt={**run,**(effective(rstyle.get(W+'val')) if rstyle is not None else {}),**properties(rpr)};body=''.join(inline(c,fmt) for c in node if c.tag!=W+'rPr');css=[]
                    if fmt.get('font'):css.append('font-family:'+html.escape(re.sub(r'[^\w\s@.-]','',fmt['font'])[:200],quote=True))
                    if fmt.get('size'):css.append('font-size:'+str(fmt['size'])+'pt')
                    for key,value in [('b','font-weight:bold'),('i','font-style:italic'),('u','text-decoration:underline')]:
                        if fmt.get(key):css.append(value)
                    if fmt.get('color'):css.append('color:'+fmt['color'])
                    if fmt.get('vertical')=='superscript':body='<sup>'+body+'</sup>'
                    elif fmt.get('vertical')=='subscript':body='<sub>'+body+'</sub>'
                    return '<span style="'+';'.join(css)+'">'+body+'</span>' if css else body
                if node.tag==W+'t':return html.escape(node.text or '')
                if node.tag==W+'tab':return '&#9;'
                if node.tag in [W+'br',W+'cr']:
                    if node.get(W+'type')=='page':warnings.add('Manuelle Seitenumbrüche können vom Word-Layout abweichen.')
                    return '<br>'
                if node.tag==W+'drawing':
                    blip=node.find('.//'+A+'blip');extent=node.find('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent');width=height=None
                    if extent is not None:
                        try:width=max(1,min(100000,int(extent.get('cx'))/9525));height=max(1,min(100000,int(extent.get('cy'))/9525))
                        except (ValueError,TypeError):pass
                    if blip is None:warnings.add('Diagramme und Zeichnungen ohne Bildvorschau werden nicht übernommen.');return ''
                    return picture(blip,width,height)
                if node.tag in [A+'blip','{urn:schemas-microsoft-com:vml}imagedata']:return picture(node)
                if node.tag in [W+'footnoteReference',W+'endnoteReference']:warnings.add('Fußnoten und Endnoten werden nicht übernommen.');return '<sup>[Anmerkung]</sup>'
                if node.tag==W+'object':warnings.add('Eingebettete OLE-Objekte werden nicht übernommen.');return ''
                if node.tag in [W+'rPr',W+'pPr',W+'sectPr',W+'instrText']:return ''
                if node.tag==W+'ins':warnings.add('Änderungsverfolgung wird als endgültiger Text importiert.')
                return ''.join(inline(c,run) for c in node)
            def paragraph(node):
                ppr=node.find(W+'pPr');style_node=ppr.find(W+'pStyle') if ppr is not None else None;style=style_node.get(W+'val') if style_node is not None else 'Normal';run=effective(style);body=''.join(inline(c,run) for c in node if c.tag!=W+'pPr');plain=''.join(n.text or '' for n in node.iter(W+'t'));level=0;css=[]
                inherited=styles.get(style,{}).get('paragraph')
                for pr in [inherited,ppr]:
                    if pr is None:continue
                    outline=pr.find(W+'outlineLvl');align=pr.find(W+'jc')
                    if outline is not None:
                        try:level=int(outline.get(W+'val'))+1
                        except (ValueError,TypeError):pass
                    if align is not None:
                        value={'both':'justify','center':'center','right':'right','left':'left','start':'left','end':'right'}.get(align.get(W+'val'))
                        if value:css.append('text-align:'+value)
                    if pr.find(W+'pageBreakBefore') is not None:css.append('page-break-before:always')
                if not level:
                    match=re.search(r'(?:heading|überschrift)\s*([1-6])',style+' '+styles.get(style,{}).get('name',''),re.I)
                    if match:level=int(match[1])
                num=ppr.find(W+'numPr') if ppr is not None else None
                if num is None and inherited is not None:num=inherited.find(W+'numPr')
                if num is not None and num.find(W+'numId') is not None and num.find(W+'numId').get(W+'val')!='0':
                    ni=num.find(W+'numId');li=num.find(W+'ilvl');nid=ni.get(W+'val') if ni is not None else '0';ilvl=li.get(W+'val','0') if li is not None else '0';fmt,start=levels.get((nums.get(nid),ilvl),('decimal',1));key=(nid,ilvl);start=overrides.get(key,start)
                    for prior in list(counts):
                        if prior[0]==nid and prior[1].isdigit() and ilvl.isdigit() and int(prior[1])>int(ilvl):counts.pop(prior)
                    counts[key]=counts.get(key,start-1)+1;tag='ul' if fmt=='bullet' else 'ol';attrs='' if tag=='ul' else ' start="'+str(counts[key])+'"'
                    if fmt in ['lowerLetter','upperLetter','lowerRoman','upperRoman']:attrs+=' type="'+dict(lowerLetter='a',upperLetter='A',lowerRoman='i',upperRoman='I')[fmt]+'"'
                    elif fmt not in ['bullet','decimal']:warnings.add('Komplexe Listennummerierung kann vom Original abweichen.')
                    if ilvl.isdigit():css.append('margin-left:'+str(min(10,int(ilvl))*20)+'px')
                    return '<'+tag+attrs+'><li style="'+';'.join(css)+'">'+body+'</li></'+tag+'>',plain,0
                tag='h'+str(level) if 1<=level<=6 else 'p';return '<'+tag+' style="'+';'.join(css)+'">'+(body or '<br>')+'</'+tag+'>',plain,level
            def table(node):
                rows=[]
                for row in node.findall(W+'tr'):
                    cells=[]
                    for cell in row.findall(W+'tc'):cells.append('<td>'+''.join(paragraph(c)[0] if c.tag==W+'p' else table(c) if c.tag==W+'tbl' else '' for c in cell)+'</td>')
                    rows.append('<tr>'+''.join(cells)+'</tr>')
                return '<table border="1" cellpadding="6">'+''.join(rows)+'</table>'
            current=dict(id=uid(),name=path.stem,html='');body=document.find(W+'body')
            if body is None:raise ValueError('DOCX enthält keinen Dokumenttext.')
            for node in body:
                if node.tag==W+'p':
                    text,plain,level=paragraph(node)
                    if split and level==1 and plain.strip():
                        if current['html']:documents.append(current)
                        current=dict(id=uid(),name=plain.strip(),html='');continue
                    current['html']+=text
                elif node.tag==W+'tbl':current['html']+=table(node)
            if current['html'] or not documents:documents.append(current)
            if 'word/comments.xml' in names or document.find('.//'+W+'bookmarkStart') is not None:warnings.add('Word-Kommentare und Word-Lesezeichen werden nicht übernommen.')
            if any(n.startswith(('word/header','word/footer')) for n in names):warnings.add('Kopf- und Fußzeilen werden nicht übernommen.')
            if any('vbaProject' in n for n in names):warnings.add('Makros werden nicht übernommen oder ausgeführt.')
    except (zipfile.BadZipFile,ET.ParseError,KeyError,RuntimeError,OverflowError) as e:raise ValueError('DOCX-Datei ist beschädigt oder wird nicht unterstützt.') from e
    return dict(documents=documents,assets=project['assets'],warnings=sorted(warnings))

"""World navigation, typed relationships, category transfer and template layouts."""
import copy,json,math
from PySide6.QtCore import Qt,QPointF,QSignalBlocker,QTimer,QRectF
from PySide6.QtGui import QColor,QPen,QBrush,QPainter,QPolygonF,QPainterPath
from PySide6.QtWidgets import *
from ui import RoomyList,RoomyTable,ArrowCombo as QComboBox
from design import label,primary,theme_colors,CURRENT
from i18n import tr
from core import uid,resolve,objects,Calendar
from worldmodel import *

class WorldBrowser(QWidget):
    world_page=True;section='world'
    def __init__(self,host):
        super().__init__(host);self.host=host;root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);area=QScrollArea();area.setWidgetResizable(True);content=QWidget();area.setWidget(content);root.addWidget(area);layout=QVBoxLayout(content);layout.setContentsMargins(28,25,28,25);layout.setSpacing(16);header=QHBoxLayout();header.addWidget(label(tr('Deine Welt'),'title'));header.addStretch();header.addWidget(primary(tr('Neuer Eintrag'),host.add_entry,'plus'));layout.addLayout(header);row=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText(tr('Einträge durchsuchen …'));row.addWidget(self.query,2);self.category=QComboBox();self.category.addItem(tr('Alle Kategorien'),None)
        for cat in host.p['categories']:self.category.addItem(cat['name'],cat['id'])
        row.addWidget(self.category,1);self.favorite=QCheckBox(tr('Favoriten'));row.addWidget(self.favorite);self.sort=QComboBox();self.sort.addItem(tr('Alphabetisch'),'name');self.sort.addItem(tr('Zuletzt geöffnet'),'recent');row.addWidget(self.sort);layout.addLayout(row);row=QHBoxLayout();self.field=QComboBox();self.value=QLineEdit();self.value.setPlaceholderText(tr('Feld enthält …'));row.addWidget(self.field);row.addWidget(self.value);self.saved=QComboBox();row.addWidget(self.saved);save=QPushButton(tr('Ansicht speichern'));save.clicked.connect(self.save_view);row.addWidget(save);remove=QPushButton(tr('Ansicht löschen'));remove.clicked.connect(self.remove_view);row.addWidget(remove);layout.addLayout(row);self.table=RoomyTable(0,3);self.table.setHorizontalHeaderLabels([tr('Name'),tr('Kategorie'),tr('Beschreibung')]);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);self.table.setColumnWidth(0,230);self.table.setColumnWidth(1,160);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.itemActivated.connect(self.open);self.table.itemDoubleClicked.connect(self.open);layout.addWidget(self.table,1);self.count=QLabel();layout.addWidget(self.count);row=QGridLayout()
        for i,(text,callback) in enumerate([('Öffnen',self.open),('Favorit umschalten',self.toggle_favorite),('Duplizieren',self.duplicate),('Kategorie wechseln',self.transfer),('Vorlage bearbeiten',self.template),('Beziehungen',lambda:RelationshipDialog(host,self.selected()).exec()),('Beziehungsgraph',lambda:GraphDialog(host,self.selected()).exec())]):b=QPushButton(tr(text));b.clicked.connect(callback);row.addWidget(b,i//4,i%4)
        layout.addLayout(row);self.query.textChanged.connect(self.refresh_data);self.value.textChanged.connect(self.refresh_data);self.favorite.toggled.connect(self.refresh_data);self.sort.currentIndexChanged.connect(self.refresh_data);self.field.currentIndexChanged.connect(self.refresh_data);self.category.currentIndexChanged.connect(self.category_changed);self.saved.activated.connect(self.load_view);self.refresh_views();self.category_changed()
    def filters(self):return dict(query=self.query.text(),category=self.category.currentData(),favorites=self.favorite.isChecked(),sort=self.sort.currentData(),field=self.field.currentData(),value=self.value.text())
    def category_changed(self,*args):
        self.field.blockSignals(True);self.field.clear();self.field.addItem(tr('Kein Feldfilter'),None);cat=next((c for c in self.host.p['categories'] if c['id']==self.category.currentData()),{})
        for f in cat.get('fields',[]):self.field.addItem(f['name'],f['id'])
        self.field.blockSignals(False);self.refresh_data()
    def refresh_data(self,*args):
        signature=tuple((c['id'],c['name'],repr(c['fields'])) for c in self.host.p['categories'])
        if getattr(self,'category_signature',None)!=signature:
            self.category_signature=signature;old=self.category.currentData();old_field=self.field.currentData()
            with QSignalBlocker(self.category):
                self.category.clear();self.category.addItem(tr('Alle Kategorien'),None)
                for category in self.host.p['categories']:self.category.addItem(category['name'],category['id'])
                self.category.setCurrentIndex(max(0,self.category.findData(old)))
            self.category_changed();self.field.setCurrentIndex(max(0,self.field.findData(old_field)));return
        current=self.selected();categories={c['id']:c['name'] for c in self.host.p['categories']};recent=self.host.recent_ids();self.entries=query_entries(self.host.p,self.filters(),recent);self.table.setUpdatesEnabled(False);self.table.setRowCount(len(self.entries))
        for i,entry in enumerate(self.entries):
            for col,text in enumerate([('★ ' if entry['id'] in self.host.p.get('favorites',[]) else '')+entry['name'],categories.get(entry['category'],'?'),plain(entry.get('html',''))[:130]]):item=QTableWidgetItem(text);item.setData(Qt.UserRole,entry['id']);self.table.setItem(i,col,item)
            if entry['id']==current:self.table.selectRow(i)
        self.table.setUpdatesEnabled(True);self.count.setText(str(len(self.entries))+' '+tr('Einträge'));self.table.viewport().installEventFilter(self.host)
    def selected(self):return self.table.item(self.table.currentRow(),0).data(Qt.UserRole) if self.table.currentRow()>=0 and self.table.item(self.table.currentRow(),0) else None
    def open(self,*args):
        if self.selected():self.host.open_object(self.selected())
    def toggle_favorite(self):
        if self.selected():toggle_favorite(self.host,self.selected());self.refresh_data()
    def duplicate(self):
        if self.selected():duplicate_dialog(self.host,self.selected());self.refresh_data()
    def transfer(self):
        if self.selected():TransferDialog(self.host,self.selected()).exec();self.refresh_data()
    def template(self):
        entry=resolve(self.host.p,self.selected());id=entry['category'] if entry else self.category.currentData();cat=next((c for c in self.host.p['categories'] if c['id']==id),None)
        if cat:self.host.template(cat);self.category_changed()
    def refresh_views(self):
        self.saved.clear();self.saved.addItem(tr('Gespeicherte Ansichten'),None)
        for view in self.host.p.get('saved_views',[]):self.saved.addItem(view['name'],view['id'])
    def save_view(self):
        name,ok=QInputDialog.getText(self,tr('Ansicht speichern'),tr('Name:'))
        if ok and name.strip():self.host.p.setdefault('saved_views',[]).append(dict(id=uid(),name=name.strip(),filters=self.filters()));self.host.changed();self.refresh_views()
    def remove_view(self):
        id=self.saved.currentData()
        if id:self.host.p['saved_views']=[v for v in self.host.p.get('saved_views',[]) if v['id']!=id];self.host.changed();self.refresh_views()
    def load_view(self,*args):
        view=next((v for v in self.host.p.get('saved_views',[]) if v['id']==self.saved.currentData()),None)
        if not view:return
        f=view['filters'];self.query.setText(f.get('query',''));self.category.setCurrentIndex(max(0,self.category.findData(f.get('category'))));self.category_changed();self.favorite.setChecked(f.get('favorites',False));self.sort.setCurrentIndex(max(0,self.sort.findData(f.get('sort','name'))));self.field.setCurrentIndex(max(0,self.field.findData(f.get('field'))));self.value.setText(f.get('value',''));self.refresh_data()

def toggle_favorite(host,id):
    items=host.p.setdefault('favorites',[])
    if id in items:items.remove(id)
    else:items.append(id)
    host.changed()

def duplicate_dialog(host,id):
    entry=resolve(host.p,id)
    if not entry or entry not in host.p['entries']:return
    name,ok=QInputDialog.getText(host,tr('Eintrag duplizieren'),tr('Name:'),text=entry['name']+' · '+tr('Kopie'))
    if ok and name.strip():item=duplicate_entry(host.p,entry,name.strip());host.changed();host.refresh();host.open_object(item['id'])

class TransferDialog(QDialog):
    def __init__(self,host,id):
        super().__init__(host);self.host=host;self.entry=resolve(host.p,id);self.setWindowTitle(tr('Kategorie wechseln · Feldzuordnung'));self.resize(720,500);layout=QVBoxLayout(self);self.target=QComboBox()
        for c in host.p['categories']:
            if self.entry and c['id']!=self.entry['category']:self.target.addItem(c['name'],c['id'])
        layout.addWidget(self.target);notice=label(tr('Gleiche Feldtypen zuordnen. Alle bisherigen Feldwerte werden zusätzlich im Eintrag archiviert.'));notice.setWordWrap(True);layout.addWidget(notice);self.table=RoomyTable(0,2);self.table.setHorizontalHeaderLabels([tr('Bisheriges Feld'),tr('Zielfeld')]);layout.addWidget(self.table,1);self.target.currentIndexChanged.connect(self.refresh);layout.addWidget(primary(tr('Übertragen'),self.apply));self.refresh()
    def refresh(self,*args):
        source=next((c for c in self.host.p['categories'] if self.entry and c['id']==self.entry['category']),{});target=next((c for c in self.host.p['categories'] if c['id']==self.target.currentData()),{});self.fields=source.get('fields',[]);self.table.setRowCount(len(self.fields))
        for i,f in enumerate(self.fields):
            self.table.setItem(i,0,QTableWidgetItem(f['name']+' · '+tr(f['type'])));combo=QComboBox();combo.addItem(tr('Nur archivieren'),None)
            for dest in target.get('fields',[]):
                if dest['type']==f['type']:combo.addItem(dest['name'],dest['id']);combo.setCurrentIndex(combo.count()-1) if dest['name']==f['name'] else None
            self.table.setCellWidget(i,1,combo)
    def apply(self):
        if not self.target.currentData():return
        try:
            mapping={f['id']:self.table.cellWidget(i,1).currentData() for i,f in enumerate(self.fields) if self.table.cellWidget(i,1).currentData()};self.host.flush_editors();self.host.backups.create(self.host.p,self.host.path,'Vor Kategorieübertragung');transfer_entry(self.host.p,self.entry,self.target.currentData(),mapping);self.host.changed();self.host.refresh();self.host.open_object(self.entry['id']);self.accept()
        except (ValueError,OSError) as error:self.host.error(error)

class RelationshipDialog(QDialog):
    def __init__(self,host,focus=None):
        super().__init__(host);self.host=host;self.focus=focus;self.setWindowTitle(tr('Beziehungen'));self.resize(900,580);layout=QVBoxLayout(self);row=QHBoxLayout();self.date=QLineEdit();self.date.setPlaceholderText(tr('Gültig am Datum · leer = alle'));row.addWidget(self.date);filter_button=QPushButton(tr('Anwenden'));filter_button.clicked.connect(self.refresh);row.addWidget(filter_button);types=QPushButton(tr('Beziehungstypen'));types.clicked.connect(self.types);row.addWidget(types);layout.addLayout(row);self.list=RoomyList();layout.addWidget(self.list,1);row=QHBoxLayout()
        for text,callback in [('Hinzufügen',lambda:self.edit()),('Bearbeiten',lambda:self.edit(self.selected())),('Löschen',self.remove),('Ziel öffnen',self.open_target)]:button=QPushButton(tr(text));button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.refresh()
    def selected(self):return next((r for r in self.host.p.get('relationships',[]) if self.list.currentItem() and r['id']==self.list.currentItem().data(Qt.UserRole)),None)
    def refresh(self):
        self.list.clear();p=self.host.p;types={t['id']:t for t in p.get('relationship_types',[])}
        try:
            if self.date.text():Calendar(p['calendar']).ordinal(self.date.text())
            for relation in p.get('relationships',[]):
                if self.focus and self.focus not in [relation['source'],relation['target']]:continue
                if self.date.text() and relation.get('start'):
                    cal=Calendar(p['calendar']);day=cal.ordinal(self.date.text());a,b=cal.span(relation['start'],relation['end']);b=b if relation['end'] else float('inf')
                    if not a<=day<=b:continue
                source=(resolve(p,relation['source']) or {}).get('name',tr('[Gelöschter Eintrag]'));target=(resolve(p,relation['target']) or {}).get('name',tr('[Gelöschter Eintrag]'));type=types.get(relation['type'],{});item=QListWidgetItem(source+'  '+('→' if type.get('directed',True) else '↔')+'  '+type.get('name','?')+'  ·  '+target+('  ·  '+relation['start']+' — '+relation['end'] if relation.get('start') else ''));item.setData(Qt.UserRole,relation['id']);item.setToolTip(relation.get('description',''));self.list.addItem(item)
        except ValueError as error:self.host.error(error)
    def types(self):
        d=QDialog(self);d.setWindowTitle(tr('Beziehungstypen'));layout=QVBoxLayout(d);table=RoomyTable(0,3);table.setHorizontalHeaderLabels([tr('Bezeichnung'),tr('Rückrichtung'),tr('Gerichtet')]);layout.addWidget(table);ids=[]
        def add(value=None):
            value=value or dict(id=uid(),name='',inverse='',directed=True);i=table.rowCount();table.insertRow(i);ids.append(value['id']);table.setItem(i,0,QTableWidgetItem(value['name']));table.setItem(i,1,QTableWidgetItem(value.get('inverse','')));check=QCheckBox();check.setChecked(value.get('directed',True));table.setCellWidget(i,2,check)
        for value in self.host.p.get('relationship_types',[]):add(value)
        remove_button=QPushButton(tr('Typ löschen'));layout.addWidget(remove_button)
        def remove_type():
            row=table.currentRow()
            if row<0:return
            if any(r['type']==ids[row] for r in self.host.p.get('relationships',[])):self.host.error('Beziehungstyp wird verwendet. Beziehungen zuerst ändern.');return
            ids.pop(row);table.removeRow(row)
        remove_button.clicked.connect(remove_type);add_button=QPushButton(tr('Typ hinzufügen'));add_button.clicked.connect(lambda:add());layout.addWidget(add_button)
        def save():
            values=[]
            for i,id in enumerate(ids):
                name=table.item(i,0).text().strip()
                if not name:self.host.error('Name fehlt.');return
                values.append(dict(id=id,name=name,inverse=table.item(i,1).text().strip(),directed=table.cellWidget(i,2).isChecked()))
            self.host.p['relationship_types']=values;self.host.changed();d.accept();self.refresh()
        layout.addWidget(primary(tr('Übernehmen'),save));d.resize(650,450);d.exec()
    def edit(self,relation=None):
        p=self.host.p
        if not p.get('relationship_types'):self.types()
        if not p.get('relationship_types'):return
        value=relation or {};d=QDialog(self);d.setWindowTitle(tr('Beziehung bearbeiten'));form=QFormLayout(d);source=QComboBox();target=QComboBox()
        categories={c['id']:c['name'] for c in p['categories']}
        for obj in objects(p):
            caption=obj['name']+' · '+categories.get(obj.get('category'),tr('Dokument / Timeline'))
            source.addItem(caption,obj['id']);target.addItem(caption,obj['id'])
        for combo,key in [(source,'source'),(target,'target')]:
            if value.get(key) and combo.findData(value[key])<0:combo.addItem(tr('[Gelöschter Eintrag]'),value[key])
        source.setCurrentIndex(max(0,source.findData(value.get('source',self.focus))));target.setCurrentIndex(max(0,target.findData(value.get('target'))));types=QComboBox()
        for type in p['relationship_types']:types.addItem(type['name'],type['id'])
        if value.get('type') and types.findData(value['type'])<0:types.addItem(tr('Fehlender Beziehungstyp'),value['type'])
        types.setCurrentIndex(max(0,types.findData(value.get('type'))));description=QPlainTextEdit(value.get('description',''));start=QLineEdit(value.get('start',''));end=QLineEdit(value.get('end',''));form.addRow(tr('Von'),source);form.addRow(tr('Beziehungstyp'),types);form.addRow(tr('Zu'),target);form.addRow(tr('Beschreibung'),description);form.addRow(tr('Anfang · optional'),start);form.addRow(tr('Ende · optional'),end)
        def save():
            try:add_relation(p,source.currentData(),target.currentData(),types.currentData(),description.toPlainText(),start.text().strip(),end.text().strip(),value.get('id'));self.host.changed();self.refresh();d.accept()
            except ValueError as error:self.host.error(error)
        form.addRow(primary(tr('Übernehmen'),save));d.resize(620,470);d.exec()
    def remove(self):
        relation=self.selected()
        if relation and QMessageBox.question(self,tr('Löschen'),tr('Beziehung löschen?'))==QMessageBox.Yes:self.host.p['relationships'].remove(relation);self.host.changed();self.refresh()
    def open_target(self):
        relation=self.selected()
        if relation:self.host.open_object(relation['target'])

class GraphView(QGraphicsView):
    def __init__(self,scene,host,parent=None):super().__init__(scene,parent);self.host=host
    def wheelEvent(self,event):self.scale(1.2 if event.angleDelta().y()>0 else 1/1.2,1.2 if event.angleDelta().y()>0 else 1/1.2);event.accept()
    def mouseDoubleClickEvent(self,event):
        item=self.itemAt(event.position().toPoint());id=item.data(0) if item else None
        if id:
            event.accept();self.host.open_object(id);self.window().accept()
        else:super().mouseDoubleClickEvent(event)
class GraphDialog(QDialog):
    def __init__(self,host,focus=None):
        super().__init__(host);self.host=host;self.setWindowTitle(tr('Beziehungsgraph'));self.resize(950,720);layout=QVBoxLayout(self);row=QHBoxLayout();self.focus=QComboBox();self.focus.addItem(tr('Alle Objekte'),None)
        for o in objects(host.p):self.focus.addItem(o['name'],o['id'])
        self.focus.setCurrentIndex(max(0,self.focus.findData(focus)));row.addWidget(self.focus);self.status=QLabel();row.addWidget(self.status);fit=QPushButton(tr('Alles zeigen'));row.addWidget(fit);layout.addLayout(row);self.scene=QGraphicsScene(self);self.view=GraphView(self.scene,host,self);self.view.setRenderHint(QPainter.Antialiasing);self.view.setDragMode(QGraphicsView.ScrollHandDrag);layout.addWidget(self.view,1);layout.addWidget(label(tr('Doppelklick öffnet ein Objekt · Mausrad zoomt · Ziehen verschiebt')));fit.clicked.connect(lambda:self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-35,-35,35,35),Qt.KeepAspectRatio));self.focus.currentIndexChanged.connect(self.refresh);self.refresh()
    def fit_scene(self):
        if self.view.scene():self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-35,-35,35,35),Qt.KeepAspectRatio)
    def showEvent(self,event):super().showEvent(event);QTimer.singleShot(0,self.fit_scene)
    def done(self,result):
        self.view.setScene(None);self.scene.clear();super().done(result)
    def refresh(self):
        self.scene.clear();p=self.host.p;lookup={o['id']:o for o in objects(p)};focus=self.focus.currentData();types={t['id']:t for t in p.get('relationship_types',[])};edges=[(r['source'],r['target'],types.get(r['type'],{}).get('name','?'),types.get(r['type'],{}).get('directed',True)) for r in p.get('relationships',[])]
        for o in objects(p):
            ids=set(o.get('links',[]))
            for value in o.get('values',{}).values():
                if isinstance(value,str) and value in lookup:ids.add(value)
                elif isinstance(value,list):ids.update(v for v in value if isinstance(v,str) and v in lookup)
            edges.extend((o['id'],id,'',True) for id in ids)
        ids=({focus}|{a for a,b,name,directed in edges if b==focus}|{b for a,b,name,directed in edges if a==focus}) if focus else set(lookup);ids=sorted(id for id in ids if id in lookup);total=len(ids);ids=ids[:200];positions={id:QPointF(350*math.cos(i*2*math.pi/max(1,len(ids))),350*math.sin(i*2*math.pi/max(1,len(ids)))) for i,id in enumerate(ids)};colors=theme_colors(CURRENT['mode'],CURRENT['accent']);self.scene.setBackgroundBrush(QColor(colors['paper']))
        edge_groups={}
        for edge in edges:edge_groups.setdefault(tuple(sorted(edge[:2])),[]).append(edge)
        drawn={}
        for a,b,name,directed in edges:
            if a not in positions or b not in positions:continue
            start=positions[a];end=positions[b];key=tuple(sorted([a,b]));group=edge_groups[key];index=drawn.get(key,0);drawn[key]=index+1;offset=(index-(len(group)-1)/2)*26;delta=positions[key[1]]-positions[key[0]];length=max(1,math.hypot(delta.x(),delta.y()));normal=QPointF(-delta.y()/length,delta.x()/length);control=(start+end)/2+normal*(offset*2);path=QPainterPath(start)
            if a==b:path.addEllipse(QRectF(start.x()-25,start.y()-55,50,55));control=start+QPointF(0,-65)
            else:path.quadTo(control,end)
            line=self.scene.addPath(path,QPen(QColor(colors['muted']),1.4,Qt.SolidLine if name else Qt.DashLine));line.setToolTip(name)
            if directed and a!=b:
                tangent=end-control;length=max(1,math.hypot(tangent.x(),tangent.y()));unit=tangent/length;tip=end-unit*13;perpendicular=QPointF(-unit.y(),unit.x());self.scene.addPolygon(QPolygonF([tip,tip-unit*11+perpendicular*5,tip-unit*11-perpendicular*5]),QPen(Qt.NoPen),QBrush(QColor(colors['muted'])))
            if name:
                text=self.scene.addText(name);text.setDefaultTextColor(QColor(colors['text']));text.setPos(control if a==b else (start+end)/2+normal*offset)
        for id,pos in positions.items():
            node=self.scene.addEllipse(-9,-9,18,18,QPen(QColor(colors['accent'])),QBrush(QColor(colors['accent'])));node.setPos(pos);node.setData(0,id);node.setToolTip(self.host.preview_html(id));node.setFlag(QGraphicsItem.ItemIsSelectable);text=self.scene.addText(lookup[id]['name']);text.setData(0,id);text.setToolTip(self.host.preview_html(id));text.setDefaultTextColor(QColor(colors['text']));text.setPos(pos.x()+12,pos.y()-12)
        self.status.setText(str(total)+' '+tr('Objekte')+(' · '+tr('Erste 200 · Objekt wählen, um Nachbarn zu sehen.') if total>200 else ''));self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-30,-30,30,30),Qt.KeepAspectRatio)

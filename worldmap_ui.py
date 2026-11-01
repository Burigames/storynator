"""Interactive offline maps with selectable, movable and linked markers."""
import html,copy
from PySide6.QtCore import Qt,QPointF,QTimer
from PySide6.QtGui import QPixmap,QColor,QPen,QBrush,QPainter
from PySide6.QtWidgets import QScrollArea,QFrame,QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QTextEdit,QPushButton,QFileDialog,QMessageBox,QInputDialog,QSplitter,QGraphicsView,QGraphicsScene,QGraphicsItem,QCheckBox,QDialogButtonBox
from ui import RoomyList,ArrowCombo
from design import label,primary,CURRENT
from i18n import tr
from core import resolve
from media import import_image,image_from_asset
from mapmodel import new_map,add_pin
class MapView(QGraphicsView):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setRenderHint(QPainter.Antialiasing);self.setDragMode(QGraphicsView.ScrollHandDrag);self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse);self.setAccessibleName(tr('Interaktive Weltkarte'));self.edit=False;self.items_by_id={};self.scene_data=QGraphicsScene(self);self.setScene(self.scene_data);self.fit_timer=QTimer(self);self.fit_timer.setSingleShot(True);self.fit_timer.timeout.connect(self.fit);self.pressed=None;self.start=None;self.setMinimumSize(320,280)
    def pin_at(self,pos):
        item=self.itemAt(pos)
        while item:
            if item.data(Qt.UserRole):return item.data(Qt.UserRole)
            item=item.parentItem()
        return None
    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2;scale=self.transform().m11()
        if .02<scale*factor<30:self.scale(factor,factor)
        event.accept()
    def mousePressEvent(self,event):
        self.pressed=self.pin_at(event.position().toPoint()) if event.button()==Qt.LeftButton else None;self.start=event.position().toPoint() if event.button()==Qt.LeftButton else None;super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if event.button()!=Qt.LeftButton:return
        id=self.pressed
        if id:
            self.owner.select_pin(id)
            if self.edit and id in self.items_by_id:
                item=self.items_by_id[id];point=item.pos();width,height=self.owner.dimensions;pin=self.owner.pin(id)
                if pin and width and height:
                    x=max(0,min(1,point.x()/width));y=max(0,min(1,point.y()/height));item.setPos(x*width,y*height)
                    if abs(x-pin['x'])>1e-7 or abs(y-pin['y'])>1e-7:pin.update(x=x,y=y);self.owner.host.changed()
        elif self.edit and self.start is not None and (event.position().toPoint()-self.start).manhattanLength()<5:
            point=self.mapToScene(event.position().toPoint());width,height=self.owner.dimensions
            if width and height and 0<=point.x()<=width and 0<=point.y()<=height:self.owner.create_pin(point.x()/width,point.y()/height)
        self.pressed=None
    def mouseDoubleClickEvent(self,event):
        id=self.pin_at(event.position().toPoint())
        if id and event.button()==Qt.LeftButton:self.owner.select_pin(id);self.owner.open_target();event.accept()
        else:super().mouseDoubleClickEvent(event)
    def draw_map(self,keep=False):
        transform=self.transform();center=self.mapToScene(self.viewport().rect().center());self.scene_data.clear();self.items_by_id={};m=self.owner.current_map();self.owner.dimensions=(0,0)
        if not m:return
        image=image_from_asset(self.owner.host.p,m['asset'],4096)
        if image.isNull():self.scene_data.addText(tr('Kartenbild fehlt oder ist nicht lesbar.'));return
        width,height=image.width(),image.height();self.owner.dimensions=(width,height);background=self.scene_data.addPixmap(QPixmap.fromImage(image));background.setZValue(-10);self.scene_data.setSceneRect(-40,-40,width+80,height+80)
        for pin in m['pins']:
            item=self.scene_data.addEllipse(-7,-7,14,14,QPen(QColor('white'),2),QBrush(QColor(CURRENT['link'])));item.setPos(pin['x']*width,pin['y']*height);item.setFlag(QGraphicsItem.ItemIgnoresTransformations);item.setFlag(QGraphicsItem.ItemIsSelectable);item.setFlag(QGraphicsItem.ItemIsMovable,self.edit);item.setData(Qt.UserRole,pin['id']);item.setZValue(5)
            target=resolve(self.owner.host.p,pin['target']) if pin['target'] else None;title=target['name'] if target else pin['name']+(' · '+tr('[Gelöschter Eintrag]') if pin['target'] else '');text=self.scene_data.addSimpleText(title);text.setParentItem(item);text.setPos(11,-15);font=self.font();font.setPointSize(11);font.setBold(True);text.setFont(font);text.setBrush(QBrush(QColor('#17212b')));card=self.scene_data.addRect(text.boundingRect().adjusted(-5,-2,5,2),QPen(QColor('#b7c4cc'),.7),QBrush(QColor(255,255,255,235)));card.setParentItem(item);card.setPos(11,-15);card.setZValue(-1);card.setData(Qt.UserRole,pin['id']);text.setData(Qt.UserRole,pin['id']);text.setFlag(QGraphicsItem.ItemIgnoresTransformations,False);tip=(self.owner.host.preview_html(pin['target']) if target else '<b>'+html.escape(title)+'</b>')+'<p>'+html.escape(pin['note'])+'</p>';item.setToolTip(tip);text.setToolTip(tip);self.items_by_id[pin['id']]=item
        if keep:self.setTransform(transform);self.centerOn(center)
        else:self.fit_timer.start(0)
    def fit(self):
        if self.owner.dimensions!=(0,0):self.fitInView(self.scene_data.sceneRect(),Qt.KeepAspectRatio)
class PinDialog(QDialog):
    def __init__(self,host,pin=None):
        super().__init__(host);self.host=host;self.target=(pin or {}).get('target','');self.setWindowTitle(tr('Kartenmarkierung'));layout=QVBoxLayout(self);form=QFormLayout();self.name=QLineEdit((pin or {}).get('name',''));self.note=QTextEdit();self.note.setAcceptRichText(False);self.note.setPlainText((pin or {}).get('note',''));form.addRow(tr('Name'),self.name);form.addRow(tr('Notiz'),self.note);layout.addLayout(form);self.link_name=label('');layout.addWidget(self.link_name);row=QHBoxLayout();link=QPushButton(tr('@ Verknüpfen'));link.clicked.connect(self.choose);row.addWidget(link);remove=QPushButton(tr('Verweis entfernen'));remove.clicked.connect(lambda:(setattr(self,'target',''),self.update_link()));row.addWidget(remove);layout.addLayout(row);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons);self.resize(570,420);self.update_link()
    def update_link(self):
        target=resolve(self.host.p,self.target);self.link_name.setText((target or {}).get('name',tr('[Gelöschter Eintrag]') if self.target else tr('Kein verknüpfter Eintrag')));self.name.setReadOnly(bool(self.target))
        if target:self.name.setText(target['name'])
    def choose(self):
        from app import Picker
        picker=Picker(self.host)
        if picker.exec():self.target=picker.id;self.update_link();self.name.setText(self.name.text() or resolve(self.host.p,self.target)['name'])
    def save(self):
        if self.name.text().strip():self.accept()
class MapBrowser(QWidget):
    worldmap_page=True;section='world'
    def __init__(self,host):
        super().__init__(host);self.host=host;self.dimensions=(0,0);self.seen_revision=-1;self._selected=None;self._loading=False;layout=QVBoxLayout(self);layout.setContentsMargins(24,20,24,20);layout.addWidget(label(tr('Deine Welt auf einen Blick'),'title'));row=QHBoxLayout();self.maps=ArrowCombo();row.addWidget(self.maps,1)
        for title,fn in [('Karte hinzufügen',self.add_map),('Karte umbenennen',self.rename_map),('Karte löschen',self.delete_map)]:b=QPushButton(tr(title));b.clicked.connect(fn);row.addWidget(b)
        layout.addWidget(self.scroll_row(row));split=QSplitter();left=QWidget();side=QVBoxLayout(left);self.search=QLineEdit();self.search.setPlaceholderText(tr('Markierungen suchen'));side.addWidget(self.search);self.list=RoomyList();side.addWidget(self.list,1);left.setMaximumWidth(330);split.addWidget(left);self.view=MapView(self);split.addWidget(self.view);split.setStretchFactor(1,1);layout.addWidget(split,1);row=QHBoxLayout();self.edit=QCheckBox(tr('Markierungen bearbeiten'));self.edit.toggled.connect(self.edit_mode);row.addWidget(self.edit)
        for title,fn in [('Markierung hinzufügen',lambda:self.create_pin(.5,.5)),('Markierung bearbeiten',self.edit_pin),('Markierung löschen',self.delete_pin),('Eintrag öffnen',self.open_target),('Einpassen',self.view.fit)]:b=QPushButton(tr(title));b.clicked.connect(fn);row.addWidget(b)
        layout.addWidget(self.scroll_row(row));notice=label(tr('Mausrad: zoomen · Ziehen: Karte verschieben · Im Bearbeitungsmodus: auf die Karte klicken oder Markierungen ziehen. Doppelklick öffnet den Eintrag.'));notice.setWordWrap(True);layout.addWidget(notice);self.maps.currentIndexChanged.connect(self.map_changed);self.search.textChanged.connect(self.refresh_list);self.list.currentRowChanged.connect(self.list_selected);self.list.itemActivated.connect(lambda _:self.open_target());self.refresh_data();controls=layout.takeAt(3).widget();layout.insertWidget(2,controls);from community_ui import scroll_content;scroll_content(self,layout)
    def scroll_row(self,row):
        body=QWidget();body.setLayout(row);area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QFrame.NoFrame);area.setWidget(body);area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);area.setFixedHeight(82);return area
    def current_map(self):return next((m for m in self.host.p.get('maps',[]) if m['id']==self.maps.currentData()),None)
    def pin(self,id):return next((p for p in (self.current_map() or {}).get('pins',[]) if p['id']==id),None)
    def refresh_data(self):
        if self.seen_revision==self.host.revision:return
        old=self.maps.currentData();self._loading=True;self.maps.clear()
        for m in self.host.p.get('maps',[]):self.maps.addItem(m['name'],m['id'])
        self.maps.setCurrentIndex(max(0,self.maps.findData(old)));self._loading=False;self.refresh_list();self.view.draw_map(keep=bool(old));self.seen_revision=self.host.revision
    def map_changed(self,*_):
        if self._loading:return
        self._selected=None;self.refresh_list();self.view.draw_map()
    def refresh_list(self,*_):
        query=self.search.text().casefold();m=self.current_map();self.list.blockSignals(True);self.list.clear();self.visible=[]
        for p in (m or {}).get('pins',[]):
            target=resolve(self.host.p,p['target']) if p['target'] else None;name=target['name'] if target else p['name']
            if query not in (name+' '+p['note']).casefold():continue
            self.visible.append(p);self.list.addItem(name)
        row=next((i for i,p in enumerate(self.visible) if p['id']==self._selected),-1);self.list.setCurrentRow(row);self.list.blockSignals(False)
    def list_selected(self,row):
        if not 0<=row<len(self.visible):return
        self._selected=self.visible[row]['id'];item=self.view.items_by_id.get(self._selected)
        if item:self.view.scene_data.clearSelection();item.setSelected(True);self.view.centerOn(item)
    def select_pin(self,id):
        self._selected=id;self.refresh_list()
        item=self.view.items_by_id.get(id)
        if item:self.view.scene_data.clearSelection();item.setSelected(True)
    def edit_mode(self,enabled):self.view.edit=enabled;self.view.draw_map(keep=True)
    def add_map(self):
        name,ok=QInputDialog.getText(self,tr('Karte hinzufügen'),tr('Name:'))
        if not ok or not name.strip():return
        path,_=QFileDialog.getOpenFileName(self,tr('Kartenbild auswählen'),'','Bilder (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path:return
        try:
            staged={'assets':dict(self.host.p['assets'])};key=import_image(staged,path);m=new_map(name,key);self.host.p['assets'].update(staged['assets']);self.host.p.setdefault('maps',[]).append(m);self.host.changed();self.refresh_data();self.maps.setCurrentIndex(self.maps.findData(m['id']))
        except Exception as e:self.host.error(e)
    def rename_map(self):
        m=self.current_map()
        if not m:return
        name,ok=QInputDialog.getText(self,tr('Karte umbenennen'),tr('Name:'),text=m['name'])
        if ok and name.strip():m['name']=name.strip();self.host.changed();self.refresh_data()
    def delete_map(self):
        m=self.current_map()
        if m and QMessageBox.question(self,tr('Karte löschen'),tr('Karte und ihre Markierungen entfernen? Welt-Einträge bleiben erhalten.'))==QMessageBox.Yes:
            try:self.host.backups.create(self.host.p,self.host.path,'Vor Karten-Löschung');self.host.p['maps'].remove(m);self.host.changed();self.refresh_data()
            except Exception as e:self.host.error(e)
    def create_pin(self,x,y):
        m=self.current_map()
        if not m:return
        d=PinDialog(self.host)
        if d.exec():add_pin(m,d.name.text(),x,y,d.target,d.note.toPlainText());self.host.changed();self.refresh_data()
    def edit_pin(self):
        p=self.pin(self._selected)
        if not p:return
        d=PinDialog(self.host,p)
        if d.exec():p.update(name=d.name.text().strip(),target=d.target,note=d.note.toPlainText());self.host.changed();self.refresh_data()
    def delete_pin(self):
        p=self.pin(self._selected);m=self.current_map()
        if p and QMessageBox.question(self,tr('Markierung löschen'),tr('Markierung entfernen?'))==QMessageBox.Yes:m['pins'].remove(p);self.host.changed();self.refresh_data()
    def open_target(self):
        p=self.pin(self._selected)
        if p and p['target']:
            if resolve(self.host.p,p['target']):self.host.open_object(p['target'])
            else:self.host.error(ValueError('Der verknüpfte Eintrag wurde gelöscht.'))

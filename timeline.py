"""Calendar-based timeline: true viewport zoom, panning and screen-space clusters."""
import math,bisect,heapq
from PySide6.QtCore import Qt,QRectF,QPointF,Signal
from PySide6.QtGui import QPainter,QPen,QColor,QFont
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QScrollBar,QToolTip,QDialog,QPushButton
from ui import RoomyList
from PySide6.QtWidgets import QListWidgetItem
from core import Calendar
from design import theme_colors,CURRENT,tool,primary
from i18n import tr

def nice_step(value):
    if value<=1:return 1
    power=10**math.floor(math.log10(value))
    return next((n*power for n in (1,2,5,10) if n*power>=value),10*power)

def cluster_points(points,threshold=32):
    """Bound the size of a cluster; adjacent chains cannot swallow the whole axis."""
    groups=[]
    for x,event in sorted(points,key=lambda item:item[0]):
        if groups and x-groups[-1][0][0]<=threshold:groups[-1].append((x,event))
        else:groups.append([(x,event)])
    return groups

def era_lanes(eras):
    active=[];free=[];placed=[];count=0
    for start,end,event in sorted(eras,key=lambda row:(row[0],row[1],row[2]['id'])):
        while active and active[0][0]<start:heapq.heappush(free,heapq.heappop(active)[1])
        if free:lane=heapq.heappop(free)
        else:lane=count;count+=1
        heapq.heappush(active,(end,lane));placed.append((start,end,event,lane))
    return placed,count

class TimelineCanvas(QWidget):
    activated=Signal(str)
    viewChanged=Signal()
    def __init__(self,host):
        super().__init__();self.host=host;self.setMouseTracking(True);self.setMinimumHeight(450);self.setFocusPolicy(Qt.StrongFocus);self.setAccessibleName(tr('Zeitstrahl · Pfeile verschieben, Plus/Minus zoomen, Eingabe öffnet Ereignisse'))
        self.era_scroll=QScrollBar(Qt.Vertical,self);self.era_scroll.valueChanged.connect(lambda _:self.update());self.era_scroll.hide();self.hits=[];self.drag=None;self.points=[];self.spans=[];self.eras=[];self.total_lanes=0;self.begin=0.;self.end=1.;self.minimum=0.;self.maximum=1.;self.set_project()
    def set_project(self,keep_view=False):
        self.cal=Calendar(self.host.p['calendar']);events=self.host.p['events'];spans=[];self.invalid=[]
        for e in events:
            try:spans.append((*self.cal.span(e['start'],e['end']),e))
            except (ValueError,KeyError,IndexError):self.invalid.append(e)
        self.eras,self.total_lanes=era_lanes([row for row in spans if row[2]['kind']=='Zeitalter']);self.points=sorted([(a,e) for a,b,e in spans if e['kind']!='Zeitalter'],key=lambda item:item[0]);self.point_values=[a for a,e in self.points];self._cluster_cache=None;self.spans=[row for row in spans if row[2]['kind']!='Zeitalter' and row[0]!=row[1]]
        lo=min((a for a,b,e in spans),default=0);hi=max((b for a,b,e in spans),default=10);pad=max(1,(hi-lo)*.06);self.minimum=lo-pad;self.maximum=max(hi+pad,self.minimum+2)
        self.era_scroll.setRange(0,max(0,self.total_lanes-5));self.era_scroll.setVisible(self.total_lanes>5)
        if not keep_view:self.fit()
        else:self.set_view(self.begin,self.end)
    def plot(self):return QRectF(34,0,max(1,self.width()-70),self.height())
    def x(self,value):return self.plot().left()+(value-self.begin)*self.plot().width()/(self.end-self.begin)
    def date_at(self,x):return self.begin+(x-self.plot().left())*(self.end-self.begin)/self.plot().width()
    def set_view(self,start,end):
        span=min(max(1.,end-start),self.maximum-self.minimum);start=max(self.minimum,min(start,self.maximum-span));self.begin=start;self.end=start+span;self.update();self.viewChanged.emit()
    def fit(self):self.set_view(self.minimum,self.maximum)
    def zoom(self,factor,anchor=None):
        anchor=(self.begin+self.end)/2 if anchor is None else max(self.begin,min(anchor,self.end));ratio=(anchor-self.begin)/(self.end-self.begin);span=(self.end-self.begin)/factor;self.set_view(anchor-span*ratio,anchor+span*(1-ratio))
    def pan(self,amount):self.set_view(self.begin+amount,self.end+amount)
    def ticks(self):
        target=max(2,int(self.plot().width()/160));span=self.end-self.begin
        year_days=sum(m['days'] for m in self.cal.c['months']) if self.cal.c['months'] else 1
        if not self.cal.c['months'] or span/target>year_days*.8:
            first=int(self.cal.date_from_ordinal(math.floor(self.begin)).split('/')[0]);last=int(self.cal.date_from_ordinal(math.ceil(self.end)).split('/')[0]);step=nice_step(max(1,(last-first)/target));ticks=[]
            for year in range(math.floor(first/step)*step,last+step+1,step):
                if year==0 and not self.cal.c['year_zero']:continue
                value=self.cal.ordinal(str(year) if not self.cal.c['months'] else f'{year}/1/1')
                if self.begin<=value<=self.end:ticks.append((value,str(year)))
            return ticks
        step=nice_step(span/target);first=math.ceil(self.begin/step)*step;out=[]
        for value in range(first,math.floor(self.end)+1,step):
            raw=self.cal.date_from_ordinal(value);out.append((value,self.cal.display(raw)))
        return out
    def clusters(self):
        key=(self.begin,self.end,self.width())
        if self._cluster_cache and self._cluster_cache[0]==key:return self._cluster_cache[1]
        lo=bisect.bisect_left(self.point_values,self.begin);hi=bisect.bisect_right(self.point_values,self.end);groups=cluster_points([(self.x(value),event) for value,event in self.points[lo:hi]]);self._cluster_cache=(key,groups);return groups
    def paintEvent(self,event):
        colors=theme_colors(CURRENT['mode'],CURRENT['accent']);accent=QColor(colors['accent']);fg=QColor(colors['text']);muted=QColor(colors['muted']);border=QColor(colors['border']);p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor(colors['paper']));plot=self.plot();self.hits=[]
        p.setFont(QFont('Segoe UI',9));ticks=self.ticks()
        for value,text in ticks:
            xx=self.x(value);p.setPen(QPen(border,1,Qt.DotLine));p.drawLine(QPointF(xx,43),QPointF(xx,self.height()-30));p.setPen(muted);p.drawText(QRectF(xx-75,10,150,26),Qt.AlignCenter,text)
        lanes=min(5,self.total_lanes);era_height=max(64,38+lanes*27);top=76
        p.setPen(muted);font=QFont('Segoe UI',8);font.setBold(True);p.setFont(font);p.drawText(QPointF(34,63),tr('ZEITALTER'))
        p.save();p.setClipRect(QRectF(33,69,plot.width()+1,era_height-24));offset=self.era_scroll.value()
        for a,b,e,lane in self.eras:
            if lane<offset or lane>=offset+5 or b<self.begin or a>self.end:continue
            xx=max(plot.left(),self.x(a));right=min(plot.right(),self.x(b));yy=top+(lane-offset)*27;rect=QRectF(xx,yy,max(5,right-xx),10);fill=QColor(accent);fill.setAlpha(100);p.setPen(Qt.NoPen);p.setBrush(fill);p.drawRoundedRect(rect,5,5);p.setPen(fg);p.setFont(QFont('Segoe UI',8));text=p.fontMetrics().elidedText(e['name'],Qt.ElideRight,max(1,int(right-xx-10)));p.drawText(QRectF(xx+4,yy+7,max(1,right-xx-8),20),Qt.AlignLeft|Qt.AlignVCenter,text);self.hits.append((QRectF(xx,yy-3,max(8,right-xx),26),[e]))
        p.restore();baseline=76+era_height+80;p.setPen(QPen(border,1));p.drawLine(QPointF(plot.left(),baseline),QPointF(plot.right(),baseline));p.setPen(muted);p.setFont(font);p.drawText(QPointF(34,baseline-46),tr('EREIGNISSE'))
        for a,b,e in self.spans:
            if b<self.begin or a>self.end:continue
            fill=QColor(accent);fill.setAlpha(45);p.setPen(QPen(fill,3));p.drawLine(QPointF(max(plot.left(),self.x(a)),baseline+31),QPointF(min(plot.right(),self.x(b)),baseline+31));self.hits.append((QRectF(max(plot.left(),self.x(a)),baseline+24,max(8,min(plot.right(),self.x(b))-max(plot.left(),self.x(a))),14),[e]))
        groups=self.clusters()
        for group in groups:
            xx=sum(x for x,e in group)/len(group);count=len(group);radius=16 if count>1 else 6;p.setPen(QPen(QColor(colors['paper']),3));p.setBrush(accent);p.drawEllipse(QPointF(xx,baseline),radius,radius)
            if count>1:
                p.setPen(QColor('#16212b') if accent.lightness()>150 else QColor('white'));p.setFont(QFont('Segoe UI',9,QFont.Bold));p.drawText(QRectF(xx-radius,baseline-radius,2*radius,2*radius),Qt.AlignCenter,str(count))
            self.hits.append((QRectF(xx-max(12,radius),baseline-max(12,radius),2*max(12,radius),2*max(12,radius)),[e for x,e in group]))
        p.setPen(muted);p.setFont(QFont('Segoe UI',9));p.drawText(QRectF(34,baseline+55,plot.width(),36),Qt.AlignLeft|Qt.AlignVCenter,tr('Punkt anklicken · Gruppen öffnen · Mausrad zoomt · Ziehen verschiebt'))
        if not self.points:p.drawText(QRectF(34,baseline-20,plot.width(),40),Qt.AlignCenter,tr('Noch keine Ereignisse.'))
        self.era_scroll.setGeometry(self.width()-18,72,12,max(26,era_height-24));p.end()
    def keyPressEvent(self,event):
        key=event.key()
        if key==Qt.Key_Left:self.pan(-(self.end-self.begin)/5)
        elif key==Qt.Key_Right:self.pan((self.end-self.begin)/5)
        elif key in [Qt.Key_Plus,Qt.Key_Equal]:self.zoom(1.5)
        elif key==Qt.Key_Minus:self.zoom(1/1.5)
        elif key==Qt.Key_Home:self.fit()
        elif key in [Qt.Key_Return,Qt.Key_Enter]:self.choose([e for value,e in self.points if self.begin<=value<=self.end]) if self.points else None
        else:super().keyPressEvent(event);return
        event.accept()
    def wheelEvent(self,event):
        if event.modifiers()&Qt.ShiftModifier or abs(event.angleDelta().x())>abs(event.angleDelta().y()):self.pan(-((event.angleDelta().x() or event.angleDelta().y())/120)*(self.end-self.begin)*.15)
        else:self.zoom(1.35**(event.angleDelta().y()/120),self.date_at(event.position().x()))
        event.accept()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self.drag=(event.position(),self.begin,self.end);self.setCursor(Qt.ClosedHandCursor)
    def mouseMoveEvent(self,event):
        if self.drag:
            point,a,b=self.drag;shift=(point.x()-event.position().x())*(b-a)/self.plot().width();self.set_view(a+shift,b+shift)
        else:self.setCursor(Qt.PointingHandCursor if self.hit(event.position()) else Qt.OpenHandCursor)
    def hit(self,pos):
        found={}
        for rect,events in self.hits:
            if rect.contains(pos):found.update({event['id']:event for event in events})
        return list(found.values()) or None
    def mouseReleaseEvent(self,event):
        if self.drag:
            point,a,b=self.drag;self.drag=None;self.setCursor(Qt.OpenHandCursor)
            if (point-event.position()).manhattanLength()<5:
                events=self.hit(event.position())
                if events:self.choose(events)
    def event(self,event):
        from PySide6.QtCore import QEvent
        if event.type()==QEvent.ToolTip:
            events=self.hit(event.pos())
            if events:
                import html
                text=self.host.preview_html(events[0]['id']) if len(events)==1 else '<b>'+str(len(events))+' '+tr('Ereignisse')+'</b><br/>'+'<br/>'.join(html.escape(e['name']) for e in events[:8]);QToolTip.showText(event.globalPos(),text,self);return True
        return super().event(event)
    def choose(self,events):
        if len(events)==1:self.activated.emit(events[0]['id']);return
        d=QDialog(self);d.setWindowTitle(str(len(events))+' '+tr('Ereignisse'));layout=QVBoxLayout(d);ls=RoomyList();layout.addWidget(ls)
        for e in events:
            item=QListWidgetItem(e['name']+' · '+self.cal.display(e['start']));item.setData(Qt.UserRole,e['id']);item.setToolTip(self.host.preview_html(e['id']));ls.addItem(item)
        def open_current():
            if ls.currentItem():self.activated.emit(ls.currentItem().data(Qt.UserRole));d.accept()
        ls.itemDoubleClicked.connect(lambda _:open_current());ls.itemActivated.connect(lambda _:open_current());
        if ls.count():ls.setCurrentRow(0)
        layout.addWidget(primary(tr('Öffnen'),open_current));d.resize(520,360);d.exec()

class TimelinePanel(QWidget):
    def __init__(self,host):
        super().__init__();layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(14);bar=QHBoxLayout();self.range_label=QLabel();bar.addWidget(self.range_label);bar.addStretch();layout.addLayout(bar);self.canvas=TimelineCanvas(host)
        left=QPushButton('←');left.setToolTip(tr('Nach links'));left.clicked.connect(lambda:self.canvas.pan(-(self.canvas.end-self.canvas.begin)/3));bar.addWidget(left);right=QPushButton('→');right.setToolTip(tr('Nach rechts'));right.clicked.connect(lambda:self.canvas.pan((self.canvas.end-self.canvas.begin)/3));bar.addWidget(right);minus=QPushButton('−');minus.setFixedWidth(42);minus.clicked.connect(lambda:self.canvas.zoom(1/1.5));bar.addWidget(minus);plus=QPushButton('+');plus.setFixedWidth(42);plus.clicked.connect(lambda:self.canvas.zoom(1.5));bar.addWidget(plus);fit=QPushButton(tr('Alles zeigen'));fit.clicked.connect(self.canvas.fit);bar.addWidget(fit);layout.addWidget(self.canvas,1)
        self.scroll=QScrollBar(Qt.Horizontal);self.scroll.setObjectName('timelineScroll');self.scroll.setRange(0,100000);self.scroll.valueChanged.connect(self.scroll_changed);layout.addWidget(self.scroll);self.canvas.viewChanged.connect(self.sync);self.canvas.activated.connect(host.open_object);self.sync()
    def sync(self):
        from PySide6.QtCore import QSignalBlocker
        c=self.canvas;span=c.end-c.begin;total=c.maximum-c.minimum;available=total-span;block=QSignalBlocker(self.scroll);self.scroll.setRange(0,100000 if available>1e-9 else 0);self.scroll.setPageStep(max(1,int(100000*span/max(1,total))));self.scroll.setValue(int(100000*(c.begin-c.minimum)/available) if available>1e-9 else 0);a=c.cal.display(c.cal.date_from_ordinal(math.floor(c.begin)));b=c.cal.display(c.cal.date_from_ordinal(math.floor(c.end)));self.range_label.setText(a+'  —  '+b)
    def scroll_changed(self,value):
        c=self.canvas;span=c.end-c.begin;available=c.maximum-c.minimum-span;start=c.minimum+value/100000*available;c.set_view(start,start+span)

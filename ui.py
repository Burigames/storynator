"""Controls with explicit hit targets and a useful minimum viewport."""
from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QPainter,QPen,QColor
from PySide6.QtWidgets import (QListWidget,QTableWidget,QTreeWidget,QComboBox,QFontComboBox,QSpinBox,QDoubleSpinBox,QStyleOptionSpinBox,QStyle,QAbstractItemView,QSizePolicy,QStyledItemDelegate,QStyleOptionViewItem,QStylePainter,QStyleOptionComboBox,QApplication)

def roomy(view,rows=4):
    height=max(38,view.fontMetrics().height()+20)
    extra=28
    if isinstance(view,QTableWidget):
        view.verticalHeader().setDefaultSectionSize(height);extra+=view.horizontalHeader().height()
    view.setMinimumHeight(height*rows+extra);view.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
    return view

class RoomyList(QListWidget):
    def __init__(self,*args):super().__init__(*args);roomy(self);self.setUniformItemSizes(True)
class RoomyTable(QTableWidget):
    def __init__(self,*args):
        super().__init__(*args);roomy(self);self.setWordWrap(False);self.verticalHeader().sectionResized.connect(self.fit_rows);self.horizontalHeader().geometriesChanged.connect(self.fit_rows);self.fit_rows()
    def fit_rows(self,*args):
        height=max([self.verticalHeader().defaultSectionSize(),38]+[self.rowHeight(r) for r in range(min(4,self.rowCount()))]);minimum=4*height+self.horizontalHeader().height()+40
        if self.minimumHeight()!=minimum:self.setMinimumHeight(minimum)
class RoomyTree(QTreeWidget):
    def __init__(self,*args):super().__init__(*args);roomy(self,5);self.setUniformRowHeights(True)

class TranslatedDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        from i18n import tr
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);opt.text=tr(opt.text) if self.parent().property('translateItems') else opt.text
        style=opt.widget.style() if opt.widget else QApplication.style();style.drawControl(QStyle.CE_ItemViewItem,opt,painter,opt.widget)

def paint_arrow(widget):
    painter=QPainter(widget);painter.setRenderHint(QPainter.Antialiasing);painter.setPen(QPen(widget.palette().text().color(),1.6));x=widget.width()-17;y=widget.height()/2;painter.drawLine(int(x-4),int(y-2),int(x),int(y+2));painter.drawLine(int(x),int(y+2),int(x+4),int(y-2));painter.end()
class ArrowCombo(QComboBox):
    def __init__(self,*args):super().__init__(*args);self.setItemDelegate(TranslatedDelegate(self));self.setMaxVisibleItems(12)
    def paintEvent(self,event):
        from i18n import tr
        painter=QStylePainter(self);opt=QStyleOptionComboBox();self.initStyleOption(opt);opt.currentText=tr(opt.currentText) if self.property('translateItems') else opt.currentText;painter.drawComplexControl(QStyle.CC_ComboBox,opt);painter.drawControl(QStyle.CE_ComboBoxLabel,opt);painter.end();paint_arrow(self)
class ArrowFontCombo(QFontComboBox):
    def paintEvent(self,event):super().paintEvent(event);paint_arrow(self)

def paint_steps(widget):
    opt=QStyleOptionSpinBox();widget.initStyleOption(opt);p=QPainter(widget);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(widget.palette().text().color(),1.5))
    for control,up in [(QStyle.SC_SpinBoxUp,True),(QStyle.SC_SpinBoxDown,False)]:
        rect=widget.style().subControlRect(QStyle.CC_SpinBox,opt,control,widget);x=rect.center().x();y=rect.center().y();delta=-2 if up else 2;p.drawLine(x-3,y-delta,x,y+delta);p.drawLine(x,y+delta,x+3,y-delta)
    p.end()
class ArrowSpin(QSpinBox):
    def paintEvent(self,event):super().paintEvent(event);paint_steps(self)
class ArrowDoubleSpin(QDoubleSpinBox):
    def paintEvent(self,event):super().paintEvent(event);paint_steps(self)

class FontSizeSpin(ArrowDoubleSpin):
    def __init__(self,*args):super().__init__(*args);self.setDecimals(2);self.setSingleStep(1)
    def textFromValue(self,value):
        return self.locale().toString(value,'f',2).rstrip('0').rstrip(self.locale().decimalPoint())

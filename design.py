"""Shared visual language: editorial type, quiet surfaces and vector icons."""
from pathlib import Path
from functools import lru_cache
import re
from PySide6.QtCore import QSettings
from i18n import tr
from PySide6.QtCore import Qt, QSize, QByteArray, QRectF
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QPalette
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QPushButton, QFrame, QGraphicsDropShadowEffect

PATHS={
 'book':'M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4z M22 4h-6a3 3 0 0 0-3 3v14a4 4 0 0 1 4-3h5z',
 'world':'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3c5 5 5 13 0 18 M12 3c-5 5-5 13 0 18',
 'timeline':'M4 4v16h17 M8 8h7 M11 12h9 M7 16h5',
 'search':'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
 'plus':'M12 5v14 M5 12h14',
 'save':'M5 3h12l4 4v14H3V3z M7 3v6h10V3 M7 21v-8h10v8',
 'folder':'M3 6h7l2 3h9v12H3z M3 6V4h7l2 2h9v3',
 'file':'M5 3h9l5 5v13H5z M14 3v6h5 M8 13h8 M8 17h6',
 'chevron':'M9 5l7 7-7 7',
 'arrow':'M5 12h14 M13 6l6 6-6 6',
 'feather':'M5 21l9-9 M8 17C3 5 15-1 21 3c1 7-3 16-13 14 M8 17l8-1 M11 13l1-7',
 'settings':'M5 7h14 M5 17h14 M9 4v6 M15 14v6',
 'image':'M3 4h18v16H3z M3 16l6-6 5 5 3-3 4 4 M17 8h.01',
 'link':'M9 15l6-6 M8 17l-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0 M16 7l2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0',
 'undo':'M8 5l-5 5 5 5 M3 10h10a6 6 0 0 1 6 9',
 'redo':'M16 5l5 5-5 5 M21 10H11a6 6 0 0 0-6 9',
 'print':'M7 8V3h10v5 M7 17H3V8h18v9h-4 M7 13h10v8H7z M17 11h.01',
 'left':'M4 5h16 M4 10h10 M4 15h16 M4 20h10',
 'center':'M4 5h16 M7 10h10 M4 15h16 M7 20h10',
 'right':'M4 5h16 M10 10h10 M4 15h16 M10 20h10',
 'justify':'M4 5h16 M4 10h16 M4 15h16 M4 20h16',
 'user':'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3',
 'check':'M5 12l4 4L20 5',
 'home':'M3 10l9-7 9 7 M5 9v12h14V9 M9 21v-8h6v8',
 'focus':'M3 8V3h5 M16 3h5v5 M21 16v5h-5 M8 21H3v-5',
 'break':'M4 4h16v5H4z M4 15h16v5H4z M2 12h20',
 'list':'M8 5h13 M8 12h13 M8 19h13 M3 5h.01 M3 12h.01 M3 19h.01',
 'edit':'M4 20l5-1L21 7l-4-4L5 15z M14 6l4 4',
 'more':'M5 12h.01 M12 12h.01 M19 12h.01',
}

def icon(name,color=None,size=22):
    color=color or theme_colors(CURRENT['mode'],CURRENT['accent'])['muted']
    return cached_icon(name,color,size)

@lru_cache(maxsize=256)
def cached_icon(name,color,size):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="-1 -1 27 27"><path d="{PATHS.get(name,PATHS["file"])}" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    pix=QPixmap(size*2,size*2);pix.fill(Qt.transparent);p=QPainter(pix);QSvgRenderer(QByteArray(svg.encode())).render(p);p.end();pix.setDevicePixelRatio(2);return QIcon(pix)

def label(text,role='body',translate=True):
    w=QLabel(tr(text) if translate else text);w.setProperty('role',role);return w

def tool(name,tip,fn,text=''):
    b=QToolButton();b.setProperty('iconName',name);b.setIcon(icon(name));b.setIconSize(QSize(19,19));b.setToolTip(tr(tip));b.setCursor(Qt.PointingHandCursor);b.setFocusPolicy(Qt.StrongFocus);b.setAccessibleName(tr(text or tip));b.clicked.connect(fn)
    if text:b.setText(tr(text));b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    return b

def primary(text,fn,name=None):
    b=QPushButton(tr(text));b.setProperty('role','primary');b.setCursor(Qt.PointingHandCursor);b.clicked.connect(fn)
    if name:b.setProperty('iconName',name);b.setIcon(icon(name,'#ffffff'))
    return b

def shadow(w):
    effect=QGraphicsDropShadowEffect(w);effect.setBlurRadius(32);effect.setOffset(0,6);effect.setColor(QColor(25,43,35,18));w.setGraphicsEffect(effect)

STYLE='''
* { selection-background-color:#d2e9dd; selection-color:#163e30; }
QMainWindow { background:#f3f4f0; }
QWidget { color:#283e35; }
QDialog { background:#f7f8f5; }
QLabel { background:transparent; }
QLabel[role="muted"] { color:#87948d; font-size:12px; }
QLabel[role="eyebrow"] { color:#84918a; font-size:10px; font-weight:600; letter-spacing:1.6px; }
QLabel[role="title"] { color:#203c30; font-size:27px; font-weight:600; }
QLabel[role="serif"] { font-family:"Georgia","DejaVu Serif"; color:#243e32; font-size:46px; }
QLabel[role="body"] { color:#687a70; font-size:14px; }
QWidget#sidebar { background:#192c26; }
QWidget#sidebar QLabel { color:#b2c2b7; }
QWidget#sidebar QLabel[role="eyebrow"] { color:#768f81; }
QLabel#brand { color:#f4f7ef; font-size:23px; font-weight:600; letter-spacing:-.6px; }
QFrame#projectCard { background:#233b30; border:1px solid #314c3c; border-radius:9px; }
QPushButton#navButton { color:#a9bfb0; border:0; text-align:left; background:transparent; padding:13px 15px; border-radius:7px; font-size:14px; }
QPushButton#navButton:hover { background:#243e31; color:white; }
QPushButton#navButton:checked { background:#34513e; color:#f5f5ec; font-weight:600; }
QTreeWidget#projectTree { background:transparent; color:#b8c9bc; border:0; outline:0; font-size:13px; }
QTreeWidget#projectTree::item { padding:10px 5px; border-radius:5px; }
QTreeWidget#projectTree::item:selected { background:#2a4636; color:#f7f7ee; }
QTreeWidget#projectTree::item:hover { background:#223d30; }
QTreeWidget#projectTree::branch { background:transparent; }
QWidget#sidebar QPushButton[role="subtle"] { color:#a9c4b1; background:#233b30; border:1px solid #34513e; text-align:left; }
QWidget#sidebar QToolButton { color:#a9c4b1; }
QFrame#header { background:#fbfcf9; border-bottom:1px solid #e0e5dd; }
QFrame#formatbar { background:#fbfcf9; border-bottom:1px solid #e1e5de; }
QFrame#paper { background:#fffefa; border:1px solid #e7e7dd; border-radius:3px; }
QFrame#context { background:#f3f4f0; border:0; }
QFrame#card { background:#fffefa; border:1px solid #e1e7dc; border-radius:12px; }
QFrame#hero { background:#e5eadf; border:1px solid #dae3d3; border-radius:16px; }
QPushButton { background:#fffefa; border:1px solid #dbe2d6; border-radius:6px; padding:10px 15px; color:#3c5445; font-weight:500; }
QPushButton:hover { background:#e9eee4; border-color:#b9cbb9; }
QPushButton:pressed { background:#dce6d5; }
QPushButton[role="primary"] { background:#365d43; color:white; border:1px solid #365d43; padding:11px 19px; }
QPushButton[role="primary"]:hover { background:#284c35; }
QPushButton[role="subtle"] { background:transparent; border:0; text-align:left; color:#607a65; }
QPushButton[role="chip"] { background:#ecf1e7; border:0; border-radius:12px; color:#4d6d50; padding:5px 10px; font-size:11px; }
QToolButton { background:transparent; border:0; border-radius:5px; padding:7px; }
QToolButton:hover,QToolButton:checked { background:#e5ecdf; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#fffefa; border:1px solid #dce4d6; border-radius:6px; padding:8px; min-height:18px; }
QLineEdit:focus,QComboBox:focus,QTextEdit:focus,QPlainTextEdit:focus { border-color:#7e9e79; }
QLineEdit#globalSearch { background:#f0f3ed; border:0; padding-left:12px; }
QComboBox::drop-down { border:0; width:28px; }
QComboBox { padding-right:30px; }
QComboBox::down-arrow { image:none; }
QSpinBox,QDoubleSpinBox { padding-right:24px; }
QSpinBox::up-button,QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:22px; height:18px; border:0; }
QSpinBox::down-button,QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:22px; height:18px; border:0; }
QSpinBox::up-arrow,QSpinBox::down-arrow,QDoubleSpinBox::up-arrow,QDoubleSpinBox::down-arrow { image:none; }
QToolButton { min-width:20px; min-height:20px; }
QPlainTextEdit { min-height:150px; }
QTextEdit,QPlainTextEdit,QListWidget,QTreeWidget,QTableWidget { background:#fffefa; border:1px solid #dce4d6; border-radius:7px; padding:8px; }
QTextEdit#manuscript { border:0; border-radius:0; padding:0; background:#fffefa; color:#303c33; }
QTextEdit#fieldEditor { min-height:130px; }
QScrollArea { border:0; background:transparent; }
QScrollArea>QWidget>QWidget { background:transparent; }
QTabWidget::pane { border:0; }
QTabBar { background:#f3f4f0; }
QTabBar::tab { color:#87948a; background:transparent; padding:14px 24px; border:0; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#2f573b; background:#fbfcf9; border-bottom:2px solid #597f52; }
QTabBar::tab:hover { color:#2f573b; }
QToolButton#tabClose { color:#8b9a87; font-size:18px; padding:0; margin:0; }
QToolButton#tabClose:hover { color:#344e35; background:#dfe8d8; }
QTabBar::close-button:hover { background:#e2e9dc; border-radius:6px; }
QMenuBar { background:#fbfcf9; color:#6c7d70; font-size:11px; padding:2px 6px; }
QMenuBar::item:selected { background:#e5ecdf; }
QMenu { background:#fffefa; border:1px solid #dce4d6; padding:6px; }
QMenu::item { padding:9px 26px; }
QMenu::item:selected { background:#e5ecdf; color:#24452e; }
QStatusBar { background:#fbfcf9; border-top:1px solid #e1e5de; color:#839080; font-size:11px; min-height:28px; }
QStatusBar::item { border:0; }
QHeaderView::section { background:#edf1e7; color:#647761; border:0; padding:11px; font-weight:500; }
QTableWidget { gridline-color:#eef0e9; }
QListWidget::item { padding:10px; border-radius:4px; }
QListWidget::item:selected { background:#e5eddf; color:#2f5437; }
QSplitter::handle { background:#e4e9df; width:1px; }
QScrollBar:vertical { border:0; background:transparent; width:8px; margin:2px; }
QScrollBar::handle:vertical { background:#c9d3c2; border-radius:4px; min-height:35px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QSlider::groove:horizontal { height:4px; background:#e1e8da; border-radius:2px; }
QSlider::handle:horizontal { width:15px; margin:-6px 0; background:#66885b; border-radius:8px; }
QCheckBox { spacing:8px; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #b9cbb0; border-radius:4px; background:white; }
QCheckBox::indicator:checked { background:#55794b; border-color:#55794b; }
QToolTip { background:#213e2d; color:white; border:0; padding:6px; }
'''

ACCENTS={'forest':('#365d43','#86ac77'),'ocean':('#235e87','#74b5de'),'lavender':('#70549b','#b29ae4'),'amber':('#8a5d19','#e5b568'),'rose':('#97536d','#df9ab8')}
CURRENT={'mode':'light','accent':'forest','link':'#365d43'}

def blend(a,b,ratio):
    a=QColor(a);b=QColor(b);return QColor(round(a.red()*(1-ratio)+b.red()*ratio),round(a.green()*(1-ratio)+b.green()*ratio),round(a.blue()*(1-ratio)+b.blue()*ratio)).name()

def theme_colors(mode,accent):
    dark=mode=='dark';base,bright=ACCENTS.get(accent,ACCENTS['forest']);paper='#20272f' if dark else '#ffffff';color=bright if dark else base
    return {'window':'#151b22' if dark else '#f3f5f8','paper':paper,'text':'#e2e8ef' if dark else '#263442','muted':'#a3afbd' if dark else '#647382','border':'#35414e' if dark else '#dfe5ec','accent':color,'selected':blend(paper,color,.18 if dark else .11),'sidebar':'#17212c'}

def apply_theme(app,mode=None,accent=None):
    settings=QSettings('Storynator','Storynator');mode=mode or settings.value('appearance/mode','light');accent=accent or settings.value('appearance/accent','forest');mode=mode if mode in ('light','dark') else 'light';accent=accent if accent in ACCENTS else 'forest';CURRENT.update(mode=mode,accent=accent);colors=theme_colors(mode,accent);CURRENT['link']=colors['accent'];base=ACCENTS[accent][0]
    roles={
      'paper':['#fffefa','#fbfcf9'],
      'window':['#f3f4f0','#f7f8f5'],
      'text':['#687a70','#283e35','#203c30','#243e32','#303c33','#3c5445','#24452e','#2f5437','#344e35','#163e30'],
      'muted':['#87948d','#84918a','#87948a','#6c7d70','#839080','#647761','#8b9a87'],
      'border':['#e0e5dd','#e1e5de','#e7e7dd','#e1e7dc','#dbe2d6','#dce4d6','#dae3d3','#b9cbb9','#eef0e9','#e4e9df','#b9cbb0','#c9d3c2'],
      'selected':['#e5eadf','#e9eee4','#dce6d5','#ecf1e7','#e5ecdf','#f0f3ed','#e2e9dc','#dfe8d8','#edf1e7','#e5eddf','#e1e8da','#d2e9dd'],
      'accent':['#607a65','#4d6d50','#2f573b','#597f52','#55794b','#7e9e79','#66885b']}
    replacements={value:colors[role] for role,values in roles.items() for value in values}
    replacements.update({'#365d43':base,'#284c35':QColor(base).darker(115).name(),'#192c26':colors['sidebar'],'#213e2d':colors['sidebar'],'#233b30':'#202e3c','#314c3c':'#324354','#34513e':blend(colors['sidebar'],base,.55),'#2a4636':blend(colors['sidebar'],base,.45),'#243e31':blend(colors['sidebar'],base,.3),'#223d30':blend(colors['sidebar'],base,.25),'#b2c2b7':'#c0cad5','#768f81':'#8294a6','#a9bfb0':'#b6c3cf','#b8c9bc':'#c0cad5','#a9c4b1':'#bdcbd9','#f4f7ef':'#f7f9fc','#f5f5ec':'#f7f9fc','#f7f7ee':'#f7f9fc'})
    style=re.sub(r'#[0-9a-fA-F]{6}',lambda match:replacements.get(match.group(),match.group()),STYLE)
    style+='\nQPushButton:focus,QToolButton:focus,QTreeWidget:focus,QListWidget:focus { border:2px solid '+colors['accent']+'; }'
    style+='\nQTextBrowser { background:transparent; border:0; } QProgressBar { background:'+colors['selected']+';border:0;border-radius:4px;height:8px; } QProgressBar::chunk { background:'+colors['accent']+';border-radius:4px; }'
    app.setStyle('Fusion');app.setFont(QFont('Segoe UI',10));app.setStyleSheet(style);palette=app.palette()
    for role,key in [(QPalette.Window,'window'),(QPalette.WindowText,'text'),(QPalette.Text,'text'),(QPalette.Base,'paper'),(QPalette.Button,'paper'),(QPalette.ButtonText,'text'),(QPalette.Highlight,'selected'),(QPalette.HighlightedText,'text'),(QPalette.ToolTipBase,'paper'),(QPalette.ToolTipText,'text')]:palette.setColor(role,QColor(colors[key]))
    palette.setColor(QPalette.Link,QColor(colors['accent']));palette.setColor(QPalette.PlaceholderText,QColor(colors['muted']));app.setPalette(palette)
    for widget in app.allWidgets():
        name=widget.property('iconName')
        if name and hasattr(widget,'setIcon'):widget.setIcon(icon(name,'#ffffff' if widget.property('role')=='primary' else colors['muted']))
        if hasattr(widget,'update_marks'):widget.update_marks()
        if widget.objectName() in ['brandMark','heroMark']:
            size=36 if widget.objectName()=='brandMark' else 180;widget.setPixmap(icon('feather',colors['accent'],size).pixmap(size,size))

"""Shared grouped template layout for reading and editing."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QGridLayout,QFrame,QLabel
from design import label
from i18n import tr
from worldmodel import missing_required

def fields_layout(host,entry,category,editing=False):
    from worldview import read_field
    box=QWidget();outer=QVBoxLayout(box);outer.setContentsMargins(0,0,0,0);outer.setSpacing(20);groups={}
    for field in category['fields']:groups.setdefault(field.get('group',''),[]).append(field)
    for name,fields in groups.items():
        if name:outer.addWidget(label(name,'eyebrow',False))
        area=QWidget();grid=QGridLayout(area);grid.setContentsMargins(0,0,0,0);grid.setSpacing(18);rows=[0,0];columns=2 if any(f.get('column',0)==1 for f in fields) else 1
        for field in fields:
            col=1 if field.get('column',0)==1 else 0;card=QFrame();card.setObjectName('card');layout=QVBoxLayout(card);layout.setContentsMargins(22,18,22,20);layout.setSpacing(10);heading=label(field['name']+(' *' if field.get('required') else ''),'eyebrow',False);layout.addWidget(heading);widget=host.field(entry,field) if editing else read_field(host,field,entry.get('values',{}).get(field['id']));widget.setAccessibleName(field['name']);layout.addWidget(widget)
            if field.get('help'):hint=label(field['help'],'muted',False);hint.setWordWrap(True);layout.addWidget(hint);widget.setAccessibleDescription(field['help'])
            grid.addWidget(card,rows[col],col);rows[col]+=1
        for col in range(columns):grid.setColumnStretch(col,1)
        outer.addWidget(area)
    return box

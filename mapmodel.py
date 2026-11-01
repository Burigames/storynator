"""Portable world-map data; normalized coordinates survive image resizing."""
import math
from core import uid

def validate_maps(project):
    maps=project.get('maps',[])
    if not isinstance(maps,list):raise ValueError('Ungültige Weltkartenliste.')
    ids=set()
    for m in maps:
        if not isinstance(m,dict) or any(not isinstance(m.get(k),str) for k in ['id','name','asset']) or not m['id'] or not m['name'].strip() or not isinstance(m.get('pins'),list):raise ValueError('Ungültige Weltkarte.')
        if m['id'] in ids:raise ValueError('Doppelte Kartenkennung.')
        ids.add(m['id'])
        for pin in m['pins']:
            if not isinstance(pin,dict) or any(not isinstance(pin.get(k),str) for k in ['id','name','target','note']) or not pin['id'] or not pin['name'].strip() or pin['id'] in ids or any(type(pin.get(k)) not in [int,float] or not math.isfinite(pin[k]) or not 0<=pin[k]<=1 for k in ['x','y']):raise ValueError('Ungültige Kartenmarkierung.')
            ids.add(pin['id'])
def new_map(name,asset):return dict(id=uid(),name=name.strip(),asset=asset,pins=[])
def add_pin(map,name,x,y,target='',note=''):
    pin=dict(id=uid(),name=name.strip(),x=x,y=y,target=target,note=note);draft={**map,'pins':map['pins']+[pin]};validate_maps({'maps':[draft]});map['pins'].append(pin);return pin

"""Bounded image imports, embedded resources and lightweight thumbnail decoding."""
import base64,hashlib
from pathlib import Path
from PySide6.QtCore import QBuffer,QByteArray,QIODevice,QSize,Qt
from PySide6.QtGui import QImage,QImageReader
from core import uid

def image_from_asset(p,key,edge=320):
    try:data=QByteArray(base64.b64decode(p['assets'].get(key,'')))
    except (ValueError,TypeError):return QImage()
    buffer=QBuffer(data);buffer.open(QIODevice.ReadOnly);reader=QImageReader(buffer);reader.setAutoTransform(True);size=reader.size()
    if size.isValid() and max(size.width(),size.height())>edge:reader.setScaledSize(size.scaled(edge,edge,Qt.KeepAspectRatio))
    return reader.read()

def store_image(p,image):
    if image.isNull():raise ValueError('Bild konnte nicht gelesen werden. Bitte PNG, JPEG oder WebP verwenden.')
    if max(image.width(),image.height())>4096:image=image.scaled(4096,4096,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);format='PNG' if image.hasAlphaChannel() else 'JPEG'
    if not image.save(buffer,format,92):raise ValueError('Bild konnte nicht eingebettet werden.')
    encoded=base64.b64encode(bytes(data)).decode()
    for key,value in p['assets'].items():
        if value==encoded:return key
    key=uid()+('.png' if format=='PNG' else '.jpg');p['assets'][key]=encoded;return key

def import_image(p,path):
    if Path(path).stat().st_size>100*1024**2:raise ValueError('Bilddatei ist zu groß (maximal 100 MB).')
    reader=QImageReader(str(path));reader.setAutoTransform(True);size=reader.size()
    if not size.isValid():raise ValueError('Bildformat konnte nicht gelesen werden.')
    if max(size.width(),size.height())>4096:reader.setScaledSize(size.scaled(4096,4096,Qt.KeepAspectRatio))
    return store_image(p,reader.read())

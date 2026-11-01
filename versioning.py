"""Exact published build version, independent of project file versions."""
import json,re,sys
from pathlib import Path
SOURCE_VERSION='0.8.1'
def version_tuple(value):
    if not isinstance(value,str) or not re.fullmatch(r'v?\d{1,6}\.\d{1,6}\.\d{1,6}',value):raise ValueError('Ungültige Versionsnummer.')
    return tuple(map(int,value.lstrip('v').split('.')))
def current_version():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    try:
        value=json.loads((root/'assets'/'release-info.json').read_text(encoding='utf-8'))['version'];version_tuple(value);return value
    except (OSError,ValueError,KeyError,TypeError):return SOURCE_VERSION

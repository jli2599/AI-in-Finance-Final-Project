"""Local JSON file repository. DEMO ONLY: not multiuser-safe, no authentication."""
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
STATE = DATA / 'app_state.json'


def read_json(path, default=None):
    p=Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default


def write_json(path, value):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.tmp',suffix='.json')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(value,f,indent=2,ensure_ascii=False)
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def load_state():
    s=read_json(STATE)
    if s is None:
        s=read_json(DATA/'app_seed.json',{})
        write_json(STATE,s)
    return s


def save_state(s):
    write_json(STATE,s)


def append_event(s, actor, action, details):
    from datetime import datetime,timezone
    s.setdefault('audit',[]).append({'time':datetime.now(timezone.utc).isoformat(timespec='seconds'),'actor':actor,'action':action,'details':details})

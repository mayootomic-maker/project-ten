"""Atomic writes, simple versioned snapshots and audit integrity checks."""
import json
import os
from pathlib import Path
from .engine import verify_chain

ROOT=Path(os.environ.get('PROJECT_TEN_ROOT',Path(__file__).resolve().parent.parent)).resolve()
DATA=ROOT/'data'
STATE=ROOT/'state'
REPORTS=ROOT/'reports'

def save_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)
        f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def load_json(path):
    with Path(path).open(encoding='utf-8') as f:return json.load(f)

def save_book(book):
    verify_chain(book['audit'])
    save_json(STATE/'book.json',book)

def load_book():
    book=load_json(STATE/'book.json')
    verify_chain(book['audit'])
    return book

"""Readable UTF-8 dashboard JSON with atomic writes without legacy-score import."""
import json,math,os,tempfile,unicodedata
from pathlib import Path

FILENAME='dashboard.json'

def clean_name(name):return ' '.join(unicodedata.normalize('NFKC',name).split())
def name_key(name):return clean_name(name).casefold()
def rank_key(row):return (-row['score'],-row['accuracy'],row['time'])
def unique_scores(rows):
    best={}
    for row in rows:
        key=name_key(row['name'])
        if key not in best or rank_key(row)<rank_key(best[key]):best[key]=row
    return sorted(best.values(),key=rank_key)

def merge_score(history,row):
    history=unique_scores(validate(history));row=validate([row])[0]
    existing=next((r for r in history if name_key(r['name'])==name_key(row['name'])),None)
    if existing is not None:
        if rank_key(row)>=rank_key(existing):return history,'kept'
        row['name']=existing['name']
        history=[r for r in history if name_key(r['name'])!=name_key(row['name'])]
    history=sorted(history+[row],key=rank_key)[:30]
    return history,'updated' if existing is not None else 'new'


def validate(rows):
    if not isinstance(rows,list):raise ValueError('Dashboard must contain a JSON array.')
    clean=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('name'),str) or not row['name'].strip():
            raise ValueError('Each score must have a player name.')
        for key in ('score','accuracy','time'):
            value=row.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError(f'Invalid score field: {key}.')
        if row['accuracy']>100:raise ValueError('Accuracy must be between 0 and 100.')
        record=dict(mode='Event',language='Python',challenge='Debug',difficulty=0,won=False)
        record.update(row);record['name']=clean_name(record['name'])
        if not record['name']:raise ValueError('Each score must have a player name.')
        clean.append(record)
    return clean

def write_scores(directory,rows):
    rows=unique_scores(validate(rows));directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    destination=directory/FILENAME;temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=directory,prefix='dashboard-',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(rows,stream,ensure_ascii=False,allow_nan=False,indent=2)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)

def load_scores(directory):
    directory=Path(directory);destination=directory/FILENAME
    if destination.exists():
        rows=validate(json.loads(destination.read_text(encoding='utf-8')))
        unique=unique_scores(rows)
        if unique!=rows:write_scores(directory,unique)
        return unique
    write_scores(directory,[])
    return []

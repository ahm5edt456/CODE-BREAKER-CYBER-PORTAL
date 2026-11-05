"""Readable UTF-8 dashboard JSON with atomic writes and legacy-score import."""
import json,math,os,tempfile
from pathlib import Path

FILENAME='dashboard.json'

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
        record.update(row);clean.append(record)
    return clean

def write_scores(directory,rows):
    rows=validate(rows);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    destination=directory/FILENAME;temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=directory,prefix='dashboard-',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(rows,stream,ensure_ascii=False,allow_nan=False,indent=2)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)

def load_scores(directory,legacy_file=None):
    directory=Path(directory);destination=directory/FILENAME
    if destination.exists():return validate(json.loads(destination.read_text(encoding='utf-8')))
    rows=[]
    if legacy_file is not None and Path(legacy_file).is_file():
        rows=validate(json.loads(Path(legacy_file).read_text(encoding='utf-8')))
    write_scores(directory,rows)
    return rows

"""Dashboard persistence, migration, UTF-8, and interrupted-write protection."""
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from score_store import load_scores,write_scores,FILENAME

def row(name='أحمد',score=100):
 return {'name':name,'score':score,'accuracy':100,'time':12,'mode':'Event','language':'Python','challenge':'Debug','difficulty':1,'won':True,'stages_completed':3}

with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);directory=root/'data'
 assert load_scores(directory)==[] and json.loads((directory/FILENAME).read_text())==[]
 write_scores(directory,[row()]);content=(directory/FILENAME).read_text(encoding='utf-8')
 assert 'أحمد' in content and '\\u0623' not in content
 assert load_scores(directory)[0]['name']=='أحمد'
 original=(directory/FILENAME).read_bytes()
 with patch('score_store.os.replace',side_effect=OSError('Simulated disk failure')):
  try:write_scores(directory,[row('NEW',200)])
  except OSError:pass
  else:raise AssertionError('Disk failure was ignored.')
 assert (directory/FILENAME).read_bytes()==original and not list(directory.glob('*.tmp'))
 # Preserve the previous save until the full new JSON is written successfully.
 write_scores(directory,[row('NEW',200),row()]);assert len(load_scores(directory))==2
 legacy=root/'legacy_scores.json';legacy.write_text(json.dumps([row('LEGACY')]))
 migrated=root/'migrated';assert load_scores(migrated)==[]
 assert legacy.exists() and json.loads((migrated/FILENAME).read_text())==[]
 # Explicitly cleared local results must not be reimported from the old file.
 write_scores(migrated,[]);assert load_scores(migrated)==[]
 (directory/FILENAME).write_text('{invalid',encoding='utf-8');bad=(directory/FILENAME).read_bytes()
 try:load_scores(directory)
 except ValueError:pass
 else:raise AssertionError('Corrupt JSON was accepted.')
 assert (directory/FILENAME).read_bytes()==bad
 for invalid in [{'name':'X','score':'wrong','time':1,'accuracy':10},{'name':'X','score':1,'time':1,'accuracy':float('nan')}]:
  try:write_scores(root/'invalid',[invalid])
  except ValueError:pass
  else:raise AssertionError('Invalid score was accepted.')
print('PASS: JSON round-trip, Arabic names, atomic disk failure, fresh resets, cleared records, malformed data protection.')

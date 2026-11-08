"""Speed rewards and one-best-score-per-normalized-name persistence."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import json,time,tempfile,concurrent.futures
from pathlib import Path
from unittest.mock import patch
from scoring import speed_bonus
from score_store import merge_score,load_scores,write_scores
import game as core
from campaign import CampaignGame

assert [speed_bonus(t) for t in (0,10,30,50,80)]==[100,80,40,0,0]
assert all(speed_bonus(t)>=speed_bonus(t+1) for t in range(80))

def settle(g):
 deadline=time.monotonic()+15
 while g.future:
  assert time.monotonic()<deadline
  time.sleep(.01);g.update(.001)

def record(name,score,accuracy=90,elapsed=20):
 return dict(name=name,score=score,accuracy=accuracy,time=elapsed)

for name in ['ahmed',' AHMED ','Ａｈｍｅｄ']:
 history,status=merge_score([record('Ahmed',100)],record(name,90))
 assert len(history)==1 and history[0]['score']==100 and status=='kept'
 history,status=merge_score(history,record(name,200))
 assert len(history)==1 and history[0]['score']==200 and history[0]['name']=='Ahmed' and status=='updated'
history,status=merge_score([record('أحمد علي',100)],record('  أحمد   علي  ',110));assert len(history)==1
history,status=merge_score([record('Ahmed',100,90,20)],record('AHMED',100,90,10));assert history[0]['time']==10

with tempfile.TemporaryDirectory() as directory:
 core.DATA=Path(directory)
 # An older JSON with duplicate spellings is cleaned on load, keeping the best.
 path=core.DATA/'dashboard.json';path.write_text(json.dumps([record('Ahmed',100),record(' AHMED ',200),record('ahmed',150)]))
 assert len(load_scores(core.DATA))==1 and json.loads(path.read_text())[0]['score']==200
 def end_game(name,score):
  g=CampaignGame();g.start();g.score=score;g.mode='lost';g.begin_name_entry();g.name=name;return g
 old=path.read_bytes();g=end_game('ahmed',150)
 with patch('game.write_scores',side_effect=AssertionError('Lower repeat must not rewrite JSON.')):g.save_result()
 assert g.result_saved and path.read_bytes()==old and 'Best score kept' in g.notice
 g=end_game('AHMED',250);g.save_result();saved=json.loads(path.read_text());assert len(saved)==1 and saved[0]['score']==250
 # The bonus clock persists through Back/reopen, excluding pause and runner time.
 g=CampaignGame();g.start();edge=next(iter(g.gates));g.open_editor(edge);settle(g)
 g.update(10);assert g.gates[edge]['solve_seconds']==10
 g.pause();g.update(20);g.resume();assert g.gates[edge]['solve_seconds']==10
 g.hint=True;g.close_editor();g.update(5);g.open_editor(edge);settle(g)
 assert g.gates[edge]['solve_seconds']==15 and g.hint
 expected=g.expected;g.future=concurrent.futures.Future();g.job='reference';g.update(5)
 assert g.gates[edge]['solve_seconds']==15
 g.future.set_result({'out':expected,'error':''});g.update(.001)
 g.evaluate(True);assert g.speed_bonus_total==70 and g.score==170
 assert g.solve_records[0]['seconds']==15
 # Actual solution speed affects the score; successful work is rewarded once.
 earned=[]
 for seconds in (10,40):
  g=CampaignGame();g.start();edge=next(iter(g.gates));g.open_editor(edge);settle(g);g.update(seconds)
  g.evaluate(True);score=g.score;g.evaluate(True);assert g.score==score
  earned.append(score)
 assert earned[0]>earned[1] and earned==[205,145]
 g.mode='lost';g.begin_name_entry();g.name='FAST';g.save_result()
 new=CampaignGame();row=next(r for r in new.history if r['name']=='FAST')
 assert row['speed_bonus']==20 and row['solve_times'][0]['seconds']==40
core.POOL.shutdown(wait=True)
print('PASS: speed curve, clock pause/run/back semantics, score once, duplicate normalization, best-score replacement, no lower-score write, legacy cleanup and persistence.')

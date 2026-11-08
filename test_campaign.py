"""Distributed gates, solvable ordered exploration, and automatic stage changes."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import tempfile,time,random,shutil,json
from pathlib import Path
import pygame
import game as core
from runner import execute
from campaign import CampaignGame,TOPICS
from campaign_questions import problem
from challenge_placement import distances

def settle(g):
 deadline=time.monotonic()+15
 while g.future:
  assert time.monotonic()<deadline
  time.sleep(.01);g.update(.001)

def walk(g,path):
 for a,b in zip(path,path[1:]):
  assert g.player==a
  step=(b[0]-a[0],b[1]-a[1]);key={(1,0):pygame.K_d,(-1,0):pygame.K_a,(0,1):pygame.K_s,(0,-1):pygame.K_w}[step]
  class Keys:
   def __getitem__(self,k):return k==key
  old=pygame.key.get_pressed;pygame.key.get_pressed=lambda:Keys()
  try:g.move_wait=0;g.update(.005)
  finally:pygame.key.get_pressed=old
  assert g.player==b
  if g.mode=='editor':settle(g)

with tempfile.TemporaryDirectory() as folder:
 core.DATA=Path(folder)
 # Placement is spread out, well outside spawn, and solvable in increasing order.
 layouts=set()
 for _ in range(100):
  g=CampaignGame();g.start();root,parent=distances(g.maze.maze,(0,0));assert len(root)==117
  edges=list(g.gates);children=[max(edge,key=root.get) for edge in edges]
  a,b=children
  assert all(sum(p)>=9 and root[p]>=12 for p in children)
  assert abs(a[0]-b[0])+abs(a[1]-b[1])>=10
  assert (a[0]>=6,a[1]>=4)!=(b[0]>=6,b[1]>=4)
  initial,_=distances(g.maze.maze,(0,0),blocked=edges)
  assert parent[a] in initial
  after_first,_=distances(g.maze.maze,parent[a],blocked=[edges[1]])
  assert parent[b] in after_first and after_first[parent[b]]>=14
  assert all(p in initial for p in g.energy)
  layouts.add(tuple(edges))
 assert len(layouts)>30
 print('PASS: 100 varied, distributed, ordered and reachable gate layouts')
 # Every concept and mode has a working reference and a genuinely faulty initial state.
 for language in ['Python','C++','Java']:
  if language=='C++' and not shutil.which('g++'):continue
  if language=='Java' and not shutil.which('javac'):continue
  for rank in range(len(TOPICS)):
   for kind in ['Debug','Complete Code']:
    q=problem(language,rank,kind,random.Random(rank+8));r=execute(q['answer'],language)
    assert not r['error'],(language,rank,r)
    bad=execute(q['code'],language);assert bad['error'] or bad['out']!=r['out']
 # Play the entire campaign by walking through real maze passages.
 g=CampaignGame();g.start();g.lives=2;topics=[];expected_topics=[TOPICS[t] for t in g.question_plan]
 for stage in range(3):
  assert g.level==stage and g.remaining==120 and g.lives==2
  assert [gate['difficulty'] for gate in g.gates.values()]==[stage*2,stage*2+1]
  edges=list(g.gates)
  g.open_editor(edges[1]);assert g.mode=='maze','The harder challenge cannot be opened first.'
  for index,edge in enumerate(edges):
   route=g.route_to_goal();assert len(route)>1
   walk(g,route)
   if g.mode!='editor':g.open_editor(edge);settle(g)
   gate=g.gates[edge];assert g.active_gate==edge
   topics.append(gate['question']['title']);g.lines=gate['question']['answer'].split('\n')
   g.run_code(True);settle(g)
   assert g.player!=(0,0),'Finishing does not require returning to spawn.'
   if index==0:assert g.mode=='maze'
  if stage<2:
   assert g.mode=='stage_clear' and g.correct==(stage+1)*2
   score=g.score;g.complete_stage();assert g.score==score
   g.draw();g.update(.3);g.draw()
   if stage==0:pygame.image.save(pygame.display.get_surface(),'preview_stage_clear.png')
   g.update(1.3);assert g.mode=='maze' and g.level==stage+1 and g.remaining==120
  else:assert g.mode=='name_entry' and g.outcome=='won' and g.correct==6
 assert topics==expected_topics
 g.draw();g.update(.3);g.draw();g.handle(pygame.event.Event(pygame.TEXTINPUT,text='AHMED'))
 g.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN,mod=0))
 assert g.result_saved and json.loads((core.DATA/'dashboard.json').read_text())[0]['stages_completed']==3
 # Complete Code progression also advances without movement back to spawn.
 g=CampaignGame();g.challenge='Complete Code';g.start()
 for edge in list(g.gates):
  g.open_editor(edge);settle(g);gate=g.gates[edge];assert 'TODO' in gate['question']['code']
  g.lines=gate['question']['answer'].split('\n');g.run_code(True);settle(g)
 assert g.mode=='stage_clear';g.update(1.3);assert g.level==1 and g.mode=='maze'
 # Pause and the deadline are unchanged.
 g.pause();remaining=g.remaining;g.update(10);assert g.remaining==remaining
 g.resume();g.remaining=.01;g.update(.02);assert g.mode=='name_entry' and g.outcome=='lost'
 g=CampaignGame();g.start();g.draw();g.update(.3);g.draw();pygame.image.save(pygame.display.get_surface(),'preview_maze.png')
 g.open_editor(next(iter(g.gates)));settle(g);g.draw();g.update(.3);g.draw();pygame.image.save(pygame.display.get_surface(),'preview_editor.png')
 g.go('menu',3);g.draw();g.update(.3);g.draw();pygame.image.save(pygame.display.get_surface(),'preview_menu.png')
core.POOL.shutdown(wait=True)
print('PASS: all puzzle concepts, full walking campaign, auto-advance, ordered difficulty, both modes, pause/deadline, named final score')

"""Headless regressions for event controls, progression, and named scores."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import json,time,tempfile,shutil
from pathlib import Path
import pygame
import game as app
from runner import execute
from questions import build_questions

def settle(g):
 deadline=time.monotonic()+15
 while g.future:
  assert time.monotonic()<deadline,'runner stalled'
  time.sleep(.01);g.update(.001)

def key(g,k,mod=0):
 g.handle(pygame.event.Event(pygame.KEYDOWN,key=k,mod=mod));g.draw()

with tempfile.TemporaryDirectory() as directory:
 app.DATA=Path(directory)/'scores'
 g=app.Game();g.draw();assert g.nav_focus==3
 key(g,pygame.K_UP);key(g,pygame.K_RIGHT);assert g.language=='Java'
 key(g,pygame.K_DOWN);key(g,pygame.K_DOWN);key(g,pygame.K_RETURN)
 assert g.mode=='settings' and len(g.buttons)==4
 key(g,pygame.K_RIGHT);assert g.challenge=='Complete Code'
 key(g,pygame.K_DOWN);old=g.sound;key(g,pygame.K_RETURN);assert g.sound!=old
 key(g,pygame.K_DOWN);key(g,pygame.K_RETURN);assert g.mode=='menu'
 key(g,pygame.K_TAB);assert g.nav_focus==4
 key(g,pygame.K_TAB,pygame.KMOD_SHIFT);assert g.nav_focus==3
 # Both retained problem types, supported local compilers, and true difficulty progression.
 for language in ['Python','C++','Java']:
  if language=='C++' and not shutil.which('g++'):continue
  if language=='Java' and not shutil.which('javac'):continue
  for kind in ['Debug','Complete Code']:
   g=app.Game();g.language=language;g.challenge=kind;g.start()
   assert len(g.gates)==2 and g.remaining==120 and g.difficulty==0
   assert [gate['difficulty'] for gate in g.gates.values()]==[0,1]
   for index,(edge,gate) in enumerate(g.gates.items()):
    titles={q['title'] for q in build_questions(language)[index]}
    assert gate['question']['title'] in titles
    g.open_editor(edge);settle(g);assert not g.reference_error,g.error
    if kind=='Complete Code':assert 'TODO' in '\n'.join(g.lines)
    g.lines=gate['question']['answer'].split('\n');before=g.lives
    g.run_code(False);settle(g);assert g.lives==before and g.mode=='editor'
    g.run_code(True);settle(g);assert gate['open']
   assert g.mode=='name_entry' and g.outcome=='won' and not g.result_saved
   # Winning must not be saved under a placeholder name.
   old_count=len(g.history);g.save_result();assert len(g.history)==old_count and g.mode=='name_entry'
   g.handle(pygame.event.Event(pygame.TEXTINPUT,text='AHMED'))
   g.draw()
   key(g,pygame.K_RETURN);assert g.mode=='won' and g.result_saved
   saved=json.loads((app.DATA/'dashboard.json').read_text());assert len(saved)<=old_count+1 and sum(row['name']=='AHMED' for row in saved)==1 and any(row['name']=='AHMED' and row['won'] for row in saved)
   g.save_result();assert len(json.loads((app.DATA/'dashboard.json').read_text()))==len(saved)
 # Loss also prompts for a name; input length and backspace work.
 g=app.Game();g.start();g.remaining=.01;g.update(.02)
 assert g.mode=='name_entry' and g.outcome=='lost'
 g.handle(pygame.event.Event(pygame.TEXTINPUT,text='B'*30));assert len(g.name)==16
 key(g,pygame.K_BACKSPACE);assert len(g.name)==15
 key(g,pygame.K_RETURN);assert g.mode=='lost' and g.result_saved
 # Score write failure leaves the pending result retryable, without duplicates.
 g=app.Game();g.start();g.remaining=.01;g.update(.02);g.name='RETRY'
 good_path=app.DATA;bad=Path(directory)/'not_a_folder';bad.write_text('x');app.DATA=bad
 count=len(g.history);g.save_result();assert g.mode=='name_entry' and not g.result_saved and len(g.history)==count
 app.DATA=good_path;g.save_result();assert g.result_saved and len(g.history)==count+1
 # Skip is explicit and never writes an anonymous score.
 g=app.Game();g.start();g.remaining=.01;g.update(.02);before=(app.DATA/'dashboard.json').read_bytes()
 key(g,pygame.K_ESCAPE);assert g.mode=='lost' and (app.DATA/'dashboard.json').read_bytes()==before
 # Existing arcade features still work.
 g=app.Game();g.start();g.player=next(iter(g.energy));score=g.score;g.update(.01);assert g.score==score+10
 key(g,pygame.K_SPACE);assert g.dash>0 and g.dash_cooldown==2
 g=app.Game();g.draw()
 g.go('settings');g.draw()
 g.start();g.draw()
 g.open_editor(next(iter(g.gates)));settle(g);g.draw()
assert execute('print(missing)')['error']
assert execute('while True: pass')['error']
app.POOL.shutdown(wait=True)
print('PASS: keyboard menus, two settings, both problem types, rising difficulty, win/loss name entry, save/retry/no duplicates/skip, energy and dash.')

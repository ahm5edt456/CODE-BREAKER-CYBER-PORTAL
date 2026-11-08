"""Dashboard deletion, random question coverage, completion, and mouse editing."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import tempfile,time,json,random,shutil
from pathlib import Path
import pygame,pygame_gui
import game as core
from campaign import CampaignGame
from campaign_questions import TOPICS,TIERS,campaign_plan,problem
from editor_support import TEXT_X,TEXT_Y,ROW_HEIGHT,SCROLLBAR

plans=[campaign_plan(random.Random(i)) for i in range(100)]
assert len(TOPICS)>=13 and len({tuple(p) for p in plans})>30
assert set(t for p in plans for t in p)==set(range(len(TOPICS)))
for plan in plans:
 assert len(plan)==len(set(plan))==6
 assert all(set(plan[i*2:i*2+2])<=set(TIERS[i]) for i in range(3))

def settle(g):
 end=time.monotonic()+15
 while g.future:
  assert time.monotonic()<end
  time.sleep(.01);g.update(.001)

def key(g,k,mod=0):g.handle(pygame.event.Event(pygame.KEYDOWN,key=k,mod=mod))
def down(g,pos,button=1,clicks=1):g.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=button,clicks=clicks))
def up(g,pos):g.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,pos=pos,button=1))
def pixel(g,row,col):return TEXT_X+g.editor_font.size(g.lines[row][:col])[0]-g.editor_hscroll,TEXT_Y+(row-g.editor_top)*ROW_HEIGHT+8

with tempfile.TemporaryDirectory() as folder:
 core.DATA=Path(folder)/'data';g=CampaignGame();g.start();g.score=222;g.mode='lost';g.begin_name_entry();g.name='OLD';g.save_result()
 assert json.loads((core.DATA/'dashboard.json').read_text())[0]['name']=='OLD'
 # Deleting a file while the same game is open must not merge cached old history.
 (core.DATA/'dashboard.json').unlink()
 g.start();g.score=50;g.mode='lost';g.begin_name_entry();g.name='NEW';g.save_result()
 assert [r['name'] for r in json.loads((core.DATA/'dashboard.json').read_text())]==['NEW']
 (core.DATA/'dashboard.json').unlink();g.go('scores');assert g.history==[]
 assert json.loads((core.DATA/'dashboard.json').read_text())==[]
 # The open scoreboard also notices a deletion without needing a restart.
 g.start();g.mode='lost';g.begin_name_entry();g.name='TEMP';g.save_result();g.go('scores')
 (core.DATA/'dashboard.json').unlink();g.update(.6);assert g.history==[]
 # Real Complete Code: the exact missing line can be typed directly, preserving indentation.
 for language in ['Python']+(['C++'] if shutil.which('g++') else [])+(['Java'] if shutil.which('javac') and shutil.which('java') else []):
  for topic in range(len(TOPICS)):
   g=CampaignGame();g.language=language;g.challenge='Complete Code';g.start();edge=next(iter(g.gates))
   g.gates[edge]['question']=q=problem(language,topic,'Complete Code',random.Random(topic))
   g.open_editor(edge);settle(g)
   row=q['missing_line'];assert g.line==row and g.editor_selection() is not None
   answer=q['answer'].splitlines()[row].lstrip()
   g.handle(pygame.event.Event(pygame.TEXTINPUT,text=answer))
   assert '\n'.join(g.lines)==q['answer'],topic
   g.run_code(True);settle(g);assert g.gates[edge]['open'],(topic,g.error)
 # Precise mouse caret placement, drag-selection replacement, double-click, scrolling.
 g=CampaignGame();g.start();edge=next(iter(g.gates));g.open_editor(edge);settle(g)
 g.lines=['alpha = 10','beta = 20','print(alpha + beta)'];g.line=g.col=0;g.editor_reset()
 down(g,pixel(g,1,4));up(g,pixel(g,1,4));assert (g.line,g.col)==(1,4)
 start=pixel(g,0,0);end=pixel(g,0,5);down(g,start)
 g.handle(pygame.event.Event(pygame.MOUSEMOTION,pos=end,rel=(30,0),buttons=(1,0,0)));up(g,end)
 assert g.editor_selection()==((0,0),(0,5))
 g.handle(pygame.event.Event(pygame.TEXTINPUT,text='value'));assert g.lines[0]=='value = 10'
 down(g,pixel(g,1,2),clicks=2);up(g,pixel(g,1,2));assert g.editor_selection()==((1,0),(1,4))
 # Clipboard operations keep multi-line text intact (local fallback works headlessly).
 g.editor_copy();assert g.editor_clipboard=='beta'
 g.lines=[''];g.line=g.col=0;g.editor_reset();key(g,pygame.K_v,pygame.KMOD_CTRL);assert g.lines==['beta']
 g.lines=[''];g.line=g.col=0;g.editor_reset();g.editor_insert('one\ntwo');assert g.lines==['one','two']
 g.lines=['if True:'];g.line=0;g.col=8;g.editor_reset();key(g,pygame.K_RETURN);assert g.lines==['if True:','    ']
 g.lines=[f'line_{i}' for i in range(40)];g.line=g.col=0;g.editor_reset()
 g.handle(pygame.event.Event(pygame.MOUSEWHEEL,x=0,y=-3,pos=(600,300)));assert g.editor_top==9
 down(g,(SCROLLBAR.centerx,SCROLLBAR.bottom-1));up(g,(SCROLLBAR.centerx,SCROLLBAR.bottom-1));assert g.editor_top==28
 # Drafts survive Back; reopening and reset preserve clock semantics.
 g.lines=['print(123)'];g.line=0;g.col=7;g.close_editor();g.open_editor(edge);settle(g);assert g.lines==['print(123)']
 # Right-click menu creates real GUI controls and leaves no ghost widgets after dismissal.
 g.draw();base=len(g.widgets);down(g,(700,300),button=3);g.draw();assert len(g.widgets)==base+3
 menu=(g.editor_menu[0]+50,g.editor_menu[1]+90)
 action=g.widgets[len(g.buttons)-1]
 g.handle(pygame.event.Event(pygame_gui.UI_BUTTON_PRESSED,ui_element=action,ui_object_id='#secondary'))
 g.draw();assert g.editor_menu is None and len(g.widgets)==base
core.POOL.shutdown(wait=True)
print('PASS: fresh JSON resets, random thirteen-type bank, real completion for all types, caret/drag/double click, scrolling, clipboard, indentation, draft persistence and context menu.')

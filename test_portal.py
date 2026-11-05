"""Integration tests for the real pygame_gui edition; all scores are temporary."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import tempfile,time,json
from pathlib import Path
import pygame,pygame_gui
from pygame_gui.elements import UIButton,UITextEntryLine
import game as core
from portal_ui import PortalGame

def frame(g):
 g.update(.025);g.draw()
def key(g,k,mod=0):
 g.handle(pygame.event.Event(pygame.KEYDOWN,key=k,mod=mod));frame(g)
def pump(g):
 for event in pygame.event.get():g.handle(event)
 frame(g)
def click(g,index):
 pos=g.widgets[index].rect.center
 old=pygame.mouse.get_pos;pygame.mouse.get_pos=lambda:pos
 frame(g)
 for event in [pygame.event.Event(pygame.MOUSEMOTION,pos=pos,rel=(0,0),buttons=(0,0,0)),pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=1),pygame.event.Event(pygame.MOUSEBUTTONUP,pos=pos,button=1)]:g.handle(event)
 pump(g);pygame.mouse.get_pos=old

def settle(g):
 end=time.monotonic()+15
 while g.future:
  assert time.monotonic()<end
  time.sleep(.01);frame(g)

with tempfile.TemporaryDirectory() as directory:
 core.DATA=Path(directory)/'scores'
 g=PortalGame();g.draw();frame(g)
 assert len(g.widgets)==6 and all(isinstance(w,UIButton) for w in g.widgets.values())
 before=pygame.image.tobytes(pygame.display.get_surface(),'RGB');g.update(1);g.draw()
 assert pygame.image.tobytes(pygame.display.get_surface(),'RGB')!=before
 pygame.image.save(pygame.display.get_surface(),'preview_menu.png')
 # Keyboard follows visual order: PLAY -> languages -> footer.
 key(g,pygame.K_DOWN);assert g.nav_focus==0
 key(g,pygame.K_RIGHT);assert g.language=='Java'
 key(g,pygame.K_UP);assert g.nav_focus==3
 key(g,pygame.K_DOWN);key(g,pygame.K_DOWN);key(g,pygame.K_RETURN);frame(g)
 assert g.mode=='settings' and len(g.widgets)==4
 key(g,pygame.K_RIGHT);assert g.challenge=='Complete Code'
 key(g,pygame.K_DOWN);before=g.sound;key(g,pygame.K_RETURN);assert g.sound!=before
 g.update(.3);g.draw();pygame.image.save(pygame.display.get_surface(),'preview_settings.png')
 key(g,pygame.K_ESCAPE);assert g.mode=='menu'
 # Mouse events are handled by pygame_gui exactly once.
 click(g,4);assert g.mode=='settings'
 before=g.sound;click(g,2);assert g.sound!=before
 click(g,3);assert g.mode=='menu'
 g.language='Python';click(g,3);assert g.mode=='maze'
 # Name entry uses a real editable text widget and named persistence.
 g.mode='lost';g.begin_name_entry();frame(g);frame(g)
 assert isinstance(g.entry,UITextEntryLine)
 g.handle(pygame.event.Event(pygame.TEXTINPUT,text='AHMED'));frame(g)
 assert g.entry.get_text()=='AHMED' and g.name=='AHMED'
 key(g,pygame.K_BACKSPACE);assert g.entry.get_text()=='AHME'
 g.handle(pygame.event.Event(pygame.TEXTINPUT,text='D'));g.update(.3);g.draw()
 pygame.image.save(pygame.display.get_surface(),'preview_name.png')
 key(g,pygame.K_RETURN);assert g.mode=='lost' and g.result_saved
 saved=json.loads((core.DATA/'dashboard.json').read_text());assert len(saved)==1 and saved[0]['name']=='AHMED'
 pump(g);assert len(json.loads((core.DATA/'dashboard.json').read_text()))==1
 # GUI -> gameplay -> both progressively harder challenges -> real name input.
 g.go('menu',3);frame(g);g.challenge='Debug';key(g,pygame.K_RETURN)
 assert g.mode=='maze' and len(g.gates)==2
 for edge,gate in g.gates.items():
  g.open_editor(edge);settle(g);assert not g.reference_error
  g.lines=gate['question']['answer'].split('\n');g.run_code(True);settle(g)
 assert g.mode=='name_entry' and g.outcome=='won'
 frame(g);g.handle(pygame.event.Event(pygame.TEXTINPUT,text='BYTE'));key(g,pygame.K_RETURN)
 assert g.mode=='won' and g.result_saved
 g.go('scores');g.draw();g.update(.3);g.draw();frame(g)
 assert len(g.widgets)==1
 pygame.image.save(pygame.display.get_surface(),'preview_scores.png')
core.POOL.shutdown(wait=True)
print('PASS: actual pygame_gui widgets, animation, keyboard + mouse, editable name, save once, full gameplay and score screen.')

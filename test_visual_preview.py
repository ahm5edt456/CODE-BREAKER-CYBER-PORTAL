"""Headless preview controls. Reference execution is mocked; runner is untouched."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import tempfile
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import Future
import pygame
import game as core
from campaign import CampaignGame
from visual_preview import PALETTES

class ReferencePool:
    def submit(self,*args,**kwargs):
        result=Future();result.set_result({'out':'11\n','error':''});return result

def key(g,code):g.handle(pygame.event.Event(pygame.KEYDOWN,key=code,mod=0))
def files(directory):return {p.name:p.read_bytes() for p in directory.iterdir() if p.is_file()}

with tempfile.TemporaryDirectory() as directory, patch.object(core,'POOL',ReferencePool()):
    core.DATA=Path(directory)
    g=CampaignGame();g.draw()
    snapshot=files(core.DATA)
    key(g,pygame.K_F10)
    assert g.admin_preview and g.mode=='menu'
    g.start()
    assert g.preview_tainted and g.mode=='maze'
    assert files(core.DATA)==snapshot
    for index in range(3):
        g.preview_stage(index);g.fx_entry=0
        g.update(.3);g.draw()
        assert g.level==index and g.stage_accent==PALETTES[index][0]
        pygame.image.save(pygame.display.get_surface(),f'preview_visual_stage{index+1}.png')
    key(g,pygame.K_PAGEDOWN);assert g.level==0
    key(g,pygame.K_PAGEUP);assert g.level==2
    for code in (pygame.K_F7,pygame.K_F8):
        key(g,code);g.update(.01);assert g.mode=='editor' and g.future is None
        g.update(.3);g.draw()
        assert g.gates[g.active_gate]['solve_seconds']==0
    pygame.image.save(pygame.display.get_surface(),'preview_visual_editor.png')
    busy=Future();g.future=busy;old=(g.level,g.active_gate,g.admin_preview)
    for code in (pygame.K_PAGEUP,pygame.K_PAGEDOWN,pygame.K_F7,pygame.K_F8,pygame.K_F9):
        key(g,code);assert (g.level,g.active_gate,g.admin_preview)==old
        assert g.future is busy
    busy.set_result({'out':'11','error':''});g.update(.01)
    g.close_editor();g.remaining=.001
    seconds=g.elapsed;g.update(.1)
    assert g.mode=='maze' and g.remaining>0 and g.elapsed==seconds
    key(g,pygame.K_F4);assert g.fx_rings
    g.update(.3);g.draw()
    key(g,pygame.K_F3);assert g.reduced_motion
    g.draw();key(g,pygame.K_F3)
    key(g,pygame.K_F9);assert g.mode=='menu' and g.pending_result is None
    g.name='ADMIN';g.save_result()
    assert files(core.DATA)==snapshot
    key(g,pygame.K_F10);assert not g.admin_preview and g.preview_tainted
    g.start();assert not g.preview_tainted
    assert (core.DATA/'question_history.json').exists()
    g.remaining=60;g.update(.1);assert 59<g.remaining<60
    g.mode='won';g.begin_name_entry();assert g.mode=='name_entry' and g.pending_result is not None
core.POOL.shutdown(wait=True)
print('PASS: themes, admin controls, busy jobs, preview clock, score/history isolation, motion and normal gameplay')

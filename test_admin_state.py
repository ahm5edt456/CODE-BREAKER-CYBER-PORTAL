"""Admin toggling is a non-destructive in-place UI operation."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import copy,random,tempfile
from pathlib import Path
from concurrent.futures import Future
from unittest.mock import patch
import pygame
import game as core
from campaign import CampaignGame

class References:
    def submit(self,*args):
        f=Future();f.set_result({'out':'11','error':''});return f

def key(g):g.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F10,mod=0))
def state(g):
    fields=('mode','level','player','remaining','elapsed','score','lives','correct','attempts','energy','energy_count','gates','lines','line','col','active_gate','question_plan','campaign_puzzles','hint','stage_finished','stage_transition')
    return {name:copy.deepcopy(getattr(g,name,None)) for name in fields}

with tempfile.TemporaryDirectory() as folder,patch.object(core,'POOL',References()):
    core.DATA=Path(folder)
    g=CampaignGame();g.draw()
    menu=state(g);key(g);assert state(g)==menu and g.fx_notice=='ADMIN ENABLED'
    assert not hasattr(g,'campaign_puzzles')
    key(g);assert state(g)==menu
    g.start();g.player=(1,0);g.remaining=37.25;g.score=210;g.lives=2
    for mode in ('maze','editor','paused'):
        if mode=='editor':
            g.open_editor(next(iter(g.gates)));g.update(.01)
            g.lines=['# unsaved draft','print(42)'];g.line=1;g.col=4
        else:g.mode=mode
        expected=state(g);maze=g.maze;gates=g.gates;rng=random.getstate()
        data={p.name:p.read_bytes() for p in core.DATA.iterdir() if p.is_file()}
        key(g)
        assert g.admin_preview and g.fx_notice=='ADMIN ENABLED'
        assert state(g)==expected and g.maze is maze and g.gates is gates
        assert random.getstate()==rng
        assert {p.name:p.read_bytes() for p in core.DATA.iterdir() if p.is_file()}==data
        key(g);assert not g.admin_preview and state(g)==expected
    # Toggling must also leave a pending protected runner future intact.
    g.mode='editor';busy=Future();g.future=busy
    key(g);assert g.future is busy and g.mode=='editor'
    key(g);assert g.future is busy
    g.future=None
    # Even fractions of a second are preserved while preview freezes the timer.
    g.mode='maze';g.remaining=.001;key(g);g.update(.1)
    assert g.remaining==.001 and g.mode=='maze'
    # Once the notification expires, no admin-key HUD or banner is drawn.
    g.fx_notice_time=0;g.draw()
    normal=pygame.display.get_surface().copy()
    g.admin_preview=False;g.draw()
    assert pygame.image.tobytes(normal,'RGB')==pygame.image.tobytes(pygame.display.get_surface(),'RGB')
core.POOL.shutdown(wait=True)
print('PASS: F10 preserves maze identity, gates, location, drafts, progress, RNG, saved files, pending jobs and exact timer; no persistent admin HUD')

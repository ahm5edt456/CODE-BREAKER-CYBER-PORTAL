"""Presentation effects and local preview controls; never executes player code."""
import math
import random
import pygame
from game import S, W, M
from scene_art import SceneArt

PALETTES = [
    ((51, 220, 235), (104, 151, 255), 'BOOT / NEON CIRCUIT'),
    ((182, 133, 255), (255, 131, 196), 'FLOW / VIOLET MATRIX'),
    ((255, 126, 99), (255, 205, 112), 'CORE / SOLAR REACTOR'),
]

class VisualPreview:
    def __init__(self):
        self.admin_preview = False
        self.preview_tainted = False
        self.reduced_motion = False
        self.fx_time = 0.
        self.fx_entry = 0.
        self.fx_rings = []
        self.fx_trail = []
        self.fx_progress = 0.
        self.fx_notice = ''
        self.fx_notice_time = 0.
        self.fx_layer = pygame.Surface((1280, 720), pygame.SRCALPHA)
        super().__init__()
        self.scene_art=SceneArt(PALETTES)
        self.actor_facing=0
        self.actor_frame=0.
        self.actor_last=tuple(self.render_pos)

    @property
    def stage_accent(self):
        return PALETTES[min(2, max(0, self.level))][0]

    def start(self):
        self.preview_tainted = self.admin_preview
        super().start()

    def start_level(self):
        super().start_level()
        self.fx_entry = 1.8
        self.fx_rings = []
        self.fx_trail = []
        self.fx_progress = 0.
        self.actor_last=tuple(self.render_pos)
        self.actor_frame=0.

    def fx_message(self, text):
        self.fx_notice = text
        self.fx_notice_time = 3.

    def burst(self, position, color=None):
        self.fx_rings.append([tuple(position), 0., color or self.stage_accent])
        self.fx_rings = self.fx_rings[-8:]

    def celebrate(self, edge):
        super().celebrate(edge)
        a, b = edge
        self.burst((42+(a[0]+b[0]+1)*24, 132+(a[1]+b[1]+1)*24))

    def begin_name_entry(self):
        if self.preview_tainted:
            self.pending_result = None
            self.result_saved = True
            self.go('menu', 3)
            self.fx_message('PREVIEW FINISHED / No leaderboard entry was saved')
            return
        super().begin_name_entry()

    def save_result(self):
        if self.preview_tainted:
            self.fx_message('PREVIEW / Score saving disabled. Start a normal game to compete.')
            return
        super().save_result()

    def preview_stage(self, level):
        if self.future:
            self.fx_message('Please wait for the current code run before switching stages.')
            return
        if not hasattr(self, 'campaign_puzzles'):
            self.start()
        if self.mode == 'editor':
            self.close_editor()
        self.preview_tainted = True
        self.pending_result = None
        self.result_saved = False
        self.active_gate = None
        self.level = level % 3
        self.lives = 3
        self.start_level()
        self.go('maze')
        pygame.key.stop_text_input()
        self.fx_message('ADMIN / Stage preview loaded. Timer paused; score saving disabled.')

    def preview_question(self, index):
        if self.future:
            self.fx_message('Please wait for the current code run.')
            return
        if self.mode == 'editor':self.close_editor()
        if self.mode != 'maze':self.preview_stage(self.level)
        edges = list(self.gates)
        for i, edge in enumerate(edges):
            self.gates[edge]['open'] = i < index
        edge = edges[index]
        self.gates[edge]['open'] = False
        self.stage_finished = False
        self.preview_tainted = True
        self.open_editor(edge)  # Uses the existing protected runner and real reference.

    def handle_preview_key(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self.reduced_motion = not self.reduced_motion
                self.fx_message('REDUCED MOTION / '+('ON' if self.reduced_motion else 'OFF'))
                return True
            if event.key == pygame.K_F10:
                self.admin_preview = not self.admin_preview
                if self.admin_preview:
                    if self.mode in ('maze','editor','paused','stage_clear'):
                        self.preview_tainted = True
                    self.fx_message('ADMIN ENABLED')
                else:
                    self.fx_message('ADMIN DISABLED')
                return True
            if self.admin_preview:
                if event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                    self.preview_stage(self.level + (1 if event.key == pygame.K_PAGEDOWN else -1))
                    return True
                if event.key in (pygame.K_F7, pygame.K_F8):
                    self.preview_question(0 if event.key == pygame.K_F7 else 1)
                    return True
                if event.key == pygame.K_F4:
                    self.burst(self.render_pos)
                    self.fx_message('ADMIN / Gate activation effect')
                    return True
                if event.key == pygame.K_F9:
                    if self.future:
                        self.fx_message('Please wait for the current code run.')
                        return True
                    if self.mode == 'editor':self.close_editor()
                    if self.mode != 'maze':self.preview_stage(self.level)
                    for gate in self.gates.values():gate['open'] = True
                    self.correct = (self.level+1)*2
                    self.complete_stage()
                    return True
        return False

    def handle(self, event):
        if not self.handle_preview_key(event):super().handle(event)

    def update(self, dt):
        self.fx_time += dt
        self.fx_entry = max(0., self.fx_entry-dt)
        self.fx_notice_time = max(0., self.fx_notice_time-dt)
        for ring in self.fx_rings:ring[1] += dt
        self.fx_rings = [r for r in self.fx_rings if r[1] < 1.1]
        for dot in self.fx_trail:dot[2] -= dt
        self.fx_trail = [p for p in self.fx_trail if p[2] > 0]
        # Freeze preview time without changing normal movement or async result handling.
        remaining = self.remaining
        elapsed = self.elapsed
        solve_times = [(g, g.get('solve_seconds')) for g in getattr(self, 'gates', {}).values()]
        if self.admin_preview and self.mode in ('maze', 'editor'):self.remaining = 120.
        super().update(dt)
        if self.admin_preview:
            self.remaining = remaining
            self.elapsed = elapsed
            for gate, value in solve_times:gate['solve_seconds'] = value
        delta=self.render_pos-pygame.Vector2(self.actor_last)
        if self.mode == 'maze' and not self.reduced_motion and delta.length() > .7:
            self.fx_trail.append([*self.actor_last, .22])
        self.actor_last=tuple(self.render_pos)
        if delta.length_squared()>.1:
            self.actor_facing=(1 if delta.x>0 else 3) if abs(delta.x)>abs(delta.y) else (0 if delta.y>0 else 2)
            if not self.reduced_motion:self.actor_frame=(self.actor_frame+dt*18)%8
        else:self.actor_frame=0.
        target = sum(g['open'] for g in getattr(self, 'gates', {}).values())/2
        self.fx_progress += (target-self.fx_progress)*min(1., dt*8)

    def draw_floor_fx(self):
        accent = self.stage_accent
        self.fx_layer.fill((0, 0, 0, 0))
        # Quiet circuit nodes: decorative only, no route or solution information.
        rng = random.Random(921+self.level)
        for _ in range(35):
            x, y = 52+rng.randrange(604), 142+rng.randrange(412)
            phase = rng.random()*math.tau
            alpha = 35 if self.reduced_motion else int(26+20*math.sin(self.fx_time*1.4+phase))
            pygame.draw.circle(self.fx_layer, (*accent, alpha), (x, y), 2)
        if not self.reduced_motion:
            y = 132+int((self.fx_time*30)%432)
            pygame.draw.rect(self.fx_layer, (*accent, 9), (42, y, 624, 18))
        S.blit(self.fx_layer, (0, 0))

    def menu(self):
        # Keep the existing centered controls and open negative space.
        super().menu()

    def draw_maze_fx(self):
        accent = self.stage_accent
        self.fx_layer.fill((0, 0, 0, 0))
        for x, y, life in self.fx_trail:
            pygame.draw.circle(self.fx_layer, (*accent, int(85*life/.22)), (int(x), int(y)), 8)
        cx, cy = map(int, self.render_pos)
        for radius, alpha in ((29, 7), (22, 13)):
            pygame.draw.circle(self.fx_layer, (*accent, alpha), (cx, cy), radius)
        for (x, y), age, color in self.fx_rings:
            opacity = max(0, int(220*(1-age/1.1)))
            radius = int(18+age*65) if not self.reduced_motion else 24
            pygame.draw.circle(self.fx_layer, (*color, opacity), (int(x), int(y)), radius, 2)
            if not self.reduced_motion:
                for i in range(12):
                    angle = i*math.tau/12+age*.5
                    pos = (int(x+math.cos(angle)*(radius+6)), int(y+math.sin(angle)*(radius+6)))
                    pygame.draw.circle(self.fx_layer, (*color, opacity), pos, 2)
        for (a, b), gate in self.gates.items():
            if gate['open']:continue
            x = 42+(a[0]+b[0]+1)*24
            y = 132+(a[1]+b[1]+1)*24
            angle = 0 if self.reduced_motion else self.fx_time*.8
            for i in range(3):
                phi = angle+i*math.tau/3
                pos = (int(x+math.cos(phi)*23), int(y+math.sin(phi)*23))
                pygame.draw.circle(self.fx_layer, (*accent, 150), pos, 2)
        old = S.get_clip()
        S.set_clip((42, 132, 624, 432))
        S.blit(self.fx_layer, (0, 0))
        S.set_clip(old)
        if self.fx_entry > 0 and not self.reduced_motion:
            width = int(280*min(1., (1.8-self.fx_entry)*4))
            rect = pygame.Rect(58, 147, width, 48)
            pygame.draw.rect(S, (9, 21, 36), rect, border_radius=8)
            old = S.get_clip();S.set_clip(rect)
            pygame.draw.rect(S, accent, (58, 147, 3, 48))
            self.text('SECTOR '+str(self.level+1)+' / ONLINE', 73, 156, 16, accent, bold=True)
            self.text(PALETTES[self.level][2], 73, 178, 10, M)
            S.set_clip(old)

    def draw_preview_overlay(self):
        # Private shortcuts stay off-screen; only transient confirmation is shown.
        if self.fx_notice_time > 0:
            width=min(840,max(230,len(self.fx_notice)*7+40))
            y=104 if self.mode in ('maze','editor') else 660
            rect=pygame.Rect(640-width//2,y,width,29)
            pygame.draw.rect(S,(13,29,44),rect,border_radius=9)
            pygame.draw.rect(S,self.stage_accent,rect,1,border_radius=9)
            self.text(self.fx_notice,640,y+7,12,W,center=True)

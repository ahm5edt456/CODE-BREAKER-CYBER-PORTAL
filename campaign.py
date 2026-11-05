"""Three themed stages with distributed challenges and automatic progression."""
import math,random,re
import pygame,pygame_gui
import engine as E
from portal_ui import PortalGame,GUI_MODES
from game import S,C,V,W,M,G,R,panel
from campaign_questions import problem,TOPICS
from challenge_placement import spread_gates,distances

GUI_MODES.update({'maze','editor','stage_clear','paused'})
NAMES=['BOOT SEQUENCE','CONTROL FLOW','CORE RECOVERY']
BADGE_RADIUS=14
BADGE_BORDER=2

class CampaignGame(PortalGame):
    def __init__(self):
        self.manual_stage_completion=True;self.feed=[];self.stage_transition=0.;self.stage_finished=False;self.render_pos=pygame.Vector2(66,156);self.resume_mode='maze'
        self.campaign_caption='3 stages. 6 challenges. Explore. Solve. Advance.'
        super().__init__()
    def button(self,title,rect,action,active=False,color=C):
        focus=self.nav_focus
        if self.mode in ('maze','editor'):self.nav_focus=-1
        try:return super().button(title,rect,action,active,color)
        finally:self.nav_focus=focus
    def notify(self,message):
        super().notify(message)
        if hasattr(self,'feed'):
            self.feed.append(message);self.feed=self.feed[-3:]
    def start(self):
        self.feed=[];super().start()
    def start_level(self):
        old_lives=self.lives;self.sector_count=3
        E.Game.start_level(self)
        if self.level:self.lives=old_lives
        self.remaining=120.;self.energy=set();self.trail=[];self.stage_transition=0.;self.stage_finished=False
        edges=spread_gates(self.maze.maze)
        self.gates={edge:{'id':i+1,'open':False} for i,edge in enumerate(edges)}
        self.render_pos=pygame.Vector2(66,156);self.move_wait=0;self.dash=0;self.dash_cooldown=0;self.auto_gate_hold=None;self.feed=[]
        for index,gate in enumerate(self.gates.values()):
            rank=self.level*2+index
            gate['difficulty']=rank;gate['kind']=self.challenge;gate['question']=problem(self.language,rank,self.challenge)
        reachable,_=distances(self.maze.maze,(0,0),blocked=self.gates)
        choices=[p for p in reachable if sum(p)>=3]
        self.energy=set(random.sample(choices,min(4,len(choices))))
        self.notify(f'STAGE {self.level+1} / Explore the maze and solve both challenges.')
    def nearby_gate(self):
        edge=super().nearby_gate()
        pending=[g['id'] for g in self.gates.values() if not g['open']]
        if edge is not None and pending and self.gates[edge]['id']==min(pending):return edge
        return None
    def open_editor(self,edge):
        pending=[g['id'] for g in self.gates.values() if not g['open']]
        if pending and self.gates[edge]['id']!=min(pending):
            self.notify('Solve the earlier-numbered challenge first.');return
        super().open_editor(edge)
    def evaluate(self,passed):
        self.attempts+=1
        if passed:
            self.celebrate(self.active_gate);self.correct+=1
            points=100+(25 if not self.hint else 0);self.score+=points
            self.gates[self.active_gate]['open']=True;self.beep('ok');self.close_editor();self.flash=1.2
            self.notify(f'GATE ONLINE / +{points} / Next challenge is in another part of the maze.')
            if self.all_open():self.complete_stage()
        else:
            self.lives-=1;self.beep('bad');self.flash=2.5
            self.notify(f'Incorrect submission / -1 heart / {self.lives} remaining')
            if self.lives<=0:self.close_editor();self.mode='lost'
    def complete_stage(self):
        if self.stage_finished or not self.all_open():return
        self.stage_finished=True;self.score+=int(self.remaining);self.particles=[]
        if self.level==2:
            self.mode='won';self.begin_name_entry()
        else:
            self.stage_transition=1.2;self.go('stage_clear')
    def all_open(self):return bool(self.gates) and all(g['open'] for g in self.gates.values())
    def begin_name_entry(self):
        super().begin_name_entry()
        self.pending_result['difficulty']=max(0,self.correct-1)
        self.pending_result['stages_completed']=3 if self.outcome=='won' else self.level
    def pause(self):
        if self.future:
            self.notify('Please wait for the current code run.');return
        self.resume_mode=self.mode;self.go('paused');pygame.key.stop_text_input()
    def resume(self):
        self.go(self.resume_mode)
        if self.mode=='editor':pygame.key.start_text_input()
    def next_stage(self):
        if self.mode!='stage_clear':return
        self.level+=1;self.start_level()
    def handle(self,event):
        if event.type==pygame.KEYDOWN:
            if self.mode=='maze' and event.key==pygame.K_e:
                candidate=E.Game.nearby_gate(self)
                pending=[g['id'] for g in self.gates.values() if not g['open']]
                if candidate is not None and pending and self.gates[candidate]['id']!=min(pending):
                    self.notify('Solve the earlier-numbered challenge first.');return
            if self.mode=='stage_clear' and event.key in (pygame.K_RETURN,pygame.K_SPACE):self.next_stage();return
            if self.mode=='paused':
                if event.key==pygame.K_ESCAPE:self.resume()
                elif event.key in (pygame.K_TAB,pygame.K_DOWN,pygame.K_UP,pygame.K_LEFT,pygame.K_RIGHT):self.nav_focus=1-self.nav_focus
                elif event.key==pygame.K_RETURN:
                    if self.nav_focus==0:self.resume()
                    else:self.go('menu',3)
                return
            if self.mode=='maze' and event.key in (pygame.K_ESCAPE,pygame.K_p):self.pause();return
        super().handle(event)
    def update(self,dt):
        super().update(dt)
        if self.mode=='maze':
            target=pygame.Vector2(42+self.player[0]*48+24,132+self.player[1]*48+24)
            self.render_pos=self.render_pos.lerp(target,min(1.,dt*18))
        elif self.mode=='stage_clear':
            self.stage_transition=max(0,self.stage_transition-dt)
            if self.stage_transition==0:self.next_stage()
    def number_badge(self,number,center,color,text_color=W):
        center=tuple(map(int,center))
        pygame.draw.circle(S,(8,23,37),center,BADGE_RADIUS)
        pygame.draw.circle(S,color,center,BADGE_RADIUS,BADGE_BORDER)
        # Center the visible glyph rather than the transparent font line box.
        if not hasattr(self,'badge_glyphs'):self.badge_glyphs={}
        cache_key=(str(number),tuple(text_color))
        if cache_key not in self.badge_glyphs:
            font=pygame.font.SysFont('dejavusans',15,bold=True)
            rendered=font.render(str(number),True,text_color)
            bounds=rendered.get_bounding_rect()
            self.badge_glyphs[cache_key]=rendered.subsurface(bounds).copy()
        glyph=self.badge_glyphs[cache_key]
        destination=glyph.get_rect(center=center)
        S.blit(glyph,destination)
        return destination
    def header(self):
        if self.mode not in ('maze','editor'):return
        panel((26,23,1228,76),(9,21,36),(32,59,78))
        self.text('CODE BREAKER',45,37,23,C,bold=True)
        self.text('CYBER PORTAL / '+self.language.upper(),46,70,10,M)
        for i in range(3):
            x=366+i*95;color=G if i<self.level else (C if i==self.level else (45,62,80))
            self.number_badge(i+1,(x,59),color,color if i<=self.level else M)
            if i<2:pygame.draw.line(S,(39,62,79),(x+22,59),(x+73,59),2)
        self.text(f'{self.correct}/6 FIXED',638,49,15,V)
        for i in range(3):
            x=779+i*27;color=R if i<self.lives else (43,57,73)
            pygame.draw.circle(S,color,(x,53),6);pygame.draw.circle(S,color,(x+9,53),6)
            pygame.draw.polygon(S,color,[(x-6,55),(x+15,55),(x+5,68)])
        self.text(f'{int(self.remaining)//60:02}:{int(self.remaining)%60:02}',901,42,25,R if self.remaining<=20 else G,bold=True)
        self.text(f'{self.score:04} PTS',1012,49,16,C)
        self.button('PAUSE',(1138,43,93,33),self.pause)
    def draw_maze(self):
        ox,oy=42,132
        panel((27,117,654,462),(9,23,38),(32,65,83))
        pygame.draw.rect(S,(9,26,40),(42,132,624,432))
        solved=sum(g['open'] for g in self.gates.values())
        wall=(45,91+solved*16,112+solved*10)
        for y,row in enumerate(self.maze.maze):
            for x,bits in enumerate(row):
                px,py=ox+x*48,oy+y*48
                for flag,a,b in [(1,(px,py),(px+48,py)),(2,(px+48,py),(px+48,py+48)),(4,(px,py+48),(px+48,py+48)),(8,(px,py),(px,py+48))]:
                    if bits&flag:
                        pygame.draw.line(S,(12,40,54),a,b,7);pygame.draw.line(S,wall,a,b,3)
        # There are deliberately no route dots and no visited-cell trail.
        for x,y in self.energy:
            cx,cy=ox+x*48+24,oy+y*48+24
            size=6
            pygame.draw.polygon(S,(255,207,101),[(cx,cy-size),(cx+size,cy),(cx,cy+size),(cx-size,cy)])
        next_id=next((g['id'] for g in self.gates.values() if not g['open']),None)
        for (a,b),gate in self.gates.items():
            x=ox+(a[0]+b[0]+1)*24;y=oy+(a[1]+b[1]+1)*24;color=G if gate['open'] else V
            self.number_badge(gate['difficulty']+1,(x,y),color)
            if gate['open']:pygame.draw.lines(S,G,False,[(x+12,y-14),(x+16,y-10),(x+23,y-18)],2)
            elif gate['id']==next_id:pygame.draw.circle(S,V,(x,y),19+int(math.sin(self.clock_time*4)*2),1)
        cx,cy=map(int,self.render_pos);cy+=int(math.sin(self.clock_time*4)*1.5)
        if self.dash>0:pygame.draw.circle(S,C,(cx,cy),23,2)
        pygame.draw.ellipse(S,(3,12,23),(cx-16,cy+12,32,9))
        pygame.draw.rect(S,(31,79,101),(cx-12,cy-7,24,25),border_radius=7)
        pygame.draw.rect(S,C,(cx-17,cy-18,34,25),border_radius=8)
        pygame.draw.rect(S,(7,28,43),(cx-13,cy-14,26,16),border_radius=5)
        for dx in [-6,6]:pygame.draw.rect(S,W,(cx+dx-2,cy-10,4,6),border_radius=2)
        pygame.draw.line(S,C,(cx,cy-18),(cx,cy-24),2);pygame.draw.circle(S,V,(cx,cy-25),3)
        panel((707,117,547,462),(9,21,36),(32,59,78))
        self.text(f'STAGE {self.level+1} / 3',733,140,12,C)
        self.text(NAMES[self.level],733,168,25,W,bold=True)
        self.text('FIND AND SOLVE BOTH CHALLENGES',733,209,17,V)
        pygame.draw.rect(S,(28,47,65),(733,246,491,8),border_radius=4)
        if solved:pygame.draw.rect(S,G,(733,246,int(491*solved/2),8),border_radius=4)
        for index,gate in enumerate(self.gates.values()):
            y=278+index*79
            self.number_badge(gate['difficulty']+1,(747,y+14),G if gate['open'] else V)
            self.text(gate['question']['title'],783,y,17,W)
            self.text('ONLINE' if gate['open'] else 'LOCKED / '+('DEBUG' if self.challenge=='Debug' else 'COMPLETE'),783,y+28,11,G if gate['open'] else M)
        self.text(f'ENERGY {self.energy_count}  /  +10 EACH',733,449,12,(255,207,101))
        self.text('DASH READY / SPACE' if self.dash_cooldown<=0 else f'DASH / {self.dash_cooldown:.1f}s',1005,449,12,C)
        self.text('Explore different areas / solve challenges in number order.',733,490,13,M)
        self.text('Solve the last challenge to advance automatically.',733,529,12,M)
        panel((28,602,1226,88),(9,21,36),(32,59,78))
        self.text(self.message if self.message_time else 'BYTE ONLINE / Explore. Collect energy. Solve the code.',48,619,15,C)
        self.text('WASD / Move    SPACE / Dash    E / Challenge    P / Pause',48,657,12,M)
        self.button('PORTAL',(1127,645,102,30),lambda:self.go('menu',3))
    def draw_editor(self):
        gate=self.gates[self.active_gate];q=gate['question']
        self.text(f'CHALLENGE {gate["difficulty"]+1:02} / 06',29,125,12,V)
        self.text(q['title'],29,149,24,W,bold=True)
        self.button('RUN / F5',(813,140,112,41),lambda:self.run_code(False))
        self.button('SUBMIT / F6',(937,140,177,41),lambda:self.run_code(True),True)
        self.button('BACK',(1126,140,107,41),self.close_editor)
        panel((28,204,302,486),(9,21,36),(32,59,78))
        self.text('MISSION BRIEF',47,222,12,C)
        from game import wrap
        for i,line in enumerate(wrap(q['prompt'],27)):self.text(line,47,253+i*23,15,W)
        self.text('EXPECTED OUTPUT',47,386,12,G)
        for i,line in enumerate(wrap(self.expected or '(No output)',28)[:6]):self.text(line,47,412+i*22,15,G)
        if self.hint:
            for i,line in enumerate(wrap(q['hint'],28)[:3]):self.text(line,47,548+i*20,13,M)
        else:self.text('Need help? Try a hint.',47,578,14,M)
        self.button('HINT / F1',(47,622,118,39),lambda:setattr(self,'hint',True))
        self.button('RESET',(181,622,128,39),self.reset_code)
        panel((348,204,884,337),(8,19,32),(32,59,78))
        self.text('main.'+{'Python':'py','Java':'java','C++':'cpp'}[self.language],366,217,13,C)
        font=pygame.font.SysFont('dejavusansmono',17)
        start=max(0,self.line-10);scroll=max(0,font.size(self.lines[self.line][:self.col])[0]-773)
        for i in range(start,min(len(self.lines),start+12)):
            yy=247+(i-start)*23
            self.text(f'{i+1:02}',365,yy,13,M)
            S.set_clip(pygame.Rect(402,243,815,287));x=408-scroll
            for part in re.findall(r'"[^"]*"|\x27[^\x27]*\x27|\b\w+\b|\s+|.',self.lines[i]):
                color=G if part.startswith(('"',"'")) else (V if part in ['def','return','if','else','for','while','in','int','static','True','False'] else (C if part in ['print','range','cout','System'] else W))
                S.blit(font.render(part,True,color),(x,yy));x+=font.size(part)[0]
            S.set_clip(None)
        if pygame.time.get_ticks()%1000<550:
            cx=408-scroll+font.size(self.lines[self.line][:self.col])[0];cy=247+(self.line-start)*23
            pygame.draw.line(S,C,(cx,cy),(cx,cy+20),2)
        panel((348,559,430,131),(9,21,36),(32,59,78));panel((794,559,438,131),(9,21,36),(32,59,78))
        self.text('ACTUAL OUTPUT',365,576,12,C);self.text('ERRORS / STATUS',810,576,12,R)
        lines=wrap(self.output,47);errors=wrap(self.error or (self.message if self.flash else self.test_status),47)
        self.output_scroll=min(self.output_scroll,max(0,max(len(lines),len(errors))-3))
        for i,line in enumerate(lines[self.output_scroll:self.output_scroll+3]):self.text(line,365,605+i*23,13,W)
        for i,line in enumerate(errors[self.output_scroll:self.output_scroll+3]):self.text(line,810,605+i*23,13,R if self.error else M)
    def results(self):
        if self.mode not in ('stage_clear','paused'):return super().results()
        if self.mode=='paused':
            self.center_text('CONNECTION PAUSED',182,33,W)
            self.center_text('Your time and hearts are safe.',242,17,M)
            self.button('RESUME',(435,349,410,62),self.resume,True)
            self.button('Back to Portal',(435,436,410,46),lambda:self.go('menu',3))
            return
        self.center_text('STAGE COMPLETE',142,34,G)
        self.center_text(NAMES[self.level]+' / RESTORED',199,17,M)
        self.portal(640,358)
        self.center_text(f'{self.correct}/6 challenges solved / {self.score} points',487,18,C)
        self.center_text('Loading next stage / '+NAMES[self.level+1],529,16,M)
        self.button('CONTINUE',(435,586,410,57),self.next_stage,True)
    def draw(self):
        if self.mode not in ('maze','editor'):return super().draw()
        self.sync_screen();self.buttons=[];self.background();self.header()
        if self.mode=='maze':self.draw_maze()
        else:self.draw_editor()
        self.ui.update(0);self.ui.draw_ui(S)
        for p in self.particles:pygame.draw.circle(S,p[5],(int(p[0]),int(p[1])),max(1,int(p[4]*3)))
        if self.fade>0 and self.previous is not None:
            self.previous.set_alpha(int(255*self.fade/.18));S.blit(self.previous,(0,0))
        self.last_frame=S.copy();pygame.display.flip()

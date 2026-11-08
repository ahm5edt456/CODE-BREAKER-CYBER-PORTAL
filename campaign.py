"""Three themed stages with distributed challenges and automatic progression."""
import math,random,re
import pygame,pygame_gui
import engine as E
from portal_ui import PortalGame,GUI_MODES
from game import S,C,V,W,M,G,R,panel
from campaign_questions import problem,TOPICS,campaign_plan,fresh_campaign
from challenge_placement import spread_gates,distances
from scoring import speed_bonus,BASE_POINTS,NO_HINT_BONUS
from visual_preview import VisualPreview
from editor_support import EditorSupport,CODE_RECT,SCROLLBAR,TEXT_X,TEXT_Y,ROW_HEIGHT,VISIBLE_ROWS

GUI_MODES.update({'maze','editor','stage_clear','paused'})
NAMES=['BOOT SEQUENCE','CONTROL FLOW','CORE RECOVERY']
BADGE_RADIUS=14
BADGE_BORDER=2

class CampaignGame(VisualPreview,EditorSupport,PortalGame):
    def __init__(self):
        self.manual_stage_completion=True;self.speed_bonus_total=0;self.solve_records=[];self.feed=[];self.stage_transition=0.;self.stage_finished=False;self.render_pos=pygame.Vector2(66,156);self.resume_mode='maze'
        self.campaign_caption='Explore. Decode. Escape.'
        super().__init__();self.editor_init()
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
        import game as core
        if self.admin_preview:
            import tempfile
            with tempfile.TemporaryDirectory() as folder:
                self.question_plan,self.campaign_puzzles,_=fresh_campaign(self.language,self.challenge,folder)
        else:
            self.question_plan,self.campaign_puzzles,self.question_history=fresh_campaign(
                self.language,self.challenge,core.DATA,getattr(self,'question_history',None))
        self.feed=[];self.speed_bonus_total=0;self.solve_records=[];super().start()
    def start_level(self):
        old_lives=self.lives;self.sector_count=3
        E.Game.start_level(self)
        if self.level:self.lives=old_lives
        self.remaining=120.;self.energy=set();self.trail=[];self.stage_transition=0.;self.stage_finished=False
        edges=spread_gates(self.maze.maze)
        self.gates={edge:{'id':i+1,'open':False} for i,edge in enumerate(edges)}
        self.render_pos=pygame.Vector2(66,156);self.move_wait=0;self.dash=0;self.dash_cooldown=0;self.auto_gate_hold=None;self.feed=[]
        for index,gate in enumerate(self.gates.values()):
            gate['solve_seconds']=None;gate['hint_used']=False
            rank=self.level*2+index
            gate['difficulty']=rank;gate['kind']=self.challenge;gate['question']=dict(self.campaign_puzzles[rank])
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
        if self.gates[edge]['open']:return
        if self.gates[edge]['solve_seconds'] is None:self.gates[edge]['solve_seconds']=0.
        super().open_editor(edge)
        self.hint=self.gates[edge]['hint_used']
        saved=self.gates[edge].get('draft_lines')
        if saved is not None:
            self.lines=list(saved);self.line,self.col=self.gates[edge].get('draft_cursor',(0,0))
        question=self.gates[edge]['question']
        self.editor_reset(question if saved is None or saved==question['code'].split('\n') else None)
    def close_editor(self):
        if self.future:return
        if self.active_gate is not None:
            gate=self.gates[self.active_gate];gate['hint_used']=gate.get('hint_used',False) or self.hint
            gate['draft_lines']=list(self.lines);gate['draft_cursor']=(self.line,self.col)
        self.editor_menu=None;self.editor_dragging=self.editor_scroll_drag=False
        super().close_editor()
    def evaluate(self,passed):
        if self.mode!='editor' or self.active_gate is None or self.gates[self.active_gate]['open']:return
        self.attempts+=1
        if passed:
            self.celebrate(self.active_gate);self.correct+=1
            gate=self.gates[self.active_gate];seconds=gate['solve_seconds'] or 0.
            bonus=speed_bonus(seconds);self.speed_bonus_total+=bonus
            points=BASE_POINTS+(NO_HINT_BONUS if not self.hint else 0)+bonus;self.score+=points
            self.solve_records.append({'challenge':gate['difficulty']+1,'seconds':round(seconds,2),'speed_bonus':bonus})
            self.gates[self.active_gate]['open']=True;self.beep('ok');self.close_editor();self.flash=1.2
            self.notify(f'GATE ONLINE / +{points} points / SPEED +{bonus} / {seconds:.1f}s')
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
        if self.pending_result is None:return
        self.pending_result['difficulty']=max(0,self.correct-1)
        self.pending_result['stages_completed']=3 if self.outcome=='won' else self.level
        self.pending_result['speed_bonus']=self.speed_bonus_total
        self.pending_result['solve_times']=[dict(record) for record in self.solve_records]
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
    def edit(self,event):
        if self.editor_key(event):return
        super().edit(event)
        if self.mode=='editor':self.editor_reveal()
    def reset_code(self):
        if self.future:return
        super().reset_code();self.editor_reset(self.gates[self.active_gate]['question'])
    def run_code(self,submit=True):
        self.editor_menu=None;self.editor_dragging=self.editor_scroll_drag=False
        super().run_code(submit)
    def handle(self,event):
        if self.handle_preview_key(event):return
        if self.mode=='editor' and self.editor_mouse(event):return
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
        # Resume/back cannot reset the clock; actual runner/compile time is excluded.
        if not self.admin_preview and self.mode in ('maze','editor') and self.future is None:
            for gate in self.gates.values():
                if not gate['open'] and gate.get('solve_seconds') is not None:gate['solve_seconds']+=dt
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
        self.text('CODE BREAKER',45,38,21,self.stage_accent,bold=True)
        self.text('SYSTEM ESCAPE / '+self.language.upper(),46,71,10,M)
        pygame.draw.line(S,self.stage_accent,(45,95),(233,95),2)
        for i in range(3):
            x=310+i*70;color=G if i<self.level else (self.stage_accent if i==self.level else (45,62,80))
            self.number_badge(i+1,(x,59),color,color if i<=self.level else M)
            if i<2:pygame.draw.line(S,(39,62,79),(x+21,59),(x+49,59),2)
        self.text(f'{self.correct}/6 FIXED',505,50,14,V)
        for i in range(3):
            x=640+i*27;color=R if i<self.lives else (43,57,73)
            pygame.draw.circle(S,color,(x,53),6);pygame.draw.circle(S,color,(x+9,53),6)
            pygame.draw.polygon(S,color,[(x-6,55),(x+15,55),(x+5,68)])
        self.text(f'{int(self.remaining)//60:02}:{int(self.remaining)%60:02}',754,42,26,R if self.remaining<=20 else G,bold=True)
        self.text(f'{self.score:04} PTS',871,50,16,C)
        pygame.draw.line(S,(32,59,78),(982,39),(982,83),1)
        self.text('EVENT EDITION',1009,37,8,M)
        self.event_header_mark.draw(S,1008,54)
        self.button('PAUSE',(1138,43,93,33),self.pause)
    def draw_maze(self):
        ox,oy=42,132
        panel((27,117,654,462),(9,23,38),(32,65,83))
        pygame.draw.rect(S,(9,26,40),(42,132,624,432))
        solved=sum(g['open'] for g in self.gates.values())
        accent=self.stage_accent
        self.scene_art.draw_materials(S,self.maze.maze,self.level,accent)
        self.draw_floor_fx()
        wall=tuple(int(c*(.38+solved*.08)) for c in accent)
        self.scene_art.draw_lighting(S,self.render_pos,self.level,self.gates,self.energy)
        self.scene_art.draw_walls(S)
        # There are deliberately no route dots and no visited-cell trail.
        for cell in self.energy:
            self.scene_art.draw_crystal(S,cell,self.fx_time,self.reduced_motion)
        next_id=next((g['id'] for g in self.gates.values() if not g['open']),None)
        for (a,b),gate in self.gates.items():
            x=ox+(a[0]+b[0]+1)*24;y=oy+(a[1]+b[1]+1)*24;color=G if gate['open'] else self.stage_accent
            self.number_badge(gate['difficulty']+1,(x,y),color)
            if gate['open']:pygame.draw.lines(S,G,False,[(x+12,y-14),(x+16,y-10),(x+23,y-18)],2)
            elif gate['id']==next_id:pygame.draw.circle(S,accent,(x,y),19+(0 if self.reduced_motion else int(math.sin(self.clock_time*4)*2)),1)
        self.scene_art.draw_actor(S,self.render_pos,self.level,self.actor_facing,
                                  self.actor_frame,self.dash>0)
        self.draw_maze_fx()
        panel((707,117,547,462),(9,21,36),(32,59,78))
        self.text(f'STAGE {self.level+1} / 3',733,140,12,accent)
        pygame.draw.rect(S,accent,(707,133,3,72),border_radius=1)
        self.text(NAMES[self.level],733,168,25,W,bold=True)
        self.text('FIND AND SOLVE BOTH CHALLENGES',733,209,17,accent)
        pygame.draw.rect(S,(28,47,65),(733,246,491,8),border_radius=4)
        if self.fx_progress>.001:pygame.draw.rect(S,accent,(733,246,max(1,int(491*self.fx_progress)),8),border_radius=4)
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
        prompt_lines=wrap(q['prompt'],31)
        prompt_step=min(21,94/max(1,len(prompt_lines)))
        for i,line in enumerate(prompt_lines):self.text(line,47,253+int(i*prompt_step),14 if len(prompt_lines)<=6 else 12,W)
        seconds=gate.get('solve_seconds') or 0.
        self.text(f'SPEED BONUS +{speed_bonus(seconds)} / {seconds:.1f}s',47,358,12,C)
        self.text('EXPECTED OUTPUT',47,386,12,G)
        for i,line in enumerate(wrap(self.expected or '(No output)',28)[:6]):self.text(line,47,412+i*22,15,G)
        if self.hint:
            for i,line in enumerate(wrap(q['hint'],28)[:3]):self.text(line,47,548+i*20,13,M)
        else:self.text('Need help? Try a hint.',47,578,14,M)
        self.button('HINT / F1',(47,622,118,39),lambda:setattr(self,'hint',True))
        self.button('RESET',(181,622,128,39),self.reset_code)
        panel((348,204,884,337),(8,19,32),(32,59,78))
        self.text('main.'+{'Python':'py','Java':'java','C++':'cpp'}[self.language],366,217,13,C)
        font=self.editor_font
        start=max(0,min(self.editor_top,max(0,len(self.lines)-VISIBLE_ROWS)));self.editor_top=start
        scroll=self.editor_hscroll;selection=self.editor_selection()
        for i in range(start,min(len(self.lines),start+VISIBLE_ROWS)):
            yy=TEXT_Y+(i-start)*ROW_HEIGHT
            self.text(f'{i+1:02}',365,yy,13,C if i==self.line else M)
            S.set_clip(CODE_RECT)
            if i==self.line:pygame.draw.rect(S,(12,30,46),(CODE_RECT.x,yy-1,CODE_RECT.w,ROW_HEIGHT))
            if selection is not None:
                (first,col),(last,end)=selection
                if first<=i<=last:
                    begin=col if i==first else 0;stop=end if i==last else len(self.lines[i])+1
                    sx=TEXT_X-scroll+font.size(self.lines[i][:begin])[0]
                    ex=TEXT_X-scroll+font.size(self.lines[i][:min(stop,len(self.lines[i]))])[0]+(font.size(' ')[0] if stop>len(self.lines[i]) else 0)
                    pygame.draw.rect(S,(29,75,101),(sx,yy-1,max(2,ex-sx),ROW_HEIGHT))
            x=TEXT_X-scroll
            for part in re.findall(r'//.*|\#.*|"[^"]*"|\x27[^\x27]*\x27|\b\w+\b|\s+|.',self.lines[i]):
                color=G if part.startswith(('"',"'")) else (V if part in ['def','return','if','else','for','while','in','int','static','True','False','public','class','void','String','string','boolean','bool','double','float','new','break','continue','true','false'] else (C if part in ['print','range','cout','System'] else W))
                if part.startswith(('//','#')):color=M
                elif part.isdigit():color=(255,207,101)
                S.blit(font.render(part,True,color),(x,yy));x+=font.size(part)[0]
            S.set_clip(None)
        if start<=self.line<start+VISIBLE_ROWS and pygame.time.get_ticks()%1000<550:
            S.set_clip(CODE_RECT)
            cx=TEXT_X-scroll+font.size(self.lines[self.line][:self.col])[0];cy=TEXT_Y+(self.line-start)*ROW_HEIGHT
            pygame.draw.line(S,C,(cx,cy),(cx,cy+20),2);S.set_clip(None)
        pygame.draw.rect(S,(18,37,53),SCROLLBAR,border_radius=4)
        height=max(24,int(SCROLLBAR.h*VISIBLE_ROWS/max(VISIBLE_ROWS,len(self.lines))))
        top=SCROLLBAR.y+int((SCROLLBAR.h-height)*start/max(1,len(self.lines)-VISIBLE_ROWS))
        pygame.draw.rect(S,(54,104,127),(SCROLLBAR.x,top,SCROLLBAR.w,height),border_radius=4)
        panel((348,559,430,131),(9,21,36),(32,59,78));panel((794,559,438,131),(9,21,36),(32,59,78))
        self.text('ACTUAL OUTPUT',365,576,12,C);self.text('ERRORS / STATUS',810,576,12,R)
        lines=wrap(self.output,47);errors=wrap(self.error or (self.message if self.flash else self.test_status),47)
        self.output_scroll=min(self.output_scroll,max(0,max(len(lines),len(errors))-3))
        for i,line in enumerate(lines[self.output_scroll:self.output_scroll+3]):self.text(line,365,605+i*23,13,W)
        for i,line in enumerate(errors[self.output_scroll:self.output_scroll+3]):self.text(line,810,605+i*23,13,R if self.error else M)
        if self.editor_menu is not None:
            x,y=self.editor_menu
            for i,(title,action) in enumerate([('Copy / Ctrl+C',self.editor_copy),('Paste / Ctrl+V',self.editor_paste),('Select all / Ctrl+A',self.editor_select_all)]):
                self.button(title,(x,y+i*38,184,36),action)
    def results(self):
        if self.mode not in ('stage_clear','paused'):
            super().results();self.text(f'Speed bonus earned: +{self.speed_bonus_total}',72,432,16,C);return
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
        for index in list(self.widgets):
            if index>=len(self.buttons):
                widget=self.widgets.pop(index);self.actions.pop(widget,None);widget.kill()
        self.ui.update(0);self.ui.draw_ui(S)
        for p in self.particles:pygame.draw.circle(S,p[5],(int(p[0]),int(p[1])),max(1,int(p[4]*3)))
        if self.fade>0 and self.previous is not None:
            self.previous.set_alpha(int(255*self.fade/.18));S.blit(self.previous,(0,0))
        self.draw_preview_overlay()
        self.last_frame=S.copy();pygame.display.flip()

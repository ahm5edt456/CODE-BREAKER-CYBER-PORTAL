"""CODE BREAKER • SYSTEM ESCAPE — IEEE event edition."""
import concurrent.futures, io, json, math, random, re, tokenize
from pathlib import Path
import pygame
import engine as E
from runner import execute
from questions import pick_questions
from score_store import load_scores,write_scores
from datetime import datetime,timezone

pygame.display.set_caption('CODE BREAKER | SYSTEM ESCAPE • IEEE Edition')
S=E.SCREEN
C=(70,222,234); V=(168,135,255); W=(231,241,255); M=(139,164,191); G=(84,226,160); R=(255,100,131)
POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1)
DEFAULT_DATA=Path(__file__).resolve().parent/'data'
DATA=DEFAULT_DATA

def label(s,x,y,size=18,color=W):
    f=pygame.font.SysFont('dejavusansmono' if size==17 else 'dejavusans',size,bold=size>=26)
    S.blit(f.render(str(s),True,color),(x,y))
def panel(rect,color=(17,29,48),edge=(39,57,81)):
    pygame.draw.rect(S,color,rect,border_radius=16);pygame.draw.rect(S,edge,rect,1,border_radius=16)
def wrap(s,width=55):
    import textwrap
    return [p for line in str(s).split('\n') for p in (textwrap.wrap(line,width,replace_whitespace=False,drop_whitespace=False) or [''])]

class Game(E.Game):
    def __init__(self):
        super().__init__();self.buttons=[];self.challenge='Debug';self.difficulty=0;self.practice=False;self.quick=True;self.sector_count=1;self.name='';self.typing=False
        self.output='Press Run to execute your code.';self.error='';self.expected='';self.future=None;self.pending_submit=False
        self.trail=[];self.elapsed=0;self.attempts=0;self.correct=0;self.flash=0;self.hint=False;self.result_saved=False;self.answer='';self.output_scroll=0;self.code_scroll=0
        self.notice='';self.history=[];self.sound=True;self.particles=[];self.sprint=False;self.energy=set();self.energy_count=0;self.dash=0;self.dash_cooldown=0;self.auto_gate_hold=None;self.choices=[];self.nav_focus=3;self.pending_result=None;self.outcome='lost'
        try:
            pygame.mixer.init(frequency=22050,size=-16,channels=1)
            import array
            self.tones={}
            for kind,freq in [('ok',740),('bad',180),('step',420)]:
                a=array.array('h',(int(2300*math.sin(2*math.pi*freq*i/22050)*(1-i/4400)) for i in range(4400)))
                self.tones[kind]=pygame.mixer.Sound(buffer=a)
        except pygame.error:self.tones={}
        self.history_load_failed=False
        try:self.history=load_scores(DATA,Path.home()/'.code_breaker_ieee'/'scores.json' if DATA==DEFAULT_DATA else None)
        except (OSError,ValueError):
            self.history_load_failed=True;self.notice='Could not load data/dashboard.json. Check the file before saving.'
    def beep(self,k):
        if self.sound and k in self.tones:self.tones[k].play()
    def button(self,title,rect,action,active=False,color=C):
        rect=pygame.Rect(rect);hover=rect.collidepoint(pygame.mouse.get_pos())
        focused=self.mode in ('menu','settings','scores','won','lost') and len(self.buttons)==self.nav_focus
        panel(rect,(29,49,70) if hover or active else (17,29,48),color if active or hover else (45,61,84))
        if focused:pygame.draw.rect(S,W,rect.inflate(6,6),2,border_radius=17)
        img=E.SMALL.render(title,True,color if active else W);S.blit(img,img.get_rect(center=rect.center));self.buttons.append((rect,action))
    def go(self,mode,focus=0):
        self.mode=mode;self.nav_focus=focus;self.typing=False
    def navigate(self,key,mod=0):
        count=len(self.buttons)
        if not count:return
        self.nav_focus%=count
        if key==pygame.K_TAB:
            self.nav_focus=(self.nav_focus+(-1 if mod & pygame.KMOD_SHIFT else 1))%count
        elif self.mode=='menu':
            f=self.nav_focus
            if key in (pygame.K_LEFT,pygame.K_RIGHT):
                step=-1 if key==pygame.K_LEFT else 1
                if f<3:self.nav_focus=(f+step)%3;self.language=['Python','Java','C++'][self.nav_focus]
                elif f in (4,5):self.nav_focus=9-f
            elif key==pygame.K_UP:self.nav_focus=['Python','Java','C++'].index(self.language) if f==3 else 3
            elif key==pygame.K_DOWN:self.nav_focus=3 if f<3 else 4
        elif self.mode=='settings':
            if key in (pygame.K_LEFT,pygame.K_RIGHT) and self.nav_focus<2:
                self.nav_focus=1-self.nav_focus;self.challenge=['Debug','Complete Code'][self.nav_focus]
            elif key==pygame.K_UP:self.nav_focus=(0 if self.challenge=='Debug' else 1) if self.nav_focus==2 else 2
            elif key==pygame.K_DOWN:self.nav_focus=2 if self.nav_focus<2 else 3
        elif key in (pygame.K_LEFT,pygame.K_UP):self.nav_focus=(self.nav_focus-1)%count
        elif key in (pygame.K_RIGHT,pygame.K_DOWN):self.nav_focus=(self.nav_focus+1)%count
        if key in (pygame.K_RETURN,pygame.K_KP_ENTER):
            self.buttons[self.nav_focus][1]();return
    def begin_name_entry(self):
        self.outcome=self.mode
        self.pending_result={'score':self.score,'time':round(self.elapsed),'accuracy':round(100*self.correct/max(1,self.attempts)),
            'mode':'Event','language':self.language,'challenge':self.challenge,'difficulty':max((g['difficulty'] for g in self.gates.values() if g['open']),default=0),'won':self.outcome=='won',
            'problems_solved':self.correct,'attempts':self.attempts,'energy_collected':self.energy_count,'lives_remaining':self.lives}
        self.name='';self.notice='';self.mode='name_entry';pygame.key.start_text_input()
    def save_result(self):
        name=self.name.strip()
        if not name:self.notice='Enter your name first.';return
        if self.result_saved or self.pending_result is None:return
        if self.history_load_failed:
            try:self.history=load_scores(DATA);self.history_load_failed=False
            except (OSError,ValueError):
                self.notice='Cannot save: check data/dashboard.json and folder permissions.';return
        row=dict(self.pending_result,name=name,saved_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        history=sorted(self.history+[row],key=lambda r:(-r['score'],-r['accuracy'],r['time']))[:30]
        try:
            write_scores(DATA,history)
        except OSError:
            self.notice='Could not save. Check folder permissions and try again.';return
        self.history=history;self.result_saved=True;self.pending_result=None;self.notice='Score saved for '+name+'.'
        pygame.key.stop_text_input();self.go(self.outcome)
    def skip_score(self):
        self.result_saved=True;self.pending_result=None;self.notice='Score was not saved.'
        pygame.key.stop_text_input();self.go(self.outcome)
    def start(self):
        self.difficulty=0;self.quick=True;self.practice=False;self.pending_result=None;self.name=''
        self.typing=False;self.sprint=True;self.particles=[];self.energy_count=0;self.dash=self.dash_cooldown=0;self.auto_gate_hold=None
        self.sector_count=1 if self.quick and not self.practice else 3;self.level=0;self.score=0;self.elapsed=0;self.attempts=self.correct=0;self.result_saved=False;self.start_level()
    def start_level(self):
        super().start_level();self.remaining=120 if self.sprint else [240,300,300][self.difficulty];self.trail=[]
        self.energy=set();cell=(0,0);route=[]
        for direction in self.maze.shortest_path:
            dx,dy=E.LETTERS[direction];cell=(cell[0]+dx,cell[1]+dy);route.append(cell)
        candidates=route[1:-1]
        if self.sprint:
            final_edge=list(self.gates)[-1]
            stop=min(route.index(cell) for cell in final_edge if cell in route)
            candidates=route[1:max(2,stop)]
        for i in range(min(6,len(candidates))):self.energy.add(candidates[(i+1)*len(candidates)//7])
        kinds=['Debug','Predict Output','Complete Code'];self.expected_cache={}
        for gate in self.gates.values():
            gate['difficulty']=min(gate['id']-1,2)
            q=pick_questions(self.language,gate['difficulty'],1)[0];gate['question']=q
            if not self.sprint and self.level==self.sector_count-1 and gate['id']==len(self.gates):
                code={
                    'Python':"total = 0\nfor n in range(1, 7):\n    if n % 2 == 1:\n        total += n\nprint(total)",
                    'Java':"int total = 0;\nfor (int n = 1; n <= 6; n++) {\n    if (n % 2 == 1) { total += n; }\n}\nSystem.out.println(total);",
                    'C++':"int total = 0;\nfor (int n = 1; n <= 6; n++) {\n    if (n % 2 == 1) { total += n; }\n}\ncout << total;"}[self.language]
                q=dict(title='FINAL CORE / Restore the power',prompt='Sum the even numbers from 1 to 6. Print 12.',code=code,answer=code.replace('% 2 == 1','% 2 == 0'),hint='Even numbers have remainder zero when divided by 2.')
                gate['question']=q
            gate['kind']=self.challenge
            # Method-only puzzles need an entry call to produce observable output.
            if 'static ' in q['answer'] or (self.language=='C++' and re.search(r'(int|string)\s+\w+\([^)]*\)\s*\{',q['answer'])):
                name=re.search(r'(?:int|string|String)\s+(\w+)\(',q['answer']).group(1)
                args='5' if name=='doubleIt' else ('5, 10' if name=='sum' else '')
                call=f'System.out.println({name}({args}));' if self.language=='Java' else f'cout << {name}({args});'
                # Runner supports methods plus explicit main separately.
                q['code']+='\n// ENTRY\n'+call;q['answer']+='\n// ENTRY\n'+call
            if gate['kind']=='Complete Code':
                lines=q['answer'].splitlines();idx=next((i for i,(a,b) in enumerate(zip(q['code'].splitlines(),lines)) if a!=b),0)
                gate['missing']=lines[idx];lines[idx]='    # TODO: complete this line' if self.language=='Python' else '// TODO: complete this line';q['code']='\n'.join(lines)
            if gate['kind']=='Predict Output':q['code']=q['answer']
    def open_editor(self,gate):
        super().open_editor(gate);self.output='Press Run to execute your code.';self.error='';self.expected='Calculating reference output…';self.reference_error=False;self.choices=[];self.test_status='Ready to run';self.answer='';self.hint=False;self.output_scroll=self.code_scroll=0
        self.future=POOL.submit(execute,self.gates[gate]['question']['answer'],self.language);self.job='reference';self.pending_submit=False
    def close_editor(self):
        if self.future:return
        self.auto_gate_hold=self.active_gate
        super().close_editor()
    def run_code(self,submit=True):
        if self.future:return
        if submit and getattr(self,'reference_error',False):
            self.notify('Reference unavailable. Check compiler installation.');self.flash=2;return
        gate=self.gates[self.active_gate]
        if gate['kind']=='Predict Output':
            if submit and not self.answer:
                self.notify('Choose an answer first.');self.flash=2;return
            if submit and not getattr(self,'reference_error',False):self.evaluate(self.answer.strip()==self.expected.strip())
            elif not submit:self.notify('Predict the output, then press Submit.')
            return
        self.pending_submit=submit;self.future=POOL.submit(execute,'\n'.join(self.lines),self.language);self.job='player';self.output='Running…';self.error='';self.output_scroll=0
    def make_choices(self):
        value=self.expected.strip();choices=[value]
        try:
            number=float(value)
            for delta in [-1,1,2]:
                alt=number+delta;choices.append(str(int(alt)) if alt.is_integer() and '.' not in value else str(alt))
        except ValueError:
            for alt in ['(No output)','Runtime error',value[::-1],'READY','0','1']:
                if alt!=value and alt not in choices:choices.append(alt)
                if len(choices)==4:break
        self.choices=choices[:4];random.shuffle(self.choices)
    def evaluate(self,passed):
        self.attempts+=1
        if passed:
            self.celebrate(self.active_gate)
            self.correct+=1;self.score+=100+(25 if not self.hint else 0);self.gates[self.active_gate]['open']=True;self.beep('ok');self.close_editor();self.notify('SYSTEM RESTORED • Gate opened! +'+str(100+(25 if not self.hint else 0)));self.flash=.9
            if not all(g['open'] for g in self.gates.values()):self.notify('ACCESS GRANTED / +'+str(100+(25 if not self.hint else 0))+' / Next challenge: harder!')
            if self.sprint and all(g['open'] for g in self.gates.values()):
                self.score+=int(self.remaining);self.mode='won'
        else:
            if not self.practice:self.lives-=1
            self.beep('bad');self.flash=3.7;self.notify('Try again — practice mode' if self.practice else f'Wrong submission: -1 heart. {self.lives} lives left.')
            if self.lives<=0:self.close_editor();self.mode='lost'
    def celebrate(self,edge):
        a,b=edge;x=42+(a[0]+b[0]+1)*24;y=132+(a[1]+b[1]+1)*24
        for i in range(32):
            angle=i*math.tau/32;speed=random.uniform(45,130)
            self.particles.append([x,y,math.cos(angle)*speed,math.sin(angle)*speed,1.4,random.choice([C,G,V,W])])
    def route_to_goal(self):
        from collections import deque
        locked=[(edge,g) for edge,g in self.gates.items() if not g['open']]
        target=min(locked,key=lambda item:item[1]['id'])[0] if locked else (self.maze.maze_exit,)
        todo=deque([self.player]);previous={self.player:None};end=None
        while todo:
            cell=todo.popleft()
            if cell in target:end=cell;break
            x,y=cell
            for (dx,dy),flag in E.MOVES.items():
                nxt=(x+dx,y+dy)
                if not(0<=nxt[0]<13 and 0<=nxt[1]<9) or self.maze.maze[y][x]&flag:continue
                gate=self.gates.get(E.edge_key(cell,nxt))
                if gate and not gate['open']:continue
                if nxt not in previous:previous[nxt]=cell;todo.append(nxt)
        path=[]
        while end is not None:path.append(end);end=previous[end]
        return path[::-1]
    def edit(self,ev):
        if ev.type==pygame.KEYDOWN and ev.key==pygame.K_F5:self.run_code(False);return
        if ev.type==pygame.KEYDOWN and ev.key==pygame.K_F6:self.run_code(True);return
        if ev.type==pygame.KEYDOWN and ev.key==pygame.K_F1:self.hint=True;return
        if self.future:return
        if self.gates[self.active_gate]['kind']=='Predict Output':
            if ev.type==pygame.TEXTINPUT:self.answer+=ev.text
            elif ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_BACKSPACE:self.answer=self.answer[:-1]
                elif ev.key==pygame.K_RETURN:self.answer+='\n'
                elif ev.key==pygame.K_ESCAPE:self.close_editor()
            return
        super().edit(ev)
    def handle(self,ev):
        if ev.type==pygame.QUIT:pygame.quit();raise SystemExit
        if ev.type==pygame.KEYDOWN and ev.key==pygame.K_F11:pygame.display.toggle_fullscreen();return
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            for rect,fn in reversed(self.buttons):
                if rect.collidepoint(ev.pos):fn();return
        if self.mode=='name_entry':
            if ev.type==pygame.TEXTINPUT:self.name=(self.name+''.join(c for c in ev.text if c.isprintable()))[:16];self.notice=''
            elif ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_BACKSPACE:self.name=self.name[:-1]
                elif ev.key in (pygame.K_RETURN,pygame.K_KP_ENTER):self.save_result()
                elif ev.key==pygame.K_ESCAPE:self.skip_score()
            return
        if self.mode in ('menu','settings','scores','won','lost'):
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE:self.go('menu',3)
                elif self.mode in ('won','lost') and ev.key==pygame.K_r:self.start()
                elif self.mode in ('won','lost') and ev.key==pygame.K_m:self.go('menu',3)
                else:self.navigate(ev.key,getattr(ev,'mod',0))
            return
        if ev.type==pygame.MOUSEWHEEL and self.mode=='editor':self.output_scroll=max(0,self.output_scroll-ev.y*2);return
        if self.mode=='maze' and ev.type==pygame.KEYDOWN and ev.key==pygame.K_SPACE and self.dash_cooldown<=0:
            self.dash=.32;self.dash_cooldown=2;self.beep('step');return
        super().handle(ev)
    def update(self,dt):
        if self.future and self.future.done():
            try:r=self.future.result()
            except Exception as e:r={'out':'','error':str(e)}
            self.future=None
            if self.job=='reference':
                self.expected=r['out'];self.error=r['error'];self.reference_error=bool(r['error'])
                if not self.reference_error and self.active_gate is not None and self.gates[self.active_gate]['kind']=='Predict Output':
                    self.make_choices();self.test_status='Choose one answer below'
            elif self.mode=='editor':
                self.output=r['out'] or '(No output)';self.error=r['error'];self.test_status=('Runtime error' if r['error'] else ('Output matches expected' if r['out'].strip()==self.expected.strip() else 'Output does not match expected'))
                if self.pending_submit:self.evaluate(not r['error'] and not getattr(self,'reference_error',False) and r['out'].strip()==self.expected.strip())
        before=self.player;old=self.mode
        if self.mode in ('maze','editor'):self.elapsed+=dt
        # Practice pauses the clock. Editor still uses the same visible timer in event mode.
        saved=self.remaining
        self.dash=max(0,self.dash-dt);self.dash_cooldown=max(0,self.dash_cooldown-dt)
        if self.dash>0:self.move_wait=min(self.move_wait,.025)
        super().update(dt if self.sprint else (0 if self.future else dt))
        if self.practice and self.mode in ('maze','editor'):self.remaining=saved
        if before!=self.player:self.trail.append(before);self.trail=self.trail[-30:]
        if self.mode=='maze':
            if self.player in self.energy:
                self.energy.remove(self.player);self.energy_count+=1;self.score+=10;self.beep('step');self.notify('ENERGY +10 / Keep moving!')
            nearby=self.nearby_gate()
            if nearby is None:self.auto_gate_hold=None
            if self.sprint and before!=self.player and nearby is not None and nearby!=self.auto_gate_hold:self.open_editor(nearby)
        self.flash=max(0,self.flash-dt)
        for p in self.particles:p[0]+=p[2]*dt;p[1]+=p[3]*dt;p[3]+=65*dt;p[4]-=dt
        self.particles=[p for p in self.particles if p[4]>0]
        if self.mode in ('won','lost') and not self.result_saved and self.pending_result is None:self.begin_name_entry()
    def header(self):
        panel((24,18,1232,85));label('CODE BREAKER',44,29,28,C);label('SYSTEM ESCAPE / IEEE EVENT EDITION',46,68,13,M)
        if self.mode in ('maze','editor'):
            label(f'{self.language} / TASK {min(self.correct+1,len(self.gates))}',427,36,20,V)
            for i in range(3):
                x=685+i*35;c=R if i<self.lives else (53,65,84)
                pygame.draw.circle(S,c,(x,47),8);pygame.draw.circle(S,c,(x+12,47),8);pygame.draw.polygon(S,c,[(x-8,48),(x+20,48),(x+6,68)])
            label(f'LIVES {self.lives}/3',683,77,11,M);label('TRAINING' if self.practice else f'{int(self.remaining)//60:02}:{int(self.remaining)%60:02}',840,39,26,R if self.sprint and self.remaining<=20 else G)
            label(f'{self.score:04} PTS',1060,40,23,C)
    def center_text(self,value,y,size=18,color=W):
        font=pygame.font.SysFont('dejavusans',size,bold=size>=26)
        image=font.render(value,True,color)
        S.blit(image,image.get_rect(midtop=(640,y)))
    def menu(self):
        # A single centered decision: choose a language, then play.
        cx,cy=640,135
        pygame.draw.circle(S,(17,41,57),(cx,cy),49)
        pygame.draw.circle(S,(34,83,99),(cx,cy),49,1)
        pygame.draw.ellipse(S,(5,13,24),(cx-25,cy+27,50,12))
        pygame.draw.rect(S,(42,82,103),(cx-20,cy-10,40,38),border_radius=11)
        pygame.draw.rect(S,C,(cx-29,cy-28,58,42),border_radius=13)
        pygame.draw.rect(S,(7,22,37),(cx-22,cy-21,44,27),border_radius=8)
        for dx in [-10,10]:pygame.draw.rect(S,W,(cx+dx-3,cy-13,6,10),border_radius=3)
        pygame.draw.line(S,C,(cx,cy-28),(cx,cy-40),2)
        pygame.draw.circle(S,V,(cx,cy-43),4)
        self.center_text('CODE BREAKER',204,42,C)
        self.center_text('SYSTEM ESCAPE',258,14,M)
        panel((400,306,480,248),(15,27,45),(37,59,79))
        self.center_text('Choose your language',328,17,M)
        for i,language in enumerate(['Python','Java','C++']):
            self.button(language,(430+i*142,369,136,46),lambda language=language:setattr(self,'language',language),self.language==language)
        self.button('START GAME  →',(430,443,420,62),self.start,True,C)
        self.center_text('120 seconds. 2 gates. One escape.' if self.quick and not self.practice else 'Collect energy. Dash. Break the code.',522,13,M)
        self.button('Settings',(470,582,164,40),lambda:self.go('settings'))
        self.button('High Scores',(646,582,164,40),lambda:self.go('scores'))
        self.center_text('Arrow keys / navigate    Enter / select    Tab / next',651,13,M)
    def settings(self):
        self.center_text('SETTINGS',160,32,C)
        self.center_text('Choose your challenge. Difficulty rises as you play.',211,15,M)
        panel((400,270,480,245))
        label('PROBLEM TYPE',430,293,15,M)
        self.button('Debugging',(430,330,200,53),lambda:setattr(self,'challenge','Debug'),self.challenge=='Debug',V)
        self.button('Complete Code',(650,330,200,53),lambda:setattr(self,'challenge','Complete Code'),self.challenge=='Complete Code',V)
        label('SOUND',430,441,16,M)
        self.button('ON' if self.sound else 'OFF',(700,422,150,48),lambda:setattr(self,'sound',not self.sound),self.sound)
        self.button('DONE',(465,554,350,52),lambda:self.go('menu',3),True)
        self.center_text('Arrows / navigate    Enter / select    Esc / back',638,13,M)
    def name_entry(self):
        self.center_text('SYSTEM RESTORED!' if self.outcome=='won' else 'MISSION ENDED',132,36,G if self.outcome=='won' else R)
        self.center_text(f'{self.score} POINTS',191,27,C)
        panel((385,266,510,294))
        self.center_text('Enter your name for High Scores',291,21,W)
        rect=pygame.Rect(430,346,420,59);panel(rect,(8,19,33),C)
        font=pygame.font.SysFont('dejavusans',24)
        value=self.name+('|' if pygame.time.get_ticks()%1000<550 else '')
        text=font.render(value or ' ',True,W);S.blit(text,text.get_rect(center=rect.center))
        self.center_text(self.notice or 'Up to 16 characters',420,14,R if self.notice else M)
        self.button('SAVE SCORE',(430,469,420,55),self.save_result,True,G)
        self.center_text('Type your name / Enter to save / Esc to skip',609,14,M)
    def draw_maze(self):
        # Connected floor, unambiguous walls; retain the original generator geometry.
        panel((30,120,650,460));ox,oy,cell=42,132,48
        pygame.draw.rect(S,(13,28,44),(ox,oy,624,432))
        for x,y in self.trail:pygame.draw.circle(S,(26,69,83),(ox+x*cell+24,oy+y*cell+24),5)
        for y,row in enumerate(self.maze.maze):
            for x,bits in enumerate(row):
                px,py=ox+x*cell,oy+y*cell
                for flag,a,b in [(1,(px,py),(px+cell,py)),(2,(px+cell,py),(px+cell,py+cell)),(4,(px,py+cell),(px+cell,py+cell)),(8,(px,py),(px,py+cell))]:
                    if bits&flag:pygame.draw.line(S,(63,91+int(30*sum(g['open'] for g in self.gates.values())/len(self.gates)),119),a,b,5)
        for x,y in self.energy:
            cx,cy=ox+x*48+24,oy+y*48+24;size=5+int(math.sin(self.player_pulse*3+x)*1.5)
            pygame.draw.circle(S,(38,47,51),(cx,cy),11)
            pygame.draw.polygon(S,(255,207,101),[(cx,cy-size),(cx+size,cy),(cx,cy+size),(cx-size,cy)])
        if self.sprint:
            for x,y in self.route_to_goal()[1:7]:
                pygame.draw.circle(S,(54,119,133),(ox+x*48+24,oy+y*48+24),4)
        next_id=next((g['id'] for g in self.gates.values() if not g['open']),None)
        for (a,b),gate in self.gates.items():
            x=ox+(a[0]+b[0]+1)*24;y=oy+(a[1]+b[1]+1)*24;color=G if gate['open'] else V
            rect=(x-5,y-17,10,34) if a[0]!=b[0] else (x-17,y-5,34,10)
            pygame.draw.rect(S,color,rect,border_radius=4)
            # Draw the success check as geometry: no missing font glyphs.
            badge_x,badge_y=x,y
            pygame.draw.circle(S,(9,20,34),(badge_x,badge_y),13)
            pygame.draw.circle(S,color,(badge_x,badge_y),13,2)
            number=pygame.font.SysFont('dejavusans',16,bold=True).render(str(gate['id']),True,W)
            S.blit(number,number.get_rect(center=(x,y)))
            if gate['open']:
                pygame.draw.circle(S,(9,20,34),(x+17,y-14),9)
                pygame.draw.lines(S,G,False,[(x+12,y-14),(x+16,y-10),(x+23,y-18)],3)
            elif gate['id']==next_id:
                pygame.draw.circle(S,V,(x,y),19+int(math.sin(self.player_pulse*3)*2),1)
        x,y=self.maze.maze_exit;cx,cy=ox+x*48+24,oy+y*48+24
        for radius in [17+int(math.sin(self.player_pulse*2)*2),12]:pygame.draw.circle(S,G,(cx,cy),radius,2)
        cx,cy=ox+self.player[0]*48+24,oy+self.player[1]*48+24+int(math.sin(self.player_pulse*3)*2)
        if self.flash and self.mode=='maze':cy-=int(abs(math.sin(self.flash*15))*8)
        if self.dash>0:pygame.draw.circle(S,C,(cx,cy),23,2)
        pygame.draw.ellipse(S,(4,12,22),(cx-16,cy+12,32,9));pygame.draw.rect(S,(42,82,103),(cx-13,cy-12,26,27),border_radius=7)
        pygame.draw.rect(S,C,(cx-17,cy-18,34,25),border_radius=8);pygame.draw.rect(S,(6,22,38),(cx-13,cy-14,26,16),border_radius=5)
        for dx in [-6,6]:pygame.draw.rect(S,W,(cx+dx-2,cy-10,4,6),border_radius=2)
        pygame.draw.line(S,C,(cx,cy-18),(cx,cy-24),2);pygame.draw.circle(S,V,(cx,cy-25),3)
        panel((710,120,525,460));label('MISSION CONTROL',737,141,28,C)
        done=sum(g['open'] for g in self.gates.values());total=len(self.gates)
        label('2 GATES / 120 SECONDS' if self.sprint else 'Restore the network power',738,191,20);label('DIFFICULTY / '+['EASY','MEDIUM','HARD'][min(self.correct,2)],738,223,16,V)
        pygame.draw.rect(S,(36,52,72),(738,265,460,12),border_radius=6)
        if done:pygame.draw.rect(S,G,(738,265,int(460*done/total),12),border_radius=6)
        label(f'{done}/{total} systems restored',738,288,18,G)
        yy=332
        for g in self.gates.values():label(f'{g["id"]:02}  '+['EASY','MEDIUM','HARD'][g['difficulty']]+'   '+('ONLINE' if g['open'] else 'LOCKED'),738,yy,17,G if g['open'] else M);yy+=28
        label(f'ENERGY  {self.energy_count} collected / +10 each',738,445,16,(255,207,101))
        label('SPACE / DASH READY' if self.dash_cooldown<=0 else f'DASH recharging / {self.dash_cooldown:.1f}s',738,473,15,C if self.dash_cooldown<=0 else M)
        near=self.nearby_gate();label('E • Open nearby challenge' if near else ('Follow the light dots' if self.sprint else 'Find the next purple gate'),738,501,18,C)
        label('Solve both gates to win instantly.' if self.sprint else 'Exit activates after all gates are solved.',738,536,16,M)
        panel((32,601,1203,85));label(self.message if self.message_time else 'BYTE is ready. Restore all systems and reach the portal.',52,619,17,C)
        label('WASD / Arrows: move   Space: dash   E: challenge   M: menu   F11: fullscreen',52,653,15,M)
    def draw_editor(self):
        gate=self.gates[self.active_gate];q=gate['question'];predict=gate['kind']=='Predict Output'
        label(f'GATE {gate["id"]:02} / {gate["kind"].upper()}',32,119,24,V);label(q['title'],766,123,22)
        label('DIFFICULTY / '+['EASY','MEDIUM','HARD'][gate['difficulty']],997,274,14,V)
        panel((28,161,265,398));label('MISSION',45,180,19,C)
        for i,line in enumerate(wrap('Predict the exact output.' if predict else q['prompt'],24)):label(line,45,216+i*23,16)
        label('EXPECTED OUTPUT',45,306,15,G)
        expected='Hidden: predict it yourself.' if predict else (self.expected or '(No output)')
        for i,line in enumerate(wrap(expected,23)[:5]):label(line,45,338+i*22,16,G)
        if self.hint:
            for i,line in enumerate(wrap(q['hint'],23)[:4]):label(line,45,464+i*21,14,M)
        else:label('Use Hint if you get stuck.',45,515,14,M)
        panel((307,161,657,398));label('READ ONLY' if predict else 'main.'+{'Python':'py','Java':'java','C++':'cpp'}[self.language],326,177,16,C)
        start=max(0,self.line-10);font=E.MONO;scroll=max(0,font.size(self.lines[self.line][:self.col])[0]-550)
        S.set_clip(pygame.Rect(318,210,632,208 if predict else 330))
        for i in range(start,min(len(self.lines),start+(8 if predict else 12))):
            yy=216+(i-start)*26;label(f'{i+1:02}',326,yy,17,M)
            line=self.lines[i];x=370-scroll;S.set_clip(pygame.Rect(366,210,582,208 if predict else 330))
            for part in re.findall(r'"[^"]*"|\x27[^\x27]*\x27|\b\w+\b|\s+|.',line):
                color=G if part.startswith(('"',"'")) else (V if part in ['def','return','if','else','for','while','in','int','static','void','True','False'] else (C if part in ['print','range','cout','System'] else W))
                S.blit(font.render(part,True,color),(x,yy));x+=font.size(part)[0]
            S.set_clip(pygame.Rect(318,210,632,208 if predict else 330))
        if not predict and pygame.time.get_ticks()%1000<550:
            x=370-scroll+font.size(self.lines[self.line][:self.col])[0];y=216+(self.line-start)*26;pygame.draw.line(S,C,(x,y),(x,y+22),2)
        S.set_clip(None)
        if predict and self.choices:
            for i,choice in enumerate(self.choices):
                rect=pygame.Rect(322+(i%2)*320,432+(i//2)*59,307,51)
                self.button('',rect,lambda choice=choice:setattr(self,'answer',choice),self.answer==choice,V)
                value=choice.replace('\n',' / ') or '(No output)'
                label('ABCD'[i],rect.x+12,rect.y+15,15,V)
                S.set_clip(rect.inflate(-56,-8))
                for row,line in enumerate(wrap(value,27)[:2]):label(line,rect.x+36,rect.y+7+row*18,14,W)
                S.set_clip(None)
        panel((980,161,272,398));label('STATUS',997,180,19,C)
        for i,line in enumerate(wrap('Reference unavailable' if getattr(self,'reference_error',False) else ('Processing…' if self.future else ('Check Errors below' if self.error else getattr(self,'test_status','Ready to run'))),23)):label(line,997,221+i*23,16,M)
        label('Click an answer below' if predict else 'Run = free experiment',997,321,15);label('Submit = graded attempt',997,350,15)
        label('Training / no penalties' if self.practice else 'Wrong submit / -1 heart',997,403,15,R)
        label('F5 Run / F6 Submit',997,462,15,C);label('F1 Hint / Ctrl+R Reset',997,491,14,M);label('Esc Back / Wheel Output',997,520,14,M)
        panel((28,574,450,115));panel((491,574,473,115))
        label('YOUR PREDICTION' if predict else 'ACTUAL OUTPUT',44,582,14,C);label('ERRORS / FEEDBACK',507,582,14,R)
        content=(self.answer or 'Click an answer, then Submit.') if predict else self.output
        lines=wrap(content,43);errors=wrap(self.error or (self.message if self.flash else 'No errors.'),44)
        self.output_scroll=min(self.output_scroll,max(0,max(len(lines),len(errors))-3))
        for i,line in enumerate(lines[self.output_scroll:self.output_scroll+3]):label(line,44,608+i*23,15,W)
        for i,line in enumerate(errors[self.output_scroll:self.output_scroll+3]):label(line,507,608+i*23,15,R if self.error or self.flash else M)
        self.button('RUN • F5',(981,605,126,38),lambda:self.run_code(False))
        self.button('SUBMIT • F6',(1117,605,135,38),lambda:self.run_code(True),True,G)
        self.button('Hint',(981,652,79,34),lambda:setattr(self,'hint',True))
        self.button('Back',(1068,652,79,34),self.close_editor)
        self.button('Reset',(1155,652,97,34),lambda:self.reset_code())
    def reset_code(self):
        if self.future:return
        self.lines=self.gates[self.active_gate]['question']['code'].split('\n');self.line=self.col=self.view_top=0;self.answer=''
    def results(self):
        label('SYSTEM RESTORED!' if self.mode=='won' else 'CONNECTION LOST',70,153,43,G if self.mode=='won' else R)
        label('Every fix brought the network back to life.' if self.mode=='won' else 'Try another route. Every attempt teaches you something.',72,217,20,M)
        for i,(a,b) in enumerate([('SCORE',str(self.score)),('ACCURACY',f'{round(100*self.correct/max(1,self.attempts))}%'),('TIME',f'{int(self.elapsed)} s'),('GATES',str(self.correct))]):
            panel((70+i*300,290,277,130));label(a,90+i*300,311,16,M);label(b,90+i*300,350,36,C)
        label(self.notice,72,460,18,M)
        label(f'Energy collected: {self.energy_count} / +{self.energy_count*10} bonus points',72,492,17,C)
        if self.mode=='won':
            center=(1130,208)
            for radius in [26,40,54]:pygame.draw.circle(S,G,center,radius,2)
            angle=pygame.time.get_ticks()/350
            pygame.draw.circle(S,C,(center[0]+int(math.cos(angle)*40),center[1]+int(math.sin(angle)*40)),7)
        self.button('PLAY AGAIN',(70,535,300,65),self.start,True);self.button('HIGH SCORES',(394,535,300,65),lambda:self.go('scores'));self.button('MENU',(718,535,300,65),lambda:self.go('menu',3))
    def scores(self):
        label('HIGH SCORES',50,132,34,C);label('Event scores only • Score, then accuracy, then time',52,184,17,M)
        rows=sorted([r for r in self.history if r['mode']=='Event'],key=lambda r:(-r['score'],-r['accuracy'],r['time']))[:7]
        label('RANK     PLAYER                 SCORE     ACCURACY     TIME      LANGUAGE',65,235,18,V)
        for i,r in enumerate(rows):
            panel((45,272+i*45,1188,39));label(f'{i+1:02}        {r["name"][:16]:16}       {r["score"]:4}       {r["accuracy"]:3}%        {r["time"]:3}s      {r["language"]}',65,280+i*45,17)
        if not rows:label('Complete your first event mission to appear here.',65,300,20,M)
        self.button('BACK TO MENU',(45,623,300,55),lambda:self.go('menu',3),True)
    def draw(self):
        self.buttons=[];self.draw_bg()
        if self.mode not in ('menu','settings','name_entry'):self.header()
        if self.mode=='menu':self.menu()
        elif self.mode=='settings':self.settings()
        elif self.mode=='name_entry':self.name_entry()
        elif self.mode=='maze':self.draw_maze()
        elif self.mode=='editor':self.draw_editor()
        elif self.mode=='scores':self.scores()
        else:self.results()
        for p in self.particles:pygame.draw.circle(S,p[5],(int(p[0]),int(p[1])),max(1,int(p[4]*3)))
        pygame.display.flip()


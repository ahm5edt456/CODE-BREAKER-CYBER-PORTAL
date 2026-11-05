"""Retained pygame_gui controls over a custom animated Cyber Portal scene."""
import math,random
from pathlib import Path
import pygame
import pygame_gui
from pygame_gui.elements import UIButton,UITextEntryLine
import game as core
from game import Game,S,C,V,W,M,G,R,label,panel

ROOT=Path(__file__).resolve().parent
GUI_MODES={'menu','settings','scores','name_entry','won','lost'}

class PortalGame(Game):
    def __init__(self):
        super().__init__()
        self.ui=pygame_gui.UIManager((1280,720),str(ROOT/'assets/theme.json'),enable_live_theme_updates=False)
        self.widgets={};self.actions={};self.gui_mode=None;self.entry=None;self.clock_time=0.;self.fade=0.;self.previous=None;self.last_frame=None
        self.fonts={}
        rng=random.Random(738)
        self.stars=[(rng.randrange(1280),rng.randrange(720),rng.random()*math.tau,rng.choice([1,1,2])) for _ in range(62)]
        # Stable decorative maze, generated once rather than rebuilding every frame.
        from mazegenerator import MazeGenerator
        random_state=random.getstate()
        try:self.backdrop=MazeGenerator(size=(13,9),perfect=True,seed=29).maze
        finally:random.setstate(random_state)
        self.glow=pygame.Surface((1280,720),pygame.SRCALPHA)
        for radius in range(300,0,-8):
            alpha=int(4*(1-radius/310))
            pygame.draw.circle(self.glow,(38,108,131,alpha),(640,195),radius)
    def text(self,value,x,y,size=18,color=W,center=False,bold=False):
        key=(size,bold)
        if key not in self.fonts:self.fonts[key]=pygame.font.SysFont('dejavusans',size,bold=bold)
        image=self.fonts[key].render(str(value),True,color)
        rect=image.get_rect(midtop=(x,y)) if center else image.get_rect(topleft=(x,y))
        S.blit(image,rect)
    def center_text(self,value,y,size=18,color=W):self.text(value,640,y,size,color,True,size>=26)
    def sync_screen(self):
        if self.gui_mode==self.mode:return
        if self.last_frame is not None:self.previous=self.last_frame.copy();self.fade=.18
        self.ui.clear_and_reset();self.widgets={};self.actions={};self.entry=None;self.gui_mode=self.mode
    def button(self,title,rect,action,active=False,color=C):
        if self.mode not in GUI_MODES:return super().button(title,rect,action,active,color)
        index=len(self.buttons);rect=pygame.Rect(rect);self.buttons.append((rect,action))
        style='#play' if title in ('PLAY','SAVE SCORE','SUBMIT / F6','CONTINUE','RESUME') else ('#selected' if active else '#secondary')
        if index not in self.widgets:
            self.widgets[index]=UIButton(rect,title,manager=self.ui,object_id=style)
        widget=self.widgets[index]
        if widget.text!=title:widget.set_text(title)
        if getattr(widget,'portal_style',None)!=style:widget.change_object_id(style);widget.portal_style=style
        self.actions[widget]=action
        if self.mode!='name_entry' and index==self.nav_focus:
            pygame.draw.rect(S,(124,231,241),rect.inflate(10,10),2,border_radius=17)
        if title=='PLAY':
            pulse=int(25+12*math.sin(self.clock_time*2))
            glow=pygame.Surface((rect.w+44,rect.h+44),pygame.SRCALPHA)
            for extra in range(18,0,-3):pygame.draw.rect(glow,(52,218,232,max(2,pulse//6)),(22-extra,22-extra,rect.w+extra*2,rect.h+extra*2),2,border_radius=16+extra)
            S.blit(glow,(rect.x-22,rect.y-22))
    def navigate(self,key,mod=0):
        # PLAY sits above the language row, so arrows follow that visual order.
        if self.mode=='menu' and key in (pygame.K_UP,pygame.K_DOWN):
            f=self.nav_focus;language=['Python','Java','C++'].index(self.language)
            if key==pygame.K_UP:self.nav_focus=3 if f<3 else (language if f>=4 else 3)
            else:self.nav_focus=language if f==3 else (4 if f<3 else f)
            return
        super().navigate(key,mod)
    def handle(self,event):
        if self.gui_mode!=self.mode:self.draw()
        if self.mode in GUI_MODES:
            self.ui.process_events(event)
            if event.type==pygame_gui.UI_BUTTON_PRESSED:
                action=self.actions.get(event.ui_element)
                if action is not None:action()
                return
            if self.mode=='name_entry' and self.entry is not None:
                self.name=self.entry.get_text()
                if event.type==pygame_gui.UI_TEXT_ENTRY_CHANGED:self.name=event.text;self.notice='';return
                if event.type==pygame_gui.UI_TEXT_ENTRY_FINISHED:self.save_result();return
                if event.type==pygame.TEXTINPUT or (event.type==pygame.KEYDOWN and event.key==pygame.K_BACKSPACE):return
            # Mouse activation is owned by pygame_gui; do not activate a second time.
            if event.type in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):return
        super().handle(event)
    def update(self,dt):
        self.clock_time+=dt;self.fade=max(0,self.fade-dt)
        self.ui.update(dt)
        super().update(dt)
    def background(self):
        S.fill((5,10,21));S.blit(self.glow,(0,0));t=self.clock_time
        # Dark maze wings give the center room to breathe.
        for y,row in enumerate(self.backdrop):
            for x,bits in enumerate(row):
                px=42+x*96+int(math.sin(t*.08)*10);py=-45+y*96+int(math.cos(t*.08)*8)
                middle=abs(px-640)<310
                color=(11,23,37) if middle else (17,35,48)
                if bits&1:pygame.draw.line(S,color,(px,py),(px+96,py),1)
                if bits&8:pygame.draw.line(S,color,(px,py),(px,py+96),1)
        for x,y,phase,radius in self.stars:
            brightness=int(44+21*math.sin(t*.7+phase))
            pygame.draw.circle(S,(brightness//2,brightness,brightness+18),(x,int((y+t*3)%720)),radius)
        pygame.draw.line(S,(24,48,63),(46,45),(167,45),1)
        self.text('IEEE / CODE LAB',46,55,11,(100,144,162))
        self.text('CYBER PORTAL',1080,55,11,(100,144,162))
        pygame.draw.line(S,(24,48,63),(1113,45),(1234,45),1)
    def portal(self,cx=640,cy=177,scale=1.):
        t=self.clock_time;r=int(83*scale)
        # Soft halos and broken orbital rings are all code-native shapes.
        halo=pygame.Surface((260,260),pygame.SRCALPHA)
        for rad,alpha in [(110,7),(94,12),(82,18)]:pygame.draw.circle(halo,(45,205,224,alpha),(130,130),int(rad*scale))
        S.blit(halo,(cx-130,cy-130))
        pygame.draw.circle(S,(26,65,82),(cx,cy),r,1)
        pygame.draw.circle(S,(21,45,64),(cx,cy),r+17,1)
        for i in range(3):
            start=t*.38+i*math.tau/3
            pygame.draw.arc(S,C,(cx-r,cy-r,2*r,2*r),start,start+1.1,3)
            outer=r+17
            pygame.draw.arc(S,V,(cx-outer,cy-outer,outer*2,outer*2),-start+.3,-start+.75,2)
        for i in range(4):
            angle=t*.34+i*math.pi/2
            pygame.draw.circle(S,W,(cx+int(math.cos(angle)*r),cy+int(math.sin(angle)*r)),3)
        cy+=int(math.sin(t*1.8)*5)
        pygame.draw.ellipse(S,(6,20,31),(cx-34,cy+48,68,10))
        pygame.draw.rect(S,(24,58,78),(cx-26,cy+6,52,39),border_radius=12)
        pygame.draw.rect(S,(39,132,154),(cx-36,cy+12,9,20),border_radius=4)
        pygame.draw.rect(S,(39,132,154),(cx+27,cy+12,9,20),border_radius=4)
        pygame.draw.rect(S,C,(cx-43,cy-38,86,58),border_radius=17)
        pygame.draw.rect(S,(9,29,45),(cx-35,cy-30,70,39),border_radius=12)
        blink=(t%5.1>4.95)
        for dx in [-16,16]:pygame.draw.rect(S,(178,255,255),(cx+dx-4,cy-19,8,3 if blink else 13),border_radius=3)
        pygame.draw.line(S,C,(cx,cy-39),(cx,cy-55),2);pygame.draw.circle(S,V,(cx,cy-59),5)
        pygame.draw.rect(S,G,(cx-8,cy+30,16,4),border_radius=2)
    def menu(self):
        self.background();self.portal()
        self.center_text('C O D E  B R E A K E R',292,33,W)
        self.center_text('S Y S T E M   E S C A P E',343,12,(112,164,180))
        self.center_text(getattr(self,'campaign_caption','Escape in 120 seconds.'),374,16,M)
        # Keep control indices stable for the existing keyboard mappings.
        for i,language in enumerate(['Python','Java','C++']):
            self.button(language,(435+i*140,532,130,42),lambda language=language:setattr(self,'language',language),self.language==language)
        self.button('PLAY',(435,423,410,65),self.start,True)
        self.center_text('CHOOSE YOUR LANGUAGE',508,11,(100,137,156))
        self.button('Settings',(435,601,195,42),lambda:self.go('settings'))
        self.button('High Scores',(650,601,195,42),lambda:self.go('scores'))
        self.center_text('ARROWS  navigate     ENTER  select     TAB  next',680,11,(99,130,149))
    def settings(self):
        self.background();self.center_text('MISSION SETTINGS',136,30,W)
        self.center_text('Two choices. Your way to escape.',183,15,M)
        panel((376,247,528,273),(10,21,36),(31,58,75))
        self.text('CHALLENGE',410,273,12,(118,157,177))
        self.button('Debugging',(410,312,218,57),lambda:setattr(self,'challenge','Debug'),self.challenge=='Debug',V)
        self.button('Complete Code',(652,312,218,57),lambda:setattr(self,'challenge','Complete Code'),self.challenge=='Complete Code',V)
        self.text('Repair broken code' if self.challenge=='Debug' else 'Fill in the missing code',410,385,14,M)
        self.text('SOUND',410,454,13,M)
        self.button('ON' if self.sound else 'OFF',(720,438,150,45),lambda:setattr(self,'sound',not self.sound),self.sound)
        self.button('Back to Portal',(435,567,410,51),lambda:self.go('menu',3),True)
        self.center_text('Difficulty increases automatically as you progress.',652,13,M)
    def name_entry(self):
        self.background();self.center_text('SYSTEM RESTORED' if self.outcome=='won' else 'MISSION ENDED',129,31,G if self.outcome=='won' else W)
        self.center_text(f'{self.score:04} POINTS',188,26,C)
        panel((375,267,530,298),(10,21,36),(31,58,75))
        self.center_text('Leave your name on the board.',292,20,W)
        if self.entry is None:
            self.entry=UITextEntryLine(pygame.Rect(420,346,440,59),manager=self.ui,object_id='#player_name')
            self.entry.set_text_length_limit(16);self.entry.set_text(self.name);self.entry.focus()
        self.center_text(self.notice or 'Your name / up to 16 characters',425,13,R if self.notice else M)
        self.button('SAVE SCORE',(420,477,440,56),self.save_result,True)
        self.center_text('ENTER  save     ESC  skip',619,12,M)
    def scores(self):
        self.background();self.center_text('HIGH SCORES',118,33,W)
        self.center_text('The fastest minds in the maze.',169,15,M)
        panel((230,224,820,356),(10,21,36),(31,58,75))
        for text,x in [('RANK',259),('PLAYER',335),('SCORE',655),('ACCURACY',780),('TIME',944)]:self.text(text,x,244,11,M)
        rows=sorted([r for r in self.history if r['mode']=='Event'],key=lambda r:(-r['score'],-r['accuracy'],r['time']))[:6]
        for i,row in enumerate(rows):
            y=286+i*45
            pygame.draw.line(S,(24,43,59),(252,y-9),(1028,y-9),1)
            color=C if i==0 else W
            self.text(f'{i+1:02}',261,y,17,color)
            self.text(row['name'][:16],335,y,17,W)
            self.text(f'{row["score"]:04}',655,y,17,color)
            self.text(f'{row["accuracy"]}%',798,y,16,M)
            self.text(f'{row["time"]}s',945,y,16,M)
        if not rows:self.center_text('Your first mission starts the story.',366,18,M)
        self.button('Back to Portal',(435,613,410,49),lambda:self.go('menu',3),True)
    def draw(self):
        self.sync_screen();self.buttons=[]
        if self.mode in GUI_MODES:
            if self.mode=='menu':self.menu()
            elif self.mode=='settings':self.settings()
            elif self.mode=='name_entry':self.name_entry()
            elif self.mode=='scores':self.scores()
            else:self.background();self.header();self.results()
            for index in list(self.widgets):
                if index>=len(self.buttons):
                    widget=self.widgets.pop(index);self.actions.pop(widget,None);widget.kill()
            self.ui.update(0)
            self.ui.draw_ui(S)
        else:
            self.draw_bg();self.header()
            if self.mode=='maze':self.draw_maze()
            else:self.draw_editor()
        for p in self.particles:pygame.draw.circle(S,p[5],(int(p[0]),int(p[1])),max(1,int(p[4]*3)))
        if self.fade>0 and self.previous is not None:
            self.previous.set_alpha(int(255*self.fade/.18));S.blit(self.previous,(0,0))
        self.last_frame=S.copy();pygame.display.flip()

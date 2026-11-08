"""Mouse hit-testing, selection, clipboard, and scrolling for the code editor."""
import re
import pygame

CODE_RECT=pygame.Rect(402,243,815,287)
GUTTER=pygame.Rect(348,243,54,287)
SCROLLBAR=pygame.Rect(1220,243,8,287)
TEXT_X,TEXT_Y,ROW_HEIGHT,VISIBLE_ROWS=408,247,23,12

class EditorSupport:
    def editor_init(self):
        self.editor_font=pygame.font.SysFont('dejavusansmono',17)
        self.editor_anchor=None;self.editor_top=0;self.editor_hscroll=0
        self.editor_dragging=False;self.editor_scroll_drag=False;self.editor_menu=None
        self.editor_clipboard='';self.editor_last_click=(0,(-100,-100))
    def editor_reset(self,question=None):
        self.editor_anchor=None;self.editor_top=0;self.editor_hscroll=0
        self.editor_dragging=False;self.editor_scroll_drag=False;self.editor_menu=None
        if question is not None and question.get('missing_line') is not None:
            row=question['missing_line'];text=self.lines[row];indent=len(text)-len(text.lstrip())
            self.line=row;self.col=len(text);self.editor_anchor=(row,indent)
        self.editor_reveal()
    def editor_clamp(self,position):
        row=max(0,min(position[0],len(self.lines)-1))
        return row,max(0,min(position[1],len(self.lines[row])))
    def editor_selection(self):
        if self.editor_anchor is None:return None
        a=self.editor_clamp(self.editor_anchor);b=self.editor_clamp((self.line,self.col))
        return tuple(sorted((a,b))) if a!=b else None
    def editor_delete_selection(self):
        selection=self.editor_selection()
        if selection is None:self.editor_anchor=None;return False
        (first,col),(last,end)=selection
        self.lines[first:last+1]=[self.lines[first][:col]+self.lines[last][end:]]
        self.line,self.col=first,col;self.editor_anchor=None;return True
    def editor_insert(self,text):
        text=text.replace('\r\n','\n').replace('\r','\n').replace('\t','    ')
        if len('\n'.join(self.lines))+len(text)>12000:
            self.notify('Code is too long.');return
        self.editor_delete_selection();self.line,self.col=self.editor_clamp((self.line,self.col))
        before=self.lines[self.line][:self.col];after=self.lines[self.line][self.col:];parts=text.split('\n')
        self.lines[self.line:self.line+1]=[before+parts[0]]+parts[1:]
        self.line+=len(parts)-1;self.col=len(before+parts[0]) if len(parts)==1 else len(parts[-1])
        self.lines[self.line]+=after;self.editor_anchor=None;self.editor_reveal()
    def editor_reveal(self):
        self.line,self.col=self.editor_clamp((self.line,self.col))
        if self.line<self.editor_top:self.editor_top=self.line
        if self.line>=self.editor_top+VISIBLE_ROWS:self.editor_top=self.line-VISIBLE_ROWS+1
        self.editor_top=max(0,min(self.editor_top,max(0,len(self.lines)-VISIBLE_ROWS)))
        pixel=self.editor_font.size(self.lines[self.line][:self.col])[0]
        if pixel-self.editor_hscroll>CODE_RECT.w-30:self.editor_hscroll=pixel-CODE_RECT.w+30
        if pixel<self.editor_hscroll:self.editor_hscroll=pixel
        self.editor_hscroll=max(0,self.editor_hscroll)
    def editor_position(self,pos):
        visible=max(0,min(VISIBLE_ROWS-1,(pos[1]-TEXT_Y)//ROW_HEIGHT))
        row=max(0,min(self.editor_top+visible,len(self.lines)-1))
        x=max(0,pos[0]-TEXT_X+self.editor_hscroll);text=self.lines[row]
        low,high=0,len(text)
        while low<high:
            mid=(low+high)//2
            if self.editor_font.size(text[:mid])[0]<x:low=mid+1
            else:high=mid
        col=low
        if col and abs(self.editor_font.size(text[:col-1])[0]-x)<=abs(self.editor_font.size(text[:col])[0]-x):col-=1
        return row,col
    def editor_copy(self):
        selection=self.editor_selection();self.editor_menu=None
        if selection is None:return
        (first,col),(last,end)=selection
        text=self.lines[first][col:end] if first==last else '\n'.join([self.lines[first][col:]]+self.lines[first+1:last]+[self.lines[last][:end]])
        self.editor_clipboard=text
        try:
            if hasattr(pygame.scrap,'put_text'):pygame.scrap.put_text(text)
            elif hasattr(pygame.scrap,'set_text'):pygame.scrap.set_text(text)
            else:
                if not pygame.scrap.get_init():pygame.scrap.init()
                pygame.scrap.put(pygame.SCRAP_TEXT,text.encode('utf-8')+b'\0')
        except (pygame.error,AttributeError,UnicodeError):pass
        self.editor_menu=None
    def editor_paste(self):
        text=self.editor_clipboard
        try:
            if hasattr(pygame.scrap,'get_text'):text=pygame.scrap.get_text() or text
            else:
                if not pygame.scrap.get_init():pygame.scrap.init()
                value=pygame.scrap.get(pygame.SCRAP_TEXT)
                if value:text=value.rstrip(b'\0').decode('utf-8')
        except (pygame.error,AttributeError,UnicodeError):pass
        self.editor_insert(text);self.editor_menu=None
    def editor_select_all(self):
        self.editor_anchor=(0,0);self.line=len(self.lines)-1;self.col=len(self.lines[-1]);self.editor_reveal();self.editor_menu=None
    def editor_scroll_to(self,y):
        maximum=max(0,len(self.lines)-VISIBLE_ROWS)
        thumb=max(24,int(SCROLLBAR.h*VISIBLE_ROWS/max(VISIBLE_ROWS,len(self.lines))))
        fraction=(y-SCROLLBAR.y-thumb/2)/max(1,SCROLLBAR.h-thumb)
        self.editor_top=max(0,min(maximum,round(fraction*maximum)))
    def editor_mouse(self,event):
        if self.future:return False
        if event.type==pygame.MOUSEWHEEL:
            pos=getattr(event,'pos',pygame.mouse.get_pos())
            if CODE_RECT.union(GUTTER).union(SCROLLBAR).collidepoint(pos):
                self.editor_top=max(0,min(max(0,len(self.lines)-VISIBLE_ROWS),self.editor_top-event.y*3))
                self.editor_hscroll=max(0,self.editor_hscroll+getattr(event,'x',0)*40)
                return True
        if event.type==pygame.MOUSEBUTTONDOWN:
            pos=event.pos
            if self.editor_menu is not None:
                menu=pygame.Rect(*self.editor_menu,184,114)
                if menu.collidepoint(pos):return False
                self.editor_menu=None
            if event.button==3 and CODE_RECT.collidepoint(pos):
                if self.editor_selection() is None:self.editor_anchor=None;self.line,self.col=self.editor_position(pos)
                self.editor_menu=(min(pos[0],1228-184),min(pos[1],690-114));return True
            if event.button!=1:return False
            if SCROLLBAR.inflate(6,0).collidepoint(pos):
                self.editor_scroll_drag=True;self.editor_scroll_to(pos[1]);return True
            if not CODE_RECT.union(GUTTER).collidepoint(pos):return False
            previous=(self.line,self.col);self.line,self.col=self.editor_position(pos)
            if GUTTER.collidepoint(pos):
                self.editor_anchor=(self.line,0)
                if self.line<len(self.lines)-1:self.line+=1;self.col=0
                else:self.col=len(self.lines[self.line])
                self.editor_dragging=False;return True
            now=pygame.time.get_ticks();last,location=self.editor_last_click
            double=getattr(event,'clicks',1)>=2 or (now-last<330 and abs(pos[0]-location[0])<4 and abs(pos[1]-location[1])<4)
            self.editor_last_click=(now,pos)
            if double:
                self.editor_anchor=None;text=self.lines[self.line]
                for match in re.finditer(r'\w+|[^\w\s]+',text):
                    if match.start()<=self.col<match.end() or self.col==len(text)==match.end():
                        self.editor_anchor=(self.line,match.start());self.col=match.end();break
                self.editor_dragging=False
            else:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    if self.editor_anchor is None:self.editor_anchor=previous
                else:self.editor_anchor=(self.line,self.col)
                self.editor_dragging=True
            pygame.key.start_text_input();return True
        if event.type==pygame.MOUSEMOTION:
            if self.editor_scroll_drag:self.editor_scroll_to(event.pos[1]);return True
            if self.editor_dragging:
                if event.pos[1]<CODE_RECT.top:self.editor_top=max(0,self.editor_top-1)
                if event.pos[1]>=CODE_RECT.bottom:self.editor_top=min(max(0,len(self.lines)-VISIBLE_ROWS),self.editor_top+1)
                self.line,self.col=self.editor_position(event.pos);return True
        if event.type==pygame.MOUSEBUTTONUP and event.button==1 and (self.editor_dragging or self.editor_scroll_drag):
            self.editor_dragging=self.editor_scroll_drag=False;return True
        return False
    def editor_key(self,event):
        if self.future:return False
        if event.type==pygame.TEXTINPUT:self.editor_insert(event.text);return True
        if event.type!=pygame.KEYDOWN:return False
        mod=getattr(event,'mod',0);key=event.key
        if mod & pygame.KMOD_CTRL:
            if key==pygame.K_r:self.reset_code();return True
            if key==pygame.K_a:self.editor_select_all();return True
            if key==pygame.K_c:self.editor_copy();return True
            if key==pygame.K_v:self.editor_paste();return True
            if key==pygame.K_x:self.editor_copy();self.editor_delete_selection();self.editor_reveal();return True
        if key==pygame.K_ESCAPE and self.editor_menu is not None:self.editor_menu=None;return True
        if key in (pygame.K_BACKSPACE,pygame.K_DELETE) and self.editor_delete_selection():self.editor_reveal();return True
        if key==pygame.K_RETURN:
            self.editor_delete_selection();before=self.lines[self.line][:self.col]
            indent=re.match(r'\s*',before).group()
            if before.rstrip().endswith((':','{')):indent+='    '
            self.editor_insert('\n'+indent);return True
        movement=key in (pygame.K_LEFT,pygame.K_RIGHT,pygame.K_UP,pygame.K_DOWN,pygame.K_HOME,pygame.K_END)
        if movement:
            if mod & pygame.KMOD_SHIFT:
                if self.editor_anchor is None:self.editor_anchor=(self.line,self.col)
            else:
                selection=self.editor_selection();self.editor_anchor=None
                if selection is not None and key in (pygame.K_LEFT,pygame.K_RIGHT):
                    self.line,self.col=selection[0 if key==pygame.K_LEFT else 1];self.editor_reveal();return True
        elif key==pygame.K_TAB:self.editor_delete_selection()
        return False

"""Code-native sprite artwork, cached materials and wall-occluded 2D light.
Uses the existing pygame-ce renderer; no player-code or execution dependencies.
"""
import math
import pygame
from pathlib import Path


def glow(radius, color):
    image = pygame.Surface((radius*2+2, radius*2+2), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        alpha = int(90*(1-r/radius)**1.7)
        pygame.draw.circle(image, (*color, alpha), (radius+1, radius+1), r)
    return image


def robot_atlas(accent, frame_size=64):
    """Four facing directions, eight walking frames; high-res art downsampled once."""
    atlas = pygame.Surface((frame_size*8, frame_size*4), pygame.SRCALPHA)
    for facing in range(4):
        for frame in range(8):
            image = pygame.Surface((512, 512), pygame.SRCALPHA)
            step = int(math.sin(frame*math.tau/8)*4)
            bob = abs(step)//2
            def rect(color, area, radius=0, width=0):
                pygame.draw.rect(image,color,pygame.Rect(*(int(v*4) for v in area)),width*4,border_radius=radius*4)
            # Segmented boots, articulated arms, metallic chassis.
            rect((5,12,23),(37,82+step,20,18),6)
            rect((5,12,23),(71,82-step,20,18),6)
            rect((60,87,107),(39,82+step,16,12),4)
            rect((60,87,107),(73,82-step,16,12),4)
            rect((*accent,255),(40,91+step,13,3),1)
            rect((*accent,255),(74,91-step,13,3),1)
            rect((6,15,27),(28,48+bob,12,31),5)
            rect((6,15,27),(88,48+bob,12,31),5)
            rect((83,111,130),(29,50+bob,9,20),4)
            rect((83,111,130),(90,50+bob,9,20),4)
            rect((12,26,40),(39,53+bob,50,36),10)
            rect((46,73,94),(41,55+bob,46,30),8)
            rect((22,43,61),(46,60+bob,36,20),5)
            rect(accent,(50,68+bob,28,4),2)
            for x in range(53,78,8):rect((187,235,235),(x,77+bob,3,2),1)
            # Ceramic head shell with a darker rim and a glass visor.
            rect((5,13,24),(25,19+bob,78,48),15)
            rect((110,143,161),(27,20+bob,74,43),13)
            rect((205,226,232),(29,21+bob,70,37),12)
            rect(accent,(30,24+bob,68,32),10)
            rect((7,20,34),(36,28+bob,56,23),8)
            rect((20,43,62),(39,29+bob,49,8),5)
            for x in (30,96):rect((42,69,89),(x,34+bob,3,8),1)
            dx,dy=((0,2),(4,0),(0,-2),(-4,0))[facing]
            for x in (50,73):
                rect((183,255,249),(x+dx,35+dy+bob,7,10),3)
                rect((248,255,255),(x+dx+1,35+dy+bob,3,3),1)
            pygame.draw.line(image,(68,104,125),(256,(21+bob)*4),(256,(10+bob)*4),12)
            pygame.draw.circle(image,accent,(256,(8+bob)*4),16)
            pygame.draw.circle(image,(230,255,255),(252,(7+bob)*4),4)
            atlas.blit(pygame.transform.smoothscale(image,(frame_size,frame_size)),(frame*frame_size,facing*frame_size))
    return atlas


class SceneArt:
    def __init__(self, palettes):
        art=Path(__file__).resolve().parent/'assets'/'art'
        self.atlases=[]
        for i,palette in enumerate(palettes):
            path=art/f'robot_stage{i+1}.png'
            image=pygame.image.load(str(path)).convert_alpha() if path.exists() else robot_atlas(palette[0])
            if image.get_size()!=(512,256):image=robot_atlas(palette[0])
            self.atlases.append(image)
        hero_path=art/'robot_hero_hq.png'
        if hero_path.exists():
            hero=pygame.image.load(str(hero_path)).convert_alpha()
        else:
            hero=robot_atlas(palettes[0][0],256).subsurface((0,0,256,256)).copy()
        # Cache the final-size menu sprite once; never enlarge a gameplay frame.
        self.menu_robot=pygame.transform.smoothscale(hero,(128,128))
        self.palette_lights=[glow(115,p[0]) for p in palettes]
        self.energy_light=glow(26,(255,190,65))
        self.player_light=[glow(142,p[0]) for p in palettes]
        self.material_key=None
        self.floor=None
        self.walls=None
        self.segments=[]
        self.light_layer=pygame.Surface((624,432),pygame.SRCALPHA)
        self.visibility=pygame.Surface((624,432),pygame.SRCALPHA)
        self.mask=pygame.Surface((624,432),pygame.SRCALPHA)

    def prepare(self, maze, stage, accent):
        key=(id(maze),stage)
        if self.material_key==key:return
        self.material_key=key
        self.floor=pygame.Surface((624,432))
        self.floor.fill((6,13,23))
        for y in range(9):
            for x in range(13):
                rect=pygame.Rect(x*48+3,y*48+3,42,42)
                tone=2*((x+y)%2)
                pygame.draw.rect(self.floor,(13+tone,25+tone,37+tone),rect,border_radius=5)
                pygame.draw.line(self.floor,(23,39,52),rect.topleft,(rect.right-4,rect.top),1)
                pygame.draw.line(self.floor,(7,16,27),(rect.left+3,rect.bottom-1),(rect.right-3,rect.bottom-1))
                for dx,dy in ((5,5),(35,35)):
                    pygame.draw.circle(self.floor,(31,47,59),(x*48+dx,y*48+dy),1)
                if (x*3+y)%7==0:
                    pygame.draw.line(self.floor,(19,36,49),(rect.x+12,rect.y+21),(rect.x+29,rect.y+21),1)
        self.walls=pygame.Surface((624,432),pygame.SRCALPHA)
        seen=set();self.segments=[]
        for y,row in enumerate(maze):
            for x,bits in enumerate(row):
                px,py=x*48,y*48
                for flag,a,b in ((1,(px,py),(px+48,py)),(2,(px+48,py),(px+48,py+48)),(4,(px,py+48),(px+48,py+48)),(8,(px,py),(px,py+48))):
                    segment=tuple(sorted((a,b)))
                    if not bits&flag or segment in seen:continue
                    seen.add(segment);self.segments.append(segment)
                    pygame.draw.line(self.walls,(0,0,0,115),(a[0]+2,a[1]+4),(b[0]+2,b[1]+4),10)
                    pygame.draw.line(self.walls,(5,13,24),a,b,10)
                    pygame.draw.line(self.walls,(40,58,74),a,b,7)
                    pygame.draw.line(self.walls,(68,87,101),a,b,3)
                    pygame.draw.line(self.walls,tuple(int(c*.43) for c in accent),a,b,1)
                    for p in (a,b):pygame.draw.circle(self.walls,(93,116,131),p,2)

    def draw_materials(self, surface, maze, stage, accent):
        self.prepare(maze,stage,accent)
        surface.blit(self.floor,(42,132))

    def draw_walls(self,surface):surface.blit(self.walls,(42,132))

    def draw_lighting(self,surface,position,stage,gates,energy):
        self.light_layer.fill((0,0,0,0))
        # Additive emissive lights for energy crystals and gate electronics.
        for x,y in energy:
            self.light_layer.blit(self.energy_light,(x*48+24-27,y*48+24-27))
        for (a,b),gate in gates.items():
            x=(a[0]+b[0]+1)*24;y=(a[1]+b[1]+1)*24
            self.light_layer.blit(self.palette_lights[stage],(x-116,y-116))
        self.light_layer.set_alpha(95)
        surface.blit(self.light_layer,(42,132))
        # Cast radial rays against nearby real maze walls. No gameplay changes.
        cx,cy=position[0]-42,position[1]-132
        candidates=[(a,b) for a,b in self.segments if min(a[0],b[0])-142<=cx<=max(a[0],b[0])+142 and min(a[1],b[1])-142<=cy<=max(a[1],b[1])+142]
        points=[]
        for i in range(112):
            angle=i*math.tau/112
            dx,dy=math.cos(angle),math.sin(angle);distance=142.
            for (ax,ay),(bx,by) in candidates:
                sx,sy=bx-ax,by-ay
                denominator=dx*sy-dy*sx
                if abs(denominator)<1e-8:continue
                qx,qy=ax-cx,ay-cy
                t=(qx*sy-qy*sx)/denominator
                u=(qx*dy-qy*dx)/denominator
                if 0<=t<distance and 0<=u<=1:distance=t
            points.append((int(cx+dx*distance),int(cy+dy*distance)))
        self.visibility.fill((0,0,0,0))
        self.visibility.blit(self.player_light[stage],(int(cx)-143,int(cy)-143))
        self.mask.fill((0,0,0,0))
        pygame.draw.polygon(self.mask,(255,255,255,255),points)
        self.visibility.blit(self.mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(self.visibility,(42,132))

    def draw_crystal(self,surface,cell,time,reduced=False):
        x,y=42+cell[0]*48+24,132+cell[1]*48+24
        if not reduced:y+=int(math.sin(time*2.8+cell[0]+cell[1])*2)
        pygame.draw.ellipse(surface,(8,16,23),(x-7,y+10,14,4))
        top=(x,y-10);right=(x+7,y);bottom=(x,y+10);left=(x-7,y)
        pygame.draw.polygon(surface,(255,235,154),(top,(x,y),left))
        pygame.draw.polygon(surface,(255,195,66),(top,right,(x,y)))
        pygame.draw.polygon(surface,(175,108,30),(left,(x,y),bottom))
        pygame.draw.polygon(surface,(236,157,41),((x,y),right,bottom))
        pygame.draw.line(surface,(255,248,207),top,left,1)

    def draw_actor(self,surface,position,stage,direction,frame,dash=False):
        x,y=map(int,position)
        pygame.draw.ellipse(surface,(3,9,17),(x-17,y+14,34,9))
        if dash:pygame.draw.circle(surface,(117,240,255),(x,y),25,1)
        surface.blit(self.atlases[stage],(x-32,y-29),(int(frame)%8*64,direction*64,64,64))

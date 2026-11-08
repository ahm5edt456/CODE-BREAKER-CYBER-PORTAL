"""Filled event wordmark, rendered once with restrained optical glow."""
import pygame

CYAN=(65,221,239)

class EventMark:
    def __init__(self,width):
        font=pygame.font.SysFont('dejavusans',96,bold=True)
        gap=7
        glyphs=[font.render(c,True,(235,250,255) if i<4 else CYAN) for i,c in enumerate('IEEE DAY')]
        source=pygame.Surface((sum(g.get_width() for g in glyphs)+gap*(len(glyphs)-1),font.get_height()),pygame.SRCALPHA)
        x=0
        for glyph in glyphs:
            source.blit(glyph,(x,0));x+=glyph.get_width()+gap
        bounds=source.get_bounding_rect()
        source=source.subsurface(bounds).copy()
        self.width=width;self.height=round(source.get_height()*width/source.get_width())
        self.letters=pygame.transform.smoothscale(source,(width,self.height))
        self.mask=self.letters.copy()
        self.glow=pygame.Surface((width+32,self.height+32),pygame.SRCALPHA)
        self.glow.blit(self.letters,(16,16))
        self.glow=pygame.transform.gaussian_blur(self.glow,6)
        self.glow.set_alpha(45)

    def draw(self,surface,x,y,time=0.,animated=False,circuits=False):
        surface.blit(self.glow,(x-16,y-16))
        surface.blit(self.letters,(x,y))
        phase=time%7
        if animated and phase<1.3:
            center=int(phase/1.3*(self.width+60))-30
            band=pygame.Surface(self.letters.get_size(),pygame.SRCALPHA)
            for offset in range(-18,19):
                alpha=int(45*(1-abs(offset)/19))
                pygame.draw.line(band,(255,255,255,alpha),(center+offset,0),(center+offset,self.height))
            band.blit(self.mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(band,(x,y))

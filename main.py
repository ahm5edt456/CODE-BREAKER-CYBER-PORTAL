"""Launch the Cyber Portal edition."""
import pygame
import engine as E
from campaign import CampaignGame

def main():
    game=CampaignGame();game.draw()
    while True:
        dt=min(E.CLOCK.tick(60)/1000,.1)
        for event in pygame.event.get():game.handle(event)
        game.update(dt);game.draw()

if __name__=='__main__':main()

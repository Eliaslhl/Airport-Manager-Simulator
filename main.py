"""
Point d'entrée du jeu : boucle principale Pygame.
"""

import time
import pygame
from game_engine import GameEngine
from ui import Screen, draw_map
from map_manager import AirportMap


# Carte de l'aéroport
AIRPORT_MAP = """
MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM
M                             M
M  W                          M
M                             M
M  MMMMMMMMM   MMMMMMMM       M
M                             M
M  MMMMMMMMM   MMMMMMMM       M
M                             M
M   C C C C                   M
M                             M
M   MMMMMMMMMMMMM             M
M                             M
M         X X X               M
M                             M
M   MMMMMMMMMMMMMMMMM         M
M                             M
M    V V       S S S S S      M
M    V V       S S S S S      M
M                             M
M              G              M
M              G              M
M           AAAAAAA           M
MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM
"""


def main():
    """Boucle principale du jeu."""
    
    # Initialisation
    pygame.init()
    
    # Moteur de jeu
    engine = GameEngine(AIRPORT_MAP)
    airport = AirportMap(AIRPORT_MAP)
    
    # DEBUG: Afficher les positions clés
    print(f"DEBUG: Spawn position: {engine.airport.spawn}")
    print(f"DEBUG: Checkins: {engine.airport.checkins_ordered}")
    print(f"DEBUG: Secus: {engine.airport.secus_ordered}")
    print(f"DEBUG: Lounge blocks: {engine.airport.lounges_ordered}")
    
    engine.initialize(total_passengers=30, spawn_rate=0.5, plane_depart_time=120.0)
    
    print(f"DEBUG: Spawner created with spawn: {engine.spawner.spawn}")
    print(f"DEBUG: Total passengers to spawn: {engine.spawner.total}")
    
    # Écran
    screen = Screen(airport.W, airport.H)
    
    # Timing
    clock = pygame.time.Clock()
    FPS = 60
    start_time = time.time()
    paused = False
    
    # Événement timer
    LOGIC_EVENT = pygame.USEREVENT + 1
    pygame.time.set_timer(LOGIC_EVENT, int(1000 / FPS))
    
    # Boucle principale
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_ESCAPE:
                    running = False
            
            elif event.type == LOGIC_EVENT and not paused:
                dt = 1.0 / FPS
                elapsed = time.time() - start_time
                
                # Mise à jour du jeu
                remaining = engine.update(dt, elapsed)
                
                # Vérifier fin
                if engine.is_finished():
                    running = False
                
                # Rendu
                state = engine.get_state()
                draw_map(
                    screen,
                    engine.airport,
                    engine.passengers,
                    state["score"],
                    remaining,
                    state["nb_boarded"],
                    state["plane_state"]
                )
        
        clock.tick(FPS)
    
    # Écran de fin
    state = engine.get_state()
    screen.draw_end_screen(state["nb_boarded"], state["score"])
    
    # Attendre avant de quitter
    waiting = True
    while waiting:
        for e in pygame.event.get():
            if e.type in (pygame.QUIT, pygame.KEYDOWN):
                waiting = False
        clock.tick(30)
    
    pygame.quit()


if __name__ == "__main__":
    main()
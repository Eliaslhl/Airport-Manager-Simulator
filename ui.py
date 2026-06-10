"""
Affichage et rendu Pygame.
"""

import pygame
import math

ZOOM = 28

class Color:
    """Palette de couleurs."""
    white = (255, 255, 255)
    black = (0, 0, 0)
    gray = (128, 128, 128)
    dark_gray = (50, 50, 50)
    red = (255, 0, 0)
    green = (0, 200, 80)
    blue = (80, 140, 255)
    yellow = (255, 220, 0)
    orange = (255, 140, 0)
    purple = (180, 80, 255)
    cyan = (0, 220, 220)
    dark = (20, 20, 30)


COLOR_MAP = {
    'M': (60, 70, 90),      # Murs
    'W': (40, 160, 80),     # Spawn
    'C': (255, 200, 50),    # Check-in
    'X': (255, 80, 80),     # Sécurité
    'G': (80, 200, 255),    # Porte
    'A': (150, 150, 200),   # Avion
    'S': (100, 180, 130),   # Lounge
}


class Screen:
    """Gère l'affichage Pygame."""
    
    def __init__(self, nx, ny, title="Airport Manager Simulator"):
        """
        Crée un écran.
        
        Args:
            nx, ny: dimensions de la grille
            title: titre de la fenêtre
        """
        self.W = nx * ZOOM
        self.H = (ny + 5) * ZOOM  # +5 au lieu de +3 pour plus d'espace
        
        pygame.display.init()
        pygame.font.init()
        
        self.surface = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption(title)
        
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("Consolas", 22, bold=True)
        self.font_small = pygame.font.SysFont("Consolas", 14)
        self.map_h = ny
    
    def grid_to_screen(self, x, y):
        """Convertit coordonnées grille → écran."""
        sx = x * ZOOM
        sy = self.H - (y + 3) * ZOOM
        return sx, sy
    
    def drawRect(self, x, y, color, border=0):
        """Dessine un rectangle de grille."""
        sx, sy = self.grid_to_screen(x, y)
        pygame.draw.rect(self.surface, color, (sx, sy, ZOOM, ZOOM), border)
    
    def drawCircle(self, x, y, r, color):
        """Dessine un cercle."""
        R = int(r * ZOOM)
        sx, sy = self.grid_to_screen(x, y)
        cx = sx + ZOOM // 2
        cy = sy + ZOOM // 2
        pygame.draw.circle(self.surface, color, (cx, cy), R)
    
    def drawTriangle(self, A, B, C, color):
        """Dessine un triangle (pour les flèches)."""
        def gs(pos):
            sx, sy = self.grid_to_screen(pos[0], pos[1])
            return (sx + ZOOM // 2, sy + ZOOM // 2)
        
        pygame.draw.polygon(self.surface, color, [gs(A), gs(B), gs(C)])
    
    def drawText(self, x, y, txt, color=Color.white, big=False):
        """Dessine du texte."""
        sx, sy = self.grid_to_screen(x, y)
        font = self.font_big if big else self.font_small
        surf = font.render(str(txt), True, color)
        self.surface.blit(surf, (sx, sy))
    
    def drawHUD(self, score, remaining, nb_passengers, nb_boarded, plane_state):
        """Dessine l'interface utilisateur en bas."""
        hud_y = self.H - 3 * ZOOM  # Ajusté pour le nouvel espace
        pygame.draw.rect(self.surface, (15, 15, 25), (0, hud_y, self.W, 3 * ZOOM))
        
        state_str = ["EN ATTENTE", "EMBARQUEMENT", "PARTI"][plane_state]
        state_color = [Color.yellow, Color.green, Color.red][plane_state]
        
        self.surface.blit(
            self.font_big.render(f"SCORE: {score}", True, Color.cyan),
            (10, hud_y + 8)
        )
        self.surface.blit(
            self.font_big.render(f"AVION: {state_str}", True, state_color),
            (250, hud_y + 8)
        )
        self.surface.blit(
            self.font_big.render(f"VOL DANS: {int(remaining)}s", True, Color.white),
            (580, hud_y + 8)
        )
        self.surface.blit(
            self.font_small.render(
                f"Passagers: {nb_passengers}  Embarqués: {nb_boarded}",
                True,
                Color.gray
            ),
            (10, hud_y + 40)
        )
    
    def show(self):
        """Affiche le buffer à l'écran."""
        pygame.display.flip()
    
    def clear(self):
        """Efface l'écran."""
        self.surface.fill(Color.dark)
    
    def draw_end_screen(self, nb_boarded, score):
        """Affiche l'écran de fin."""
        self.clear()
        lines = [
            "═══ SIMULATION TERMINÉE ═══",
            f"Passagers embarqués : {nb_boarded}",
            f"Score final : {score}",
            "Appuyez sur une touche pour quitter",
        ]
        colors = [Color.cyan, Color.green, Color.yellow, Color.gray]
        
        for i, (line, col) in enumerate(zip(lines, colors)):
            surf = self.font_big.render(line, True, col)
            self.surface.blit(
                surf,
                (self.W // 2 - surf.get_width() // 2, 150 + i * 50)
            )
        self.show()


def draw_map(screen, airport, passengers, score, remaining, nb_boarded, plane_state):
    """Dessine la carte complète."""
    screen.clear()
    
    # Mise à jour densité
    airport.densite[:, :] = 0
    for p in passengers:
        ix, iy = int(p.x), int(p.y)
        if airport.walkable(ix, iy):
            airport.densite[ix, iy] += 1
    
    # Grille
    for x in range(airport.W):
        for y in range(airport.H):
            cell = airport.grid[x, y]
            
            if cell == 'M':
                screen.drawRect(x, y, (40, 45, 60))
            elif cell == ' ':
                nb = airport.densite[x, y]
                shade = max(15, 35 - nb * 4)
                screen.drawRect(x, y, (shade, shade, shade + 10))
                screen.drawRect(x, y, (50, 50, 70), 1)
            else:
                color = COLOR_MAP.get(cell, Color.gray)
                screen.drawRect(x, y, color)
                screen.drawRect(x, y, Color.black, 1)
    
    # Passagers
    for p in passengers:
        r = 0.35
        color = p.get_color()
        screen.drawCircle(p.x, p.y, r, color)
        
        # Flèche direction
        dx, dy = p.dir
        norm = math.hypot(dx, dy)
        if norm > 0.01:
            dx /= norm
            dy /= norm
            A = (p.x + dx * 0.4, p.y + dy * 0.4)
            lx, ly = -dy * 0.15, dx * 0.15
            B = (p.x + lx, p.y + ly)
            C = (p.x - lx, p.y - ly)
            screen.drawTriangle(A, B, C, Color.white)
    
    screen.drawHUD(score, remaining, len(passengers), nb_boarded, plane_state)
    screen.show()

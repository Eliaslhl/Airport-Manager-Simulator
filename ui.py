"""
Affichage et rendu Pygame.
"""

import pygame
import math
from entities import PassengerState

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
    'V': (255, 215, 0),     # VIP Lounge (doré)
    'B': (190, 120, 70),    # Boutique / commerce
    'K': (160, 90, 60),     # Café (optionnel)
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
        self.H = (ny + 5) * ZOOM
        
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
    
    def drawHUD(self, score, remaining, nb_passengers, nb_boarded, plane_state,
                missed_passengers=0, total_passengers=0, success_rate=0.0, final_bonus_points=0):
        """Dessine l'interface utilisateur en bas."""
        hud_y = self.H - 3 * ZOOM  
        pygame.draw.rect(self.surface, (15, 15, 25), (0, hud_y, self.W, 3 * ZOOM))
        
        state_str = ["EN ATTENTE", "EMBARQUEMENT", "PARTI"][plane_state]
        state_color = [Color.yellow, Color.green, Color.red][plane_state]
        total = total_passengers or max(nb_boarded + missed_passengers + nb_passengers, 1)
        percent = int(success_rate * 100)
        
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
                f"Actifs: {nb_passengers}  Embarqués: {nb_boarded}/{total}  Ratés: {missed_passengers}  Réussite: {percent}%",
                True,
                Color.gray
            ),
            (10, hud_y + 40)
        )
        self.surface.blit(
            self.font_small.render(
                f"Barème: check-in +5 | sécurité +8 | lounge +5 | normal +30 | VIP +45 | bonus final +{final_bonus_points}",
                True,
                Color.gray
            ),
            (10, hud_y + 60)
        )
    
    def show(self):
        """Affiche le buffer à l'écran."""
        pygame.display.flip()
    
    def clear(self):
        """Efface l'écran."""
        self.surface.fill(Color.dark)
    
    def draw_end_screen(self, nb_boarded, score, missed_passengers=0, total_passengers=0,
                        success_rate=0.0, final_bonus_points=0, score_details=None):
        """Affiche l'écran de fin."""
        self.clear()
        total = total_passengers or max(nb_boarded + missed_passengers, 1)
        percent = int(success_rate * 100)
        details = score_details or {}

        lines = [
            "═══ SIMULATION TERMINÉE ═══",
            f"Passagers embarqués : {nb_boarded}/{total}  ({percent}%)",
            f"Passagers ratés : {missed_passengers}",
            f"Bonus final : +{final_bonus_points}",
            f"Score final : {score}",
            "Appuyez sur une touche pour quitter",
        ]
        colors = [Color.cyan, Color.green, Color.orange, Color.yellow, Color.yellow, Color.gray]

        if details:
            lines.insert(5, (
                "Détail: "
                f"check-in {details.get('checkin', 0)} | "
                f"sécurité {details.get('security', 0)} | "
                f"lounge {details.get('lounge', 0)} | "
                f"embarquement {details.get('boarding', 0)} | "
                f"pénalités {details.get('penalties', 0)}"
            ))
            colors.insert(5, Color.gray)
        
        for i, (line, col) in enumerate(zip(lines, colors)):
            font = self.font_small if line.startswith("Détail:") else self.font_big
            surf = font.render(line, True, col)
            self.surface.blit(
                surf,
                (self.W // 2 - surf.get_width() // 2, 120 + i * 42)
            )
        self.show()


def draw_map(screen, airport, passengers, score, remaining, nb_boarded, plane_state,
             missed_passengers=0, total_passengers=0, success_rate=0.0, final_bonus_points=0):
    """Dessine la carte complète."""
    screen.clear()
    airport.densite[:, :] = 0
    
    for p in passengers:
        if p.state == PassengerState.TERMINE:
            continue
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
    
    for p in passengers:
        if p.state == PassengerState.TERMINE:
            continue
        
        r = 0.35
        color = p.get_color()
        screen.drawCircle(p.x, p.y, r, color)

        moving_states = (
            PassengerState.ARRIVE,
            PassengerState.VA_ENREGISTREMENT,
            PassengerState.VA_SECURITE,
            PassengerState.VA_PORTE,
            PassengerState.VA_COMMERCE,
            PassengerState.RETOUR_CHECKIN,
            PassengerState.RETOUR_SECURITE,
            PassengerState.VA_EMBARQUER,
        )
        
        if p.state in moving_states:
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
    
    screen.drawHUD(
        score, remaining, len(passengers), nb_boarded, plane_state,
        missed_passengers=missed_passengers,
        total_passengers=total_passengers,
        success_rate=success_rate,
        final_bonus_points=final_bonus_points,
    )
    screen.show()

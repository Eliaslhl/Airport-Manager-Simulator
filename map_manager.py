"""
Gestion de la carte et algorithme de pathfinding (distance map).
"""

import numpy as np
from numba import njit


class AirportMap:
    """Représentation et gestion de la grille de l'aéroport."""
    
    def __init__(self, map_text):
        """Initialise la carte depuis un texte."""
        self.grid, self.W, self.H = self._parse(map_text)
        
        # Localisation des zones clés
        self.spawn = self._find('W')[0]
        self.checkins = self._find('C')
        self.secus = self._find('X')
        self.gates = self._find('G')
        self.planes = self._find('A')
        self.lounges = self._find('S')  # Zones de lounge normales
        self.vip_lounges = self._find('V')  # Zones de lounge VIP
        self.commerces = self._find('B') + self._find('K')
        
        from collections import defaultdict
        lounge_columns = defaultdict(list)
        for x, y in self.lounges:
            lounge_columns[x].append((x, y))
        
        self.lounge_column_list = [
            lounge_columns[x] for x in sorted(lounge_columns.keys())
        ]
        
        vip_lounge_columns = defaultdict(list)
        for x, y in self.vip_lounges:
            vip_lounge_columns[x].append((x, y))
        
        self.vip_lounge_column_list = [
            vip_lounge_columns[x] for x in sorted(vip_lounge_columns.keys())
        ]
        
        self.checkins_ordered = sorted(self.checkins, key=lambda p: (p[0], p[1]), reverse=True)
        self.secus_ordered = sorted(self.secus, key=lambda p: (p[0], p[1]), reverse=True)
        self.lounges_ordered = sorted(self.lounges, key=lambda p: (p[0], p[1]), reverse=True)
        self.vip_lounges_ordered = sorted(self.vip_lounges, key=lambda p: (p[0], p[1]), reverse=True)
        self.commerces_ordered = sorted(self.commerces, key=lambda p: (p[0], p[1]), reverse=True)
        
        self.target_checkin = self.checkins[len(self.checkins) // 2]
        self.target_secu = self.secus[len(self.secus) // 2]
        self.target_gate = self.lounge_column_list[0][0] if self.lounge_column_list else self.gates[0]
        self.target_vip_gate = self.vip_lounge_column_list[0][0] if self.vip_lounge_column_list else self.target_gate
        self.target_embarkation = self.gates[0]
        self.target_commerce = self.commerces_ordered[0] if self.commerces_ordered else None
        
        # Cache des cartes de distance
        self._dist_cache = {}
        self.dist_checkin = self.get_dist(self.target_checkin)
        self.dist_secu = self.get_dist(self.target_secu)
        self.dist_gate = self.get_dist(self.target_gate)
        self.dist_vip_gate = self.get_dist(self.target_vip_gate)
        self.dist_embarkation = self.get_dist(self.target_embarkation)
        self.dist_commerce = self.get_dist(self.target_commerce) if self.target_commerce is not None else None
        
        # Matrice de densité 
        self.densite = np.zeros((self.W, self.H), dtype=np.int32)
    
    def _parse(self, text):
        """Parse le texte de la carte en grille numpy."""
        rows = [list(line) for line in text.strip().splitlines()]
        rows.reverse()
        maxlen = max(len(r) for r in rows)
        for r in rows:
            while len(r) < maxlen:
                r.append('M')
        arr = np.array(rows, dtype='U1').T
        return arr, arr.shape[0], arr.shape[1]
    
    def _find(self, ch):
        """Trouve toutes les cellules avec un caractère donné."""
        pts = []
        for x in range(self.W):
            for y in range(self.H):
                if self.grid[x, y] == ch:
                    pts.append((x, y))
        return pts
    
    def walkable(self, x, y):
        """Teste si une cellule est marchable (pas un mur)."""
        if x < 0 or y < 0 or x >= self.W or y >= self.H:
            return False
        return self.grid[x, y] != 'M'
    
    def get_dist(self, target):
        """Retourne (ou crée) la carte de distance vers une cible."""
        if target is None:
            return None
        if target not in self._dist_cache:
            dist = np.full((self.W, self.H), 9999, dtype=np.int32)
            _calc_bfs(dist, self.grid, self.W, self.H, target[0], target[1])
            self._dist_cache[target] = dist
        return self._dist_cache[target]
    
    def get_next_move(self, x, y, target_dist, avoid_overcrowding=True):
        """
        Retourne la meilleure cellule adjacente vers la cible.
        
        Args:
            x, y: position actuelle
            target_dist: carte de distance vers l'objectif
            avoid_overcrowding: si True, évite les cellules trop denses
        
        Returns:
            (nx, ny) ou None
        """
        ix, iy = int(x), int(y)
        
        if not self.walkable(ix, iy):
            return None
        
        current_dist = target_dist[ix, iy]
        neighbors = [(ix+1, iy), (ix-1, iy), (ix, iy+1), (ix, iy-1)]
        
        valid = []
        for nx, ny in neighbors:
            if not self.walkable(nx, ny):
                continue
            
            next_dist = target_dist[nx, ny]

            if next_dist > current_dist:
                continue

            if avoid_overcrowding and self.densite[nx, ny] >= 6:
                continue
            
            valid.append((nx, ny))
        
        if not valid:
            return None
        
        best = min(valid, key=lambda p: target_dist[p[0], p[1]])
        return best


@njit
def _calc_bfs(dist, grid, w, h, tx, ty):
    """
    Calcule la carte de distance via BFS depuis une cible.
    """
    
    dist[tx, ty] = 0
    changed = True
    max_iterations = 1000
    iteration = 0
    
    while changed and iteration < max_iterations:
        changed = False
        iteration += 1
        
        for x in range(w):
            for y in range(h):
                if grid[x, y] == 'M':
                    continue
                
                v = dist[x, y]
                if v == 9999:
                    # Cherche le minimum parmi les voisins
                    best = 9999
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < w and 0 <= ny < h:
                                if grid[nx, ny] != 'M':
                                    best = min(best, dist[nx, ny])
                    
                    if best < 9999:
                        nv = best + 1
                        dist[x, y] = nv
                        changed = True

import random
import math
from enum import IntEnum

class PassengerState(IntEnum):
    """États d'un passager (machine à états)."""
    ARRIVE = 0
    VA_ENREGISTREMENT = 1
    ATTEND_ENREGISTREMENT = 2
    VA_SECURITE = 3
    ATTEND_SECURITE = 4
    VA_PORTE = 5
    ATTEND_EMBARQUEMENT = 6
    VA_COMMERCE = 7       
    ATTEND_COMMERCE = 8
    RETOUR_CHECKIN = 9
    RETOUR_SECURITE = 10
    VA_EMBARQUER = 11
    EMBARQUEMENT = 12
    TERMINE = 13


STATE_NAMES = {
    PassengerState.ARRIVE: "ARRIVE",
    PassengerState.VA_ENREGISTREMENT: "→ ENREG.",
    PassengerState.ATTEND_ENREGISTREMENT: "FILE ENREG.",
    PassengerState.VA_SECURITE: "→ SECU",
    PassengerState.ATTEND_SECURITE: "FILE SECU",
    PassengerState.VA_PORTE: "→ PORTE",
    PassengerState.ATTEND_EMBARQUEMENT: "LOUNGE",
    PassengerState.VA_COMMERCE: "→ COMMERCE",
    PassengerState.ATTEND_COMMERCE: "COMMERCE",
    PassengerState.RETOUR_CHECKIN: "↩ ENREG.",
    PassengerState.RETOUR_SECURITE: "↩ SECU",
    PassengerState.VA_EMBARQUER: "→ EMBARQUER",
    PassengerState.EMBARQUEMENT: "EMBARQUEMENT",
    PassengerState.TERMINE: "TERMINE",
}


class Passenger:
    """Représente un passager avec position, état et comportement."""
    
    _id_counter = 0
    
    def __init__(self, spawn, is_vip=False, event_bus=None):
        """
        Crée un passager.
        
        Args:
            spawn: tuple (x, y) de la position de spawn
            is_vip: True pour priorité en file d'attente
            event_bus: EventBus pour logger les événements
        """
        Passenger._id_counter += 1
        self.id = Passenger._id_counter
        
        sx, sy = spawn
        self.x = sx + 0.5 + random.uniform(-0.2, 0.2)
        self.y = sy + 0.5 + random.uniform(-0.2, 0.2)
        self.dir = (0.0, 1.0)
        
        self.state = PassengerState.ARRIVE
        self.is_vip = is_vip
        self.speed = 1.8 + random.uniform(-0.3, 0.3)
        self.wait_timer = 0.0
        self.patience = 60.0
        self.angry = False
        self.event_bus = event_bus
        self.current_lounge_block = None  
        self.current_vip_lounge_block = None
        self.assigned_checkin_zone = None
        self.assigned_security_zone = None
        self.assigned_lounge_block = None
        self.assigned_checkin_slot = None
        self.assigned_security_slot = None
        self.assigned_lounge_slot = None
        self.assigned_target_cell = None
        self.assigned_target_pos = None
        self.boarding_timer = 0.0

        self.return_after_commerce = None  # "CHECKIN" ou "SECURITY"
        self.commerce_timer = 0.0
        self.used_commerce_for_checkin = False
        self.used_commerce_for_security = False
    
    def get_color(self):
        """Retourne la couleur selon le type et l'état."""
        if self.angry:
            return (255, 50, 50)  # Rouge si énervé
        return (180, 80, 255) if self.is_vip else (80, 140, 255)
    
    def set_state(self, new_state):
        """Change d'état et publie l'événement."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.wait_timer = 0.0
            
            if new_state in (PassengerState.ATTEND_ENREGISTREMENT, PassengerState.ATTEND_SECURITE,
                            PassengerState.ATTEND_EMBARQUEMENT, PassengerState.ATTEND_COMMERCE,
                            PassengerState.EMBARQUEMENT):
                
                if self.assigned_target_pos is not None:
                    self.x, self.y = self.assigned_target_pos
                else:
                    self.x = int(self.x) + 0.5
                    self.y = int(self.y) + 0.5
                self.dir = (0.0, 0.0) 
            
            if self.event_bus:
                self.event_bus.publish("passenger_state_changed", {
                    "passenger_id": self.id,
                    "old_state": old_state,
                    "new_state": new_state
                })
    
    def get_target_dist(self, airport):
        """Retourne la carte de distance vers l'objectif actuel."""
        
        if self.state in (
            PassengerState.VA_ENREGISTREMENT,
            PassengerState.VA_SECURITE,
            PassengerState.VA_PORTE,
            PassengerState.VA_COMMERCE,
            PassengerState.RETOUR_CHECKIN,
            PassengerState.RETOUR_SECURITE,
        ):
            if self.assigned_target_cell is not None:
                return airport.get_dist(self.assigned_target_cell)
            return None

        if self.state == PassengerState.VA_EMBARQUER:
            return airport.dist_embarkation

        return None

    def get_target_pos(self, airport):
        """Retourne la position cible."""
        if self.assigned_target_pos is not None:
            return self.assigned_target_pos

        if self.state == PassengerState.VA_EMBARQUER:
            return airport.target_embarkation

        return None

    def near_target(self, target, radius=1.5):
        """Teste si le passager est près de sa cible."""
        tx, ty = target
        return abs(self.x - tx) <= radius and abs(self.y - ty) <= radius
    
    def reached_assigned_target(self, radius=0.6):
        """
        Teste si le passager a atteint sa destination assignée.
        
        Retourne True si:
        - Le passager est proche de assigned_target_pos (position exacte du slot), OU
        - Le passager est dans la même cellule que assigned_target_cell
        
        Cela gère le cas où le pathfinding amène le passager dans la bonne case
        mais pas exactement sur l'offset du slot.
        """
        if self.assigned_target_pos is None:
            return False
        
        if self.near_target(self.assigned_target_pos, radius):
            return True
        
        if self.assigned_target_cell is not None:
            tx, ty = self.assigned_target_cell
            if int(self.x) == tx and int(self.y) == ty:
                return True
        
        return False
    
    def move(self, dt, airport):
        """Déplace le passager vers sa cible."""
        
        if self.state in (PassengerState.ATTEND_ENREGISTREMENT, PassengerState.ATTEND_SECURITE,
                         PassengerState.ATTEND_EMBARQUEMENT, PassengerState.ATTEND_COMMERCE,
                         PassengerState.EMBARQUEMENT, PassengerState.TERMINE):
            self.dir = (0.0, 0.0)  
            return
        
        dist_map = self.get_target_dist(airport)
        if dist_map is None:
            self.dir = (0.0, 0.0)
            return
        
        avoid_crowding = (self.state != PassengerState.VA_EMBARQUER)
        
        next_move = airport.get_next_move(self.x, self.y, dist_map, avoid_overcrowding=avoid_crowding)
        if next_move is None:
            self.dir = (0.0, 0.0)
            return
        
        nx, ny = next_move
        dx = (nx + 0.5) - self.x
        dy = (ny + 0.5) - self.y
        norm = math.hypot(dx, dy)
        
        if norm > 0:
            dx /= norm
            dy /= norm
        
        v = self.speed
        self.dir = (dx, dy)
        self.x += dx * v * dt
        self.y += dy * v * dt
    
    def update_patience(self, dt):
        """Décrémente la patience et marque comme énervé si nécessaire."""
        if self.state in (PassengerState.ATTEND_ENREGISTREMENT, PassengerState.ATTEND_SECURITE, PassengerState.ATTEND_EMBARQUEMENT):
            self.wait_timer += dt
            self.patience -= dt
            if self.patience <= 0 and not self.angry:
                self.angry = True


class PlaneState(IntEnum):
    """États de l'avion."""
    WAITING = 0
    BOARDING = 1
    DEPARTED = 2


class Plane:
    """Gère l'état et le timing de l'avion."""
    
    def __init__(self, depart_time=120.0, event_bus=None):
        """
        Crée un avion.
        
        Args:
            depart_time: secondes avant départ
            event_bus: EventBus pour publier les événements
        """
        self.state = PlaneState.WAITING
        self.depart_time = depart_time
        self.passengers_boarded = 0
        self.event_bus = event_bus
    
    def update(self, elapsed):
        """
        Met à jour l'état de l'avion.
        
        Args:
            elapsed: temps écoulé depuis le début
        
        Returns:
            temps restant avant départ
        """
        remaining = max(0.0, self.depart_time - elapsed)
        
        if remaining <= 60.0 and self.state == PlaneState.WAITING:
            self.state = PlaneState.BOARDING
            if self.event_bus:
                self.event_bus.publish("plane_boarding_opened", None)
        
        if remaining <= 0 and self.state != PlaneState.DEPARTED:
            self.state = PlaneState.DEPARTED
            if self.event_bus:
                self.event_bus.publish("plane_departed", None)
        
        return remaining
    
    @property
    def boarding_open(self):
        """Retourne True si l'embarquement est ouvert."""
        return self.state == PlaneState.BOARDING


class QueueZone:
    """
    Gère une file d'attente avec support priorité VIP.
    """
    
    def __init__(self, name, capacity=10, service_time=3.0, event_bus=None):
        """
        Crée une zone de file d'attente.
        
        Args:
            name: nom de la zone
            capacity: nombre max de passagers
            service_time: temps pour servir un passager
            event_bus: EventBus
        """
        self.name = name
        self.normal_queue = []  # Passagers normaux
        self.vip_queue = []     # Passagers VIP
        self.capacity = capacity
        self.service_time = service_time
        self.timer = 0.0
        self.current_passenger = None
        self.event_bus = event_bus
    
    def enqueue(self, passenger):
        """Ajoute un passager à la file appropriée."""
        if passenger.is_vip:
            self.vip_queue.append(passenger)
        else:
            self.normal_queue.append(passenger)
    
    def dequeue(self):
        """Retourne le prochain passager à servir (VIP en priorité)."""
        if self.vip_queue:
            return self.vip_queue.pop(0)
        elif self.normal_queue:
            return self.normal_queue.pop(0)
        return None
    
    def is_full(self):
        """Teste si la file est pleine."""
        return len(self.normal_queue) + len(self.vip_queue) >= self.capacity
    
    def update(self, dt):
        """
        Met à jour la file d'attente.
        
        Returns:
            Le passager qui vient d'être servi (ou None)
        """
        if self.current_passenger is None:
            self.current_passenger = self.dequeue()
            self.timer = 0.0
        
        if self.current_passenger is None:
            return None
        
        self.timer += dt
        
        if self.timer >= self.service_time:
            served = self.current_passenger
            self.current_passenger = None
            self.timer = 0.0
            
            if self.event_bus:
                self.event_bus.publish("passenger_served", {
                    "passenger_id": served.id,
                    "queue": self.name
                })
            
            return served
        
        return None
    
    def size(self):
        """Retourne le nombre de passagers en file."""
        return len(self.normal_queue) + len(self.vip_queue) + (1 if self.current_passenger else 0)
    
    def position_in_queue(self, passenger):
        """Retourne la position d'un passager dans la file (-1 si absent)."""
        if passenger == self.current_passenger:
            return 0
        
        if passenger in self.vip_queue:
            return self.vip_queue.index(passenger) + 1
        
        if passenger in self.normal_queue:
            return len(self.vip_queue) + self.normal_queue.index(passenger) + 1
        
        return -1


class ServiceZone:
    """
    Zone de service générique (check-in ou sécurité) avec slots.
    Chaque zone peut traiter 2 passagers simultanément (2 slots).
    """
    
    def __init__(self, zone_id, name, position=None, capacity=2, service_time=3.0, event_bus=None):
        """
        Crée une zone de service.
        
        Args:
            zone_id: identifiant unique
            name: nom (ex "Check-in 1", "Sécurité 1")
            position: tuple (x, y) de la position physique sur la carte
            capacity: nombre de slots (2 agents = 2 slots)
            service_time: temps pour servir un passager
            event_bus: EventBus
        """
        self.zone_id = zone_id
        self.name = name
        self.position = position  # (x, y) sur la carte
        self.capacity = capacity
        self.service_time = service_time
        self.event_bus = event_bus
        
        self.slots = [
            {
                "passenger": None,
                "timer": 0.0,
                "active": False
            }
            for _ in range(capacity)
        ]
        
        self.slot_offsets = [(-0.25, 0.0), (0.25, 0.0)]
        
        self.normal_queue = []
        self.vip_queue = []
    
    def has_free_slot(self):
        """Teste si un slot est libre (pas de passager réservé)."""
        return any(slot["passenger"] is None for slot in self.slots)
    
    def reserve_slot(self, passenger):
        """
        Réserve un slot pour un passager.
        
        Le passager est marqué comme "en route" (active=False).
        Le timer ne commencera qu'après start_service().
        
        Returns:
            Index du slot réservé, ou None si pas de slot libre
        """
        for i, slot in enumerate(self.slots):
            if slot["passenger"] is None:
                self.slots[i]["passenger"] = passenger
                self.slots[i]["timer"] = 0.0
                self.slots[i]["active"] = False
                return i
        return None
    
    def start_service(self, passenger):
        """
        Démarre le service pour un passager déjà réservé.
        
        Appelée seulement quand le passager arrive physiquement à la zone.
        
        Returns:
            True si le service a démarré, False si le passager n'était pas trouvé
        """
        for slot in self.slots:
            if slot["passenger"] is passenger:
                slot["timer"] = 0.0
                slot["active"] = True
                return True
        return False
    
    def release_slot(self, passenger):
        """Libère le slot occupé par un passager."""
        for slot in self.slots:
            if slot["passenger"] is passenger:
                slot["passenger"] = None
                slot["timer"] = 0.0
                slot["active"] = False
                return True
        return False
    
    def get_slot_position(self, slot_index):
        """
        Retourne la position précise du slot.
        
        Returns:
            (x.xx, y.yy) dans la case de la zone
        """
        if not self.position or slot_index >= len(self.slot_offsets):
            return self.position
        
        ox, oy = self.slot_offsets[slot_index]
        return (self.position[0] + 0.5 + ox, self.position[1] + 0.5 + oy)
    
    def enqueue(self, passenger):
        """Ajoute un passager à la file (obsolète - ne plus utiliser)."""
        if passenger.is_vip:
            self.vip_queue.append(passenger)
        else:
            self.normal_queue.append(passenger)
    
    def update(self, dt):
        """
        Met à jour la zone.
        
        Incrémente le timer SEULEMENT pour les slots actifs.
        Retourne les passagers qui viennent de finir leur service.
        
        Returns:
            Liste des passagers qui viennent d'être servis
        """
        served = []
        
        for slot in self.slots:
            passenger = slot["passenger"]
            
            if passenger is None:
                continue
            
            if not slot["active"]:
                continue
            
            slot["timer"] += dt
            
            if slot["timer"] >= self.service_time:
                served.append(passenger)
                self.release_slot(passenger)
                
                if self.event_bus:
                    self.event_bus.publish("passenger_served", {
                        "passenger_id": passenger.id,
                        "zone": self.name
                    })
        
        return served
    
    def size(self):
        """Retourne le nombre de passagers en attente ou en cours."""
        total = len(self.normal_queue) + len(self.vip_queue)
        total += sum(1 for slot in self.slots if slot["passenger"] is not None)
        return total


class Spawner:
    """Crée des passagers au fil du temps."""
    
    def __init__(self, spawn, passengers, total=60, rate=1.0, event_bus=None):
        """
        Crée un spawner.
        
        Args:
            spawn: position de spawn
            passengers: liste des passagers (modifiée par le spawner)
            total: nombre total de passagers à créer
            rate: passagers/seconde
            event_bus: EventBus
        """
        self.spawn = spawn
        self.passengers = passengers
        self.total = total
        self.created = 0
        self.accu = 0.0
        self.rate = rate
        self.event_bus = event_bus
        self.nb_vip = int(total * 0.1)
        self.nb_normal = total - self.nb_vip
        self.vip_created = 0
        self.normal_created = 0
    
    def update(self, dt):
        """Crée des passagers selon le timing - VIP d'abord, puis normaux."""
        if self.created >= self.total:
            return
        
        self.accu += self.rate * dt
        while self.accu >= 1.0 and self.created < self.total:
            if self.vip_created < self.nb_vip:
                is_vip = True
                self.vip_created += 1
            else:
                is_vip = False
                self.normal_created += 1
            
            p = Passenger(self.spawn, is_vip=is_vip, event_bus=self.event_bus)
            self.passengers.append(p)
            
            if self.event_bus:
                self.event_bus.publish("passenger_spawned", {
                    "passenger_id": p.id,
                    "is_vip": is_vip
                })
            
            self.created += 1
            self.accu -= 1.0


class CheckinDesk:
    """Représente un guichet d'enregistrement avec hôtesse."""
    
    def __init__(self, desk_id, capacity=2, service_time=3.0, event_bus=None):
        """
        Crée un guichet.
        
        Args:
            desk_id: identifiant du guichet
            capacity: nombre de passagers traités simultanément
            service_time: temps pour servir un passager
            event_bus: EventBus
        """
        self.desk_id = desk_id
        self.normal_queue = []
        self.vip_queue = []
        self.capacity = capacity
        self.service_time = service_time
        self.current_passengers = [] 
        self.timers = [] 
        self.event_bus = event_bus
    
    def enqueue(self, passenger):
        """Ajoute un passager à la file."""
        if passenger.is_vip:
            self.vip_queue.append(passenger)
        else:
            self.normal_queue.append(passenger)
    
    def has_space(self):
        """Teste si le guichet peut accepter un nouveau passager."""
        return len(self.current_passengers) < self.capacity
    
    def update(self, dt):
        """
        Met à jour le guichet.
        
        Returns:
            Liste des passagers qui viennent d'être servis
        """
        served = []
        
        while self.has_space() and (self.vip_queue or self.normal_queue):
            if self.vip_queue:
                p = self.vip_queue.pop(0)
            else:
                p = self.normal_queue.pop(0)
            self.current_passengers.append(p)
            self.timers.append(0.0)
        
        for i in range(len(self.current_passengers) - 1, -1, -1):
            self.timers[i] += dt
            
            if self.timers[i] >= self.service_time:
                served.append(self.current_passengers.pop(i))
                self.timers.pop(i)
                
                if self.event_bus:
                    self.event_bus.publish("passenger_served", {
                        "passenger_id": served[-1].id,
                        "desk": self.desk_id
                    })
        
        return served
    
    def size(self):
        """Retourne le nombre de passagers en attente ou en cours."""
        return len(self.normal_queue) + len(self.vip_queue) + len(self.current_passengers)


class LoungeBlock:
    """Représente un bloc du lounge (une seule case S) accueillant max 5 passagers."""
    
    def __init__(self, block_id, position=None, capacity=5):
        """
        Crée un bloc de lounge.
        
        Args:
            block_id: identifiant unique du bloc
            position: tuple (x, y) de la position physique sur la carte
            capacity: nombre max de passagers (5 pour remplir les 5 slots visuels)
        """
        self.block_id = block_id
        self.position = position  # (x, y) sur la carte
        self.capacity = capacity
    
        self.slots = [None] * capacity
        
        # Offsets visuels pour chaque slot : 4 coins + centre
        self.slot_offsets = [
            (-0.25, -0.25),  
            (0.25, -0.25),   
            (-0.25, 0.25),   
            (0.25, 0.25),   
            (0.0, 0.0)       
        ]
    
    def has_free_slot(self):
        """Teste si un slot est libre."""
        return any(slot is None for slot in self.slots)
    
    def reserve_slot(self, passenger):
        """
        Réserve un slot pour un passager.
        
        Returns:
            Index du slot réservé, ou None si pas de slot libre
        """
        for i in range(len(self.slots)):
            if self.slots[i] is None:
                self.slots[i] = passenger
                return i
        return None
    
    def release_slot(self, passenger):
        """Libère le slot occupé par un passager."""
        for i in range(len(self.slots)):
            if self.slots[i] is passenger:
                self.slots[i] = None
                return
    
    def get_slot_position(self, slot_index):
        """
        Retourne la position précise du slot.
        
        Returns:
            (x.xx, y.yy) dans la case du lounge
        """
        if not self.position or slot_index >= len(self.slot_offsets):
            return self.position
        
        ox, oy = self.slot_offsets[slot_index]
        return (self.position[0] + 0.5 + ox, self.position[1] + 0.5 + oy)
    
    def add_passenger(self, passenger):
        """Ajoute un passager au bloc (pour compatibilité)."""
        return self.reserve_slot(passenger) is not None
    
    def remove_passenger(self, passenger):
        """Retire un passager du bloc."""
        self.release_slot(passenger)
        return True
    
    def can_accept(self):
        """Teste si le bloc peut accepter un passager de plus."""
        return self.has_free_slot()
    
    def size(self):
        """Retourne le nombre de passagers dans le bloc."""
        return sum(1 for slot in self.slots if slot is not None)

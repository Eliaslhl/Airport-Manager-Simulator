"""
Entités du jeu : Passagers, Avion, Gestionnaires de files.
"""

import random
import math
from enum import IntEnum


class PassengerState(IntEnum):
    """États d'une passager (machine à états)."""
    ARRIVE = 0
    VA_ENREGISTREMENT = 1
    ATTEND_ENREGISTREMENT = 2
    VA_SECURITE = 3
    ATTEND_SECURITE = 4
    VA_PORTE = 5
    ATTEND_EMBARQUEMENT = 6
    VA_EMBARQUER = 7  # Se déplace vers la porte pour embarquer
    EMBARQUEMENT = 8  # À la porte, attend validation (1s)
    TERMINE = 9


STATE_NAMES = {
    PassengerState.ARRIVE: "ARRIVE",
    PassengerState.VA_ENREGISTREMENT: "→ ENREG.",
    PassengerState.ATTEND_ENREGISTREMENT: "FILE ENREG.",
    PassengerState.VA_SECURITE: "→ SECU",
    PassengerState.ATTEND_SECURITE: "FILE SECU",
    PassengerState.VA_PORTE: "→ PORTE",
    PassengerState.ATTEND_EMBARQUEMENT: "LOUNGE",
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
        self.patience = 60.0  # Secondes avant de s'énerver
        self.angry = False
        self.event_bus = event_bus
        self.current_lounge_block = None  # Bloc du lounge occupé
        self.current_vip_lounge_block = None  # Bloc du VIP lounge occupé
        self.assigned_checkin_zone = None  # Zone de check-in assignée
        self.assigned_security_zone = None  # Zone de sécurité assignée
        self.boarding_timer = 0.0  # Timer pour embarquement (1s)
    
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
            
            if self.event_bus:
                self.event_bus.publish("passenger_state_changed", {
                    "passenger_id": self.id,
                    "old_state": old_state,
                    "new_state": new_state
                })
    
    def get_target_dist(self, airport):
        """Retourne la carte de distance vers l'objectif actuel."""
        if self.state in (PassengerState.VA_ENREGISTREMENT, PassengerState.ATTEND_ENREGISTREMENT):
            return airport.dist_checkin
        elif self.state in (PassengerState.VA_SECURITE, PassengerState.ATTEND_SECURITE):
            return airport.dist_secu
        elif self.state in (PassengerState.VA_PORTE, PassengerState.ATTEND_EMBARQUEMENT):
            # Aller au lounge d'attente
            if self.is_vip:
                return airport.dist_vip_gate
            return airport.dist_gate
        elif self.state in (PassengerState.VA_EMBARQUER, PassengerState.EMBARQUEMENT):
            # Aller à la vraie porte pour embarquer
            return airport.dist_embarkation
        return None
    
    def get_target_pos(self, airport):
        """Retourne la position cible."""
        if self.state in (PassengerState.VA_ENREGISTREMENT, PassengerState.ATTEND_ENREGISTREMENT):
            # Si assigné à une zone, utiliser sa position; sinon, le centre
            if self.assigned_checkin_zone and self.assigned_checkin_zone.position:
                return self.assigned_checkin_zone.position
            return airport.target_checkin
        elif self.state in (PassengerState.VA_SECURITE, PassengerState.ATTEND_SECURITE):
            # Si assigné à une zone, utiliser sa position; sinon, le centre
            if self.assigned_security_zone and self.assigned_security_zone.position:
                return self.assigned_security_zone.position
            return airport.target_secu
        elif self.state in (PassengerState.VA_PORTE, PassengerState.ATTEND_EMBARQUEMENT):
            # Aller au lounge d'attente
            if self.is_vip:
                return airport.target_vip_gate
            return airport.target_gate
        elif self.state in (PassengerState.VA_EMBARQUER, PassengerState.EMBARQUEMENT):
            # Aller à la vraie porte pour embarquer
            return airport.target_embarkation
        return None
    
    def near_target(self, target, radius=1.5):
        """Teste si le passager est près de sa cible."""
        tx, ty = target
        return abs(self.x - tx) <= radius and abs(self.y - ty) <= radius
    
    def move(self, dt, airport):
        """Déplace le passager vers sa cible."""
        # Les passagers en attente ne bougent pas
        if self.state in (PassengerState.ATTEND_ENREGISTREMENT, PassengerState.ATTEND_SECURITE, PassengerState.ATTEND_EMBARQUEMENT):
            return
        
        dist_map = self.get_target_dist(airport)
        if dist_map is None:
            return
        
        next_move = airport.get_next_move(self.x, self.y, dist_map, avoid_overcrowding=True)
        if next_move is None:
            return
        
        nx, ny = next_move
        dx = (nx + 0.5) - self.x
        dy = (ny + 0.5) - self.y
        norm = math.hypot(dx, dy)
        
        if norm > 0:
            dx /= norm
            dy /= norm
        
        # Appliquer la vitesse
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
        
        # Transition vers embarquement
        if remaining <= 60.0 and self.state == PlaneState.WAITING:
            self.state = PlaneState.BOARDING
            if self.event_bus:
                self.event_bus.publish("plane_boarding_opened", None)
        
        # Transition vers départ
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
    CORRECTED : Pas de "in_queue" flag bugué.
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
        # Commence à servir le prochain passager si libre
        if self.current_passenger is None:
            self.current_passenger = self.dequeue()
            self.timer = 0.0
        
        if self.current_passenger is None:
            return None
        
        self.timer += dt
        
        # Passager fini de se faire servir
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
    Zone de service générique (check-in ou sécurité) avec 2 agents.
    Chaque zone traite 2 passagers simultanément.
    """
    
    def __init__(self, zone_id, name, position=None, capacity=2, service_time=3.0, event_bus=None):
        """
        Crée une zone de service.
        
        Args:
            zone_id: identifiant unique
            name: nom (ex "Check-in 1", "Sécurité 1")
            position: tuple (x, y) de la position physique sur la carte
            capacity: nombre de passagers en parallèle (2 agents)
            service_time: temps pour servir un passager
            event_bus: EventBus
        """
        self.zone_id = zone_id
        self.name = name
        self.position = position  # (x, y) sur la carte
        self.normal_queue = []
        self.vip_queue = []
        self.capacity = capacity
        self.service_time = service_time
        self.current_passengers = []  # Liste de passagers en cours
        self.timers = []  # Timers pour chaque passager
        self.event_bus = event_bus
    
    def enqueue(self, passenger):
        """Ajoute un passager à la file."""
        if passenger.is_vip:
            self.vip_queue.append(passenger)
        else:
            self.normal_queue.append(passenger)
    
    def has_space(self):
        """Teste si la zone peut accepter un nouveau passager."""
        return len(self.current_passengers) < self.capacity
    
    def can_accept(self):
        """Teste si la zone peut accepter un passager (file + en cours)."""
        return len(self.normal_queue) + len(self.vip_queue) + len(self.current_passengers) < 20
    
    def update(self, dt):
        """
        Met à jour la zone.
        
        Returns:
            Liste des passagers qui viennent d'être servis
        """
        served = []
        
        # Faire monter les passagers en attente
        while self.has_space() and (self.vip_queue or self.normal_queue):
            if self.vip_queue:
                p = self.vip_queue.pop(0)
            else:
                p = self.normal_queue.pop(0)
            self.current_passengers.append(p)
            self.timers.append(0.0)
        
        # Mettre à jour les timers
        for i in range(len(self.current_passengers) - 1, -1, -1):
            self.timers[i] += dt
            
            if self.timers[i] >= self.service_time:
                served.append(self.current_passengers.pop(i))
                self.timers.pop(i)
                
                if self.event_bus:
                    self.event_bus.publish("passenger_served", {
                        "passenger_id": served[-1].id,
                        "zone": self.name
                    })
        
        return served
    
    def size(self):
        """Retourne le nombre de passagers en attente ou en cours."""
        return len(self.normal_queue) + len(self.vip_queue) + len(self.current_passengers)


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
        # Calculer le nombre de VIP (10%) et de normaux
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
            # Spawner les VIP d'abord, puis les passagers normaux
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
        self.current_passengers = []  # Liste de passagers en cours
        self.timers = []  # Timers pour chaque passager
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
        
        # Faire monter les passagers en attente
        while self.has_space() and (self.vip_queue or self.normal_queue):
            if self.vip_queue:
                p = self.vip_queue.pop(0)
            else:
                p = self.normal_queue.pop(0)
            self.current_passengers.append(p)
            self.timers.append(0.0)
        
        # Mettre à jour les timers
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
    """Représente un bloc du lounge accueillant max 10 passagers."""
    
    def __init__(self, block_id, capacity=10):
        """
        Crée un bloc de lounge.
        
        Args:
            block_id: identifiant unique du bloc
            capacity: nombre max de passagers
        """
        self.block_id = block_id
        self.capacity = capacity
        self.passengers = []
    
    def can_accept(self):
        """Teste si le bloc peut accepter un passager de plus."""
        return len(self.passengers) < self.capacity
    
    def add_passenger(self, passenger):
        """Ajoute un passager au bloc."""
        if self.can_accept():
            self.passengers.append(passenger)
            return True
        return False
    
    def remove_passenger(self, passenger):
        """Retire un passager du bloc."""
        if passenger in self.passengers:
            self.passengers.remove(passenger)
            return True
        return False
    
    def size(self):
        """Retourne le nombre de passagers dans le bloc."""
        return len(self.passengers)

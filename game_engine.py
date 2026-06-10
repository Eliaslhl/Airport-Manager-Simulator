"""
Moteur de jeu : logique principale et machine à états.
"""

from entities import (
    PassengerState, PlaneState, QueueZone, Spawner, Plane, CheckinDesk, LoungeBlock
)
from events import EventBus, EventType
from map_manager import AirportMap


class GameEngine:
    """Moteur de jeu principal."""
    
    def __init__(self, airport_map_text, event_bus=None):
        """
        Initialise le moteur.
        
        Args:
            airport_map_text: texte de définition de la carte
            event_bus: EventBus pour les événements (créé si None)
        """
        self.event_bus = event_bus or EventBus()
        
        # Carte
        self.airport = AirportMap(airport_map_text)
        
        # Entités (initialisées dans initialize())
        self.passengers: list = []
        self.plane: Plane | None = None
        self.spawner: Spawner | None = None
        self.checkin_desks: list = []  # Plusieurs guichets
        self.queue_secu: QueueZone | None = None
        self.lounge_blocks: list = []  # Blocs de lounge
        self.lounge_assignment_counter: int = 0  # Compteur pour distribuer aux blocs
        
        # Scoring
        self.score: int = 0
        self.nb_boarded: int = 0
        self.missed_passengers: int = 0
    
    def initialize(self, total_passengers=60, spawn_rate=1.0, plane_depart_time=120.0, num_desks=3):
        """
        Initialise les entités du jeu.
        
        Args:
            total_passengers: nombre de passagers à spawner
            spawn_rate: passagers/seconde
            plane_depart_time: secondes avant départ de l'avion
            num_desks: nombre de guichets de check-in
        """
        self.passengers = []
        self.plane = Plane(plane_depart_time, self.event_bus)
        self.spawner = Spawner(
            self.airport.spawn,
            self.passengers,
            total=total_passengers,
            rate=spawn_rate,
            event_bus=self.event_bus
        )
        
        # Créer les guichets (chacun avec 2 places et 3s par passager)
        self.checkin_desks = [
            CheckinDesk(i, capacity=2, service_time=3.0, event_bus=self.event_bus)
            for i in range(num_desks)
        ]
        
        self.queue_secu = QueueZone(
            "Sécurité",
            capacity=10,
            service_time=3.0,
            event_bus=self.event_bus
        )
        
        # Créer les blocs de lounge (un par colonne S, max 10 pers par bloc)
        self.lounge_blocks = [
            LoungeBlock(i, capacity=10)
            for i in range(len(self.airport.lounge_column_list))
        ]
        
        self.score = 0
        self.nb_boarded = 0
        self.missed_passengers = 0
        self.lounge_assignment_counter = 0
    
    def update(self, dt, elapsed_time):
        """
        Met à jour le jeu (une frame).
        
        Args:
            dt: delta temps (frame time)
            elapsed_time: temps total écoulé depuis le début
        """
        if not self.plane or not self.spawner or not self.checkin_desks or not self.queue_secu:
            return 0.0
        
        # Mise à jour avion
        remaining = self.plane.update(elapsed_time)
        
        # Spawn passagers
        self.spawner.update(dt)
        
        # Mise à jour guichets check-in (distribution de file d'attente)
        all_served_checkin = []
        for desk in self.checkin_desks:
            served = desk.update(dt)
            all_served_checkin.extend(served)
        
        for p in all_served_checkin:
            p.set_state(PassengerState.VA_SECURITE)
        
        # Mise à jour file de sécurité
        served_secu = self.queue_secu.update(dt)
        if served_secu:
            served_secu.set_state(PassengerState.VA_PORTE)
        
        # Passagers à retirer
        to_remove = []
        
        # Mise à jour chaque passager
        for p in self.passengers:
            # Machine à états
            self._update_passenger_state(p, dt)
            
            # Mouvement
            p.move(dt, self.airport)
            
            # Patience
            p.update_patience(dt)
        
        # Avion parti : marquer les passagers manqués
        if self.plane.state == PlaneState.DEPARTED:
            for p in self.passengers:
                if p.state != PassengerState.TERMINE:
                    # Retirer du lounge si nécessaire
                    if p.current_lounge_block:
                        p.current_lounge_block.remove_passenger(p)
                    self.score -= 20
                    self.missed_passengers += 1
                    self.event_bus.publish(EventType.PASSENGER_MISSED, {
                        "passenger_id": p.id
                    })
                    to_remove.append(p)
        
        # Retirer les passagers
        for p in to_remove:
            if p in self.passengers:
                self.passengers.remove(p)
        
        return remaining
    
    def _update_passenger_state(self, p, dt):
        """
        Met à jour l'état d'un passager (machine à états).
        
        Distribution dans les guichets de check-in.
        """
        if not self.plane or not self.checkin_desks or not self.queue_secu:
            return
        
        if p.state == PassengerState.ARRIVE:
            # Première étape : aller vers l'enregistrement
            p.set_state(PassengerState.VA_ENREGISTREMENT)
        
        elif p.state == PassengerState.VA_ENREGISTREMENT:
            # Arrivé au check-in ?
            if p.near_target(self.airport.target_checkin, 1.8):
                # Trouver le guichet avec le moins de gens
                best_desk = min(self.checkin_desks, key=lambda d: d.size())
                if not best_desk.has_space() and all(not d.has_space() for d in self.checkin_desks):
                    # Tous les guichets sont pleins, attendre
                    pass
                else:
                    best_desk.enqueue(p)
                    p.set_state(PassengerState.ATTEND_ENREGISTREMENT)
        
        elif p.state == PassengerState.ATTEND_ENREGISTREMENT:
            # Reste en file (pas de mouvement)
            pass
        
        elif p.state == PassengerState.VA_SECURITE:
            # Aller vers la sécurité
            if p.near_target(self.airport.target_secu, 1.8):
                if not self.queue_secu.is_full():
                    self.queue_secu.enqueue(p)
                    p.set_state(PassengerState.ATTEND_SECURITE)
        
        elif p.state == PassengerState.ATTEND_SECURITE:
            # Reste en file
            pass
        
        elif p.state == PassengerState.VA_PORTE:
            # Aller vers le lounge
            if p.near_target(self.airport.target_gate, 1.8):
                p.set_state(PassengerState.ATTEND_EMBARQUEMENT)
        
        elif p.state == PassengerState.ATTEND_EMBARQUEMENT:
            # Passager au lounge : assigner à un bloc
            if p.current_lounge_block is None:
                # Assigner cycliquement aux blocs (distribution progressive)
                block_idx = self.lounge_assignment_counter % len(self.lounge_blocks)
                block = self.lounge_blocks[block_idx]
                
                if block.can_accept():
                    block.add_passenger(p)
                    p.current_lounge_block = block
                    self.lounge_assignment_counter += 1
                # Sinon, attendre qu'il y ait de la place
            
            # Attendre ouverture embarquement
            if self.plane.boarding_open:
                # Retirer du bloc lounge
                if p.current_lounge_block:
                    p.current_lounge_block.remove_passenger(p)
                    p.current_lounge_block = None
                p.set_state(PassengerState.EMBARQUE)
        
        elif p.state == PassengerState.EMBARQUE:
            # Passager à bord : fin
            p.set_state(PassengerState.TERMINE)
            self.score += 10
            self.nb_boarded += 1
            self.event_bus.publish(EventType.PASSENGER_BOARDED, {
                "passenger_id": p.id
            })
    
    def is_finished(self):
        """Retourne True si la simulation est terminée."""
        if not self.plane:
            return False
        # Avion parti et tous les passagers traités
        if self.plane.state == PlaneState.DEPARTED:
            return len(self.passengers) == 0
        return False
    
    def get_state(self):
        """Retourne l'état du jeu (pour UI)."""
        return {
            "score": self.score,
            "nb_boarded": self.nb_boarded,
            "nb_passengers": len(self.passengers),
            "plane_state": self.plane.state if self.plane else 0,
        }


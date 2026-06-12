"""
Moteur de jeu : logique        # Entités (initialisées dans initialize())
        self.passengers: list = []
        self.plane: Plane | None = None
        self.spawner: Spawner | None = None
        self.checkin_zones: list = []  # Zones de check-in (une par C)
        self.security_zones: list = []  # Zones de sécurité (une par X)
        self.lounge_blocks: list = []  # Blocs de lounge
        self.checkin_assignment_counter: int = 0  # Compteur pour distribuer aux zones check-in
        self.security_assignment_counter: int = 0  # Compteur pour distribuer aux zones sécurité
        self.lounge_assignment_counter: int = 0  # Compteur pour distribuer aux blocs loungeale et machine à états.
"""

from entities import (
    PassengerState, PlaneState, Spawner, Plane, LoungeBlock, ServiceZone
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
        self.checkin_zones: list = []  # Zones de check-in (une par C)
        self.security_zones: list = []  # Zones de sécurité (une par X)
        self.lounge_blocks: list = []  # Blocs de lounge
        self.vip_lounge_blocks: list = []  # Blocs de VIP lounge
        self.lounge_assignment_counter: int = 0  # Compteur pour distribuer aux blocs
        self.vip_lounge_assignment_counter: int = 0  # Compteur pour distribuer aux blocs VIP
        
        # Boarding system (embarquement 2 par 2)
        self.boarding_group_timer: float = 0.0  # Timer entre groupes (2s)
        self.passengers_in_boarding: list = []  # Passagers en cours d'embarquement (VA_EMBARQUER/EMBARQUEMENT)
        
        # Scoring
        self.score: int = 0
        self.nb_boarded: int = 0
        self.missed_passengers: int = 0
    
    def initialize(self, total_passengers=60, spawn_rate=1.0, plane_depart_time=120.0):
        """
        Initialise les entités du jeu.
        
        Args:
            total_passengers: nombre de passagers à spawner
            spawn_rate: passagers/seconde
            plane_depart_time: secondes avant départ de l'avion
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
        
        # Créer une zone de check-in pour chaque C (2 agents par zone)
        self.checkin_zones = [
            ServiceZone(i, f"Check-in {i+1}", position=self.airport.checkins[i], capacity=2, service_time=3.0, event_bus=self.event_bus)
            for i in range(len(self.airport.checkins))
        ]
        
        # Créer une zone de sécurité pour chaque X (2 agents par zone)
        self.security_zones = [
            ServiceZone(i, f"Sécurité {i+1}", position=self.airport.secus[i], capacity=2, service_time=3.0, event_bus=self.event_bus)
            for i in range(len(self.airport.secus))
        ]
        
        # Créer les blocs de lounge (un par colonne S, max 5 pers par bloc)
        self.lounge_blocks = [
            LoungeBlock(i, capacity=5)
            for i in range(len(self.airport.lounge_column_list))
        ]
        
        # Créer les blocs de VIP lounge (un par colonne V, max 5 pers par bloc)
        self.vip_lounge_blocks = [
            LoungeBlock(i, capacity=5)
            for i in range(len(self.airport.vip_lounge_column_list))
        ]
        
        self.score = 0
        self.nb_boarded = 0
        self.missed_passengers = 0
        self.checkin_assignment_counter = 0
        self.security_assignment_counter = 0
        self.lounge_assignment_counter = 0
        self.vip_lounge_assignment_counter = 0
    
    def update(self, dt, elapsed_time):
        """
        Met à jour le jeu (une frame).
        
        Args:
            dt: delta temps (frame time)
            elapsed_time: temps total écoulé depuis le début
        """
        if not self.plane or not self.spawner or not self.checkin_zones or not self.security_zones:
            return 0.0
        
        # Mise à jour avion
        remaining = self.plane.update(elapsed_time)
        
        # Spawn passagers
        self.spawner.update(dt)
        
        # Mise à jour zones check-in (distribution de file d'attente)
        all_served_checkin = []
        for zone in self.checkin_zones:
            served = zone.update(dt)
            all_served_checkin.extend(served)
        
        for p in all_served_checkin:
            p.set_state(PassengerState.VA_SECURITE)
        
        # Mise à jour zones de sécurité
        all_served_secu = []
        for zone in self.security_zones:
            served = zone.update(dt)
            all_served_secu.extend(served)
        
        for p in all_served_secu:
            p.set_state(PassengerState.VA_PORTE)
        
        # Passagers à retirer
        to_remove = []
        
        # Mise à jour chaque passager (VIP d'abord, puis les autres)
        vip_passengers = [p for p in self.passengers if p.is_vip]
        normal_passengers = [p for p in self.passengers if not p.is_vip]
        
        for p in vip_passengers + normal_passengers:
            # Machine à états
            self._update_passenger_state(p, dt)
            
            # Mouvement
            p.move(dt, self.airport)
            
            # Patience
            p.update_patience(dt)
        
        # Gestion du timing d'embarquement (2 par 2 avec 2s d'intervalle)
        # Compter les passagers actuellement en VA_EMBARQUER ou EMBARQUEMENT
        passengers_boarding = [p for p in self.passengers 
                              if p.state in (PassengerState.VA_EMBARQUER, PassengerState.EMBARQUEMENT)]
        
        # Si 2 passagers sont en EMBARQUEMENT, activer le timer d'attente
        in_embarquement = sum(1 for p in passengers_boarding if p.state == PassengerState.EMBARQUEMENT)
        if in_embarquement >= 2:
            self.boarding_group_timer += dt
        else:
            self.boarding_group_timer = 0.0
        
        # Si timer >= 2s, réinitialiser pour laisser les 2 suivants embarquer
        if self.boarding_group_timer >= 2.0:
            self.boarding_group_timer = 0.0
        
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
        
        Distribution cyclique en partant de la fin (dernier C, X, etc).
        """
        if not self.plane or not self.checkin_zones or not self.security_zones:
            return
        
        if p.state == PassengerState.ARRIVE:
            # Première étape : aller vers l'enregistrement
            p.set_state(PassengerState.VA_ENREGISTREMENT)
        
        elif p.state == PassengerState.VA_ENREGISTREMENT:
            # Arrivé au check-in ?
            if p.near_target(self.airport.target_checkin, 1.8):
                # Assigner cycliquement en partant de la fin (dernier C d'abord)
                # Pour 4 zones: 0,1,2,3 -> on veut 3,2,1,0,3,2,1,0...
                num_zones = len(self.checkin_zones)
                zone_idx = (num_zones - 1 - (self.checkin_assignment_counter % num_zones))
                zone = self.checkin_zones[zone_idx]
                
                if zone.has_space():
                    zone.enqueue(p)
                    p.assigned_checkin_zone = zone  # Assigner la zone au passager
                    p.set_state(PassengerState.ATTEND_ENREGISTREMENT)
                    self.checkin_assignment_counter += 1
                # Sinon attendre qu'il y ait de la place
        
        elif p.state == PassengerState.ATTEND_ENREGISTREMENT:
            # Reste en file (pas de mouvement)
            pass
        
        elif p.state == PassengerState.VA_SECURITE:
            # Aller vers la sécurité
            if p.near_target(self.airport.target_secu, 1.8):
                # Assigner cycliquement en partant de la fin (dernier X d'abord)
                num_zones = len(self.security_zones)
                zone_idx = (num_zones - 1 - (self.security_assignment_counter % num_zones))
                zone = self.security_zones[zone_idx]
                
                if zone.has_space():
                    zone.enqueue(p)
                    p.assigned_security_zone = zone  # Assigner la zone au passager
                    p.set_state(PassengerState.ATTEND_SECURITE)
                    self.security_assignment_counter += 1
                # Sinon attendre qu'il y ait de la place
        
        elif p.state == PassengerState.ATTEND_SECURITE:
            # Reste en file
            pass
        
        elif p.state == PassengerState.VA_PORTE:
            # Aller vers le lounge (VIP ou normal)
            target = p.get_target_pos(self.airport)
            if p.near_target(target, 1.8):
                p.set_state(PassengerState.ATTEND_EMBARQUEMENT)
        
        elif p.state == PassengerState.ATTEND_EMBARQUEMENT:
            # Passager au lounge : assigner à un bloc
            if p.is_vip:
                # VIP lounge
                if p.current_vip_lounge_block is None and len(self.vip_lounge_blocks) > 0:
                    block_idx = self.vip_lounge_assignment_counter % len(self.vip_lounge_blocks)
                    block = self.vip_lounge_blocks[block_idx]
                    
                    if block.can_accept():
                        block.add_passenger(p)
                        p.current_vip_lounge_block = block
                        self.vip_lounge_assignment_counter += 1
                
                # Attendre ouverture embarquement
                if self.plane.boarding_open:
                    # Les VIP embarquent en premier (2 par 2)
                    # Compter combien de VIP sont actuellement en mouvement/embarquement
                    vip_in_boarding = sum(1 for pass_check in self.passengers 
                                         if pass_check.is_vip and 
                                         pass_check.state in (PassengerState.VA_EMBARQUER, PassengerState.EMBARQUEMENT))
                    
                    # Si moins de 2 VIP embarquent, laisser ce VIP embarquer
                    if vip_in_boarding < 2:
                        if p.current_vip_lounge_block:
                            p.current_vip_lounge_block.remove_passenger(p)
                            p.current_vip_lounge_block = None
                        p.set_state(PassengerState.VA_EMBARQUER)
            else:
                # Lounge normal - ATTENDRE que les VIP embarquent d'abord
                if p.current_lounge_block is None:
                    block_idx = self.lounge_assignment_counter % len(self.lounge_blocks)
                    block = self.lounge_blocks[block_idx]
                    
                    if block.can_accept():
                        block.add_passenger(p)
                        p.current_lounge_block = block
                        self.lounge_assignment_counter += 1
                
                # Embarquement: vérifier que l'embarquement est ouvert ET qu'il n'y a plus de VIP en attente
                if self.plane.boarding_open:
                    # Compter les VIP qui sont encore en VA_EMBARQUER ou EMBARQUEMENT
                    vip_still_boarding = sum(1 for pass_check in self.passengers 
                                            if pass_check.is_vip and 
                                            pass_check.state in (PassengerState.VA_EMBARQUER, PassengerState.EMBARQUEMENT))
                    
                    # Les normaux n'embarquent que si aucun VIP n'embarque
                    if vip_still_boarding == 0:
                        # Compter combien de passagers normaux embarquent (2 par 2)
                        normal_in_boarding = sum(1 for pass_check in self.passengers 
                                                if not pass_check.is_vip and 
                                                pass_check.state in (PassengerState.VA_EMBARQUER, PassengerState.EMBARQUEMENT))
                        
                        # Si moins de 2 embarquent, laisser celui-ci embarquer
                        if normal_in_boarding < 2:
                            if p.current_lounge_block:
                                p.current_lounge_block.remove_passenger(p)
                                p.current_lounge_block = None
                            p.set_state(PassengerState.VA_EMBARQUER)
        
        elif p.state == PassengerState.VA_EMBARQUER:
            # Aller vers la porte (G)
            if p.near_target(self.airport.gates[0], 1.8):
                p.set_state(PassengerState.EMBARQUEMENT)
                p.boarding_timer = 0.0
        
        elif p.state == PassengerState.EMBARQUEMENT:
            # À la porte, attendre 1 seconde avant de disparaître
            p.boarding_timer += dt
            if p.boarding_timer >= 1.0:
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


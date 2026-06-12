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


# Extension IA dynamique : seuils simples et configurables
CHECKIN_SATURATION_THRESHOLD = 4
SECURITY_SATURATION_THRESHOLD = 4
MIN_TIME_BEFORE_FLIGHT_FOR_SHOPPING = 30.0
MAX_COMMERCE_WAIT_TIME = 8.0
COMMERCE_RETURN_CHECKIN = "CHECKIN"
COMMERCE_RETURN_SECURITY = "SECURITY"


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
        self.commerce_assignment_counter: int = 0  # Répartition simple dans les cases commerce
        self.current_remaining: float = 0.0
        
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
        
        # Créer les zones de check-in basées sur les positions ordonnées (du plus loin vers le plus proche)
        self.checkin_zones = [
            ServiceZone(i, f"Check-in {i+1}", position=pos, capacity=2, service_time=3.0, event_bus=self.event_bus)
            for i, pos in enumerate(self.airport.checkins_ordered)
        ]
        
        # Créer les zones de sécurité basées sur les positions ordonnées
        self.security_zones = [
            ServiceZone(i, f"Sécurité {i+1}", position=pos, capacity=2, service_time=3.0, event_bus=self.event_bus)
            for i, pos in enumerate(self.airport.secus_ordered)
        ]
        
        # Créer un bloc de lounge pour chaque case S (pas par colonne!)
        self.lounge_blocks = [
            LoungeBlock(i, position=pos, capacity=5)
            for i, pos in enumerate(self.airport.lounges_ordered)
        ]
        
        # Créer un bloc de VIP lounge pour chaque case V
        self.vip_lounge_blocks = [
            LoungeBlock(i, position=pos, capacity=5)
            for i, pos in enumerate(self.airport.vip_lounges_ordered)
        ]
        
        self.lounge_assignment_counter = 0
        self.vip_lounge_assignment_counter = 0
        self.commerce_assignment_counter = 0
        self.current_remaining = plane_depart_time
        self.score = 0
        self.nb_boarded = 0
        self.missed_passengers = 0
    
    def find_free_service_zone(self, zones):
        """
        Trouve une zone de service avec un slot libre.
        Les zones sont déjà triées du plus loin vers le plus proche.
        
        Returns:
            ServiceZone avec slot libre, ou None
        """
        for zone in zones:
            if zone.has_free_slot():
                return zone
        return None
    
    def find_free_lounge_block(self, blocks):
        """
        Trouve un bloc de lounge avec un slot libre.
        Les blocs sont déjà triés du plus loin vers le plus proche.
        
        Returns:
            LoungeBlock avec slot libre, ou None
        """
        for block in blocks:
            if block.has_free_slot():
                return block
        return None

    def _service_load(self, zones):
        """Nombre de passagers réservés/en service dans un ensemble de zones."""
        return sum(zone.size() for zone in zones)

    def _has_free_service_slot(self, zones):
        """Indique s'il reste au moins un slot réservable."""
        return any(zone.has_free_slot() for zone in zones)

    def is_checkin_saturated(self):
        """Saturation du check-in : trop de passagers ou aucun slot libre."""
        return (
            self._service_load(self.checkin_zones) >= CHECKIN_SATURATION_THRESHOLD
            or not self._has_free_service_slot(self.checkin_zones)
        )

    def is_security_saturated(self):
        """Saturation de la sécurité : trop de passagers ou aucun slot libre."""
        return (
            self._service_load(self.security_zones) >= SECURITY_SATURATION_THRESHOLD
            or not self._has_free_service_slot(self.security_zones)
        )

    def is_flight_urgent(self):
        """Retourne True quand il reste trop peu de temps pour faire un détour."""
        return self.current_remaining <= MIN_TIME_BEFORE_FLIGHT_FOR_SHOPPING

    def _should_detour_to_commerce(self, passenger, return_target):
        """Décide si un passager peut faire un détour vers le commerce."""
        if not self.airport.commerces_ordered:
            return False
        if self.is_flight_urgent():
            return False

        if return_target == COMMERCE_RETURN_CHECKIN:
            if passenger.used_commerce_for_checkin:
                return False
            return self.is_checkin_saturated()

        if return_target == COMMERCE_RETURN_SECURITY:
            if passenger.used_commerce_for_security:
                return False
            return self.is_security_saturated()

        return False

    def _assign_to_commerce(self, passenger, return_target):
        """Assigne une case commerce comme détour temporaire."""
        if not self.airport.commerces_ordered:
            return False

        cells = self.airport.commerces_ordered
        cell = cells[self.commerce_assignment_counter % len(cells)]
        offsets = [
            (-0.25, -0.25),
            (0.25, -0.25),
            (-0.25, 0.25),
            (0.25, 0.25),
            (0.0, 0.0),
        ]
        offset = offsets[self.commerce_assignment_counter % len(offsets)]
        self.commerce_assignment_counter += 1

        passenger.return_after_commerce = return_target
        passenger.commerce_timer = 0.0
        passenger.assigned_target_cell = cell
        passenger.assigned_target_pos = (cell[0] + 0.5 + offset[0], cell[1] + 0.5 + offset[1])

        if return_target == COMMERCE_RETURN_CHECKIN:
            passenger.used_commerce_for_checkin = True
        elif return_target == COMMERCE_RETURN_SECURITY:
            passenger.used_commerce_for_security = True

        passenger.set_state(PassengerState.VA_COMMERCE)
        return True

    def _commerce_can_leave(self, passenger):
        """Indique si un passager doit/quitte la zone commerce."""
        if passenger.return_after_commerce is None:
            return True
        if self.is_flight_urgent():
            return True
        if passenger.commerce_timer >= MAX_COMMERCE_WAIT_TIME:
            return True
        if passenger.return_after_commerce == COMMERCE_RETURN_CHECKIN:
            return not self.is_checkin_saturated()
        if passenger.return_after_commerce == COMMERCE_RETURN_SECURITY:
            return not self.is_security_saturated()
        return True

    def _assign_checkin_destination(self, passenger, new_state=PassengerState.VA_ENREGISTREMENT):
        """Réserve un slot check-in et définit la cible du passager."""
        checkin_zone = self.find_free_service_zone(self.checkin_zones)
        if not checkin_zone:
            return False

        slot_idx = checkin_zone.reserve_slot(passenger)
        if slot_idx is None:
            return False

        passenger.assigned_checkin_zone = checkin_zone
        passenger.assigned_checkin_slot = slot_idx
        passenger.assigned_target_cell = checkin_zone.position
        passenger.assigned_target_pos = checkin_zone.get_slot_position(slot_idx)
        passenger.return_after_commerce = None
        passenger.set_state(new_state)
        return True

    def _assign_security_destination(self, passenger, new_state=PassengerState.VA_SECURITE):
        """Réserve un slot sécurité et définit la cible du passager."""
        security_zone = self.find_free_service_zone(self.security_zones)
        if not security_zone:
            return False

        slot_idx = security_zone.reserve_slot(passenger)
        if slot_idx is None:
            return False

        passenger.assigned_security_zone = security_zone
        passenger.assigned_security_slot = slot_idx
        passenger.assigned_target_cell = security_zone.position
        passenger.assigned_target_pos = security_zone.get_slot_position(slot_idx)
        passenger.return_after_commerce = None
        passenger.set_state(new_state)
        return True

    def _assign_lounge_destination(self, passenger):
        """Réserve une place dans le lounge normal ou VIP."""
        lounge_blocks = self.vip_lounge_blocks if passenger.is_vip else self.lounge_blocks
        lounge_zone = self.find_free_lounge_block(lounge_blocks)
        if not lounge_zone:
            return False

        slot_idx = lounge_zone.reserve_slot(passenger)
        if slot_idx is None:
            return False

        passenger.assigned_lounge_block = lounge_zone
        passenger.assigned_lounge_slot = slot_idx
        passenger.assigned_target_cell = lounge_zone.position
        passenger.assigned_target_pos = lounge_zone.get_slot_position(slot_idx)
        passenger.set_state(PassengerState.VA_PORTE)
        return True
    
    def has_vip_not_finished(self):
        """
        Teste s'il reste au moins un VIP qui n'est pas encore TERMINE.
        
        Returns:
            True si un VIP est encore en route ou en service
        """
        return any(
            p.is_vip and p.state != PassengerState.TERMINE
            for p in self.passengers
        )
    
    def _start_boarding_passenger(self, p):
        """
        Lance un passager vers l'embarquement.
        
        Appelé quand le passager doit passer en VA_EMBARQUER.
        """
        # Libérer le slot lounge
        if p.assigned_lounge_block:
            p.assigned_lounge_block.release_slot(p)
            p.assigned_lounge_block = None
            p.assigned_lounge_slot = None
        
        # Réinitialiser les références de bloc courant
        if p.is_vip:
            p.current_vip_lounge_block = None
        else:
            p.current_lounge_block = None
        
        # Très important : changer la cible vers la vraie porte d'embarquement
        gate = self.airport.target_embarkation
        p.assigned_target_cell = gate
        p.assigned_target_pos = (gate[0] + 0.5, gate[1] + 0.5)
        
        p.set_state(PassengerState.VA_EMBARQUER)
    
    def _handle_boarding_priority(self):
        """
        Gère la priorité d'embarquement : VIP avant normaux.
        
        Appelée une fois par frame pour lancer les prochains passagers en embarquement.
        """
        if not self.plane or not self.plane.boarding_open:
            return
        
        # Vérifier s'il y a déjà des passagers en cours d'embarquement
        active_boarding = [
            p for p in self.passengers
            if p.state in (PassengerState.VA_EMBARQUER, PassengerState.EMBARQUEMENT)
        ]
        
        # S'il y a déjà 2 passagers en cours d'embarquement, ne pas en lancer d'autres
        if len(active_boarding) >= 2:
            return
        
        # Les VIP ont priorité
        vip_waiting = [
            p for p in self.passengers
            if p.is_vip and p.state == PassengerState.ATTEND_EMBARQUEMENT
        ]
        
        if vip_waiting:
            # Lancer les VIP qui attendent (jusqu'à 2 au total)
            slots_available = 2 - len(active_boarding)
            for p in vip_waiting[:slots_available]:
                self._start_boarding_passenger(p)
            return
        
        # S'il reste des VIP ailleurs dans le parcours, les normaux doivent attendre
        if self.has_vip_not_finished():
            return
        
        # Tous les VIP sont TERMINE : les normaux peuvent embarquer
        normal_waiting = [
            p for p in self.passengers
            if not p.is_vip and p.state == PassengerState.ATTEND_EMBARQUEMENT
        ]
        
        if normal_waiting:
            # Lancer les normaux qui attendent (jusqu'à 2 au total)
            slots_available = 2 - len(active_boarding)
            for p in normal_waiting[:slots_available]:
                self._start_boarding_passenger(p)
    
    def _update_density(self):
        """
        Met à jour la matrice de densité basée sur les passagers actuels.
        Exclut les passagers TERMINE pour qu'ils ne bloquent pas la porte.
        Doit être appelée avant le mouvement des passagers.
        """
        self.airport.densite[:, :] = 0
        
        for p in self.passengers:
            if p.state == PassengerState.TERMINE:
                continue
            
            ix, iy = int(p.x), int(p.y)
            if self.airport.walkable(ix, iy):
                self.airport.densite[ix, iy] += 1
    
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
        self.current_remaining = remaining
        
        # Spawn passagers
        self.spawner.update(dt)
        
        # Mise à jour zones check-in (distribution de file d'attente)
        all_served_checkin = []
        for zone in self.checkin_zones:
            served = zone.update(dt)
            all_served_checkin.extend(served)
        
        for p in all_served_checkin:
            # Service check-in terminé : le slot a déjà été libéré par ServiceZone.update().
            p.assigned_checkin_zone = None
            p.assigned_checkin_slot = None

            # Si la sécurité est saturée et que le temps le permet, détour commerce.
            if self._should_detour_to_commerce(p, COMMERCE_RETURN_SECURITY):
                if self._assign_to_commerce(p, COMMERCE_RETURN_SECURITY):
                    continue

            # Sinon, direction sécurité. Si aucun slot n'est libre, utiliser le commerce comme zone d'attente.
            if not self._assign_security_destination(p):
                self._assign_to_commerce(p, COMMERCE_RETURN_SECURITY)
        
        # Mise à jour zones de sécurité
        all_served_secu = []
        for zone in self.security_zones:
            served = zone.update(dt)
            all_served_secu.extend(served)
        
        for p in all_served_secu:
            # Service sécurité terminé : le slot a déjà été libéré par ServiceZone.update().
            p.assigned_security_zone = None
            p.assigned_security_slot = None

            # Le lounge est assigné uniquement APRÈS la sécurité.
            self._assign_lounge_destination(p)
        
        # Passagers à retirer
        to_remove = []
        
        # Supprimer les passagers TERMINE du jeu (d'avant cette frame)
        # CRITIQUE: Les TERMINE ne doivent pas rester pour bloquer la densité de la porte
        # IMPORTANT: Modifier la liste sur place au lieu de la réassigner!
        # Sinon le Spawner perd sa référence à la liste
        i = 0
        while i < len(self.passengers):
            if self.passengers[i].state == PassengerState.TERMINE:
                self.passengers.pop(i)
            else:
                i += 1
        
        # Mise à jour chaque passager (VIP d'abord, puis les autres)
        vip_passengers = [p for p in self.passengers if p.is_vip]
        normal_passengers = [p for p in self.passengers if not p.is_vip]
        
        # IMPORTANT: Mettre à jour la densité AVANT le mouvement
        # Sinon le pathfinding utilisera une densité obsolète
        self._update_density()
        
        for p in vip_passengers + normal_passengers:
            # Machine à états
            self._update_passenger_state(p, dt)
            
            # Mouvement
            p.move(dt, self.airport)
            
            # Patience
            p.update_patience(dt)
        
        # Gestion des priorités d'embarquement VIP vs normaux
        self._handle_boarding_priority()
        
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
        
        # Retirer les passagers manqués
        for p in to_remove:
            if p in self.passengers:
                self.passengers.remove(p)
        
        return remaining
    
    def _update_passenger_state(self, p, dt):
        """
        Met à jour l'état d'un passager (machine à états).
        
        Assigne les destinations AVANT le déplacement.
        """
        if not self.plane or not self.checkin_zones or not self.security_zones:
            return
        
        if p.state == PassengerState.ARRIVE:
            # Avant de partir au check-in, le passager peut faire un détour commerce
            # si les guichets sont saturés et si le vol n'est pas urgent.
            if self._should_detour_to_commerce(p, COMMERCE_RETURN_CHECKIN):
                self._assign_to_commerce(p, COMMERCE_RETURN_CHECKIN)
            else:
                self._assign_checkin_destination(p, PassengerState.VA_ENREGISTREMENT)

        elif p.state in (PassengerState.VA_ENREGISTREMENT, PassengerState.RETOUR_CHECKIN):
            # Se déplacer vers le check-in assigné
            if p.reached_assigned_target(radius=0.6):
                p.x, p.y = p.assigned_target_pos
                if p.assigned_checkin_zone:
                    p.assigned_checkin_zone.start_service(p)
                p.set_state(PassengerState.ATTEND_ENREGISTREMENT)

        elif p.state == PassengerState.ATTEND_ENREGISTREMENT:
            # Si le service est déjà terminé mais qu'aucune sécurité n'a pu être assignée,
            # retenter proprement. Sinon, ServiceZone.update() déclenchera la suite.
            if p.assigned_checkin_zone is None and p.assigned_security_zone is None:
                if self._should_detour_to_commerce(p, COMMERCE_RETURN_SECURITY):
                    self._assign_to_commerce(p, COMMERCE_RETURN_SECURITY)
                else:
                    self._assign_security_destination(p, PassengerState.VA_SECURITE)

        elif p.state in (PassengerState.VA_SECURITE, PassengerState.RETOUR_SECURITE):
            # Se déplacer vers la sécurité assignée
            if p.reached_assigned_target(radius=0.6):
                p.x, p.y = p.assigned_target_pos
                if p.assigned_security_zone:
                    p.assigned_security_zone.start_service(p)
                p.set_state(PassengerState.ATTEND_SECURITE)

        elif p.state == PassengerState.ATTEND_SECURITE:
            # Reste en file/service sécurité. La transition vers le lounge est déclenchée
            # par ServiceZone.update() quand le service est terminé.
            pass

        elif p.state == PassengerState.VA_COMMERCE:
            # Le pathfinding arrive dans la case commerce ; on snappe ensuite sur le slot visuel.
            if p.reached_assigned_target(radius=0.6):
                p.x, p.y = p.assigned_target_pos
                p.commerce_timer = 0.0
                p.set_state(PassengerState.ATTEND_COMMERCE)

        elif p.state == PassengerState.ATTEND_COMMERCE:
            # Attente intelligente : le passager repart si la file visée se vide,
            # si le temps presse ou si l'attente maximale est dépassée.
            p.commerce_timer += dt
            if self._commerce_can_leave(p):
                if p.return_after_commerce == COMMERCE_RETURN_CHECKIN:
                    self._assign_checkin_destination(p, PassengerState.RETOUR_CHECKIN)
                elif p.return_after_commerce == COMMERCE_RETURN_SECURITY:
                    self._assign_security_destination(p, PassengerState.RETOUR_SECURITE)

        elif p.state == PassengerState.VA_PORTE:
            # Se déplacer vers le lounge assigné
            if p.reached_assigned_target(radius=0.6):
                p.x, p.y = p.assigned_target_pos
                p.set_state(PassengerState.ATTEND_EMBARQUEMENT)

        elif p.state == PassengerState.ATTEND_EMBARQUEMENT:
            # Passager au lounge : le slot est déjà réservé.
            # Ne pas appeler add_passenger() une deuxième fois.
            if p.is_vip:
                if p.current_vip_lounge_block is None and p.assigned_lounge_block:
                    p.current_vip_lounge_block = p.assigned_lounge_block
            else:
                if p.current_lounge_block is None and p.assigned_lounge_block:
                    p.current_lounge_block = p.assigned_lounge_block

        elif p.state == PassengerState.VA_EMBARQUER:
            # Aller vers la porte d'embarquement.
            if p.reached_assigned_target(radius=0.8):
                p.x, p.y = p.assigned_target_pos
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


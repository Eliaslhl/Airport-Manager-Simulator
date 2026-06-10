"""
Système d'événements minimaliste pour découpler les composants.
"""

class EventBus:
    """Bus événementiel simple pour publier/souscrire à des événements."""
    
    def __init__(self):
        self.subscribers = {}
    
    def subscribe(self, event_type, callback):
        """S'abonner à un type d'événement."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def publish(self, event_type, data=None):
        """Publier un événement."""
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                callback(data)


# Types d'événements
class EventType:
    PASSENGER_SPAWNED = "passenger_spawned"
    PASSENGER_STATE_CHANGED = "passenger_state_changed"
    PASSENGER_SERVED = "passenger_served"
    PASSENGER_BOARDED = "passenger_boarded"
    PASSENGER_MISSED = "passenger_missed"
    PLANE_BOARDING_OPENED = "plane_boarding_opened"
    PLANE_DEPARTED = "plane_departed"
    QUEUE_UPDATED = "queue_updated"

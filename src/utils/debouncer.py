"""Centralized event system with debouncing."""

import threading
import time
from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict
from dataclasses import dataclass
from . import logger


@dataclass
class Event:
    """Event data structure."""
    type: str
    data: Dict[str, Any]
    timestamp: float


class Debouncer:
    """Centralized event bus with debouncing support."""
    
    def __init__(self, debounce_interval: float = 0.5):
        """Initialize event bus.
        
        Args:
            debounce_interval: Time to wait before processing accumulated events
        """
        self.debounce_interval = debounce_interval
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.pending_events: Dict[str, Event] = {}  # key -> latest event
        self.debounce_timers: Dict[str, threading.Timer] = {}
        self.lock = threading.RLock()
        
    def subscribe(self, event_type: str, callback: Callable[[Event], None]):
        """Subscribe to event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
        """
        with self.lock:
            self.subscribers[event_type].append(callback)
            
    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]):
        """Unsubscribe from event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: Function to remove from subscribers
        """
        with self.lock:
            if callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
                
    def emit(self, event_type: str, data: Dict[str, Any], debounce_key: Optional[str] = None):
        """Emit event with optional debouncing.
        
        Args:
            event_type: Type of event
            data: Event data
            debounce_key: Key for debouncing (if None, no debouncing)
        """
        event = Event(event_type, data, time.time())
        
        if debounce_key is None:
            # Emit immediately
            self._emit_event(event)
        else:
            # Debounce the event
            self._debounce_event(event, debounce_key)
            
    def _emit_event(self, event: Event):
        """Emit event to all subscribers.
        
        Args:
            event: Event to emit
        """
        with self.lock:
            callbacks = self.subscribers.get(event.type, [])
            
        # Call callbacks outside of lock to prevent deadlocks
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback for {event.type}: {e}")
                
    def _debounce_event(self, event: Event, debounce_key: str):
        """Debounce event by key.
        
        Args:
            event: Event to debounce
            debounce_key: Key for debouncing
        """
        with self.lock:
            # Cancel existing timer for this key
            if debounce_key in self.debounce_timers:
                self.debounce_timers[debounce_key].cancel()
                
            # Store latest event for this key
            self.pending_events[debounce_key] = event
            
            # Schedule new timer
            timer = threading.Timer(
                self.debounce_interval,
                self._process_debounced_event,
                args=[debounce_key]
            )
            self.debounce_timers[debounce_key] = timer
            timer.start()
            
    def _process_debounced_event(self, debounce_key: str):
        """Process debounced event after timeout.
        
        Args:
            debounce_key: Key of debounced event
        """
        with self.lock:
            # Get and remove pending event
            event = self.pending_events.pop(debounce_key, None)
            self.debounce_timers.pop(debounce_key, None)
            
        if event:
            self._emit_event(event)
            
    def shutdown(self):
        with self.lock:
            # Cancel all pending timers
            for timer in self.debounce_timers.values():
                timer.cancel()
            self.debounce_timers.clear()
            self.pending_events.clear()
            self.subscribers.clear()
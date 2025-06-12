"""Tests for Debouncer class."""

import threading
import time
import unittest
from unittest.mock import Mock, patch

from src.utils.debouncer import Debouncer, Event




class TestDebouncer(unittest.TestCase):
    """Test cases for Debouncer."""
    
    def setUp(self):
        """Set up test environment."""
        self.debouncer = Debouncer(debounce_interval=0.1)
        self.mock_callback = Mock()
        
    def tearDown(self):
        """Clean up test environment."""
        self.debouncer.shutdown()
        
        
    def test_subscribe_single_callback(self):
        """Test subscribing a single callback."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        self.assertIn("TEST_EVENT", self.debouncer.subscribers)
        self.assertIn(self.mock_callback, self.debouncer.subscribers["TEST_EVENT"])
        
    def test_subscribe_multiple_callbacks(self):
        """Test subscribing multiple callbacks to same event."""
        callback2 = Mock()
        
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        self.debouncer.subscribe("TEST_EVENT", callback2)
        
        self.assertEqual(len(self.debouncer.subscribers["TEST_EVENT"]), 2)
        self.assertIn(self.mock_callback, self.debouncer.subscribers["TEST_EVENT"])
        self.assertIn(callback2, self.debouncer.subscribers["TEST_EVENT"])
        
    def test_unsubscribe(self):
        """Test unsubscribing callback."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        self.debouncer.unsubscribe("TEST_EVENT", self.mock_callback)
        
        self.assertNotIn(self.mock_callback, self.debouncer.subscribers["TEST_EVENT"])
        
        
    def test_emit_immediate(self):
        """Test immediate event emission (no debouncing)."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        # Emit event without debounce_key
        self.debouncer.emit("TEST_EVENT", {"test": "data"})
        
        # Callback should be called immediately
        self.mock_callback.assert_called_once()
        event = self.mock_callback.call_args[0][0]
        self.assertEqual(event.type, "TEST_EVENT")
        self.assertEqual(event.data, {"test": "data"})
        
    def test_emit_with_invalid_data(self):
        """Test emitting events with invalid data types."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        # Test various invalid data types that should still work
        invalid_data_types = [
            None,
            [],
            123,
            "string",
            set(),
        ]
        
        for invalid_data in invalid_data_types:
            self.debouncer.emit("TEST_EVENT", invalid_data)
            
        # Should handle all data types gracefully
        self.assertEqual(self.mock_callback.call_count, len(invalid_data_types))
        
    def test_subscribe_with_invalid_callback(self):
        """Test subscribing with invalid callback types."""
        invalid_callbacks = [None, "not_callable", 123, [], {}]
        
        for invalid_callback in invalid_callbacks:
            # Should not raise exception during subscription
            self.debouncer.subscribe("TEST_EVENT", invalid_callback)
            
        # But should fail when trying to call
        self.debouncer.emit("TEST_EVENT", {"test": "data"})
        # The invalid callbacks will cause exceptions but shouldn't crash the system
        
    def test_emit_debounced_single_event(self):
        """Test debounced event emission."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        # Emit debounced event
        self.debouncer.emit("TEST_EVENT", {"test": "data"}, debounce_key="test_key")
        
        # Callback should not be called immediately
        self.mock_callback.assert_not_called()
        
        # Wait for debounce interval
        time.sleep(0.15)
        
        # Callback should now be called
        self.mock_callback.assert_called_once()
        event = self.mock_callback.call_args[0][0]
        self.assertEqual(event.type, "TEST_EVENT")
        self.assertEqual(event.data, {"test": "data"})
        
    def test_emit_debounced_multiple_events_same_key(self):
        """Test multiple debounced events with same key (should merge)."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        # Emit multiple events quickly with same debounce key
        self.debouncer.emit("TEST_EVENT", {"count": 1}, debounce_key="test_key")
        self.debouncer.emit("TEST_EVENT", {"count": 2}, debounce_key="test_key")
        self.debouncer.emit("TEST_EVENT", {"count": 3}, debounce_key="test_key")
        
        # Wait for debounce interval
        time.sleep(0.15)
        
        # Only the last event should be processed
        self.mock_callback.assert_called_once()
        event = self.mock_callback.call_args[0][0]
        self.assertEqual(event.data, {"count": 3})
        
    def test_emit_debounced_multiple_events_different_keys(self):
        """Test multiple debounced events with different keys."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        # Emit events with different debounce keys
        self.debouncer.emit("TEST_EVENT", {"key": "A"}, debounce_key="key_a")
        self.debouncer.emit("TEST_EVENT", {"key": "B"}, debounce_key="key_b")
        
        # Wait for debounce interval
        time.sleep(0.15)
        
        # Both events should be processed
        self.assertEqual(self.mock_callback.call_count, 2)
        
    def test_callback_exception_handling(self):
        """Test exception handling in callbacks."""
        # Create callback that raises exception
        def failing_callback(event):
            raise Exception("Test exception")
            
        def working_callback(event):
            working_callback.called = True
            
        working_callback.called = False
        
        self.debouncer.subscribe("TEST_EVENT", failing_callback)
        self.debouncer.subscribe("TEST_EVENT", working_callback)
        
        # Emit event
        self.debouncer.emit("TEST_EVENT", {"test": "data"})
        
        # Working callback should still be called despite exception
        self.assertTrue(working_callback.called)
        
    def test_multiple_event_types(self):
        """Test handling multiple event types."""
        callback_a = Mock()
        callback_b = Mock()
        
        self.debouncer.subscribe("EVENT_A", callback_a)
        self.debouncer.subscribe("EVENT_B", callback_b)
        
        # Emit different event types
        self.debouncer.emit("EVENT_A", {"type": "A"})
        self.debouncer.emit("EVENT_B", {"type": "B"})
        
        # Each callback should only receive its event type
        callback_a.assert_called_once()
        callback_b.assert_called_once()
        
        event_a = callback_a.call_args[0][0]
        event_b = callback_b.call_args[0][0]
        
        self.assertEqual(event_a.data, {"type": "A"})
        self.assertEqual(event_b.data, {"type": "B"})
        
    def test_debounce_timer_cancellation(self):
        """Test that previous timers are cancelled when new events arrive."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        # Emit first event
        self.debouncer.emit("TEST_EVENT", {"count": 1}, debounce_key="test_key")
        
        # Wait half the debounce interval
        time.sleep(0.05)
        
        # Emit second event (should cancel first timer)
        self.debouncer.emit("TEST_EVENT", {"count": 2}, debounce_key="test_key")
        
        # Wait for full debounce interval
        time.sleep(0.15)
        
        # Only second event should be processed
        self.mock_callback.assert_called_once()
        event = self.mock_callback.call_args[0][0]
        self.assertEqual(event.data, {"count": 2})
        
    def test_shutdown(self):
        """Test shutdown cancels all timers and clears state."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        # Emit debounced event
        self.debouncer.emit("TEST_EVENT", {"test": "data"}, debounce_key="test_key")
        
        # Verify timer was created
        self.assertEqual(len(self.debouncer.debounce_timers), 1)
        self.assertEqual(len(self.debouncer.pending_events), 1)
        
        # Shutdown
        self.debouncer.shutdown()
        
        # Verify state is cleared
        self.assertEqual(len(self.debouncer.debounce_timers), 0)
        self.assertEqual(len(self.debouncer.pending_events), 0)
        self.assertEqual(len(self.debouncer.subscribers), 0)
        
        # Wait and verify callback was not called
        time.sleep(0.15)
        self.mock_callback.assert_not_called()
        
    def test_thread_safety(self):
        """Test thread safety of debouncer operations."""
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        def emit_events():
            for i in range(10):
                self.debouncer.emit("TEST_EVENT", {"count": i}, debounce_key=f"key_{i}")
                time.sleep(0.01)
                
        # Start multiple threads emitting events
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=emit_events)
            threads.append(thread)
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Wait for all debounced events to process
        time.sleep(0.2)
        
        # Should have received events from all threads
        self.assertTrue(self.mock_callback.call_count > 0)
        
    def test_custom_debounce_interval(self):
        """Test custom debounce interval."""
        debouncer = Debouncer(debounce_interval=0.05)
        debouncer.subscribe("TEST_EVENT", self.mock_callback)
        
        try:
            # Emit debounced event
            debouncer.emit("TEST_EVENT", {"test": "data"}, debounce_key="test_key")
            
            # Wait less than default interval but more than custom interval
            time.sleep(0.08)
            
            # Callback should be called with shorter interval
            self.mock_callback.assert_called_once()
            
        finally:
            debouncer.shutdown()
            
    @patch('time.time')
    def test_event_timestamp(self, mock_time):
        """Test event timestamp is set correctly."""
        mock_time.return_value = 123.456
        
        self.debouncer.subscribe("TEST_EVENT", self.mock_callback)
        self.debouncer.emit("TEST_EVENT", {"test": "data"})
        
        # Verify timestamp
        event = self.mock_callback.call_args[0][0]
        self.assertEqual(event.timestamp, 123.456)
        
        
    def test_concurrent_subscribe_unsubscribe(self):
        """Test concurrent subscribe/unsubscribe operations."""
        def subscribe_unsubscribe():
            for i in range(10):
                callback = Mock()
                self.debouncer.subscribe("TEST_EVENT", callback)
                self.debouncer.unsubscribe("TEST_EVENT", callback)
                
        # Run concurrent operations
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=subscribe_unsubscribe)
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()
            
        # Should not raise any exceptions


if __name__ == '__main__':
    unittest.main()
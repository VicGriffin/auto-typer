"""
Abstract Event Generation Layer for Typing Simulation

This module provides an abstraction layer for emitting keyboard events with
multiple backend support, timing jitter, and drift correction.
"""

import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from enum import Enum
import queue
import random

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

try:
    import win32api
    import win32con
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


class EmitterType(Enum):
    PYAUTOGUI = "pyautogui"
    WIN32_API = "win32_api"
    SIMULATION = "simulation"  # For testing


@dataclass
class KeyEvent:
    """Represents a keyboard event to be emitted"""
    character: str
    timestamp: float  # Planned timestamp
    event_type: str = "press"  # press, release, or both
    is_correction: bool = False
    original_timestamp: float = 0.0  # For drift tracking


@dataclass
class TimingLogEntry:
    """Entry for timing drift analysis"""
    planned_time: float
    actual_start_time: float
    actual_end_time: float
    drift: float
    character: str
    success: bool


@dataclass
class EmitterConfig:
    """Configuration for event emitter"""
    emitter_type: EmitterType = EmitterType.PYAUTOGUI
    jitter_enabled: bool = True
    jitter_magnitude: float = 0.02  # 2% timing jitter
    drift_correction: bool = True
    drift_threshold: float = 0.1  # 10% drift threshold
    fallback_enabled: bool = True
    logging_enabled: bool = True
    max_retry_attempts: int = 3


class InputEmitter(ABC):
    """Abstract base class for input emitters"""
    
    @abstractmethod
    def emit_key(self, key_event: KeyEvent) -> bool:
        """Emit a key event and return success status"""
        pass
    
    @abstractmethod
    def get_actual_timestamp(self) -> float:
        """Get current high-precision timestamp"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the emitter is available"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Cleanup resources"""
        pass


class PyAutoGUIEmitter(InputEmitter):
    """PyAutoGUI-based input emitter"""
    
    def __init__(self, config: EmitterConfig):
        self.config = config
        self.timing_log: List[TimingLogEntry] = []
        self.error_log: List[Exception] = []
        
        if PYAUTOGUI_AVAILABLE:
            pyautogui.PAUSE = 0.01  # Small pause between keystrokes
            pyautogui.FAILSAFE = False  # Disable failsafe for our use case
    
    def emit_key(self, key_event: KeyEvent) -> bool:
        """Emit a key event using PyAutoGUI"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        actual_start = self.get_actual_timestamp()
        success = False
        
        try:
            if key_event.character == 'backspace':
                pyautogui.press('backspace')
            elif len(key_event.character) == 1:
                # Regular character
                pyautogui.press(key_event.character)
            else:
                # Special key
                pyautogui.press(key_event.character)
            
            actual_end = self.get_actual_timestamp()
            
            # Log timing for drift correction
            if self.config.logging_enabled:
                self.timing_log.append(TimingLogEntry(
                    planned_time=key_event.timestamp,
                    actual_start=actual_start,
                    actual_end=actual_end,
                    drift=actual_start - key_event.timestamp,
                    character=key_event.character,
                    success=True
                ))
            
            success = True
            
        except Exception as e:
            self.error_log.append(e)
            if self.config.logging_enabled:
                self.timing_log.append(TimingLogEntry(
                    planned_time=key_event.timestamp,
                    actual_start=actual_start,
                    actual_end=self.get_actual_timestamp(),
                    drift=actual_start - key_event.timestamp,
                    character=key_event.character,
                    success=False
                ))
        
        return success
    
    def get_actual_timestamp(self) -> float:
        """Get current high-precision timestamp"""
        return time.perf_counter()
    
    def is_available(self) -> bool:
        """Check if PyAutoGUI is available"""
        return PYAUTOGUI_AVAILABLE
    
    def cleanup(self):
        """Cleanup PyAutoGUI resources"""
        pass


class Win32APIEmitter(InputEmitter):
    """Win32 API-based input emitter for Windows"""
    
    def __init__(self, config: EmitterConfig):
        self.config = config
        self.timing_log: List[TimingLogEntry] = []
        self.error_log: List[Exception] = []
        
        # Key code mapping
        self.key_codes = self._build_key_map()
    
    def _build_key_map(self) -> Dict[str, int]:
        """Build mapping from characters to virtual key codes"""
        key_map = {}
        
        # Basic keys
        for i in range(26):
            key_map[chr(ord('a') + i)] = win32con.VK_A + i
            key_map[chr(ord('A') + i)] = win32con.VK_A + i
        
        for i in range(10):
            key_map[str(i)] = win32con.VK_0 + i
        
        # Special keys
        special_keys = {
            ' ': win32con.VK_SPACE,
            '\n': win32con.VK_RETURN,
            '\r': win32con.VK_RETURN,
            '\t': win32con.VK_TAB,
            '\b': win32con.VK_BACK,
            'backspace': win32con.VK_BACK,
        }
        
        key_map.update(special_keys)
        return key_map
    
    def emit_key(self, key_event: KeyEvent) -> bool:
        """Emit a key event using Win32 API"""
        if not WIN32_AVAILABLE:
            return False
        
        actual_start = self.get_actual_timestamp()
        success = False
        
        try:
            vk_code = self.key_codes.get(key_event.character)
            if vk_code is None:
                # Try to handle as printable character
                if len(key_event.character) == 1:
                    vk_code = win32api.VkKeyScan(ord(key_event.character)) & 0xFF
                else:
                    raise ValueError(f"Unknown key: {key_event.character}")
            
            # Send key down and up events
            win32api.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.01)  # Small delay
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            actual_end = self.get_actual_timestamp()
            
            # Log timing
            if self.config.logging_enabled:
                self.timing_log.append(TimingLogEntry(
                    planned_time=key_event.timestamp,
                    actual_start=actual_start,
                    actual_end=actual_end,
                    drift=actual_start - key_event.timestamp,
                    character=key_event.character,
                    success=True
                ))
            
            success = True
            
        except Exception as e:
            self.error_log.append(e)
            if self.config.logging_enabled:
                self.timing_log.append(TimingLogEntry(
                    planned_time=key_event.timestamp,
                    actual_start=actual_start,
                    actual_end=self.get_actual_timestamp(),
                    drift=actual_start - key_event.timestamp,
                    character=key_event.character,
                    success=False
                ))
        
        return success
    
    def get_actual_timestamp(self) -> float:
        """Get current high-precision timestamp"""
        return time.perf_counter()
    
    def is_available(self) -> bool:
        """Check if Win32 API is available"""
        return WIN32_AVAILABLE
    
    def cleanup(self):
        """Cleanup Win32 API resources"""
        pass


class SimulationEmitter(InputEmitter):
    """Simulation emitter for testing and development"""
    
    def __init__(self, config: EmitterConfig):
        self.config = config
        self.timing_log: List[TimingLogEntry] = []
        self.error_log: List[Exception] = []
        self.emitted_events: List[KeyEvent] = []
    
    def emit_key(self, key_event: KeyEvent) -> bool:
        """Simulate emitting a key event"""
        actual_start = self.get_actual_timestamp()
        
        # Simulate processing time
        processing_time = random.uniform(0.001, 0.01)
        time.sleep(processing_time)
        
        actual_end = self.get_actual_timestamp()
        
        # Log timing
        if self.config.logging_enabled:
            self.timing_log.append(TimingLogEntry(
                planned_time=key_event.timestamp,
                actual_start=actual_start,
                actual_end=actual_end,
                drift=actual_start - key_event.timestamp,
                character=key_event.character,
                success=True
            ))
        
        self.emitted_events.append(key_event)
        return True
    
    def get_actual_timestamp(self) -> float:
        """Get current high-precision timestamp"""
        return time.perf_counter()
    
    def is_available(self) -> bool:
        """Simulation emitter is always available"""
        return True
    
    def cleanup(self):
        """Cleanup simulation resources"""
        pass


class EventScheduler:
    """Schedules and manages event emission with timing correction"""
    
    def __init__(self, emitter: InputEmitter, config: EmitterConfig):
        self.emitter = emitter
        self.config = config
        self.event_queue = queue.Queue()
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        
        # Timing correction state
        self.cumulative_drift = 0.0
        self.drift_history: List[float] = []
        self.correction_factor = 1.0
    
    def schedule_events(self, events: List[KeyEvent]) -> bool:
        """Schedule a list of events for emission"""
        if not self.emitter.is_available():
            return False
        
        # Add events to queue
        for event in events:
            self.event_queue.put(event)
        
        return True
    
    def start_execution(self) -> bool:
        """Start executing scheduled events"""
        if self.is_running:
            return False
        
        if not self.emitter.is_available():
            return False
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._execute_events)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        return True
    
    def stop_execution(self):
        """Stop event execution"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1.0)
    
    def _execute_events(self):
        """Execute events with timing correction"""
        start_time = self.get_actual_timestamp()
        
        while self.is_running and not self.event_queue.empty():
            try:
                # Get next event
                event = self.event_queue.get(timeout=0.1)
                
                # Calculate target time
                target_time = start_time + event.timestamp
                
                # Wait until target time with jitter
                current_time = self.get_actual_timestamp()
                wait_time = target_time - current_time
                
                if wait_time > 0:
                    # Apply jitter if enabled
                    if self.config.jitter_enabled:
                        jitter = random.gauss(1.0, self.config.jitter_magnitude)
                        wait_time *= jitter
                    
                    time.sleep(max(0, wait_time))
                
                # Apply drift correction if enabled
                if self.config.drift_correction:
                    self._apply_drift_correction()
                
                # Emit event with retry logic
                success = self._emit_with_retry(event)
                
                # Update drift tracking
                if self.config.logging_enabled:
                    self._update_drift_tracking(event, success)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error executing event: {e}")
        
        self.is_running = False
    
    def _emit_with_retry(self, event: KeyEvent) -> bool:
        """Emit event with retry logic"""
        for attempt in range(self.config.max_retry_attempts):
            if self.emitter.emit_key(event):
                return True
            
            # Wait before retry
            time.sleep(0.01)
        
        return False
    
    def _apply_drift_correction(self):
        """Apply drift correction to timing"""
        if len(self.drift_history) < 5:
            return
        
        # Calculate average recent drift
        recent_drift = self.drift_history[-5:]
        avg_drift = sum(recent_drift) / len(recent_drift)
        
        # Apply correction if drift exceeds threshold
        if abs(avg_drift) > self.config.drift_threshold:
            # Gradually adjust correction factor
            adjustment = 1.0 - (avg_drift * 0.1)
            self.correction_factor *= adjustment
            self.correction_factor = max(0.5, min(1.5, self.correction_factor))
    
    def _update_drift_tracking(self, event: KeyEvent, success: bool):
        """Update drift tracking metrics"""
        if hasattr(self.emitter, 'timing_log') and self.emitter.timing_log:
            latest_log = self.emitter.timing_log[-1]
            if latest_log.character == event.character:
                self.drift_history.append(latest_log.drift)
                
                # Keep only recent history
                if len(self.drift_history) > 100:
                    self.drift_history = self.drift_history[-100:]
    
    def get_actual_timestamp(self) -> float:
        """Get current timestamp"""
        return time.perf_counter()
    
    def get_execution_statistics(self) -> Dict:
        """Get execution statistics"""
        stats = {
            'events_queued': self.event_queue.qsize(),
            'is_running': self.is_running,
            'cumulative_drift': self.cumulative_drift,
            'correction_factor': self.correction_factor,
            'drift_samples': len(self.drift_history)
        }
        
        if hasattr(self.emitter, 'timing_log'):
            stats.update({
                'events_emitted': len(self.emitter.timing_log),
                'successful_events': sum(1 for log in self.emitter.timing_log if log.success),
                'failed_events': sum(1 for log in self.emitter.timing_log if not log.success),
                'avg_drift': sum(log.drift for log in self.emitter.timing_log) / len(self.emitter.timing_log) if self.emitter.timing_log else 0,
            })
        
        return stats


class EmitterFactory:
    """Factory for creating input emitters"""
    
    @staticmethod
    def create_emitter(emitter_type: EmitterType, config: EmitterConfig) -> InputEmitter:
        """Create an emitter of the specified type"""
        if emitter_type == EmitterType.PYAUTOGUI:
            return PyAutoGUIEmitter(config)
        elif emitter_type == EmitterType.WIN32_API:
            return Win32APIEmitter(config)
        elif emitter_type == EmitterType.SIMULATION:
            return SimulationEmitter(config)
        else:
            raise ValueError(f"Unknown emitter type: {emitter_type}")
    
    @staticmethod
    def get_available_emitters() -> List[EmitterType]:
        """Get list of available emitter types"""
        available = [EmitterType.SIMULATION]  # Always available
        
        if PYAUTOGUI_AVAILABLE:
            available.append(EmitterType.PYAUTOGUI)
        
        if WIN32_AVAILABLE:
            available.append(EmitterType.WIN32_API)
        
        return available


# Example usage and testing
if __name__ == "__main__":
    # Create configuration
    config = EmitterConfig(
        emitter_type=EmitterType.SIMULATION,
        jitter_enabled=True,
        drift_correction=True,
        logging_enabled=True
    )
    
    # Create emitter
    emitter = EmitterFactory.create_emitter(EmitterType.SIMULATION, config)
    
    # Create scheduler
    scheduler = EventScheduler(emitter, config)
    
    # Create test events
    events = [
        KeyEvent(character='H', timestamp=0.0),
        KeyEvent(character='e', timestamp=0.1),
        KeyEvent(character='l', timestamp=0.2),
        KeyEvent(character='l', timestamp=0.3),
        KeyEvent(character='o', timestamp=0.4),
        KeyEvent(character=' ', timestamp=0.5),
        KeyEvent(character='W', timestamp=0.6),
        KeyEvent(character='o', timestamp=0.7),
        KeyEvent(character='r', timestamp=0.8),
        KeyEvent(character='l', timestamp=0.9),
        KeyEvent(character='d', timestamp=1.0),
    ]
    
    # Schedule and execute
    print("Starting event execution...")
    scheduler.schedule_events(events)
    scheduler.start_execution()
    
    # Wait for completion
    scheduler.scheduler_thread.join()
    
    # Show statistics
    stats = scheduler.get_execution_statistics()
    print("\nExecution Statistics:")
    print("-" * 40)
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Show timing log
    if hasattr(emitter, 'timing_log') and emitter.timing_log:
        print("\nTiming Log (first 5 events):")
        print("-" * 50)
        for log in emitter.timing_log[:5]:
            print(f"'{log.character}': planned={log.planned_time:.3f}s "
                  f"actual={log.actual_start:.3f}s drift={log.drift:.3f}s")

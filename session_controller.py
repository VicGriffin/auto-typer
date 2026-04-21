"""
Session Controller - Main Orchestrator for Typing Simulation

This module coordinates all components and manages the complete typing session
with variability, state evolution, and real-time correction.
"""

import time
import threading
import uuid
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Any
from enum import Enum
import random
from pathlib import Path

from text_processor import TextProcessor, TextAnalysis
from keyboard_model import KeyboardModel
from timing_model import NonStationaryTimingModel, TimingEvent
from error_model import RealisticErrorModel, ErrorEvent
from input_emitter import EventScheduler, InputEmitter, KeyEvent, EmitterType
from behavior_profiles import BehaviorProfile, ProfileManager
from observability import SessionMetrics, MetricsCollector, TimelineVisualizer, DiagnosticLogger


class SessionState(Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    COUNTDOWN = "countdown"
    TYPING = "typing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class SessionConfig:
    """Configuration for a typing session"""
    text: str
    profile_name: str
    target_duration: float
    countdown_duration: float = 3.0
    press_enter_after: bool = True
    deterministic: bool = False
    random_seed: Optional[int] = None
    enable_observability: bool = True
    save_timeline: bool = True
    save_metrics: bool = True


@dataclass
class SessionResult:
    """Results of a completed typing session"""
    session_id: str
    success: bool
    start_time: float
    end_time: float
    total_duration: float
    characters_typed: int
    errors: List[ErrorEvent]
    metrics: SessionMetrics
    timeline_events: List
    error_message: Optional[str] = None


class SessionController:
    """Main controller for typing sessions"""
    
    def __init__(self):
        # Core components
        self.text_processor = TextProcessor()
        self.keyboard_model = KeyboardModel()
        self.profile_manager = ProfileManager()
        self.metrics_collector = MetricsCollector()
        self.diagnostic_logger = DiagnosticLogger()
        self.timeline_visualizer = TimelineVisualizer()
        
        # Session state
        self.current_session_id: Optional[str] = None
        self.session_state: SessionState = SessionState.IDLE
        self.session_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Callbacks for UI updates
        self.status_callback: Optional[Callable[[str, str], None]] = None
        self.progress_callback: Optional[Callable[[float], None]] = None
        self.metrics_callback: Optional[Callable[[Dict], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        
        # Session results
        self.last_result: Optional[SessionResult] = None
    
    def set_callbacks(self, status: Callable = None, progress: Callable = None, 
                     metrics: Callable = None, error: Callable = None):
        """Set callback functions for UI updates"""
        self.status_callback = status
        self.progress_callback = progress
        self.metrics_callback = metrics
        self.error_callback = error
    
    def start_session(self, config: SessionConfig) -> str:
        """Start a new typing session"""
        if self.session_state != SessionState.IDLE:
            raise RuntimeError("Session already in progress")
        
        # Validate configuration
        profile = self.profile_manager.get_profile(config.profile_name)
        if not profile:
            raise ValueError(f"Unknown profile: {config.profile_name}")
        
        # Set random seed if specified
        if config.deterministic and config.random_seed is not None:
            random.seed(config.random_seed)
            np.random.seed(config.random_seed)
        
        # Generate session ID
        self.current_session_id = str(uuid.uuid4())
        self.session_state = SessionState.PREPARING
        self.stop_event.clear()
        
        # Start session in separate thread
        self.session_thread = threading.Thread(
            target=self._execute_session,
            args=(config, profile),
            daemon=True
        )
        self.session_thread.start()
        
        return self.current_session_id
    
    def stop_session(self):
        """Stop the current session"""
        if self.session_state in [SessionState.TYPING, SessionState.COUNTDOWN]:
            self.stop_event.set()
            self.session_state = SessionState.PAUSED
            
            if self.status_callback:
                self.status_callback("Stopping session...", "paused")
    
    def _execute_session(self, config: SessionConfig, profile: BehaviorProfile):
        """Execute the typing session"""
        start_time = time.time()
        
        try:
            # Update status
            self._update_status("Preparing session...", "preparing")
            
            # Parse text
            text_analysis = self.text_processor.parse_text(config.text)
            
            # Start diagnostic logging
            if config.enable_observability:
                self.diagnostic_logger.start_session(
                    self.current_session_id,
                    config.profile_name,
                    config.text
                )
            
            # Generate timing schedule
            self._update_status("Generating timing schedule...", "preparing")
            timing_model = NonStationaryTimingModel(self.keyboard_model, profile.timing_profile)
            timing_events = timing_model.generate_timing_schedule(
                text_analysis.chunks,
                config.target_duration
            )
            
            # Add errors to schedule
            self._update_status("Adding realistic errors...", "preparing")
            error_model = RealisticErrorModel(self.keyboard_model, profile.error_profile)
            enhanced_events = error_model.enhance_timing_schedule(timing_events, profile)
            
            # Convert to key events
            key_events = self._convert_to_key_events(enhanced_events)
            
            # Countdown
            self._execute_countdown(config.countdown_duration)
            
            if self.stop_event.is_set():
                return self._create_stopped_result(start_time, profile)
            
            # Create input emitter
            emitter = self._create_emitter(profile.emitter_config)
            scheduler = EventScheduler(emitter, profile.emitter_config)
            
            # Schedule events
            self._update_status("Starting typing...", "typing")
            scheduler.schedule_events(key_events)
            
            # Start execution with monitoring
            self._execute_with_monitoring(scheduler, config, profile, start_time, text_analysis)
            
        except Exception as e:
            self._handle_error(e, start_time, profile)
        finally:
            self.session_state = SessionState.IDLE
    
    def _execute_countdown(self, duration: float):
        """Execute countdown before typing"""
        self.session_state = SessionState.COUNTDOWN
        
        for remaining in range(int(duration), 0, -1):
            if self.stop_event.is_set():
                return
            
            self._update_status(f"Starting in {remaining}...", "countdown")
            
            # Update progress
            progress = 1.0 - (remaining / duration)
            if self.progress_callback:
                self.progress_callback(progress * 0.1)  # First 10% of progress
            
            time.sleep(1)
    
    def _execute_with_monitoring(self, scheduler: EventScheduler, config: SessionConfig, 
                               profile: BehaviorProfile, start_time: float, 
                               text_analysis: TextAnalysis):
        """Execute typing with real-time monitoring"""
        self.session_state = SessionState.TYPING
        
        # Start scheduler
        scheduler.start_execution()
        
        # Monitor progress
        last_progress_update = 0
        monitoring_interval = 0.5  # Update every 500ms
        
        while scheduler.is_running and not self.stop_event.is_set():
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Update progress
            if elapsed - last_progress_update > monitoring_interval:
                progress = min(0.95, elapsed / config.target_duration)
                if self.progress_callback:
                    self.progress_callback(0.1 + progress * 0.85)  # 10-95% progress
                
                # Update metrics
                stats = scheduler.get_execution_statistics()
                if self.metrics_callback:
                    self.metrics_callback(stats)
                
                last_progress_update = elapsed
            
            time.sleep(0.1)
        
        # Wait for completion
        if scheduler.scheduler_thread:
            scheduler.scheduler_thread.join(timeout=1.0)
        
        # Create final result
        end_time = time.time()
        
        # Collect timing log
        timing_log = []
        if hasattr(scheduler.emitter, 'timing_log'):
            timing_log = scheduler.emitter.timing_log
        
        # Collect error events
        error_events = []
        if hasattr(scheduler.emitter, 'error_log'):
            # Convert error log to ErrorEvent objects (simplified)
            pass
        
        # Calculate metrics
        if timing_log:
            # Reconstruct events for metrics calculation
            events = self._reconstruct_events_from_log(timing_log)
            metrics = self.metrics_collector.calculate_metrics(
                events, timing_log, error_events, config.target_duration
            )
        else:
            metrics = SessionMetrics(
                total_duration=end_time - start_time,
                characters_typed=len(config.text),
                words_typed=len(config.text.split()),
                target_wpm=profile.target_wpm,
                actual_wpm=0,
                mean_inter_key_delay=0,
                std_inter_key_delay=0,
                cv_inter_key_delay=0,
                pause_count=0,
                total_pause_time=0,
                burst_count=0,
                avg_burst_duration=0,
                total_errors=0,
                error_rate=0,
                correction_rate=0,
                avg_correction_delay=0,
                error_type_distribution={},
                mean_drift=0,
                max_drift=0,
                drift_std=0,
                timing_accuracy=0,
                rhythm_regularity=0,
                session_consistency=0,
                typing_efficiency=0,
                fatigue_impact=0,
                learning_curve=0
            )
        
        # Create result
        self.last_result = SessionResult(
            session_id=self.current_session_id,
            success=not self.stop_event.is_set(),
            start_time=start_time,
            end_time=end_time,
            total_duration=end_time - start_time,
            characters_typed=metrics.characters_typed,
            errors=error_events,
            metrics=metrics,
            timeline_events=[],  # Would be populated from timeline
            error_message=None if not self.stop_event.is_set() else "Session stopped by user"
        )
        
        # Save results
        if config.enable_observability:
            self._save_session_results(config, profile, text_analysis)
        
        # Update final status
        if self.stop_event.is_set():
            self._update_status("Session stopped", "stopped")
        else:
            self._update_status("Session completed", "completed")
            if self.progress_callback:
                self.progress_callback(1.0)  # 100% progress
    
    def _convert_to_key_events(self, timing_events: List[TimingEvent]) -> List[KeyEvent]:
        """Convert timing events to key events"""
        key_events = []
        
        for event in timing_events:
            key_event = KeyEvent(
                character=event.character,
                timestamp=event.timestamp,
                event_type="press",
                is_correction=getattr(event.context, 'is_error', False)
            )
            key_events.append(key_event)
        
        return key_events
    
    def _create_emitter(self, config):
        """Create input emitter based on configuration"""
        from input_emitter import EmitterFactory
        
        emitter = EmitterFactory.create_emitter(config.emitter_type, config)
        return emitter
    
    def _reconstruct_events_from_log(self, timing_log):
        """Reconstruct timing events from timing log"""
        # Simplified reconstruction
        events = []
        for i, log in enumerate(timing_log):
            event = TimingEvent(
                character=log.character,
                timestamp=log.planned_time,
                delay=log.actual_end - log.actual_start,
                context=None,  # Simplified
                mode="normal"
            )
            events.append(event)
        return events
    
    def _save_session_results(self, config: SessionConfig, profile: BehaviorProfile, 
                            text_analysis: TextAnalysis):
        """Save session results and observability data"""
        if not self.last_result:
            return
        
        # Create session directory
        session_dir = Path("sessions") / self.current_session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metrics
        if config.save_metrics:
            metrics_file = session_dir / "metrics.json"
            self.metrics_collector.export_metrics_json(self.last_result.metrics, metrics_file)
            
            metrics_csv = session_dir / "metrics.csv"
            self.metrics_collector.export_metrics_csv(self.last_result.metrics, metrics_csv)
        
        # Save session info
        session_info = {
            "session_id": self.current_session_id,
            "profile": config.profile_name,
            "target_duration": config.target_duration,
            "actual_duration": self.last_result.total_duration,
            "success": self.last_result.success,
            "text_length": len(config.text),
            "characters_typed": self.last_result.characters_typed,
            "target_wpm": profile.target_wpm,
            "actual_wpm": self.last_result.metrics.actual_wpm
        }
        
        info_file = session_dir / "session_info.json"
        with open(info_file, 'w') as f:
            import json
            json.dump(session_info, f, indent=2)
    
    def _create_stopped_result(self, start_time: float, profile: BehaviorProfile) -> SessionResult:
        """Create result for stopped session"""
        end_time = time.time()
        
        return SessionResult(
            session_id=self.current_session_id,
            success=False,
            start_time=start_time,
            end_time=end_time,
            total_duration=end_time - start_time,
            characters_typed=0,
            errors=[],
            metrics=SessionMetrics(
                total_duration=end_time - start_time,
                characters_typed=0,
                words_typed=0,
                target_wpm=profile.target_wpm,
                actual_wpm=0,
                mean_inter_key_delay=0,
                std_inter_key_delay=0,
                cv_inter_key_delay=0,
                pause_count=0,
                total_pause_time=0,
                burst_count=0,
                avg_burst_duration=0,
                total_errors=0,
                error_rate=0,
                correction_rate=0,
                avg_correction_delay=0,
                error_type_distribution={},
                mean_drift=0,
                max_drift=0,
                drift_std=0,
                timing_accuracy=0,
                rhythm_regularity=0,
                session_consistency=0,
                typing_efficiency=0,
                fatigue_impact=0,
                learning_curve=0
            ),
            timeline_events=[],
            error_message="Session stopped by user"
        )
    
    def _handle_error(self, error: Exception, start_time: float, profile: BehaviorProfile):
        """Handle session error"""
        end_time = time.time()
        
        self.last_result = SessionResult(
            session_id=self.current_session_id,
            success=False,
            start_time=start_time,
            end_time=end_time,
            total_duration=end_time - start_time,
            characters_typed=0,
            errors=[],
            metrics=SessionMetrics(
                total_duration=end_time - start_time,
                characters_typed=0,
                words_typed=0,
                target_wpm=profile.target_wpm,
                actual_wpm=0,
                mean_inter_key_delay=0,
                std_inter_key_delay=0,
                cv_inter_key_delay=0,
                pause_count=0,
                total_pause_time=0,
                burst_count=0,
                avg_burst_duration=0,
                total_errors=0,
                error_rate=0,
                correction_rate=0,
                avg_correction_delay=0,
                error_type_distribution={},
                mean_drift=0,
                max_drift=0,
                drift_std=0,
                timing_accuracy=0,
                rhythm_regularity=0,
                session_consistency=0,
                typing_efficiency=0,
                fatigue_impact=0,
                learning_curve=0
            ),
            timeline_events=[],
            error_message=str(error)
        )
        
        self.session_state = SessionState.ERROR
        
        if self.error_callback:
            self.error_callback(str(error))
        
        if self.status_callback:
            self.status_callback(f"Error: {error}", "error")
    
    def _update_status(self, message: str, state: str):
        """Update status via callback"""
        self.session_state = SessionState(state)
        
        if self.status_callback:
            self.status_callback(message, state)
    
    def get_available_profiles(self) -> Dict[str, BehaviorProfile]:
        """Get all available behavior profiles"""
        return self.profile_manager.get_all_profiles()
    
    def get_session_result(self) -> Optional[SessionResult]:
        """Get the last session result"""
        return self.last_result
    
    def is_session_active(self) -> bool:
        """Check if a session is currently active"""
        return self.session_state in [SessionState.PREPARING, SessionState.COUNTDOWN, SessionState.TYPING]


# Example usage and testing
if __name__ == "__main__":
    # Create session controller
    controller = SessionController()
    
    # Set callbacks
    def on_status(message, state):
        print(f"[{state.upper()}] {message}")
    
    def on_progress(progress):
        print(f"Progress: {progress:.1%}")
    
    def on_metrics(metrics):
        print(f"Metrics: {metrics.get('events_emitted', 0)} events emitted")
    
    controller.set_callbacks(
        status=on_status,
        progress=on_progress,
        metrics=on_metrics
    )
    
    # Create session config
    config = SessionConfig(
        text="The quick brown fox jumps over the lazy dog. This is a test of the session controller.",
        profile_name="bursty",
        target_duration=15.0,
        countdown_duration=3.0,
        enable_observability=True
    )
    
    # Start session
    print("Starting session...")
    session_id = controller.start_session(config)
    print(f"Session ID: {session_id}")
    
    # Wait for completion
    while controller.is_session_active():
        time.sleep(0.1)
    
    # Get results
    result = controller.get_session_result()
    if result:
        print(f"\nSession Results:")
        print(f"Success: {result.success}")
        print(f"Duration: {result.total_duration:.2f}s")
        print(f"Characters: {result.characters_typed}")
        print(f"Actual WPM: {result.metrics.actual_wpm:.1f}")
        print(f"Error Rate: {result.metrics.error_rate:.3f}")
        print(f"Timing Accuracy: {result.metrics.timing_accuracy:.3f}")
        
        if result.error_message:
            print(f"Error: {result.error_message}")

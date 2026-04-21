"""
Observability and Diagnostic Tools for Typing Simulation

This module provides comprehensive monitoring, visualization, and analysis
capabilities for typing sessions with detailed metrics and timeline tracking.
"""

import time
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import statistics
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import csv

from timing_model import TimingEvent, TimingMode
from error_model import ErrorEvent
from input_emitter import TimingLogEntry


class MetricType(Enum):
    TIMING = "timing"
    ERRORS = "errors"
    PERFORMANCE = "performance"
    DRIFT = "drift"
    RHYTHM = "rhythm"


@dataclass
class SessionMetrics:
    """Comprehensive metrics for a typing session"""
    # Basic metrics
    total_duration: float
    characters_typed: int
    words_typed: int
    target_wpm: float
    actual_wpm: float
    
    # Timing metrics
    mean_inter_key_delay: float
    std_inter_key_delay: float
    cv_inter_key_delay: float  # Coefficient of variation
    pause_count: int
    total_pause_time: float
    burst_count: int
    avg_burst_duration: float
    
    # Error metrics
    total_errors: int
    error_rate: float
    correction_rate: float
    avg_correction_delay: float
    error_type_distribution: Dict[str, float]
    
    # Drift and performance
    mean_drift: float
    max_drift: float
    drift_std: float
    timing_accuracy: float  # Percentage of events within threshold
    
    # Rhythm and variability
    rhythm_regularity: float  # 0-1, higher = more regular
    session_consistency: float  # How consistent timing was throughout
    
    # Advanced metrics
    typing_efficiency: float  # Characters per second vs theoretical maximum
    fatigue_impact: float  # How much fatigue affected performance
    learning_curve: float  # Improvement/degradation over time


@dataclass
class TimelineEvent:
    """Event for timeline visualization"""
    timestamp: float
    event_type: str  # character, pause, error, correction
    character: str
    planned_delay: float
    actual_delay: float
    drift: float
    is_error: bool = False
    mode: str = "normal"


class TimelineVisualizer:
    """Creates visual representations of typing sessions"""
    
    def __init__(self):
        self.fig_size = (12, 8)
        self.colors = {
            'normal': '#2E86AB',
            'burst': '#A23B72',
            'pause': '#F18F01',
            'error': '#C73E1D',
            'correction': '#6A994E',
            'drift': '#8B5A3C'
        }
    
    def generate_timeline(self, events: List[TimingEvent], 
                         timing_log: List[TimingLogEntry]) -> List[TimelineEvent]:
        """Generate timeline data from events and logs"""
        timeline = []
        
        for i, event in enumerate(events):
            # Find corresponding timing log entry
            log_entry = None
            if i < len(timing_log):
                log_entry = timing_log[i]
            
            actual_delay = log_entry.actual_end - log_entry.actual_start if log_entry else event.delay
            drift = log_entry.drift if log_entry else 0.0
            
            timeline_event = TimelineEvent(
                timestamp=event.timestamp,
                event_type="character",
                character=event.character,
                planned_delay=event.delay,
                actual_delay=actual_delay,
                drift=drift,
                is_error=getattr(event.context, 'is_error', False),
                mode=event.mode.value
            )
            
            timeline.append(timeline_event)
        
        return timeline
    
    def create_timing_plot(self, timeline: List[TimelineEvent], 
                          save_path: Optional[Path] = None) -> str:
        """Create timing visualization plot"""
        fig, axes = plt.subplots(3, 1, figsize=self.fig_size)
        
        timestamps = [e.timestamp for e in timeline]
        delays = [e.actual_delay * 1000 for e in timeline]  # Convert to ms
        drifts = [e.drift * 1000 for e in timeline]  # Convert to ms
        
        # Plot 1: Inter-key delays over time
        axes[0].plot(timestamps, delays, alpha=0.7, color=self.colors['normal'])
        axes[0].set_ylabel('Delay (ms)')
        axes[0].set_title('Inter-key Delays Over Time')
        axes[0].grid(True, alpha=0.3)
        
        # Add mode coloring
        for i, event in enumerate(timeline):
            if event.mode == 'burst':
                axes[0].scatter(event.timestamp, delays[i], 
                              color=self.colors['burst'], s=20, alpha=0.8)
            elif event.mode == 'pause':
                axes[0].scatter(event.timestamp, delays[i], 
                              color=self.colors['pause'], s=20, alpha=0.8)
        
        # Plot 2: Drift over time
        axes[1].plot(timestamps, drifts, color=self.colors['drift'], alpha=0.7)
        axes[1].axhline(y=0, color='red', linestyle='--', alpha=0.5)
        axes[1].set_ylabel('Drift (ms)')
        axes[1].set_title('Timing Drift Over Time')
        axes[1].grid(True, alpha=0.3)
        
        # Plot 3: Delay distribution
        axes[2].hist(delays, bins=30, alpha=0.7, color=self.colors['normal'], edgecolor='black')
        axes[2].set_xlabel('Delay (ms)')
        axes[2].set_ylabel('Frequency')
        axes[2].set_title('Delay Distribution')
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            return str(save_path)
        else:
            # Save to temporary file
            temp_path = Path("timing_plot.png")
            plt.savefig(temp_path, dpi=150, bbox_inches='tight')
            plt.close()
            return str(temp_path)
    
    def create_rhythm_plot(self, timeline: List[TimelineEvent], 
                          save_path: Optional[Path] = None) -> str:
        """Create rhythm analysis plot"""
        fig, axes = plt.subplots(2, 2, figsize=self.fig_size)
        
        # Extract delays and calculate rhythm metrics
        delays = [e.actual_delay for e in timeline]
        
        # Plot 1: Rhythm heatmap (delays over time)
        window_size = 20
        rhythm_matrix = []
        for i in range(0, len(delays), window_size):
            window = delays[i:i+window_size]
            if len(window) < window_size:
                window.extend([0] * (window_size - len(window)))
            rhythm_matrix.append(window)
        
        if rhythm_matrix:
            im = axes[0, 0].imshow(rhythm_matrix, cmap='viridis', aspect='auto')
            axes[0, 0].set_title('Rhythm Heatmap')
            axes[0, 0].set_xlabel('Position in Window')
            axes[0, 0].set_ylabel('Time Window')
            plt.colorbar(im, ax=axes[0, 0])
        
        # Plot 2: Autocorrelation
        if len(delays) > 10:
            autocorr = [np.corrcoef(delays[:-i], delays[i:])[0, 1] for i in range(1, min(20, len(delays)//2))]
            axes[0, 1].plot(range(1, len(autocorr) + 1), autocorr)
            axes[0, 1].set_title('Delay Autocorrelation')
            axes[0, 1].set_xlabel('Lag')
            axes[0, 1].set_ylabel('Correlation')
            axes[0, 1].grid(True, alpha=0.3)
        
        # Plot 3: Moving average
        if len(delays) > 5:
            window = min(10, len(delays) // 4)
            moving_avg = [np.mean(delays[max(0, i-window):i+window]) for i in range(len(delays))]
            axes[1, 0].plot([e.timestamp for e in timeline], moving_avg, color=self.colors['normal'])
            axes[1, 0].set_title('Moving Average of Delays')
            axes[1, 0].set_ylabel('Average Delay (s)')
            axes[1, 0].grid(True, alpha=0.3)
        
        # Plot 4: Variance over time
        variance_window = 20
        variances = []
        for i in range(len(delays)):
            window = delays[max(0, i-variance_window):i+variance_window]
            if len(window) > 1:
                variances.append(np.var(window))
            else:
                variances.append(0)
        
        axes[1, 1].plot([e.timestamp for e in timeline], variances, color=self.colors['burst'])
        axes[1, 1].set_title('Local Variance Over Time')
        axes[1, 1].set_ylabel('Variance')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            return str(save_path)
        else:
            temp_path = Path("rhythm_plot.png")
            plt.savefig(temp_path, dpi=150, bbox_inches='tight')
            plt.close()
            return str(temp_path)


class MetricsCollector:
    """Collects and analyzes metrics from typing sessions"""
    
    def __init__(self):
        self.session_history: List[SessionMetrics] = []
    
    def calculate_metrics(self, events: List[TimingEvent], 
                          timing_log: List[TimingLogEntry],
                          error_events: List[ErrorEvent],
                          target_duration: float) -> SessionMetrics:
        """Calculate comprehensive session metrics"""
        
        # Basic metrics
        total_duration = events[-1].timestamp - events[0].timestamp if events else 0
        characters_typed = len([e for e in events if not e.character.isspace()])
        words_typed = len(''.join([e.character for e in events if not e.character.isspace()]).split())
        target_wpm = (characters_typed / 5) / (target_duration / 60) if target_duration > 0 else 0
        actual_wpm = (characters_typed / 5) / (total_duration / 60) if total_duration > 0 else 0
        
        # Timing metrics
        delays = [e.delay for e in events]
        mean_delay = statistics.mean(delays) if delays else 0
        std_delay = statistics.stdev(delays) if len(delays) > 1 else 0
        cv_delay = std_delay / mean_delay if mean_delay > 0 else 0
        
        # Pause and burst analysis
        pause_events = [e for e in events if e.mode == TimingMode.PAUSE]
        burst_events = [e for e in events if e.mode == TimingMode.BURST]
        
        pause_count = len(pause_events)
        total_pause_time = sum(e.delay for e in pause_events)
        burst_count = len(burst_events)
        avg_burst_duration = self._calculate_avg_burst_duration(events) if burst_events else 0
        
        # Error metrics
        total_errors = len(error_events)
        error_rate = total_errors / max(1, characters_typed)
        correction_rate = len([e for e in error_events if e.backspace_count > 0]) / max(1, total_errors)
        avg_correction_delay = statistics.mean([e.correction_delay for e in error_events]) if error_events else 0
        
        error_type_dist = {}
        for error in error_events:
            error_type = error.error_type.value
            error_type_dist[error_type] = error_type_dist.get(error_type, 0) + 1
        
        # Normalize error type distribution
        if total_errors > 0:
            error_type_dist = {k: v/total_errors for k, v in error_type_dist.items()}
        
        # Drift metrics
        drifts = [log.drift for log in timing_log]
        mean_drift = statistics.mean(drifts) if drifts else 0
        max_drift = max(abs(d) for d in drifts) if drifts else 0
        drift_std = statistics.stdev(drifts) if len(drifts) > 1 else 0
        
        # Timing accuracy (within 10ms threshold)
        threshold = 0.01  # 10ms
        accurate_events = sum(1 for d in drifts if abs(d) < threshold)
        timing_accuracy = accurate_events / max(1, len(drifts))
        
        # Rhythm and consistency
        rhythm_regularity = self._calculate_rhythm_regularity(delays)
        session_consistency = self._calculate_session_consistency(events)
        
        # Advanced metrics
        typing_efficiency = self._calculate_typing_efficiency(events, target_wpm)
        fatigue_impact = self._calculate_fatigue_impact(events)
        learning_curve = self._calculate_learning_curve(events)
        
        return SessionMetrics(
            total_duration=total_duration,
            characters_typed=characters_typed,
            words_typed=words_typed,
            target_wpm=target_wpm,
            actual_wpm=actual_wpm,
            mean_inter_key_delay=mean_delay,
            std_inter_key_delay=std_delay,
            cv_inter_key_delay=cv_delay,
            pause_count=pause_count,
            total_pause_time=total_pause_time,
            burst_count=burst_count,
            avg_burst_duration=avg_burst_duration,
            total_errors=total_errors,
            error_rate=error_rate,
            correction_rate=correction_rate,
            avg_correction_delay=avg_correction_delay,
            error_type_distribution=error_type_dist,
            mean_drift=mean_drift,
            max_drift=max_drift,
            drift_std=drift_std,
            timing_accuracy=timing_accuracy,
            rhythm_regularity=rhythm_regularity,
            session_consistency=session_consistency,
            typing_efficiency=typing_efficiency,
            fatigue_impact=fatigue_impact,
            learning_curve=learning_curve
        )
    
    def _calculate_avg_burst_duration(self, events: List[TimingEvent]) -> float:
        """Calculate average burst duration"""
        burst_durations = []
        in_burst = False
        burst_start = 0
        
        for i, event in enumerate(events):
            if event.mode == TimingMode.BURST and not in_burst:
                in_burst = True
                burst_start = event.timestamp
            elif event.mode != TimingMode.BURST and in_burst:
                in_burst = False
                burst_durations.append(event.timestamp - burst_start)
        
        return statistics.mean(burst_durations) if burst_durations else 0
    
    def _calculate_rhythm_regularity(self, delays: List[float]) -> float:
        """Calculate rhythm regularity (0-1, higher = more regular)"""
        if len(delays) < 10:
            return 0.5
        
        # Use autocorrelation at lag 1 as rhythm measure
        if len(delays) > 1:
            autocorr = np.corrcoef(delays[:-1], delays[1:])[0, 1]
            return max(0, autocorr)  # Normalize to 0-1
        
        return 0.5
    
    def _calculate_session_consistency(self, events: List[TimingEvent]) -> float:
        """Calculate how consistent timing was throughout session"""
        if len(events) < 20:
            return 0.5
        
        # Split session into quarters and compare
        quarter_size = len(events) // 4
        quarters = []
        
        for i in range(4):
            start = i * quarter_size
            end = (i + 1) * quarter_size if i < 3 else len(events)
            quarter_events = events[start:end]
            quarter_delays = [e.delay for e in quarter_events]
            quarters.append(statistics.mean(quarter_delays))
        
        # Calculate coefficient of variation across quarters
        mean_quarter = statistics.mean(quarters)
        std_quarter = statistics.stdev(quarters) if len(quarters) > 1 else 0
        
        consistency = 1 - (std_quarter / mean_quarter) if mean_quarter > 0 else 0
        return max(0, min(1, consistency))
    
    def _calculate_typing_efficiency(self, events: List[TimingEvent], target_wpm: float) -> float:
        """Calculate typing efficiency vs theoretical maximum"""
        if not events or target_wpm == 0:
            return 0
        
        actual_wpm = self._calculate_actual_wpm(events)
        efficiency = actual_wpm / target_wpm
        return min(1.0, efficiency)
    
    def _calculate_fatigue_impact(self, events: List[TimingEvent]) -> float:
        """Calculate how much fatigue affected performance"""
        if len(events) < 20:
            return 0
        
        # Compare first half to second half
        mid_point = len(events) // 2
        first_half = events[:mid_point]
        second_half = events[mid_point:]
        
        first_wpm = self._calculate_actual_wpm(first_half)
        second_wpm = self._calculate_actual_wpm(second_half)
        
        if first_wpm == 0:
            return 0
        
        fatigue_impact = (first_wpm - second_wpm) / first_wpm
        return max(0, fatigue_impact)
    
    def _calculate_learning_curve(self, events: List[TimingEvent]) -> float:
        """Calculate improvement/degradation over time"""
        if len(events) < 20:
            return 0
        
        # Calculate moving average of delays
        window_size = min(10, len(events) // 4)
        moving_avgs = []
        
        for i in range(len(events)):
            start = max(0, i - window_size // 2)
            end = min(len(events), i + window_size // 2)
            window_events = events[start:end]
            avg_delay = statistics.mean([e.delay for e in window_events])
            moving_avgs.append(avg_delay)
        
        # Calculate trend
        if len(moving_avgs) > 1:
            trend = np.polyfit(range(len(moving_avgs)), moving_avgs, 1)[0]
            # Normalize to -1 to 1 scale
            return max(-1, min(1, -trend * 100))  # Negative trend = improvement
        
        return 0
    
    def _calculate_actual_wpm(self, events: List[TimingEvent]) -> float:
        """Calculate actual WPM for a subset of events"""
        if not events:
            return 0
        
        duration = events[-1].timestamp - events[0].timestamp
        characters = len([e for e in events if not e.character.isspace()])
        
        if duration <= 0:
            return 0
        
        return (characters / 5) / (duration / 60)
    
    def export_metrics_csv(self, metrics: SessionMetrics, filepath: Path):
        """Export metrics to CSV file"""
        metrics_dict = asdict(metrics)
        
        # Flatten nested dictionaries
        flattened = {}
        for key, value in metrics_dict.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    flattened[f"{key}_{sub_key}"] = sub_value
            else:
                flattened[key] = value
        
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=flattened.keys())
            writer.writeheader()
            writer.writerow(flattened)
    
    def export_metrics_json(self, metrics: SessionMetrics, filepath: Path):
        """Export metrics to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(asdict(metrics), f, indent=2)


class DiagnosticLogger:
    """Advanced logging for typing sessions"""
    
    def __init__(self, log_dir: Path = Path("logs")):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        self.session_logs: Dict[str, List[Dict]] = {}
    
    def start_session(self, session_id: str, profile_name: str, text: str):
        """Start logging a new session"""
        self.session_logs[session_id] = [{
            "timestamp": time.time(),
            "event": "session_start",
            "profile": profile_name,
            "text_length": len(text),
            "text_preview": text[:50] + "..." if len(text) > 50 else text
        }]
    
    def log_event(self, session_id: str, event_type: str, data: Dict):
        """Log an event during the session"""
        if session_id not in self.session_logs:
            return
        
        log_entry = {
            "timestamp": time.time(),
            "event": event_type,
            **data
        }
        
        self.session_logs[session_id].append(log_entry)
    
    def end_session(self, session_id: str, metrics: SessionMetrics):
        """End a session and save logs"""
        if session_id not in self.session_logs:
            return
        
        # Add session end with metrics
        self.session_logs[session_id].append({
            "timestamp": time.time(),
            "event": "session_end",
            "metrics": asdict(metrics)
        })
        
        # Save to file
        log_file = self.log_dir / f"session_{session_id}.json"
        with open(log_file, 'w') as f:
            json.dump(self.session_logs[session_id], f, indent=2)
    
    def analyze_session_patterns(self, session_id: str) -> Dict:
        """Analyze patterns in a completed session"""
        if session_id not in self.session_logs:
            return {}
        
        logs = self.session_logs[session_id]
        
        # Extract timing patterns
        timing_events = [log for log in logs if log.get("event") == "timing_event"]
        error_events = [log for log in logs if log.get("event") == "error"]
        
        analysis = {
            "total_events": len(logs),
            "timing_events": len(timing_events),
            "error_events": len(error_events),
            "session_duration": logs[-1]["timestamp"] - logs[0]["timestamp"] if logs else 0
        }
        
        return analysis


# Example usage and testing
if __name__ == "__main__":
    # Create mock data for testing
    from timing_model import TimingMode
    from error_model import ErrorType
    
    # Mock timing events
    events = []
    for i in range(100):
        mode = TimingMode.NORMAL if i % 10 != 5 else TimingMode.BURST
        event = TimingEvent(
            character='a' if i % 26 < 24 else ' ',
            timestamp=i * 0.1,
            delay=0.08 + np.random.normal(0, 0.02),
            context=None,  # Simplified for testing
            mode=mode
        )
        events.append(event)
    
    # Mock timing log
    timing_log = []
    for event in events:
        log = TimingLogEntry(
            planned_time=event.timestamp,
            actual_start=event.timestamp + np.random.normal(0, 0.005),
            actual_end=event.timestamp + event.delay + np.random.normal(0, 0.005),
            drift=np.random.normal(0, 0.01),
            character=event.character,
            success=True
        )
        timing_log.append(log)
    
    # Mock error events
    error_events = []
    for i in range(5):
        error = ErrorEvent(
            target_char='e',
            error_char='w',
            error_type=ErrorType.SUBSTITUTION,
            position=i * 20,
            timestamp=time.time(),
            correction_delay=0.3,
            backspace_count=1
        )
        error_events.append(error)
    
    # Test metrics collection
    collector = MetricsCollector()
    metrics = collector.calculate_metrics(events, timing_log, error_events, target_duration=10.0)
    
    print("Session Metrics:")
    print("-" * 40)
    print(f"Duration: {metrics.total_duration:.2f}s")
    print(f"Characters: {metrics.characters_typed}")
    print(f"Words: {metrics.words_typed}")
    print(f"Target WPM: {metrics.target_wpm:.1f}")
    print(f"Actual WPM: {metrics.actual_wpm:.1f}")
    print(f"Mean delay: {metrics.mean_inter_key_delay:.3f}s")
    print(f"CV delay: {metrics.cv_inter_key_delay:.3f}")
    print(f"Error rate: {metrics.error_rate:.3f}")
    print(f"Timing accuracy: {metrics.timing_accuracy:.3f}")
    print(f"Rhythm regularity: {metrics.rhythm_regularity:.3f}")
    
    # Test timeline visualization
    visualizer = TimelineVisualizer()
    timeline = visualizer.generate_timeline(events, timing_log)
    
    timing_plot_path = visualizer.create_timing_plot(timeline)
    rhythm_plot_path = visualizer.create_rhythm_plot(timeline)
    
    print(f"\nVisualization files created:")
    print(f"Timing plot: {timing_plot_path}")
    print(f"Rhythm plot: {rhythm_plot_path}")
    
    # Test diagnostic logging
    logger = DiagnosticLogger()
    session_id = f"test_{int(time.time())}"
    logger.start_session(session_id, "test_profile", "Hello world test")
    
    for i, event in enumerate(events[:10]):
        logger.log_event(session_id, "character_typed", {
            "character": event.character,
            "delay": event.delay,
            "mode": event.mode.value
        })
    
    logger.end_session(session_id, metrics)
    print(f"\nDiagnostic log saved for session: {session_id}")

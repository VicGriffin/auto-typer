"""
Non-Stationary Stochastic Timing Model for Realistic Typing Simulation

This module implements sophisticated timing models that evolve over time and
incorporate burst typing, pauses, fatigue, and rhythm drift.
"""

import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Callable
from enum import Enum
import random
import math

from text_processor import TextChunk, ChunkType
from keyboard_model import KeyboardModel


class TimingMode(Enum):
    NORMAL = "normal"
    BURST = "burst"
    PAUSE = "pause"
    RECOVERY = "recovery"


@dataclass
class TimingContext:
    """Context information for timing calculations"""
    prev_char: str
    current_char: str
    chunk_type: ChunkType
    position_in_chunk: int
    session_progress: float  # 0.0 to 1.0
    time_since_last_pause: float
    current_wpm: float
    fatigue_level: float  # 0.0 to 1.0


@dataclass
class TimingEvent:
    """Single timing event in the schedule"""
    character: str
    timestamp: float  # Planned timestamp
    delay: float  # Delay from previous event
    context: TimingContext
    mode: TimingMode


@dataclass
class TimingProfile:
    """Profile defining timing behavior characteristics"""
    base_wpm: float = 60.0
    variability: float = 0.2  # Coefficient of variation
    burst_probability: float = 0.15
    burst_duration_factor: float = 0.6  # Faster during bursts
    pause_frequency: float = 0.25
    pause_duration_mean: float = 0.5  # seconds
    pause_duration_std: float = 0.2
    fatigue_rate: float = 0.1  # Fatigue accumulation rate
    rhythm_drift: float = 0.3  # Rhythm variation over time
    warmup_duration: float = 30.0  # seconds to reach full speed
    
    # Distribution parameters
    base_delay_mu: float = 0.1  # Base inter-key delay (seconds)
    base_delay_sigma: float = 0.05
    
    # Burst mode parameters
    burst_delay_mu: float = 0.06
    burst_delay_sigma: float = 0.03
    
    # Pause mode parameters
    pause_delay_mu: float = 0.8
    pause_delay_sigma: float = 0.4


class NonStationaryTimingModel:
    """Advanced timing model with non-stationary stochastic processes"""
    
    def __init__(self, keyboard_model: KeyboardModel, profile: TimingProfile):
        self.keyboard_model = keyboard_model
        self.profile = profile
        
        # Initialize distributions
        self.base_distribution = stats.lognorm(
            s=profile.base_delay_sigma,
            scale=math.exp(profile.base_delay_mu)
        )
        
        self.burst_distribution = stats.lognorm(
            s=profile.burst_delay_sigma,
            scale=math.exp(profile.burst_delay_mu)
        )
        
        self.pause_distribution = stats.lognorm(
            s=profile.pause_duration_std,
            scale=math.exp(profile.pause_duration_mean)
        )
        
        # Session state
        self.session_state = {
            'current_wpm': profile.base_wpm,
            'fatigue_level': 0.0,
            'rhythm_phase': 0.0,
            'last_pause_time': 0.0,
            'burst_count': 0,
            'pause_count': 0
        }
    
    def generate_timing_schedule(self, chunks: List[TextChunk], 
                               target_duration: float) -> List[TimingEvent]:
        """Generate complete timing schedule before execution"""
        events = []
        current_time = 0.0
        prev_char = ''
        
        # Calculate total characters for WPM adjustment
        total_chars = sum(len(chunk.content) for chunk in chunks if not chunk.content.isspace())
        target_wpm = (total_chars / target_duration) * 60 if target_duration > 0 else self.profile.base_wpm
        
        # Flatten chunks into character sequence
        char_sequence = []
        for chunk in chunks:
            for char in chunk.content:
                char_sequence.append((char, chunk))
        
        # Generate timing for each character
        for i, (char, chunk) in enumerate(char_sequence):
            # Calculate session progress
            session_progress = i / max(1, len(char_sequence))
            
            # Update session state
            self._update_session_state(session_progress, current_time)
            
            # Create timing context
            context = TimingContext(
                prev_char=prev_char,
                current_char=char,
                chunk_type=chunk.chunk_type,
                position_in_chunk=i,
                session_progress=session_progress,
                time_since_last_pause=current_time - self.session_state['last_pause_time'],
                current_wpm=target_wpm,
                fatigue_level=self.session_state['fatigue_level']
            )
            
            # Determine timing mode
            mode = self._determine_timing_mode(context, chunk)
            
            # Calculate delay
            delay = self._calculate_delay(context, mode, target_wpm)
            
            # Create timing event
            event = TimingEvent(
                character=char,
                timestamp=current_time + delay,
                delay=delay,
                context=context,
                mode=mode
            )
            
            events.append(event)
            
            # Update state
            current_time += delay
            prev_char = char
            
            # Update session state based on event
            if mode == TimingMode.PAUSE:
                self.session_state['last_pause_time'] = current_time
                self.session_state['pause_count'] += 1
            elif mode == TimingMode.BURST:
                self.session_state['burst_count'] += 1
        
        return events
    
    def _determine_timing_mode(self, context: TimingContext, chunk: TextChunk) -> TimingMode:
        """Determine the timing mode based on context"""
        
        # High semantic weight suggests pause
        if chunk.semantic_weight > 0.5:
            return TimingMode.PAUSE
        
        # Check if we're in a burst pattern
        if self._should_burst(context):
            return TimingMode.BURST
        
        # Check for recovery after fatigue
        if context.fatigue_level > 0.7:
            return TimingMode.RECOVERY
        
        # Check for regular pause patterns
        if (context.time_since_last_pause > 5.0 and 
            random.random() < self.profile.pause_frequency):
            return TimingMode.PAUSE
        
        return TimingMode.NORMAL
    
    def _should_burst(self, context: TimingContext) -> bool:
        """Determine if typing should be in burst mode"""
        # Burst probability influenced by session progress and fatigue
        base_prob = self.profile.burst_probability
        
        # Less likely to burst when fatigued
        fatigue_factor = 1.0 - context.fatigue_level * 0.5
        
        # More likely to burst during warmup
        warmup_factor = 1.0
        if context.session_progress < 0.2:  # First 20% of session
            warmup_factor = 1.3
        
        # Rhythm-based bursting
        rhythm_factor = 0.5 + 0.5 * math.sin(self.session_state['rhythm_phase'])
        
        total_prob = base_prob * fatigue_factor * warmup_factor * rhythm_factor
        
        return random.random() < total_prob
    
    def _calculate_delay(self, context: TimingContext, mode: TimingMode, target_wpm: float) -> float:
        """Calculate delay for current context"""
        
        # Base delay from keyboard movement cost
        if context.prev_char:
            movement_cost = self.keyboard_model.movement_cost(context.prev_char, context.current_char)
        else:
            movement_cost = 1.0
        
        # Get base delay from appropriate distribution
        if mode == TimingMode.BURST:
            base_delay = self.burst_distribution.rvs()
            base_delay *= self.profile.burst_duration_factor
        elif mode == TimingMode.PAUSE:
            # For pauses, use semantic weight to scale
            base_delay = self.pause_distribution.rvs()
            if context.chunk_type != ChunkType.SPACE:
                base_delay *= context.chunk.semantic_weight
        else:
            base_delay = self.base_distribution.rvs()
        
        # Apply movement cost
        delay = base_delay * movement_cost
        
        # Apply WPM scaling
        wpm_factor = self.profile.base_wpm / target_wpm
        delay *= wpm_factor
        
        # Apply session evolution factors
        delay *= self._apply_session_evolution(context)
        
        # Apply fatigue
        if context.fatigue_level > 0.3:
            fatigue_factor = 1.0 + context.fatigue_level * 0.5
            delay *= fatigue_factor
        
        # Apply rhythm variation
        rhythm_variation = self._calculate_rhythm_variation(context)
        delay *= rhythm_variation
        
        # Add small jitter for realism
        jitter = np.random.normal(1.0, 0.02)  # 2% CV
        delay *= jitter
        
        return max(0.01, delay)  # Minimum delay
    
    def _apply_session_evolution(self, context: TimingContext) -> float:
        """Apply session evolution factors to delay"""
        evolution_factor = 1.0
        
        # Warmup period - gradually increase speed
        if context.session_progress < 0.2:
            warmup_progress = context.session_progress / 0.2
            evolution_factor *= (0.7 + 0.3 * warmup_progress)
        
        # Rhythm drift over session
        drift_amplitude = self.profile.rhythm_drift * 0.2
        drift = math.sin(context.session_progress * 2 * math.pi) * drift_amplitude
        evolution_factor *= (1.0 + drift)
        
        return evolution_factor
    
    def _calculate_rhythm_variation(self, context: TimingContext) -> float:
        """Calculate rhythm-based timing variation"""
        # Use multiple sine waves for complex rhythm
        rhythm1 = math.sin(self.session_state['rhythm_phase']) * 0.1
        rhythm2 = math.sin(self.session_state['rhythm_phase'] * 2.3) * 0.05
        rhythm3 = math.sin(self.session_state['rhythm_phase'] * 3.7) * 0.03
        
        variation = 1.0 + rhythm1 + rhythm2 + rhythm3
        return max(0.5, min(1.5, variation))
    
    def _update_session_state(self, session_progress: float, current_time: float):
        """Update internal session state"""
        # Update fatigue based on session progress
        fatigue_rate = self.profile.fatigue_rate
        if session_progress > 0.3:  # Fatigue starts after 30% of session
            fatigue_increase = fatigue_rate * (session_progress - 0.3)
            self.session_state['fatigue_level'] = min(1.0, fatigue_increase)
        
        # Update rhythm phase
        rhythm_speed = 2.0 + self.session_state['fatigue_level'] * 1.0  # Slow down when fatigued
        self.session_state['rhythm_phase'] += 0.1 * rhythm_speed
        
        # Update current WPM based on fatigue and rhythm
        base_wpm = self.profile.base_wpm
        fatigue_penalty = self.session_state['fatigue_level'] * 0.3  # Lose up to 30% speed
        rhythm_variation = math.sin(self.session_state['rhythm_phase']) * 0.1
        
        self.session_state['current_wpm'] = base_wpm * (1.0 - fatigue_penalty + rhythm_variation)
    
    def get_timing_statistics(self, events: List[TimingEvent]) -> Dict[str, float]:
        """Calculate timing statistics for generated schedule"""
        if not events:
            return {}
        
        delays = [event.delay for event in events]
        modes = [event.mode for event in events]
        
        # Basic statistics
        mean_delay = np.mean(delays)
        std_delay = np.std(delays)
        cv_delay = std_delay / mean_delay if mean_delay > 0 else 0
        
        # Mode distribution
        mode_counts = {mode: modes.count(mode) for mode in TimingMode}
        total_events = len(events)
        mode_percentages = {mode: count/total_events for mode, count in mode_counts.items()}
        
        # Burst and pause statistics
        burst_events = [e for e in events if e.mode == TimingMode.BURST]
        pause_events = [e for e in events if e.mode == TimingMode.PAUSE]
        
        burst_delays = [e.delay for e in burst_events]
        pause_delays = [e.delay for e in pause_events]
        
        return {
            'total_events': total_events,
            'mean_delay': mean_delay,
            'std_delay': std_delay,
            'cv_delay': cv_delay,
            'mode_percentages': mode_percentages,
            'burst_count': len(burst_events),
            'pause_count': len(pause_events),
            'mean_burst_delay': np.mean(burst_delays) if burst_delays else 0,
            'mean_pause_delay': np.mean(pause_delays) if pause_delays else 0,
            'estimated_wpm': self._calculate_wpm_from_events(events)
        }
    
    def _calculate_wpm_from_events(self, events: List[TimingEvent]) -> float:
        """Calculate effective WPM from timing events"""
        if len(events) < 2:
            return 0.0
        
        total_time = events[-1].timestamp - events[0].timestamp
        char_count = len([e for e in events if not e.character.isspace()])
        
        if total_time <= 0:
            return 0.0
        
        # Convert to WPM (assuming 5 characters per word)
        wpm = (char_count / 5.0) / (total_time / 60.0)
        return wpm


# Example usage and testing
if __name__ == "__main__":
    from keyboard_model import KeyboardModel
    from text_processor import TextProcessor
    
    # Create models
    keyboard_model = KeyboardModel()
    text_processor = TextProcessor()
    
    # Create timing profile
    profile = TimingProfile(
        base_wpm=65,
        variability=0.25,
        burst_probability=0.2,
        pause_frequency=0.3,
        fatigue_rate=0.15,
        rhythm_drift=0.4
    )
    
    # Create timing model
    timing_model = NonStationaryTimingModel(keyboard_model, profile)
    
    # Test with sample text
    test_text = "The quick brown fox jumps over the lazy dog. This sentence contains every letter of the alphabet!"
    
    # Parse and generate timing
    analysis = text_processor.parse_text(test_text)
    events = timing_model.generate_timing_schedule(analysis.chunks, target_duration=10.0)
    
    # Display statistics
    stats = timing_model.get_timing_statistics(events)
    
    print("Timing Model Statistics:")
    print("-" * 40)
    print(f"Total events: {stats['total_events']}")
    print(f"Mean delay: {stats['mean_delay']:.4f}s")
    print(f"CV delay: {stats['cv_delay']:.3f}")
    print(f"Estimated WPM: {stats['estimated_wpm']:.1f}")
    print(f"Burst events: {stats['burst_count']} ({stats['mode_percentages'][TimingMode.BURST]:.1%})")
    print(f"Pause events: {stats['pause_count']} ({stats['mode_percentages'][TimingMode.PAUSE]:.1%})")
    
    # Show first few events
    print("\nFirst 10 timing events:")
    print("-" * 60)
    for i, event in enumerate(events[:10]):
        print(f"{i:2d}: '{event.character}' ({event.mode.value}) "
              f"delay={event.delay:.4f}s timestamp={event.timestamp:.4f}s")

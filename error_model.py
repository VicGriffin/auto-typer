"""
Realistic Error and Correction Model for Human Typing Simulation

This module simulates human typing mistakes and correction patterns based on
keyboard proximity, typing speed, and cognitive factors.
"""

import random
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import time

from keyboard_model import KeyboardModel, KeyMapping
from text_processor import TextChunk, ChunkType
from timing_model import TimingContext


class ErrorType(Enum):
    SUBSTITUTION = "substitution"  # Wrong character
    INSERTION = "insertion"       # Extra character
    DELETION = "deletion"         # Missing character
    TRANSPOSITION = "transposition"  # Swapped characters


@dataclass
class ErrorEvent:
    """Represents a typing error and its correction"""
    target_char: str
    error_char: str
    error_type: ErrorType
    position: int
    timestamp: float
    correction_delay: float
    backspace_count: int


@dataclass
class ErrorContext:
    """Context information for error generation"""
    current_char: str
    position: int
    current_wpm: float
    fatigue_level: float
    chunk_type: ChunkType
    previous_errors: int
    session_progress: float


@dataclass
class ErrorProfile:
    """Profile defining error behavior characteristics"""
    base_error_rate: float = 0.02  # 2% base error rate
    speed_error_factor: float = 0.5  # How much speed affects errors
    fatigue_error_factor: float = 0.3  # How much fatigue affects errors
    complexity_error_factor: float = 0.2  # How complexity affects errors
    
    # Correction behavior
    correction_delay_mean: float = 0.3  # Mean delay before correction
    correction_delay_std: float = 0.1   # Std dev of correction delay
    backspace_probability: float = 0.9  # Probability of using backspace
    multiple_backspace_prob: float = 0.1  # Probability of multiple backspaces
    
    # Error type probabilities
    substitution_prob: float = 0.7
    insertion_prob: float = 0.15
    deletion_prob: float = 0.1
    transposition_prob: float = 0.05
    
    # Context-specific error rates
    punctuation_error_rate: float = 0.05
    number_error_rate: float = 0.08
    symbol_error_rate: float = 0.12
    shift_error_rate: float = 0.15  # Errors with shifted characters


class RealisticErrorModel:
    """Model for generating realistic typing errors and corrections"""
    
    def __init__(self, keyboard_model: KeyboardModel, profile: ErrorProfile):
        self.keyboard_model = keyboard_model
        self.profile = profile
        
        # Error state tracking
        self.error_history: List[ErrorEvent] = []
        self.error_count = 0
        self.correction_count = 0
        
        # Common error patterns
        self.common_substitutions = {
            'e': 'w', 'r': 't', 't': 'r', 'y': 'u', 'u': 'y', 'i': 'o',
            'o': 'i', 'p': 'l', 'l': 'p', 'k': 'l', 'd': 's', 's': 'd',
            'a': 's', 'z': 'x', 'x': 'z', 'c': 'v', 'v': 'c', 'b': 'n',
            'n': 'b', 'm': 'n', 'h': 'g', 'g': 'h', 'j': 'h', 'f': 'g'
        }
        
        # Characters that are commonly confused
        self.confusion_pairs = {
            ('i', 'l'), ('l', 'i'), ('o', 'p'), ('p', 'o'),
            ('k', 'l'), ('l', 'k'), ('m', 'n'), ('n', 'm'),
            ('u', 'y'), ('y', 'u'), ('e', 'r'), ('r', 'e')
        }
    
    def should_make_error(self, context: ErrorContext) -> bool:
        """Determine if an error should occur based on context"""
        
        # Calculate base error probability
        error_prob = self.profile.base_error_rate
        
        # Adjust for typing speed (higher speed = more errors)
        speed_factor = 1.0 + (context.current_wpm - 60) / 60 * self.profile.speed_error_factor
        error_prob *= max(0.1, speed_factor)
        
        # Adjust for fatigue
        fatigue_factor = 1.0 + context.fatigue_level * self.profile.fatigue_error_factor
        error_prob *= fatigue_factor
        
        # Adjust for character complexity
        if context.chunk_type == ChunkType.PUNCTUATION:
            error_prob *= (1.0 + self.profile.punctuation_error_rate)
        elif context.chunk_type == ChunkType.NUMBER:
            error_prob *= (1.0 + self.profile.number_error_rate)
        elif context.chunk_type == ChunkType.SYMBOL:
            error_prob *= (1.0 + self.profile.symbol_error_rate)
        
        # Adjust for shift requirements
        mapping = self.keyboard_model.layout.get_mapping(context.current_char)
        if mapping and mapping.shift_required:
            error_prob *= (1.0 + self.profile.shift_error_rate)
        
        # Error clustering - more likely after recent errors
        if context.previous_errors > 0:
            clustering_factor = 1.0 + context.previous_errors * 0.2
            error_prob *= clustering_factor
        
        # Session progression effects
        if context.session_progress > 0.8:  # More errors near end
            error_prob *= 1.3
        elif context.session_progress < 0.1:  # Fewer errors at start
            error_prob *= 0.7
        
        return random.random() < error_prob
    
    def generate_error(self, context: ErrorContext) -> Optional[ErrorEvent]:
        """Generate a realistic typing error"""
        
        error_type = self._determine_error_type()
        error_char = ""
        
        if error_type == ErrorType.SUBSTITUTION:
            error_char = self._generate_substitution_error(context.current_char)
        elif error_type == ErrorType.INSERTION:
            error_char = self._generate_insertion_error(context.current_char)
        elif error_type == ErrorType.DELETION:
            error_char = ""  # No character typed
        elif error_type == ErrorType.TRANSPOSITION:
            # Transposition is handled differently
            error_char = self._generate_transposition_error(context.current_char)
        
        if error_char is None:  # Failed to generate error
            return None
        
        # Calculate correction delay
        correction_delay = self._calculate_correction_delay(context)
        
        # Determine backspace behavior
        backspace_count = self._calculate_backspace_count(error_type, error_char)
        
        error_event = ErrorEvent(
            target_char=context.current_char,
            error_char=error_char,
            error_type=error_type,
            position=context.position,
            timestamp=time.time(),
            correction_delay=correction_delay,
            backspace_count=backspace_count
        )
        
        self.error_history.append(error_event)
        self.error_count += 1
        
        return error_event
    
    def _determine_error_type(self) -> ErrorType:
        """Determine the type of error to generate"""
        rand = random.random()
        
        cumulative = 0.0
        cumulative += self.profile.substitution_prob
        if rand < cumulative:
            return ErrorType.SUBSTITUTION
        
        cumulative += self.profile.insertion_prob
        if rand < cumulative:
            return ErrorType.INSERTION
        
        cumulative += self.profile.deletion_prob
        if rand < cumulative:
            return ErrorType.DELETION
        
        return ErrorType.TRANSPOSITION
    
    def _generate_substitution_error(self, target_char: str) -> Optional[str]:
        """Generate a substitution error based on keyboard proximity"""
        
        # Check for common substitutions first
        if target_char.lower() in self.common_substitutions:
            if random.random() < 0.3:  # 30% chance of common substitution
                return self.common_substitutions[target_char.lower()]
        
        # Get adjacent keys
        adjacent_keys = self.keyboard_model.layout.get_adjacent_keys(target_char)
        if not adjacent_keys:
            return None
        
        # Weight by proximity and common confusion
        weights = []
        for key in adjacent_keys:
            weight = key.proximity_weight
            
            # Boost weight for commonly confused pairs
            if (target_char.lower(), key.character.lower()) in self.confusion_pairs:
                weight *= 2.0
            
            weights.append(weight)
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return None
        
        weights = [w / total_weight for w in weights]
        
        # Select error character
        selected_key = random.choices(adjacent_keys, weights=weights)[0]
        
        # Preserve case if possible
        if target_char.isupper() and selected_key.character.islower():
            return selected_key.character.upper()
        elif target_char.islower() and selected_key.character.isupper():
            return selected_key.character.lower()
        
        return selected_key.character
    
    def _generate_insertion_error(self, target_char: str) -> str:
        """Generate an insertion error (extra character)"""
        
        # Get adjacent keys for insertion
        adjacent_keys = self.keyboard_model.layout.get_adjacent_keys(target_char)
        if adjacent_keys:
            # Prefer adjacent keys for insertion
            weights = [key.proximity_weight for key in adjacent_keys]
            selected_key = random.choices(adjacent_keys, weights=weights)[0]
            return selected_key.character
        
        # Fallback to common nearby keys
        common_insertions = ['e', 't', 'a', 'o', 'i', 'n', 's', 'h', 'r']
        return random.choice(common_insertions)
    
    def _generate_transposition_error(self, target_char: str) -> str:
        """Generate a transposition error (swapped with next character)"""
        # This is a simplified version - in practice, we'd need to know the next character
        # For now, return a nearby character as if it were transposed
        return self._generate_substitution_error(target_char) or target_char
    
    def _calculate_correction_delay(self, context: ErrorContext) -> float:
        """Calculate realistic delay before error correction"""
        
        base_delay = np.random.normal(
            self.profile.correction_delay_mean,
            self.profile.correction_delay_std
        )
        
        # Adjust for context
        if context.fatigue_level > 0.5:
            base_delay *= 1.5  # Slower correction when fatigued
        
        if context.current_wpm > 80:
            base_delay *= 0.8  # Faster correction when typing fast
        
        # Add some randomness
        base_delay *= random.uniform(0.5, 1.5)
        
        return max(0.1, base_delay)
    
    def _calculate_backspace_count(self, error_type: ErrorType, error_char: str) -> int:
        """Calculate number of backspaces needed for correction"""
        
        if error_type == ErrorType.DELETION:
            return 0  # No backspace for deletion
        
        if not random.random() < self.profile.backspace_probability:
            return 0  # No backspace (might use mouse or other method)
        
        # Calculate backspaces needed
        if error_type == ErrorType.SUBSTITUTION:
            return 1  # One backspace for substitution
        elif error_type == ErrorType.INSERTION:
            return 1  # One backspace for insertion
        elif error_type == ErrorType.TRANSPOSITION:
            return 2  # Two backspaces for transposition
        
        # Multiple backspaces for complex errors
        if random.random() < self.profile.multiple_backspace_prob:
            return random.randint(2, 4)
        
        return 1
    
    def enhance_timing_schedule(self, events: List, profile) -> List:
        """Enhance timing schedule with errors and corrections"""
        enhanced_events = []
        position = 0
        
        for event in events:
            # Create error context
            context = ErrorContext(
                current_char=event.character,
                position=position,
                current_wpm=event.context.current_wpm,
                fatigue_level=event.context.fatigue_level,
                chunk_type=event.context.chunk_type,
                previous_errors=len([e for e in self.error_history if e.position >= position - 5]),
                session_progress=event.context.session_progress
            )
            
            # Check if error should occur
            if self.should_make_error(context) and event.character.strip():
                error_event = self.generate_error(context)
                
                if error_event:
                    # Add error event
                    error_timing_event = self._create_error_timing_event(event, error_event)
                    enhanced_events.append(error_timing_event)
                    
                    # Add correction events
                    correction_events = self._create_correction_events(event, error_event)
                    enhanced_events.extend(correction_events)
                    
                    self.correction_count += 1
                else:
                    # No error generated, add original event
                    enhanced_events.append(event)
            else:
                # No error, add original event
                enhanced_events.append(event)
            
            position += 1
        
        return enhanced_events
    
    def _create_error_timing_event(self, original_event, error_event: ErrorEvent):
        """Create a timing event for the error"""
        # Copy original event but modify character
        error_timing_event = type(original_event)(
            character=error_event.error_char,
            timestamp=original_event.timestamp,
            delay=original_event.delay,
            context=original_event.context,
            mode=original_event.mode
        )
        
        # Mark as error in context (extend context if needed)
        if hasattr(error_timing_event.context, 'is_error'):
            error_timing_event.context.is_error = True
        
        return error_timing_event
    
    def _create_correction_events(self, original_event, error_event: ErrorEvent) -> List:
        """Create timing events for error correction"""
        correction_events = []
        
        # Add delay before correction
        correction_delay = error_event.correction_delay
        
        # Add backspace events
        for i in range(error_event.backspace_count):
            backspace_event = type(original_event)(
                character='backspace',
                timestamp=original_event.timestamp + correction_delay + i * 0.1,
                delay=0.1,
                context=original_event.context,
                mode=original_event.mode
            )
            correction_events.append(backspace_event)
        
        # Add corrected character
        corrected_event = type(original_event)(
            character=error_event.target_char,
            timestamp=original_event.timestamp + correction_delay + error_event.backspace_count * 0.1,
            delay=original_event.delay,
            context=original_event.context,
            mode=original_event.mode
        )
        correction_events.append(corrected_event)
        
        return correction_events
    
    def get_error_statistics(self) -> Dict[str, float]:
        """Calculate error statistics for the session"""
        if not self.error_history:
            return {
                'total_errors': 0,
                'error_rate': 0.0,
                'correction_rate': 0.0,
                'avg_correction_delay': 0.0,
                'error_type_distribution': {}
            }
        
        total_events = len(self.error_history) + self.correction_count
        error_rate = len(self.error_history) / max(1, total_events)
        
        # Calculate correction rate
        corrections = sum(1 for error in self.error_history if error.backspace_count > 0)
        correction_rate = corrections / max(1, len(self.error_history))
        
        # Average correction delay
        avg_delay = np.mean([error.correction_delay for error in self.error_history])
        
        # Error type distribution
        type_counts = {}
        for error in self.error_history:
            error_type = error.error_type.value
            type_counts[error_type] = type_counts.get(error_type, 0) + 1
        
        type_distribution = {
            error_type: count / len(self.error_history)
            for error_type, count in type_counts.items()
        }
        
        return {
            'total_errors': len(self.error_history),
            'error_rate': error_rate,
            'correction_rate': correction_rate,
            'avg_correction_delay': avg_delay,
            'error_type_distribution': type_distribution
        }


# Example usage and testing
if __name__ == "__main__":
    from keyboard_model import KeyboardModel
    from text_processor import TextProcessor
    from timing_model import TimingModel, TimingProfile
    
    # Create models
    keyboard_model = KeyboardModel()
    text_processor = TextProcessor()
    
    # Create error profile
    error_profile = ErrorProfile(
        base_error_rate=0.03,
        speed_error_factor=0.6,
        fatigue_error_factor=0.4,
        correction_delay_mean=0.35
    )
    
    # Create error model
    error_model = RealisticErrorModel(keyboard_model, error_profile)
    
    # Test error generation
    test_chars = ['e', 't', 'a', 'o', 'i', 'n', 's', 'h', 'r', 'l']
    
    print("Error Generation Test:")
    print("-" * 40)
    
    for i, char in enumerate(test_chars):
        context = ErrorContext(
            current_char=char,
            position=i,
            current_wpm=70 + i * 2,
            fatigue_level=i / 20,
            chunk_type=ChunkType.WORD,
            previous_errors=0,
            session_progress=0.3
        )
        
        if error_model.should_make_error(context):
            error = error_model.generate_error(context)
            if error:
                print(f"'{char}' -> '{error.error_char}' ({error.error_type.value}) "
                      f"delay={error.correction_delay:.3f}s backspaces={error.backspace_count}")
        else:
            print(f"'{char}' - No error")
    
    # Show statistics
    stats = error_model.get_error_statistics()
    print(f"\nError Statistics:")
    print(f"Total errors: {stats['total_errors']}")
    print(f"Error rate: {stats['error_rate']:.3f}")
    print(f"Correction rate: {stats['correction_rate']:.3f}")
    print(f"Avg correction delay: {stats['avg_correction_delay']:.3f}s")

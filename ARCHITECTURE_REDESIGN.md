# Overlay Typer Bot - Architecture Redesign Specification

## Overview

This document outlines a comprehensive redesign of the Overlay Typer Bot to increase behavioral realism, modularity, and observability while maintaining focus on legitimate use cases (accessibility, testing, demonstration).

## Refactored Architecture

```
Overlay Typer Bot v2.0
|
+-- SessionController
|   +-- Orchestrates all components
|   +-- Manages session state and evolution
|   +-- Handles user interactions and UI events
|
+-- TextProcessor
|   +-- Semantic chunking and parsing
|   +-- Word boundary detection
|   +-- Punctuation and sentence structure analysis
|
+-- TimingModel
|   +-- Non-stationary stochastic processes
|   +-- Burst typing and pause modeling
|   +-- Fatigue and rhythm drift simulation
|
+-- ErrorModel
|   +-- Realistic typing mistake generation
|   +-- Keyboard proximity-based errors
|   +-- Backspace correction patterns
|
+-- KeyboardModel
|   +-- Finger-to-key mapping
|   +-- Inter-key movement cost calculation
|   +-- Adjacency probability modeling
|
+-- InputEmitter
|   +-- Abstract event generation
|   +-- Multiple backend support
|   +-- Timing jitter and drift correction
|
+-- ObservabilityLayer
|   +-- Timeline visualization
|   +-- Metrics collection and analysis
|   +-- Diagnostic logging
|
+-- ProfileManager
|   +-- Behavior profile definitions
|   +-- Parameter set management
|   +-- Profile validation and testing
```

## Core Module Specifications

### 1. TextProcessor

**Purpose**: Preprocess input text into semantic units that influence timing.

**Key Functions**:
- `parse_text(text)`: Returns list of TextChunk objects
- `detect_boundaries(text)`: Identifies word, sentence, paragraph boundaries
- `analyze_structure(text)`: Determines punctuation patterns and complexity

**Data Structures**:
```python
@dataclass
class TextChunk:
    content: str
    chunk_type: ChunkType  # WORD, PUNCTUATION, SPACE, SENTENCE_END
    position: int
    semantic_weight: float  # Influences pause duration
    complexity_score: float  # Affects error probability

class ChunkType(Enum):
    WORD = "word"
    PUNCTUATION = "punctuation"
    SPACE = "space"
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
```

### 2. TimingModel

**Purpose**: Generate realistic inter-key timing using non-stationary stochastic processes.

**Key Functions**:
- `generate_timing_schedule(chunks)`: Creates full timing schedule before execution
- `calculate_base_delay(prev_key, next_key, context)`: Base timing calculation
- `apply_session_evolution(schedule, session_progress)`: Modifies timing over time

**Core Algorithm**:
```python
class NonStationaryTimingModel:
    def __init__(self, profile: TimingProfile):
        self.base_distribution = LogNormal(
            loc=profile.base_mu,
            sigma=profile.base_sigma
        )
        self.burst_probability = GaussianMixture(
            weights=[0.7, 0.3],
            means=[profile.burst_mean, profile.normal_mean],
            covariances=[profile.burst_var, profile.normal_var]
        )
        
    def generate_delay(self, context: TimingContext) -> float:
        # Base delay from keyboard model
        movement_cost = self.keyboard_model.movement_cost(
            context.prev_key, context.next_key
        )
        
        # Apply stochastic process
        if self.is_burst_mode(context):
            delay = self.burst_distribution.sample() * movement_cost
        else:
            delay = self.base_distribution.sample() * movement_cost
            
        # Apply session evolution
        evolution_factor = self.calculate_evolution_factor(
            context.session_progress
        )
        
        return delay * evolution_factor
```

### 3. ErrorModel

**Purpose**: Simulate realistic human typing mistakes and corrections.

**Key Functions**:
- `should_make_error(context)`: Determines if error should occur
- `generate_error_char(target_char)`: Creates realistic mistake
- `plan_correction(error_char, target_char)`: Plans backspace correction

**Error Generation Logic**:
```python
class RealisticErrorModel:
    def __init__(self, profile: ErrorProfile):
        self.keyboard_layout = QWERTYLayout()
        self.error_probability = profile.base_error_rate
        
    def generate_error(self, target_char: str, context: ErrorContext) -> Optional[str]:
        # Error probability increases with speed
        speed_factor = 1 + (context.current_wpm / 60) * profile.speed_error_factor
        
        if random.random() > self.error_probability * speed_factor:
            return None
            
        # Generate error based on keyboard proximity
        adjacent_keys = self.keyboard_layout.get_adjacent_keys(target_char)
        weights = [key.proximity_weight for key in adjacent_keys]
        
        return random.choices(adjacent_keys, weights=weights)[0].character
```

### 4. KeyboardModel

**Purpose**: Model finger-to-key mappings and movement costs.

**Data Structure**:
```python
@dataclass
class KeyMapping:
    character: str
    finger: Finger  # LEFT_PINKY, LEFT_RING, etc.
    position: Tuple[int, int]  # Row, column on keyboard
    hand: Hand  # LEFT, RIGHT
    
@dataclass
class MovementCost:
    base_cost: float
    same_hand_penalty: float
    same_finger_penalty: float
    cross_hand_bonus: float
    stretch_penalty: float

class KeyboardModel:
    def movement_cost(self, from_key: str, to_key: str) -> float:
        from_mapping = self.key_map[from_key]
        to_mapping = self.key_map[to_key]
        
        cost = self.base_movement_cost
        
        if from_mapping.hand == to_mapping.hand:
            cost *= self.same_hand_penalty
            
        if from_mapping.finger == to_mapping.finger:
            cost *= self.same_finger_penalty
        elif from_mapping.hand != to_mapping.hand:
            cost *= self.cross_hand_bonus
            
        # Add stretch penalty for awkward movements
        distance = self.calculate_distance(from_mapping, to_mapping)
        if distance > self.stretch_threshold:
            cost *= (1 + self.stretch_penalty * (distance - self.stretch_threshold))
            
        return cost
```

### 5. InputEmitter

**Purpose**: Abstract event generation with multiple backend support.

**Interface**:
```python
class InputEmitter(ABC):
    @abstractmethod
    def emit_key(self, key_event: KeyEvent) -> bool:
        """Emit a key event and return success status"""
        pass
        
    @abstractmethod
    def get_actual_timestamp(self) -> float:
        """Get current high-precision timestamp"""
        pass

class PyAutoGUIEmitter(InputEmitter):
    def emit_key(self, key_event: KeyEvent) -> bool:
        actual_start = self.get_actual_timestamp()
        
        try:
            pyautogui.press(key_event.character)
            actual_end = self.get_actual_timestamp()
            
            # Record timing for drift correction
            self.timing_log.append(TimingLogEntry(
                planned_time=key_event.timestamp,
                actual_start=actual_start,
                actual_end=actual_end,
                drift=actual_start - key_event.timestamp
            ))
            
            return True
        except Exception as e:
            self.error_log.append(e)
            return False
```

### 6. SessionController

**Purpose**: Orchestrates all components and manages session state.

**Core Workflow**:
```python
class SessionController:
    def execute_typing_session(self, text: str, profile: Profile) -> SessionResult:
        # 1. Parse text into semantic chunks
        chunks = self.text_processor.parse_text(text)
        
        # 2. Generate complete timing schedule
        schedule = self.timing_model.generate_timing_schedule(chunks, profile)
        
        # 3. Add errors and corrections
        enhanced_schedule = self.error_model.enhance_schedule(schedule, profile)
        
        # 4. Execute with real-time correction
        result = self.execute_schedule_with_correction(enhanced_schedule)
        
        # 5. Generate observability report
        return self.observability.generate_report(result)
```

## Behavior Profiles

### Profile Definitions

```python
@dataclass
class BehaviorProfile:
    name: str
    description: str
    timing_profile: TimingProfile
    error_profile: ErrorProfile
    session_profile: SessionProfile

# Example Profiles
PROFILES = {
    "consistent": BehaviorProfile(
        name="Consistent Typist",
        description="Steady pace with low variability",
        timing_profile=TimingProfile(
            base_wpm=60,
            variability=0.1,
            burst_probability=0.1,
            pause_frequency=0.2
        ),
        error_profile=ErrorProfile(
            base_error_rate=0.02,
            correction_delay=0.3,
            speed_error_factor=0.5
        ),
        session_profile=SessionProfile(
            fatigue_rate=0.05,
            rhythm_drift=0.1,
            warmup_duration=30
        )
    ),
    
    "bursty": BehaviorProfile(
        name="Bursty Typist",
        description="Alternates between fast bursts and pauses",
        timing_profile=TimingProfile(
            base_wpm=75,
            variability=0.3,
            burst_probability=0.4,
            pause_frequency=0.3
        ),
        error_profile=ErrorProfile(
            base_error_rate=0.04,
            correction_delay=0.2,
            speed_error_factor=0.8
        ),
        session_profile=SessionProfile(
            fatigue_rate=0.15,
            rhythm_drift=0.3,
            warmup_duration=45
        )
    ),
    
    "fatigued": BehaviorProfile(
        name="Fatigued Typist",
        description="Shows increasing errors and slowing over time",
        timing_profile=TimingProfile(
            base_wpm=45,
            variability=0.4,
            burst_probability=0.05,
            pause_frequency=0.4
        ),
        error_profile=ErrorProfile(
            base_error_rate=0.08,
            correction_delay=0.5,
            speed_error_factor=1.2
        ),
        session_profile=SessionProfile(
            fatigue_rate=0.4,
            rhythm_drift=0.5,
            warmup_duration=60
        )
    )
}
```

## Observability and Diagnostics

### Timeline Visualization

```python
class TimelineVisualizer:
    def generate_timeline(self, session_result: SessionResult) -> Timeline:
        events = []
        
        for event in session_result.events:
            events.append(TimelineEvent(
                timestamp=event.timestamp,
                event_type=event.type,
                character=event.character,
                planned_delay=event.planned_delay,
                actual_delay=event.actual_delay,
                is_error=event.is_error
            ))
            
        return Timeline(events)
        
    def export_visualization(self, timeline: Timeline, format: str) -> str:
        if format == "html":
            return self.generate_html_timeline(timeline)
        elif format == "json":
            return self.generate_json_timeline(timeline)
        elif format == "csv":
            return self.generate_csv_timeline(timeline)
```

### Metrics Collection

```python
@dataclass
class SessionMetrics:
    total_duration: float
    characters_typed: int
    actual_wpm: float
    target_wpm: float
    error_count: int
    correction_count: int
    pause_distribution: Dict[str, int]
    delay_variance: float
    drift_statistics: DriftStats
    
class MetricsCollector:
    def calculate_metrics(self, session_result: SessionResult) -> SessionMetrics:
        return SessionMetrics(
            total_duration=session_result.end_time - session_result.start_time,
            characters_typed=len(session_result.typed_characters),
            actual_wpm=self.calculate_wpm(session_result),
            target_wpm=session_result.profile.target_wpm,
            error_count=session_result.error_count,
            correction_count=session_result.correction_count,
            pause_distribution=self.analyze_pauses(session_result),
            delay_variance=self.calculate_variance(session_result.delays),
            drift_statistics=self.calculate_drift(session_result.timing_log)
        )
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)
1. Refactor existing code into modular architecture
2. Implement TextProcessor with semantic chunking
3. Create KeyboardModel with finger mapping
4. Set up basic InputEmitter abstraction

### Phase 2: Timing and Error Models (Week 3-4)
1. Implement non-stationary timing model
2. Create realistic error generation system
3. Add session evolution and fatigue modeling
4. Integrate timing with keyboard movement costs

### Phase 3: Observability and UI (Week 5-6)
1. Build timeline visualization system
2. Implement metrics collection
3. Create diagnostic logging
4. Design advanced UI controls for profiles

### Phase 4: Testing and Refinement (Week 7-8)
1. Create comprehensive test suite
2. Validate timing realism against human baselines
3. Optimize performance for long sessions
4. Documentation and examples

## Validation Approach

### Baseline Comparison
- Collect human typing data for comparison
- Statistical analysis of inter-key delays
- Error pattern validation
- Session evolution verification

### Deterministic Testing
- Fixed random seeds for reproducible tests
- Profile validation against expected parameters
- Timing accuracy measurement
- Error rate verification

This redesigned architecture provides a solid foundation for realistic typing simulation while maintaining modularity, testability, and observability appropriate for legitimate use cases.

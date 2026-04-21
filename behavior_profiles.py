"""
Behavior Profiles and Parameter Sets for Typing Simulation

This module defines comprehensive behavior profiles that control timing,
error patterns, and session characteristics for different typing styles.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import json
from pathlib import Path

from timing_model import TimingProfile
from error_model import ErrorProfile
from input_emitter import EmitterConfig, EmitterType


class ProfileCategory(Enum):
    CONSISTENT = "consistent"
    BURSTY = "bursty"
    FATIGUED = "fatigued"
    CAUTIOUS = "cautious"
    PROFESSIONAL = "professional"
    CASUAL = "casual"


@dataclass
class BehaviorProfile:
    """Complete behavior profile defining all typing characteristics"""
    name: str
    category: ProfileCategory
    description: str
    
    # Core profiles
    timing_profile: TimingProfile
    error_profile: ErrorProfile
    emitter_config: EmitterConfig
    
    # Metadata
    target_wpm: float
    variability_level: float  # 0.0 (very consistent) to 1.0 (highly variable)
    realism_score: float  # 0.0 (robotic) to 1.0 (very human-like)
    complexity_level: float  # 0.0 (simple) to 1.0 (complex)
    
    # Usage metadata
    recommended_for: List[str]
    tags: List[str]


class ProfileManager:
    """Manages behavior profiles with validation and serialization"""
    
    def __init__(self):
        self.profiles: Dict[str, BehaviorProfile] = {}
        self._initialize_default_profiles()
    
    def _initialize_default_profiles(self):
        """Initialize default behavior profiles"""
        
        # Consistent Typist Profile
        self.profiles["consistent"] = BehaviorProfile(
            name="Consistent Typist",
            category=ProfileCategory.CONSISTENT,
            description="Steady, reliable typing with minimal variability",
            timing_profile=TimingProfile(
                base_wpm=60,
                variability=0.1,
                burst_probability=0.05,
                burst_duration_factor=0.8,
                pause_frequency=0.15,
                pause_duration_mean=0.3,
                pause_duration_std=0.1,
                fatigue_rate=0.02,
                rhythm_drift=0.1,
                warmup_duration=20.0,
                base_delay_mu=0.12,
                base_delay_sigma=0.03,
                burst_delay_mu=0.08,
                burst_delay_sigma=0.02,
                pause_delay_mu=0.4,
                pause_delay_sigma=0.15
            ),
            error_profile=ErrorProfile(
                base_error_rate=0.015,
                speed_error_factor=0.3,
                fatigue_error_factor=0.1,
                complexity_error_factor=0.1,
                correction_delay_mean=0.25,
                correction_delay_std=0.08,
                backspace_probability=0.95,
                multiple_backspace_prob=0.05,
                substitution_prob=0.8,
                insertion_prob=0.1,
                deletion_prob=0.05,
                transposition_prob=0.05,
                punctuation_error_rate=0.02,
                number_error_rate=0.03,
                symbol_error_rate=0.04,
                shift_error_rate=0.08
            ),
            emitter_config=EmitterConfig(
                emitter_type=EmitterType.PYAUTOGUI,
                jitter_enabled=False,
                jitter_magnitude=0.01,
                drift_correction=True,
                drift_threshold=0.05,
                fallback_enabled=True,
                logging_enabled=True,
                max_retry_attempts=2
            ),
            target_wpm=60,
            variability_level=0.2,
            realism_score=0.6,
            complexity_level=0.3,
            recommended_for=["data entry", "form filling", "consistent typing"],
            tags=["reliable", "steady", "low-variability", "professional"]
        )
        
        # Bursty Typist Profile
        self.profiles["bursty"] = BehaviorProfile(
            name="Bursty Typist",
            category=ProfileCategory.BURSTY,
            description="Alternates between fast bursts and thoughtful pauses",
            timing_profile=TimingProfile(
                base_wpm=75,
                variability=0.4,
                burst_probability=0.35,
                burst_duration_factor=0.5,
                pause_frequency=0.3,
                pause_duration_mean=0.8,
                pause_duration_std=0.3,
                fatigue_rate=0.08,
                rhythm_drift=0.4,
                warmup_duration=30.0,
                base_delay_mu=0.08,
                base_delay_sigma=0.04,
                burst_delay_mu=0.04,
                burst_delay_sigma=0.015,
                pause_delay_mu=0.9,
                pause_delay_sigma=0.4
            ),
            error_profile=ErrorProfile(
                base_error_rate=0.035,
                speed_error_factor=0.7,
                fatigue_error_factor=0.3,
                complexity_error_factor=0.25,
                correction_delay_mean=0.4,
                correction_delay_std=0.15,
                backspace_probability=0.85,
                multiple_backspace_prob=0.15,
                substitution_prob=0.65,
                insertion_prob=0.2,
                deletion_prob=0.1,
                transposition_prob=0.05,
                punctuation_error_rate=0.06,
                number_error_rate=0.08,
                symbol_error_rate=0.12,
                shift_error_rate=0.18
            ),
            emitter_config=EmitterConfig(
                emitter_type=EmitterType.PYAUTOGUI,
                jitter_enabled=True,
                jitter_magnitude=0.03,
                drift_correction=True,
                drift_threshold=0.1,
                fallback_enabled=True,
                logging_enabled=True,
                max_retry_attempts=3
            ),
            target_wpm=75,
            variability_level=0.7,
            realism_score=0.8,
            complexity_level=0.6,
            recommended_for=["creative writing", "coding", "natural typing"],
            tags=["expressive", "variable", "human-like", "creative"]
        )
        
        # Fatigued Typist Profile
        self.profiles["fatigued"] = BehaviorProfile(
            name="Fatigued Typist",
            category=ProfileCategory.FATIGUED,
            description="Shows increasing errors and slowing over time",
            timing_profile=TimingProfile(
                base_wpm=45,
                variability=0.5,
                burst_probability=0.08,
                burst_duration_factor=0.7,
                pause_frequency=0.5,
                pause_duration_mean=1.2,
                pause_duration_std=0.6,
                fatigue_rate=0.4,
                rhythm_drift=0.6,
                warmup_duration=45.0,
                base_delay_mu=0.18,
                base_delay_sigma=0.08,
                burst_delay_mu=0.12,
                burst_delay_sigma=0.04,
                pause_delay_mu=1.5,
                pause_delay_sigma=0.8
            ),
            error_profile=ErrorProfile(
                base_error_rate=0.08,
                speed_error_factor=1.2,
                fatigue_error_factor=0.8,
                complexity_error_factor=0.4,
                correction_delay_mean=0.7,
                correction_delay_std=0.3,
                backspace_probability=0.7,
                multiple_backspace_prob=0.25,
                substitution_prob=0.5,
                insertion_prob=0.25,
                deletion_prob=0.15,
                transposition_prob=0.1,
                punctuation_error_rate=0.12,
                number_error_rate=0.15,
                symbol_error_rate=0.2,
                shift_error_rate=0.25
            ),
            emitter_config=EmitterConfig(
                emitter_type=EmitterType.PYAUTOGUI,
                jitter_enabled=True,
                jitter_magnitude=0.05,
                drift_correction=True,
                drift_threshold=0.15,
                fallback_enabled=True,
                logging_enabled=True,
                max_retry_attempts=4
            ),
            target_wpm=45,
            variability_level=0.8,
            realism_score=0.9,
            complexity_level=0.7,
            recommended_for=["long sessions", "end-of-day typing", "realistic simulation"],
            tags=["fatigued", "slow", "error-prone", "realistic"]
        )
        
        # Professional Typist Profile
        self.profiles["professional"] = BehaviorProfile(
            name="Professional Typist",
            category=ProfileCategory.PROFESSIONAL,
            description="High-speed, accurate typing with minimal errors",
            timing_profile=TimingProfile(
                base_wpm=85,
                variability=0.15,
                burst_probability=0.2,
                burst_duration_factor=0.6,
                pause_frequency=0.2,
                pause_duration_mean=0.25,
                pause_duration_std=0.08,
                fatigue_rate=0.03,
                rhythm_drift=0.15,
                warmup_duration=15.0,
                base_delay_mu=0.07,
                base_delay_sigma=0.02,
                burst_delay_mu=0.04,
                burst_delay_sigma=0.01,
                pause_delay_mu=0.3,
                pause_delay_std=0.1
            ),
            error_profile=ErrorProfile(
                base_error_rate=0.008,
                speed_error_factor=0.2,
                fatigue_error_factor=0.05,
                complexity_error_factor=0.08,
                correction_delay_mean=0.15,
                correction_delay_std=0.05,
                backspace_probability=0.98,
                multiple_backspace_prob=0.02,
                substitution_prob=0.85,
                insertion_prob=0.08,
                deletion_prob=0.04,
                transposition_prob=0.03,
                punctuation_error_rate=0.01,
                number_error_rate=0.015,
                symbol_error_rate=0.02,
                shift_error_rate=0.04
            ),
            emitter_config=EmitterConfig(
                emitter_type=EmitterType.WIN32_API,
                jitter_enabled=False,
                jitter_magnitude=0.005,
                drift_correction=True,
                drift_threshold=0.03,
                fallback_enabled=True,
                logging_enabled=True,
                max_retry_attempts=2
            ),
            target_wpm=85,
            variability_level=0.3,
            realism_score=0.5,
            complexity_level=0.4,
            recommended_for=["professional work", "fast typing", "accuracy-focused"],
            tags=["fast", "accurate", "professional", "efficient"]
        )
        
        # Cautious Typist Profile
        self.profiles["cautious"] = BehaviorProfile(
            name="Cautious Typist",
            category=ProfileCategory.CAUTIOUS,
            description="Slow, deliberate typing with careful consideration",
            timing_profile=TimingProfile(
                base_wpm=35,
                variability=0.2,
                burst_probability=0.02,
                burst_duration_factor=0.9,
                pause_frequency=0.4,
                pause_duration_mean=1.0,
                pause_duration_std=0.3,
                fatigue_rate=0.01,
                rhythm_drift=0.2,
                warmup_duration=40.0,
                base_delay_mu=0.25,
                base_delay_sigma=0.06,
                burst_delay_mu=0.22,
                burst_delay_sigma=0.04,
                pause_delay_mu=1.2,
                pause_duration_std=0.4
            ),
            error_profile=ErrorProfile(
                base_error_rate=0.012,
                speed_error_factor=0.1,
                fatigue_error_factor=0.02,
                complexity_error_factor=0.15,
                correction_delay_mean=0.5,
                correction_delay_std=0.2,
                backspace_probability=0.9,
                multiple_backspace_prob=0.08,
                substitution_prob=0.75,
                insertion_prob=0.08,
                deletion_prob=0.12,
                transposition_prob=0.05,
                punctuation_error_rate=0.015,
                number_error_rate=0.02,
                symbol_error_rate=0.03,
                shift_error_rate=0.06
            ),
            emitter_config=EmitterConfig(
                emitter_type=EmitterType.PYAUTOGUI,
                jitter_enabled=False,
                jitter_magnitude=0.01,
                drift_correction=True,
                drift_threshold=0.08,
                fallback_enabled=True,
                logging_enabled=True,
                max_retry_attempts=2
            ),
            target_wpm=35,
            variability_level=0.4,
            realism_score=0.7,
            complexity_level=0.5,
            recommended_for=["careful work", "form filling", "learning"],
            tags=["slow", "careful", "deliberate", "accurate"]
        )
        
        # Casual Typist Profile
        self.profiles["casual"] = BehaviorProfile(
            name="Casual Typist",
            category=ProfileCategory.CASUAL,
            description="Relaxed, informal typing with moderate speed and errors",
            timing_profile=TimingProfile(
                base_wpm=55,
                variability=0.35,
                burst_probability=0.25,
                burst_duration_factor=0.65,
                pause_frequency=0.35,
                pause_duration_mean=0.6,
                pause_duration_std=0.25,
                fatigue_rate=0.12,
                rhythm_drift=0.35,
                warmup_duration=25.0,
                base_delay_mu=0.11,
                base_delay_sigma=0.05,
                burst_delay_mu=0.07,
                burst_delay_sigma=0.025,
                pause_delay_mu=0.7,
                pause_duration_std=0.3
            ),
            error_profile=ErrorProfile(
                base_error_rate=0.04,
                speed_error_factor=0.5,
                fatigue_error_factor=0.25,
                complexity_error_factor=0.2,
                correction_delay_mean=0.45,
                correction_delay_std=0.18,
                backspace_probability=0.8,
                multiple_backspace_prob=0.12,
                substitution_prob=0.6,
                insertion_prob=0.18,
                deletion_prob=0.12,
                transposition_prob=0.1,
                punctuation_error_rate=0.05,
                number_error_rate=0.07,
                symbol_error_rate=0.1,
                shift_error_rate=0.15
            ),
            emitter_config=EmitterConfig(
                emitter_type=EmitterType.PYAUTOGUI,
                jitter_enabled=True,
                jitter_magnitude=0.025,
                drift_correction=True,
                drift_threshold=0.12,
                fallback_enabled=True,
                logging_enabled=True,
                max_retry_attempts=3
            ),
            target_wpm=55,
            variability_level=0.6,
            realism_score=0.85,
            complexity_level=0.55,
            recommended_for=["casual writing", "emails", "everyday typing"],
            tags=["relaxed", "moderate", "natural", "everyday"]
        )
    
    def get_profile(self, name: str) -> Optional[BehaviorProfile]:
        """Get a profile by name"""
        return self.profiles.get(name)
    
    def get_all_profiles(self) -> Dict[str, BehaviorProfile]:
        """Get all available profiles"""
        return self.profiles.copy()
    
    def get_profiles_by_category(self, category: ProfileCategory) -> List[BehaviorProfile]:
        """Get profiles by category"""
        return [p for p in self.profiles.values() if p.category == category]
    
    def get_profiles_by_tag(self, tag: str) -> List[BehaviorProfile]:
        """Get profiles by tag"""
        return [p for p in self.profiles.values() if tag in p.tags]
    
    def search_profiles(self, query: str) -> List[BehaviorProfile]:
        """Search profiles by name, description, or tags"""
        query = query.lower()
        results = []
        
        for profile in self.profiles.values():
            if (query in profile.name.lower() or 
                query in profile.description.lower() or
                any(query in tag.lower() for tag in profile.tags)):
                results.append(profile)
        
        return results
    
    def validate_profile(self, profile: BehaviorProfile) -> List[str]:
        """Validate a profile and return list of issues"""
        issues = []
        
        # Check timing profile
        if profile.timing_profile.base_wpm <= 0 or profile.timing_profile.base_wpm > 200:
            issues.append("Base WPM must be between 0 and 200")
        
        if profile.timing_profile.variability < 0 or profile.timing_profile.variability > 1:
            issues.append("Variability must be between 0 and 1")
        
        # Check error profile
        if profile.error_profile.base_error_rate < 0 or profile.error_profile.base_error_rate > 0.5:
            issues.append("Base error rate must be between 0 and 0.5")
        
        # Check metadata
        if profile.target_wpm <= 0 or profile.target_wpm > 200:
            issues.append("Target WPM must be between 0 and 200")
        
        if profile.variability_level < 0 or profile.variability_level > 1:
            issues.append("Variability level must be between 0 and 1")
        
        if profile.realism_score < 0 or profile.realism_score > 1:
            issues.append("Realism score must be between 0 and 1")
        
        return issues
    
    def save_profile(self, profile: BehaviorProfile, filepath: Path):
        """Save a profile to JSON file"""
        # Convert to serializable format
        profile_dict = {
            "name": profile.name,
            "category": profile.category.value,
            "description": profile.description,
            "timing_profile": {
                "base_wpm": profile.timing_profile.base_wpm,
                "variability": profile.timing_profile.variability,
                "burst_probability": profile.timing_profile.burst_probability,
                "burst_duration_factor": profile.timing_profile.burst_duration_factor,
                "pause_frequency": profile.timing_profile.pause_frequency,
                "pause_duration_mean": profile.timing_profile.pause_duration_mean,
                "pause_duration_std": profile.timing_profile.pause_duration_std,
                "fatigue_rate": profile.timing_profile.fatigue_rate,
                "rhythm_drift": profile.timing_profile.rhythm_drift,
                "warmup_duration": profile.timing_profile.warmup_duration,
                "base_delay_mu": profile.timing_profile.base_delay_mu,
                "base_delay_sigma": profile.timing_profile.base_delay_sigma,
                "burst_delay_mu": profile.timing_profile.burst_delay_mu,
                "burst_delay_sigma": profile.timing_profile.burst_delay_sigma,
                "pause_delay_mu": profile.timing_profile.pause_delay_mu,
                "pause_delay_sigma": profile.timing_profile.pause_delay_sigma
            },
            "error_profile": {
                "base_error_rate": profile.error_profile.base_error_rate,
                "speed_error_factor": profile.error_profile.speed_error_factor,
                "fatigue_error_factor": profile.error_profile.fatigue_error_factor,
                "complexity_error_factor": profile.error_profile.complexity_error_factor,
                "correction_delay_mean": profile.error_profile.correction_delay_mean,
                "correction_delay_std": profile.error_profile.correction_delay_std,
                "backspace_probability": profile.error_profile.backspace_probability,
                "multiple_backspace_prob": profile.error_profile.multiple_backspace_prob,
                "substitution_prob": profile.error_profile.substitution_prob,
                "insertion_prob": profile.error_profile.insertion_prob,
                "deletion_prob": profile.error_profile.deletion_prob,
                "transposition_prob": profile.error_profile.transposition_prob,
                "punctuation_error_rate": profile.error_profile.punctuation_error_rate,
                "number_error_rate": profile.error_profile.number_error_rate,
                "symbol_error_rate": profile.error_profile.symbol_error_rate,
                "shift_error_rate": profile.error_profile.shift_error_rate
            },
            "emitter_config": {
                "emitter_type": profile.emitter_config.emitter_type.value,
                "jitter_enabled": profile.emitter_config.jitter_enabled,
                "jitter_magnitude": profile.emitter_config.jitter_magnitude,
                "drift_correction": profile.emitter_config.drift_correction,
                "drift_threshold": profile.emitter_config.drift_threshold,
                "fallback_enabled": profile.emitter_config.fallback_enabled,
                "logging_enabled": profile.emitter_config.logging_enabled,
                "max_retry_attempts": profile.emitter_config.max_retry_attempts
            },
            "target_wpm": profile.target_wpm,
            "variability_level": profile.variability_level,
            "realism_score": profile.realism_score,
            "complexity_level": profile.complexity_level,
            "recommended_for": profile.recommended_for,
            "tags": profile.tags
        }
        
        with open(filepath, 'w') as f:
            json.dump(profile_dict, f, indent=2)
    
    def load_profile(self, filepath: Path) -> Optional[BehaviorProfile]:
        """Load a profile from JSON file"""
        try:
            with open(filepath, 'r') as f:
                profile_dict = json.load(f)
            
            # Reconstruct profile
            timing_profile = TimingProfile(**profile_dict["timing_profile"])
            error_profile = ErrorProfile(**profile_dict["error_profile"])
            
            emitter_config_dict = profile_dict["emitter_config"]
            emitter_config_dict["emitter_type"] = EmitterType(emitter_config_dict["emitter_type"])
            emitter_config = EmitterConfig(**emitter_config_dict)
            
            profile = BehaviorProfile(
                name=profile_dict["name"],
                category=ProfileCategory(profile_dict["category"]),
                description=profile_dict["description"],
                timing_profile=timing_profile,
                error_profile=error_profile,
                emitter_config=emitter_config,
                target_wpm=profile_dict["target_wpm"],
                variability_level=profile_dict["variability_level"],
                realism_score=profile_dict["realism_score"],
                complexity_level=profile_dict["complexity_level"],
                recommended_for=profile_dict["recommended_for"],
                tags=profile_dict["tags"]
            )
            
            return profile
        
        except Exception as e:
            print(f"Error loading profile: {e}")
            return None
    
    def create_custom_profile(self, name: str, base_profile: str, 
                            modifications: Dict) -> Optional[BehaviorProfile]:
        """Create a custom profile based on an existing one"""
        base = self.get_profile(base_profile)
        if not base:
            return None
        
        # Create a copy and apply modifications
        # This is a simplified version - in practice, you'd want more sophisticated merging
        new_profile = BehaviorProfile(
            name=name,
            category=base.category,
            description=base.description + " (modified)",
            timing_profile=base.timing_profile,
            error_profile=base.error_profile,
            emitter_config=base.emitter_config,
            target_wpm=modifications.get("target_wpm", base.target_wpm),
            variability_level=modifications.get("variability_level", base.variability_level),
            realism_score=modifications.get("realism_score", base.realism_score),
            complexity_level=modifications.get("complexity_level", base.complexity_level),
            recommended_for=base.recommended_for,
            tags=base.tags + modifications.get("additional_tags", [])
        )
        
        # Apply specific modifications
        if "timing_modifications" in modifications:
            for key, value in modifications["timing_modifications"].items():
                if hasattr(new_profile.timing_profile, key):
                    setattr(new_profile.timing_profile, key, value)
        
        if "error_modifications" in modifications:
            for key, value in modifications["error_modifications"].items():
                if hasattr(new_profile.error_profile, key):
                    setattr(new_profile.error_profile, key, value)
        
        # Validate the new profile
        issues = self.validate_profile(new_profile)
        if issues:
            print(f"Validation issues: {issues}")
            return None
        
        return new_profile


# Example usage and testing
if __name__ == "__main__":
    # Create profile manager
    manager = ProfileManager()
    
    # List all profiles
    print("Available Profiles:")
    print("-" * 40)
    for name, profile in manager.get_all_profiles().items():
        print(f"{name}: {profile.description}")
        print(f"  Target WPM: {profile.target_wpm}, Realism: {profile.realism_score:.2f}")
    
    # Search for profiles
    print("\nSearch Results for 'fast':")
    print("-" * 30)
    fast_profiles = manager.search_profiles("fast")
    for profile in fast_profiles:
        print(f"{profile.name}: {profile.description}")
    
    # Create custom profile
    print("\nCreating Custom Profile:")
    print("-" * 30)
    custom = manager.create_custom_profile(
        "Fast Professional",
        "professional",
        {
            "target_wpm": 95,
            "timing_modifications": {"base_wpm": 95, "variability": 0.2},
            "additional_tags": ["very-fast", "expert"]
        }
    )
    
    if custom:
        print(f"Created: {custom.name}")
        print(f"Target WPM: {custom.target_wpm}")
        print(f"Tags: {', '.join(custom.tags)}")
    else:
        print("Failed to create custom profile")

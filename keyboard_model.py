"""
Keyboard and Finger Mapping System for Realistic Typing Simulation

This module provides the foundation for modeling human typing behavior by mapping
keys to fingers and calculating movement costs between keys.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math


class Hand(Enum):
    LEFT = "left"
    RIGHT = "right"


class Finger(Enum):
    LEFT_PINKY = "left_pinky"
    LEFT_RING = "left_ring"
    LEFT_MIDDLE = "left_middle"
    LEFT_INDEX = "left_index"
    RIGHT_INDEX = "right_index"
    RIGHT_MIDDLE = "right_middle"
    RIGHT_RING = "right_ring"
    RIGHT_PINKY = "right_pinky"
    LEFT_THUMB = "left_thumb"
    RIGHT_THUMB = "right_thumb"


@dataclass
class KeyMapping:
    character: str
    finger: Finger
    position: Tuple[int, int]  # (row, col) on keyboard grid
    hand: Hand
    shift_required: bool = False
    proximity_weight: float = 1.0  # For error generation


@dataclass
class MovementCost:
    base_cost: float = 1.0
    same_hand_penalty: float = 1.2
    same_finger_penalty: float = 1.5
    cross_hand_bonus: float = 0.8
    stretch_penalty: float = 0.1
    stretch_threshold: float = 2.0


class QWERTYLayout:
    """QWERTY keyboard layout with finger assignments"""
    
    def __init__(self):
        self.key_map: Dict[str, KeyMapping] = {}
        self._setup_layout()
        self.movement_cost = MovementCost()
    
    def _setup_layout(self):
        """Setup QWERTY keyboard layout with proper finger assignments"""
        
        # Top row (numbers and symbols)
        top_row = [
            ('1', Finger.LEFT_PINKY), ('2', Finger.LEFT_RING), ('3', Finger.LEFT_MIDDLE),
            ('4', Finger.LEFT_INDEX), ('5', Finger.LEFT_INDEX), ('6', Finger.RIGHT_INDEX),
            ('7', Finger.RIGHT_INDEX), ('8', Finger.RIGHT_MIDDLE), ('9', Finger.RIGHT_RING),
            ('0', Finger.RIGHT_PINKY)
        ]
        
        # Home row
        home_row = [
            ('q', Finger.LEFT_PINKY), ('w', Finger.LEFT_RING), ('e', Finger.LEFT_MIDDLE),
            ('r', Finger.LEFT_INDEX), ('t', Finger.LEFT_INDEX), ('y', Finger.RIGHT_INDEX),
            ('u', Finger.RIGHT_INDEX), ('i', Finger.RIGHT_MIDDLE), ('o', Finger.RIGHT_RING),
            ('p', Finger.RIGHT_PINKY)
        ]
        
        # Middle row (ASDF...)
        middle_row = [
            ('a', Finger.LEFT_PINKY), ('s', Finger.LEFT_RING), ('d', Finger.LEFT_MIDDLE),
            ('f', Finger.LEFT_INDEX), ('g', Finger.LEFT_INDEX), ('h', Finger.RIGHT_INDEX),
            ('j', Finger.RIGHT_INDEX), ('k', Finger.RIGHT_MIDDLE), ('l', Finger.RIGHT_RING),
            (';', Finger.RIGHT_PINKY)
        ]
        
        # Bottom row
        bottom_row = [
            ('z', Finger.LEFT_PINKY), ('x', Finger.LEFT_RING), ('c', Finger.LEFT_MIDDLE),
            ('v', Finger.LEFT_INDEX), ('b', Finger.LEFT_INDEX), ('n', Finger.RIGHT_INDEX),
            ('m', Finger.RIGHT_INDEX), (',', Finger.RIGHT_MIDDLE), ('.', Finger.RIGHT_RING),
            ('/', Finger.RIGHT_PINKY)
        ]
        
        # Space bar
        space_mapping = KeyMapping(
            character=' ',
            finger=Finger.RIGHT_THUMB,
            position=(4, 5),
            hand=Hand.RIGHT,
            proximity_weight=0.5
        )
        self.key_map[' '] = space_mapping
        
        # Process all rows
        for row_idx, row in enumerate([top_row, home_row, middle_row, bottom_row]):
            for col_idx, (char, finger) in enumerate(row):
                hand = Hand.LEFT if finger.value.startswith('left') else Hand.RIGHT
                
                mapping = KeyMapping(
                    character=char,
                    finger=finger,
                    position=(row_idx, col_idx),
                    hand=hand,
                    proximity_weight=1.0
                )
                self.key_map[char] = mapping
        
        # Add shifted characters
        shifted_chars = {
            '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
            '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
            'Q': 'q', 'W': 'w', 'E': 'e', 'R': 'r', 'T': 't',
            'Y': 'y', 'U': 'u', 'I': 'i', 'O': 'o', 'P': 'p',
            'A': 'a', 'S': 's', 'D': 'd', 'F': 'f', 'G': 'g',
            'H': 'h', 'J': 'j', 'K': 'k', 'L': 'l',
            'Z': 'z', 'X': 'x', 'C': 'c', 'V': 'v', 'B': 'b',
            'N': 'n', 'M': 'm'
        }
        
        for shifted, base in shifted_chars.items():
            if base in self.key_map:
                base_mapping = self.key_map[base]
                shifted_mapping = KeyMapping(
                    character=shifted,
                    finger=base_mapping.finger,
                    position=base_mapping.position,
                    hand=base_mapping.hand,
                    shift_required=True,
                    proximity_weight=base_mapping.proximity_weight
                )
                self.key_map[shifted] = shifted_mapping
    
    def get_mapping(self, character: str) -> Optional[KeyMapping]:
        """Get key mapping for a character"""
        return self.key_map.get(character)
    
    def get_adjacent_keys(self, character: str) -> List[KeyMapping]:
        """Get keys adjacent to the given character for error generation"""
        if character not in self.key_map:
            return []
        
        target_mapping = self.key_map[character]
        adjacent = []
        
        for char, mapping in self.key_map.items():
            if char == character:
                continue
                
            distance = self._calculate_distance(target_mapping, mapping)
            if distance <= 1.5:  # Adjacent or near-adjacent keys
                # Adjust proximity weight based on distance
                adjacent_mapping = KeyMapping(
                    character=mapping.character,
                    finger=mapping.finger,
                    position=mapping.position,
                    hand=mapping.hand,
                    shift_required=mapping.shift_required,
                    proximity_weight=max(0.1, 1.0 - distance * 0.3)
                )
                adjacent.append(adjacent_mapping)
        
        return sorted(adjacent, key=lambda x: x.proximity_weight, reverse=True)
    
    def _calculate_distance(self, mapping1: KeyMapping, mapping2: KeyMapping) -> float:
        """Calculate Euclidean distance between two keys"""
        pos1 = mapping1.position
        pos2 = mapping2.position
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)


class KeyboardModel:
    """Main keyboard model for calculating movement costs and timing"""
    
    def __init__(self, layout: QWERTYLayout = None):
        self.layout = layout or QWERTYLayout()
        self.movement_cost = MovementCost()
        
        # Common bigram frequencies for optimization
        self.common_bigrams = {
            'th', 'he', 'in', 'er', 'an', 're', 'ed', 'nd', 'on', 'en',
            'es', 'st', 'nt', 'to', 'it', 'ou', 'ea', 'of', 'ng', 'as'
        }
    
    def movement_cost(self, from_key: str, to_key: str) -> float:
        """Calculate movement cost between two keys"""
        from_mapping = self.layout.get_mapping(from_key)
        to_mapping = self.layout.get_mapping(to_key)
        
        if not from_mapping or not to_mapping:
            return self.movement_cost.base_cost
        
        # Start with base cost
        cost = self.movement_cost.base_cost
        
        # Apply hand-based modifiers
        if from_mapping.hand == to_mapping.hand:
            cost *= self.movement_cost.same_hand_penalty
        else:
            cost *= self.movement_cost.cross_hand_bonus
        
        # Apply finger-based modifiers
        if from_mapping.finger == to_mapping.finger:
            cost *= self.movement_cost.same_finger_penalty
        
        # Calculate distance and apply stretch penalty
        distance = self.layout._calculate_distance(from_mapping, to_mapping)
        if distance > self.movement_cost.stretch_threshold:
            stretch_factor = 1 + self.movement_cost.stretch_penalty * (distance - self.movement_cost.stretch_threshold)
            cost *= stretch_factor
        
        # Optimize for common bigrams
        bigram = (from_key + to_key).lower()
        if bigram in self.common_bigrams:
            cost *= 0.7  # Faster for common combinations
        
        return max(0.1, cost)  # Ensure minimum cost
    
    def get_finger_transition_difficulty(self, from_key: str, to_key: str) -> float:
        """Get difficulty score for finger transition (0-1 scale)"""
        from_mapping = self.layout.get_mapping(from_key)
        to_mapping = self.layout.get_mapping(to_key)
        
        if not from_mapping or not to_mapping:
            return 0.5
        
        # Same finger transitions are hardest
        if from_mapping.finger == to_mapping.finger:
            return 0.9
        
        # Same hand but different fingers
        if from_mapping.hand == to_mapping.hand:
            return 0.6
        
        # Cross-hand transitions are easiest
        return 0.3
    
    def is_awkward_stretch(self, from_key: str, to_key: str) -> bool:
        """Determine if transition requires awkward finger stretch"""
        from_mapping = self.layout.get_mapping(from_key)
        to_mapping = self.layout.get_mapping(to_key)
        
        if not from_mapping or not to_mapping:
            return False
        
        distance = self.layout._calculate_distance(from_mapping, to_mapping)
        
        # Check for specific awkward patterns
        awkward_patterns = [
            (Finger.LEFT_PINKY, Finger.RIGHT_PINKY),
            (Finger.RIGHT_PINKY, Finger.LEFT_PINKY),
            (Finger.LEFT_RING, Finger.RIGHT_INDEX),
            (Finger.RIGHT_INDEX, Finger.LEFT_RING)
        ]
        
        if (from_mapping.finger, to_mapping.finger) in awkward_patterns:
            return True
        
        return distance > 2.5
    
    def get_typing_rhythm_impact(self, keys: List[str]) -> float:
        """Calculate overall rhythm impact for a sequence of keys"""
        if len(keys) < 2:
            return 1.0
        
        total_cost = 0
        for i in range(len(keys) - 1):
            total_cost += self.movement_cost(keys[i], keys[i + 1])
        
        avg_cost = total_cost / (len(keys) - 1)
        
        # Normalize to 0-1 scale (higher cost = more disruptive to rhythm)
        return min(1.0, avg_cost / 3.0)


# Example usage and testing
if __name__ == "__main__":
    # Create keyboard model
    model = KeyboardModel()
    
    # Test movement costs
    test_pairs = [
        ('a', 's'),  # Same hand, adjacent fingers
        ('f', 'j'),  # Cross-hand, index fingers
        ('q', 'p'),  # Same hand, far apart
        ('t', 'h'),  # Cross-hand, middle fingers
    ]
    
    print("Movement Cost Analysis:")
    print("-" * 40)
    for from_key, to_key in test_pairs:
        cost = model.movement_cost(from_key, to_key)
        difficulty = model.get_finger_transition_difficulty(from_key, to_key)
        awkward = model.is_awkward_stretch(from_key, to_key)
        
        print(f"{from_key} -> {to_key}: Cost={cost:.2f}, Difficulty={difficulty:.2f}, Awkward={awkward}")
    
    # Test adjacent keys for error generation
    print("\nAdjacent Keys to 'f':")
    print("-" * 30)
    for adj in model.layout.get_adjacent_keys('f'):
        print(f"'{adj.character}' (weight: {adj.proximity_weight:.2f})")

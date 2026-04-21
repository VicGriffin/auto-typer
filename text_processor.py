"""
Text Processing and Semantic Chunking Module

This module handles the parsing and semantic analysis of input text to create
meaningful chunks that influence typing timing and behavior.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import re
from collections import defaultdict


class ChunkType(Enum):
    WORD = "word"
    PUNCTUATION = "punctuation"
    SPACE = "space"
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
    NUMBER = "number"
    SYMBOL = "symbol"


@dataclass
class TextChunk:
    content: str
    chunk_type: ChunkType
    position: int
    semantic_weight: float  # Influences pause duration (0.0-1.0)
    complexity_score: float  # Affects error probability (0.0-1.0)
    typing_difficulty: float  # Overall difficulty (0.0-1.0)
    
    def __post_init__(self):
        # Ensure values are in valid range
        self.semantic_weight = max(0.0, min(1.0, self.semantic_weight))
        self.complexity_score = max(0.0, min(1.0, self.complexity_score))
        self.typing_difficulty = max(0.0, min(1.0, self.typing_difficulty))


@dataclass
class TextAnalysis:
    chunks: List[TextChunk]
    total_words: int
    total_characters: int
    avg_word_length: float
    punctuation_density: float
    complexity_score: float
    estimated_typing_time: float  # in seconds


class TextProcessor:
    """Processes text into semantic chunks for realistic typing simulation"""
    
    def __init__(self):
        # Punctuation pause weights
        self.punctuation_weights = {
            ',': 0.3,      # Short pause
            ';': 0.4,      # Medium pause
            ':': 0.4,
            '.': 0.6,      # Sentence end pause
            '!': 0.7,      # Emphasis pause
            '?': 0.7,
            '\n': 0.8,     # Line break pause
            '\t': 0.5,     # Tab pause
        }
        
        # Complex patterns that require more attention
        self.complex_patterns = [
            r'\d{2,}',           # Multi-digit numbers
            r'[A-Z]{2,}',        # Acronyms
            r'[a-z]+[A-Z][a-z]+', # CamelCase
            r'\w+\.\w+',         # Dotted notation
            r'[^\w\s]',          # Special symbols
        ]
        
        # Common word frequencies (simplified)
        self.common_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have',
            'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you',
            'do', 'at', 'this', 'but', 'his', 'by', 'from'
        }
    
    def parse_text(self, text: str) -> TextAnalysis:
        """Parse text into semantic chunks and analyze structure"""
        chunks = self._create_chunks(text)
        analysis = self._analyze_text(chunks)
        
        return TextAnalysis(
            chunks=chunks,
            total_words=analysis['total_words'],
            total_characters=analysis['total_characters'],
            avg_word_length=analysis['avg_word_length'],
            punctuation_density=analysis['punctuation_density'],
            complexity_score=analysis['complexity_score'],
            estimated_typing_time=analysis['estimated_time']
        )
    
    def _create_chunks(self, text: str) -> List[TextChunk]:
        """Create semantic chunks from text"""
        chunks = []
        position = 0
        
        # Use regex to find all meaningful segments
        pattern = r'(\w+|\s+|[^\w\s])'
        matches = re.finditer(pattern, text)
        
        prev_chunk = None
        
        for match in matches:
            content = match.group()
            chunk_type = self._determine_chunk_type(content)
            
            # Calculate semantic properties
            semantic_weight = self._calculate_semantic_weight(content, chunk_type, prev_chunk)
            complexity_score = self._calculate_complexity_score(content, chunk_type)
            typing_difficulty = self._calculate_typing_difficulty(content, chunk_type)
            
            chunk = TextChunk(
                content=content,
                chunk_type=chunk_type,
                position=position,
                semantic_weight=semantic_weight,
                complexity_score=complexity_score,
                typing_difficulty=typing_difficulty
            )
            
            chunks.append(chunk)
            prev_chunk = chunk
            position += len(content)
        
        return chunks
    
    def _determine_chunk_type(self, content: str) -> ChunkType:
        """Determine the type of text chunk"""
        if content.isspace():
            if '\n' in content:
                return ChunkType.PARAGRAPH_END if content.count('\n') > 1 else ChunkType.SENTENCE_END
            return ChunkType.SPACE
        elif content.isdigit() or (content.replace('.', '').replace('-', '').isdigit()):
            return ChunkType.NUMBER
        elif content.isalpha():
            return ChunkType.WORD
        elif content in '.,;:!?':
            return ChunkType.PUNCTUATION
        else:
            return ChunkType.SYMBOL
    
    def _calculate_semantic_weight(self, content: str, chunk_type: ChunkType, 
                                  prev_chunk: Optional[TextChunk]) -> float:
        """Calculate semantic weight based on content and context"""
        base_weight = 0.1
        
        if chunk_type == ChunkType.SPACE:
            # Check if it's after punctuation
            if prev_chunk and prev_chunk.chunk_type == ChunkType.PUNCTUATION:
                return self.punctuation_weights.get(prev_chunk.content, 0.3)
            return 0.05
        elif chunk_type == ChunkType.PUNCTUATION:
            return self.punctuation_weights.get(content, 0.3)
        elif chunk_type == ChunkType.PARAGRAPH_END:
            return 0.8
        elif chunk_type == ChunkType.SENTENCE_END:
            return 0.6
        elif chunk_type == ChunkType.WORD:
            # Longer words might need more attention
            if len(content) > 8:
                base_weight += 0.1
            # Uncommon words might require more focus
            if content.lower() not in self.common_words:
                base_weight += 0.05
            # All caps might require shift attention
            if content.isupper():
                base_weight += 0.1
        elif chunk_type == ChunkType.NUMBER:
            # Numbers often require more precision
            base_weight = 0.3 if len(content) <= 2 else 0.4
        elif chunk_type == ChunkType.SYMBOL:
            # Special symbols often require attention
            base_weight = 0.4
        
        return min(1.0, base_weight)
    
    def _calculate_complexity_score(self, content: str, chunk_type: ChunkType) -> float:
        """Calculate complexity score based on content patterns"""
        base_score = 0.1
        
        if chunk_type == ChunkType.WORD:
            # Check for complex patterns
            for pattern in self.complex_patterns:
                if re.match(pattern, content):
                    base_score += 0.2
            
            # Mixed case increases complexity
            if content != content.lower() and content != content.upper():
                base_score += 0.1
            
            # Repeated characters might be tricky
            if len(set(content)) < len(content) * 0.5:
                base_score += 0.1
                
        elif chunk_type == ChunkType.NUMBER:
            # Multi-digit numbers with special formatting
            if '.' in content or '-' in content:
                base_score = 0.4
            else:
                base_score = 0.2
                
        elif chunk_type == ChunkType.SYMBOL:
            # Some symbols are harder to type
            difficult_symbols = {'@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+', '='}
            if content in difficult_symbols:
                base_score = 0.5
            else:
                base_score = 0.3
        
        return min(1.0, base_score)
    
    def _calculate_typing_difficulty(self, content: str, chunk_type: ChunkType) -> float:
        """Calculate overall typing difficulty"""
        # Combine semantic weight and complexity
        semantic = self._calculate_semantic_weight(content, chunk_type, None)
        complexity = self._calculate_complexity_score(content, chunk_type)
        
        # Weight the combination
        difficulty = semantic * 0.6 + complexity * 0.4
        
        # Add length factor for longer chunks
        if len(content) > 10:
            difficulty += 0.1
        
        return min(1.0, difficulty)
    
    def _analyze_text(self, chunks: List[TextChunk]) -> Dict[str, float]:
        """Analyze overall text statistics"""
        total_chars = sum(len(chunk.content) for chunk in chunks)
        word_chunks = [c for c in chunks if c.chunk_type == ChunkType.WORD]
        total_words = len(word_chunks)
        
        # Calculate average word length
        if word_chunks:
            avg_word_length = sum(len(chunk.content) for chunk in word_chunks) / len(word_chunks)
        else:
            avg_word_length = 0
        
        # Calculate punctuation density
        punct_chunks = [c for c in chunks if c.chunk_type == ChunkType.PUNCTUATION]
        punctuation_density = len(punct_chunks) / max(1, total_words)
        
        # Calculate overall complexity
        if chunks:
            avg_complexity = sum(chunk.complexity_score for chunk in chunks) / len(chunks)
        else:
            avg_complexity = 0
        
        # Estimate typing time (simplified - base 60 WPM)
        base_wpm = 60
        if total_words > 0:
            estimated_time = (total_words / base_wpm) * 60  # seconds
        else:
            estimated_time = 0
        
        return {
            'total_words': total_words,
            'total_characters': total_chars,
            'avg_word_length': avg_word_length,
            'punctuation_density': punctuation_density,
            'complexity_score': avg_complexity,
            'estimated_time': estimated_time
        }
    
    def get_pause_points(self, chunks: List[TextChunk]) -> List[Tuple[int, float]]:
        """Identify points where pauses should occur and their durations"""
        pause_points = []
        
        for i, chunk in enumerate(chunks):
            if chunk.chunk_type in [ChunkType.SPACE, ChunkType.PUNCTUATION, 
                                   ChunkType.SENTENCE_END, ChunkType.PARAGRAPH_END]:
                if chunk.semantic_weight > 0.1:  # Only significant pauses
                    pause_points.append((i, chunk.semantic_weight))
        
        return pause_points
    
    def get_burst_segments(self, chunks: List[TextChunk]) -> List[Tuple[int, int]]:
        """Identify segments suitable for burst typing"""
        segments = []
        start_idx = 0
        
        for i, chunk in enumerate(chunks):
            # End burst at significant pause points
            if chunk.semantic_weight > 0.4:
                if i - start_idx > 1:  # Only create segments with multiple chunks
                    segments.append((start_idx, i))
                start_idx = i + 1
        
        # Add final segment if there's remaining content
        if start_idx < len(chunks) - 1:
            segments.append((start_idx, len(chunks)))
        
        return segments
    
    def calculate_rhythm_pattern(self, chunks: List[TextChunk]) -> List[float]:
        """Calculate rhythm pattern for the text"""
        rhythm = []
        
        for chunk in chunks:
            if chunk.chunk_type == ChunkType.SPACE:
                rhythm.append(chunk.semantic_weight)
            else:
                # For non-space chunks, use inverse of difficulty
                rhythm.append(1.0 - chunk.typing_difficulty * 0.5)
        
        return rhythm


# Example usage and testing
if __name__ == "__main__":
    processor = TextProcessor()
    
    # Test text with various elements
    test_text = "Hello, world! This is a test of the text processor. It handles numbers like 123, symbols like @#$, and various punctuation... Does it work well?"
    
    analysis = processor.parse_text(test_text)
    
    print(f"Text Analysis:")
    print(f"Total words: {analysis.total_words}")
    print(f"Total characters: {analysis.total_characters}")
    print(f"Avg word length: {analysis.avg_word_length:.2f}")
    print(f"Punctuation density: {analysis.punctuation_density:.3f}")
    print(f"Complexity score: {analysis.complexity_score:.3f}")
    print(f"Estimated time: {analysis.estimated_typing_time:.2f}s")
    
    print("\nFirst 10 chunks:")
    print("-" * 60)
    for i, chunk in enumerate(analysis.chunks[:10]):
        print(f"{i:2d}: '{chunk.content}' ({chunk.chunk_type.value}) "
              f"W:{chunk.semantic_weight:.2f} C:{chunk.complexity_score:.2f} "
              f"D:{chunk.typing_difficulty:.2f}")
    
    print("\nPause points:")
    print("-" * 30)
    pauses = processor.get_pause_points(analysis.chunks)
    for idx, weight in pauses[:5]:
        chunk = analysis.chunks[idx]
        print(f"Position {idx}: '{chunk.content}' (weight: {weight:.2f})")
    
    print("\nBurst segments:")
    print("-" * 30)
    bursts = processor.get_burst_segments(analysis.chunks)
    for start, end in bursts[:3]:
        segment_text = ''.join(c.content for c in analysis.chunks[start:end])
        print(f"Segment {start}-{end}: '{segment_text[:30]}...'")

"""
Content Quality Assessment Module - Clean Implementation

This module provides comprehensive content quality metrics and assessment
for extracted text content, helping evaluate extraction effectiveness.

This is a clean, minimal implementation that addresses all historical problems
while providing detailed quality analysis capabilities.
"""

import logging
import math
import re
from collections import Counter
from typing import Any, Dict

logger = logging.getLogger(__name__)


def calculate_quality_metrics(text: str) -> Dict[str, Any]:
    """
    Calculate comprehensive quality metrics for extracted text content.
    
    Returns a structured dictionary with readability, diversity, structure,
    noise, coherence, and aggregate quality scores.
    """
    try:
        if not text or not text.strip():
            return _empty_quality_metrics()
        
        text = text.strip()
        
        # Basic text statistics
        words = text.split()
        sentences = _split_sentences(text)
        paragraphs = _split_paragraphs(text)
        
        word_count = len(words)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        
        if word_count == 0:
            return _empty_quality_metrics()
        
        # Calculate individual metric categories
        readability = _calculate_readability_metrics(text, words, sentences)
        diversity = _calculate_diversity_metrics(words)
        structure = _calculate_structure_metrics(text, words, sentences, paragraphs)
        noise = _calculate_noise_metrics(text, words)
        coherence = _calculate_coherence_metrics(sentences)
        aggregate_score = _calculate_aggregate_score(readability, diversity, structure, noise, coherence)
        
        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "readability": readability,
            "diversity": diversity,
            "structure": structure,
            "noise": noise,
            "coherence": coherence,
            "aggregate_score": aggregate_score
        }
        
    except Exception as e:
        logger.error(f"Quality metrics calculation failed: {e}")
        return _empty_quality_metrics()


def _empty_quality_metrics() -> Dict[str, Any]:
    """Return empty quality metrics structure."""
    return {
        "word_count": 0,
        "sentence_count": 0,
        "paragraph_count": 0,
        "readability": {
            "avg_sentence_length": 0.0,
            "avg_word_length_chars": 0.0,
            "avg_syllables_per_word": 0.0,
            "flesch_reading_ease_de": 0.0,
            "wiener_sachtextformel_v1": 0.0
        },
        "diversity": {
            "type_token_ratio": 0.0,
            "guiraud_r": 0.0,
            "herdans_c": 0.0,
            "yules_k": 0.0,
            "lexical_density": 0.0,
            "shannon_entropy": 0.0
        },
        "structure": {
            "paragraph_count": 0,
            "avg_paragraph_length": 0.0,
            "heading_count": 0,
            "heading_word_ratio": 0.0,
            "sentence_length_variance": 0.0,
            "has_good_structure": False
        },
        "noise": {
            "non_letter_ratio": 0.0,
            "caps_ratio": 0.0,
            "multi_punctuation_count": 0,
            "special_char_ratio": 0.0,
            "repetition_ratio": 0.0,
            "error_indicator_count": 0
        },
        "coherence": {
            "avg_sentence_overlap": 0.0,
            "coherence_score": 0.0
        },
        "aggregate_score": {
            "final_quality_score": 0.0,
            "likert_quality_score": 0.0
        }
    }


def _split_sentences(text: str) -> list:
    """Split text into sentences using simple heuristics."""
    # Simple sentence splitting - can be improved with more sophisticated NLP
    sentences = re.split(r'[.!?]+\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _split_paragraphs(text: str) -> list:
    """Split text into paragraphs."""
    paragraphs = re.split(r'\n\s*\n', text)
    return [p.strip() for p in paragraphs if p.strip()]


def _count_syllables(word: str) -> int:
    """Estimate syllable count for a word (German/English heuristic)."""
    word = word.lower()
    vowels = 'aeiouäöü'
    syllable_count = 0
    prev_was_vowel = False
    
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            syllable_count += 1
        prev_was_vowel = is_vowel
    
    # Adjust for silent e
    if word.endswith('e') and syllable_count > 1:
        syllable_count -= 1
    
    return max(1, syllable_count)


def _calculate_readability_metrics(text: str, words: list, sentences: list) -> Dict[str, float]:
    """Calculate readability metrics."""
    try:
        word_count = len(words)
        sentence_count = len(sentences)
        
        if sentence_count == 0:
            return {
                "avg_sentence_length": 0.0,
                "avg_word_length_chars": 0.0,
                "avg_syllables_per_word": 0.0,
                "flesch_reading_ease_de": 0.0,
                "wiener_sachtextformel_v1": 0.0
            }
        
        # Average sentence length
        avg_sentence_length = word_count / sentence_count
        
        # Average word length in characters
        total_chars = sum(len(word) for word in words)
        avg_word_length_chars = total_chars / word_count if word_count > 0 else 0
        
        # Average syllables per word
        total_syllables = sum(_count_syllables(word) for word in words)
        avg_syllables_per_word = total_syllables / word_count if word_count > 0 else 0
        
        # Flesch Reading Ease (adapted for German)
        flesch_reading_ease_de = 180 - avg_sentence_length - (58.5 * avg_syllables_per_word)
        
        # Wiener Sachtextformel (German readability)
        wiener_sachtextformel_v1 = (
            0.1935 * avg_sentence_length +
            0.1672 * (total_chars / word_count * 100) +
            0.1297 * avg_syllables_per_word -
            0.0327 * (word_count / sentence_count) -
            0.875
        )
        
        return {
            "avg_sentence_length": round(avg_sentence_length, 2),
            "avg_word_length_chars": round(avg_word_length_chars, 2),
            "avg_syllables_per_word": round(avg_syllables_per_word, 2),
            "flesch_reading_ease_de": round(flesch_reading_ease_de, 2),
            "wiener_sachtextformel_v1": round(wiener_sachtextformel_v1, 2)
        }
        
    except Exception as e:
        logger.error(f"Readability calculation failed: {e}")
        return {
            "avg_sentence_length": 0.0,
            "avg_word_length_chars": 0.0,
            "avg_syllables_per_word": 0.0,
            "flesch_reading_ease_de": 0.0,
            "wiener_sachtextformel_v1": 0.0
        }


def _calculate_diversity_metrics(words: list) -> Dict[str, float]:
    """Calculate lexical diversity metrics."""
    try:
        word_count = len(words)
        if word_count == 0:
            return {
                "type_token_ratio": 0.0,
                "guiraud_r": 0.0,
                "herdans_c": 0.0,
                "yules_k": 0.0,
                "lexical_density": 0.0,
                "shannon_entropy": 0.0
            }
        
        # Convert to lowercase for analysis
        words_lower = [word.lower() for word in words]
        word_freq = Counter(words_lower)
        unique_words = len(word_freq)
        
        # Type-Token Ratio
        type_token_ratio = unique_words / word_count
        
        # Guiraud's R
        guiraud_r = unique_words / math.sqrt(word_count)
        
        # Herdan's C
        herdans_c = math.log(unique_words) / math.log(word_count) if word_count > 1 else 0
        
        # Yule's K (simplified)
        freq_freq = Counter(word_freq.values())
        yules_k = 10000 * (sum(freq * (freq_count ** 2) for freq, freq_count in freq_freq.items()) - word_count) / (word_count ** 2)
        
        # Lexical density (content words vs function words - simplified)
        content_words = [word for word in words_lower if len(word) > 3]
        lexical_density = len(content_words) / word_count
        
        # Shannon entropy
        shannon_entropy = -sum((freq / word_count) * math.log2(freq / word_count) for freq in word_freq.values())
        
        return {
            "type_token_ratio": round(type_token_ratio, 3),
            "guiraud_r": round(guiraud_r, 3),
            "herdans_c": round(herdans_c, 3),
            "yules_k": round(yules_k, 3),
            "lexical_density": round(lexical_density, 3),
            "shannon_entropy": round(shannon_entropy, 3)
        }
        
    except Exception as e:
        logger.error(f"Diversity calculation failed: {e}")
        return {
            "type_token_ratio": 0.0,
            "guiraud_r": 0.0,
            "herdans_c": 0.0,
            "yules_k": 0.0,
            "lexical_density": 0.0,
            "shannon_entropy": 0.0
        }


def _calculate_structure_metrics(text: str, words: list, sentences: list, paragraphs: list) -> Dict[str, Any]:
    """Calculate text structure metrics."""
    try:
        word_count = len(words)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        
        # Average paragraph length
        avg_paragraph_length = word_count / paragraph_count if paragraph_count > 0 else 0
        
        # Count headings (simple heuristic)
        heading_patterns = [
            r'^[A-ZÄÖÜ][^.!?]*$',  # Lines starting with capital, no punctuation
            r'^\d+\.?\s+[A-ZÄÖÜ]',  # Numbered headings
            r'^[IVX]+\.?\s+[A-ZÄÖÜ]'  # Roman numeral headings
        ]
        
        lines = text.split('\n')
        heading_count = 0
        for line in lines:
            line = line.strip()
            if line and any(re.match(pattern, line) for pattern in heading_patterns):
                heading_count += 1
        
        heading_word_ratio = heading_count / word_count if word_count > 0 else 0
        
        # Sentence length variance
        if sentence_count > 1:
            sentence_lengths = [len(sentence.split()) for sentence in sentences]
            mean_length = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((length - mean_length) ** 2 for length in sentence_lengths) / len(sentence_lengths)
            sentence_length_variance = variance
        else:
            sentence_length_variance = 0.0
        
        # Assess if text has good structure
        has_good_structure = (
            paragraph_count >= 2 and
            avg_paragraph_length > 10 and
            avg_paragraph_length < 200 and
            sentence_length_variance < 100
        )
        
        return {
            "paragraph_count": paragraph_count,
            "avg_paragraph_length": round(avg_paragraph_length, 2),
            "heading_count": heading_count,
            "heading_word_ratio": round(heading_word_ratio, 4),
            "sentence_length_variance": round(sentence_length_variance, 2),
            "has_good_structure": has_good_structure
        }
        
    except Exception as e:
        logger.error(f"Structure calculation failed: {e}")
        return {
            "paragraph_count": 0,
            "avg_paragraph_length": 0.0,
            "heading_count": 0,
            "heading_word_ratio": 0.0,
            "sentence_length_variance": 0.0,
            "has_good_structure": False
        }


def _calculate_noise_metrics(text: str, words: list) -> Dict[str, float]:
    """Calculate noise and quality indicators."""
    try:
        if not text or not words:
            return {
                "non_letter_ratio": 0.0,
                "caps_ratio": 0.0,
                "multi_punctuation_count": 0,
                "special_char_ratio": 0.0,
                "repetition_ratio": 0.0,
                "error_indicator_count": 0
            }
        
        text_length = len(text)
        word_count = len(words)
        
        # Non-letter ratio
        letter_count = sum(1 for char in text if char.isalpha())
        non_letter_ratio = (text_length - letter_count) / text_length
        
        # Caps ratio
        caps_count = sum(1 for char in text if char.isupper())
        caps_ratio = caps_count / text_length
        
        # Multi-punctuation count
        multi_punctuation_count = len(re.findall(r'[!?]{2,}|\.{3,}', text))
        
        # Special character ratio
        special_chars = sum(1 for char in text if not char.isalnum() and not char.isspace())
        special_char_ratio = special_chars / text_length
        
        # Repetition ratio (repeated words)
        word_freq = Counter(word.lower() for word in words)
        repeated_words = sum(freq - 1 for freq in word_freq.values() if freq > 1)
        repetition_ratio = repeated_words / word_count if word_count > 0 else 0
        
        # Error indicators
        error_patterns = [
            r'\b(error|fehler|404|not found|page not found)\b',
            r'\b(javascript|js|css|html)\b',
            r'[{}[\]<>]'
        ]
        error_indicator_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in error_patterns)
        
        return {
            "non_letter_ratio": round(non_letter_ratio, 3),
            "caps_ratio": round(caps_ratio, 3),
            "multi_punctuation_count": multi_punctuation_count,
            "special_char_ratio": round(special_char_ratio, 3),
            "repetition_ratio": round(repetition_ratio, 3),
            "error_indicator_count": error_indicator_count
        }
        
    except Exception as e:
        logger.error(f"Noise calculation failed: {e}")
        return {
            "non_letter_ratio": 0.0,
            "caps_ratio": 0.0,
            "multi_punctuation_count": 0,
            "special_char_ratio": 0.0,
            "repetition_ratio": 0.0,
            "error_indicator_count": 0
        }


def _calculate_coherence_metrics(sentences: list) -> Dict[str, float]:
    """Calculate text coherence metrics."""
    try:
        if len(sentences) < 2:
            return {
                "avg_sentence_overlap": 0.0,
                "coherence_score": 0.0
            }
        
        # Calculate average sentence overlap (simplified)
        total_overlap = 0
        comparison_count = 0
        
        for i in range(len(sentences) - 1):
            words1 = set(sentences[i].lower().split())
            words2 = set(sentences[i + 1].lower().split())
            
            if words1 and words2:
                overlap = len(words1.intersection(words2)) / len(words1.union(words2))
                total_overlap += overlap
                comparison_count += 1
        
        avg_sentence_overlap = total_overlap / comparison_count if comparison_count > 0 else 0
        
        # Simple coherence score based on overlap and other factors
        coherence_score = min(1.0, avg_sentence_overlap * 2)  # Scale to 0-1
        
        return {
            "avg_sentence_overlap": round(avg_sentence_overlap, 3),
            "coherence_score": round(coherence_score, 3)
        }
        
    except Exception as e:
        logger.error(f"Coherence calculation failed: {e}")
        return {
            "avg_sentence_overlap": 0.0,
            "coherence_score": 0.0
        }


def _calculate_aggregate_score(readability: dict, diversity: dict, structure: dict, noise: dict, coherence: dict) -> Dict[str, float]:
    """Calculate aggregate quality scores."""
    try:
        # Normalize individual scores (0-1 scale)
        readability_score = min(1.0, max(0.0, (100 - abs(readability.get("flesch_reading_ease_de", 0) - 60)) / 100))
        diversity_score = min(1.0, diversity.get("type_token_ratio", 0) * 2)
        structure_score = 1.0 if structure.get("has_good_structure", False) else 0.5
        noise_score = max(0.0, 1.0 - noise.get("error_indicator_count", 0) * 0.1)
        coherence_score = coherence.get("coherence_score", 0)
        
        # Weighted aggregate score
        weights = {
            "readability": 0.25,
            "diversity": 0.20,
            "structure": 0.25,
            "noise": 0.15,
            "coherence": 0.15
        }
        
        final_quality_score = (
            readability_score * weights["readability"] +
            diversity_score * weights["diversity"] +
            structure_score * weights["structure"] +
            noise_score * weights["noise"] +
            coherence_score * weights["coherence"]
        )
        
        # Convert to Likert scale (1-5)
        likert_quality_score = 1 + (final_quality_score * 4)
        
        return {
            "final_quality_score": round(final_quality_score, 3),
            "likert_quality_score": round(likert_quality_score, 1)
        }
        
    except Exception as e:
        logger.error(f"Aggregate score calculation failed: {e}")
        return {
            "final_quality_score": 0.0,
            "likert_quality_score": 1.0
        }


def calculate_simplified_quality_metrics(text: str) -> Dict[str, Any]:
    """
    Calculate simplified, user-friendly quality metrics.
    
    Returns aggregated scores that are easy to understand:
    - character_length: Number of characters
    - readability_score: 0-1 (higher = more readable)
    - diversity_score: 0-1 (higher = more diverse vocabulary)
    - structure_score: 0-1 (higher = better structure)
    - noise_coherence_score: 0-1 (higher = less noise, more coherent)
    - error_indicator_score: 0-1 (higher = likely error/bot page)
    - overall_quality_score: 0-1 (higher = better overall quality)
    """
    try:
        if not text or not text.strip():
            return _empty_simplified_quality_metrics()
        
        text = text.strip()
        character_length = len(text)
        
        # Get detailed metrics for calculation
        detailed_metrics = calculate_quality_metrics(text)
        
        # Extract components
        readability = detailed_metrics.get("readability", {})
        diversity = detailed_metrics.get("diversity", {})
        structure = detailed_metrics.get("structure", {})
        noise = detailed_metrics.get("noise", {})
        coherence = detailed_metrics.get("coherence", {})
        
        # Calculate simplified scores (0-1 normalized)
        
        # 1. Readability Score (based on Flesch Reading Ease)
        flesch_score = readability.get("flesch_reading_ease_de", 0)
        readability_score = min(1.0, max(0.0, flesch_score / 100.0))
        
        # 2. Diversity Score (based on type-token ratio and entropy)
        ttr = diversity.get("type_token_ratio", 0)
        entropy = diversity.get("shannon_entropy", 0)
        diversity_score = min(1.0, (ttr + min(entropy / 5.0, 1.0)) / 2.0)
        
        # 3. Structure Score (based on paragraphs, headings, sentence variance)
        has_good_structure = structure.get("has_good_structure", False)
        heading_ratio = structure.get("heading_word_ratio", 0)
        sentence_variance = structure.get("sentence_length_variance", 0)
        
        structure_base = 0.8 if has_good_structure else 0.3
        structure_bonus = min(0.2, heading_ratio * 10)  # Bonus for headings
        structure_penalty = min(0.3, sentence_variance / 1000)  # Penalty for high variance
        structure_score = min(1.0, max(0.0, structure_base + structure_bonus - structure_penalty))
        
        # 4. Noise & Coherence Score (combined - lower noise + higher coherence = better)
        noise_ratio = noise.get("non_letter_ratio", 0)
        caps_ratio = noise.get("caps_ratio", 0)
        repetition_ratio = noise.get("repetition_ratio", 0)
        coherence_score_raw = coherence.get("coherence_score", 0)
        
        # Calculate noise penalty (0-1, where 1 = very noisy)
        noise_penalty = min(1.0, (noise_ratio + caps_ratio + repetition_ratio) / 3.0)
        # Combine with coherence (0-1, where 1 = very coherent)
        noise_coherence_score = min(1.0, max(0.0, (coherence_score_raw + (1.0 - noise_penalty)) / 2.0))
        
        # 5. Error Indicator Score (0-1, where 1 = likely error page)
        error_indicators = noise.get("error_indicator_count", 0)
        special_char_ratio = noise.get("special_char_ratio", 0)
        multi_punct_count = noise.get("multi_punctuation_count", 0)
        
        # Detect error page patterns
        error_score = 0.0
        
        # Short text with high error indicators
        if character_length < 100 and error_indicators > 0:
            error_score += 0.4
        
        # High special character ratio
        if special_char_ratio > 0.3:
            error_score += 0.3
            
        # Multiple punctuation (often in error messages)
        if multi_punct_count > 5:
            error_score += 0.2
            
        # Very low coherence (typical for error pages)
        if coherence_score_raw < 0.2:
            error_score += 0.3
            
        # Check for common error patterns in text
        error_patterns = [
            "404", "not found", "error", "forbidden", "access denied",
            "server error", "bad request", "unauthorized", "timeout",
            "cloudflare", "ray id", "blocked", "captcha"
        ]
        
        text_lower = text.lower()
        error_pattern_matches = sum(1 for pattern in error_patterns if pattern in text_lower)
        if error_pattern_matches > 0:
            error_score += min(0.4, error_pattern_matches * 0.1)
        
        error_indicator_score = min(1.0, error_score)
        
        # 6. Overall Quality Score (weighted combination)
        weights = {
            "readability": 0.25,
            "diversity": 0.20,
            "structure": 0.25,
            "noise_coherence": 0.20,
            "error_penalty": 0.10
        }
        
        overall_quality_score = (
            readability_score * weights["readability"] +
            diversity_score * weights["diversity"] +
            structure_score * weights["structure"] +
            noise_coherence_score * weights["noise_coherence"] -
            error_indicator_score * weights["error_penalty"]  # Subtract error penalty
        )
        
        overall_quality_score = min(1.0, max(0.0, overall_quality_score))
        
        return {
            "character_length": character_length,
            "readability_score": round(readability_score, 3),
            "diversity_score": round(diversity_score, 3),
            "structure_score": round(structure_score, 3),
            "noise_coherence_score": round(noise_coherence_score, 3),
            "error_indicator_score": round(error_indicator_score, 3),
            "overall_quality_score": round(overall_quality_score, 3)
        }
        
    except Exception as e:
        logger.error(f"Simplified quality metrics calculation failed: {e}")
        return _empty_simplified_quality_metrics()


def _empty_simplified_quality_metrics() -> Dict[str, Any]:
    """Return empty simplified quality metrics structure."""
    return {
        "character_length": 0,
        "readability_score": 0.0,
        "diversity_score": 0.0,
        "structure_score": 0.0,
        "noise_coherence_score": 0.0,
        "error_indicator_score": 0.0,
        "overall_quality_score": 0.0
    }
